import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Braces, Database, Download, MessageSquare, Plus, Upload } from 'lucide-react';
import { MessageText } from './LiveViews';

declare const workspaceAuth: {request(input: RequestInfo | URL, init?: RequestInit): Promise<Response>};
interface Pair {question:string;answer:string;source:string}
interface Dataset {name:string;pairs:Pair[]}
interface Summary {name:string;pairs:number;vocabulary_size:number;sha256:string}
interface Reply {
 answer:string;matched:boolean;reason:string;source:string|null;selected_question:string|null;n:number;dataset:Summary;elapsed_ms:number;
 trace:{tokens:string[];features:{term:string;count:number;idf:number;weight:number}[];unknown_words:string[];coverage:number;threshold:number;margin:number;gap:number;candidates:{index:number;question:string;score:number;contributions:{term:string;contribution:number}[]}[]};
}
interface Turn {question:string;reply?:Reply;error?:string}
const decimal=(value:number)=>value.toLocaleString('id-ID',{maximumFractionDigits:4});
async function api<T>(path:string,body?:unknown,signal?:AbortSignal):Promise<T> {
 const response=await workspaceAuth.request(path,{signal,...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
 const value=await response.json();
 if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'Data Q&A tidak valid. Periksa format dan batas ukuran.');
 return value as T;
}
function download(value:unknown,name:string) {
 const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function Trace({reply}:{reply:Reply}) {
 const trace=reply.trace;
 return <details className="ngchat-trace"><summary><Braces size={15} aria-hidden="true"/> Jejak pencocokan <span>{decimal(reply.elapsed_ms)} ms</span></summary>
  <ol className="ngchat-timeline">
   <li><strong>01 · Tokenisasi</strong><p>{trace.tokens.join(' · ')||'Tidak ada token'}</p><small>{trace.unknown_words.length?`Kata belum dikenal: ${trace.unknown_words.join(', ')}`:'Semua kata informatif ada di kosakata.'}</small></li>
   <li><strong>02 · Fitur 1–{reply.n}-gram</strong><p>{trace.features.length} fitur · cakupan kata {decimal(trace.coverage*100)}%</p><div className="ngchat-terms">{trace.features.slice(0,30).map(item=><code key={item.term}>{item.term}</code>)}</div>
    <details><summary>Bobot fitur lengkap</summary><div className="ngram-table"><table><caption>TF-IDF pertanyaan, dinormalisasi</caption><thead><tr><th>Fitur</th><th>Count</th><th>IDF</th><th>Bobot</th></tr></thead><tbody>{trace.features.map(item=><tr key={item.term}><td>{item.term}</td><td>{item.count}</td><td>{decimal(item.idf)}</td><td>{decimal(item.weight)}</td></tr>)}</tbody></table></div></details></li>
   <li><strong>03 · Peringkat jawaban</strong>{trace.candidates.map(item=><div className="ngchat-candidate" key={item.index}><p>{item.question}</p><b>{decimal(item.score)}</b><small>{item.contributions.slice(0,8).map(term=>`${term.term}: ${decimal(term.contribution)}`).join(' · ')||'Tidak ada fitur yang cocok'}</small></div>)}</li>
   <li><strong>04 · {reply.matched?'Jawaban dipilih':'Belum cukup cocok'}</strong><p>Ambang {trace.threshold} · selisih kandidat {decimal(trace.gap)} (min. {trace.margin})</p><small>{reply.matched?`Sumber: ${reply.source}`:{low_coverage:'Cakupan kata dikenal kurang dari 50%.',low_score:'Skor tertinggi belum mencapai ambang.',ambiguous:'Dua jawaban berbeda terlalu dekat.'}[reply.reason]||reply.reason}</small></li>
  </ol><p className="ngchat-fingerprint">Dataset SHA-256: <code>{reply.dataset.sha256}</code></p>
 </details>;
}
export function NgramChat() {
 const [data,setData]=useState<Dataset|null>(null),[summary,setSummary]=useState<Summary|null>(null);
 const [draft,setDraft]=useState(''),[turns,setTurns]=useState<Turn[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[order,setOrder]=useState(2);
 const [tab,setTab]=useState<'chat'|'data'>('chat');
 const pending=useRef(false),request=useRef<AbortController|null>(null),composer=useRef<HTMLTextAreaElement>(null),scroll=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  const controller=new AbortController();let loading=false;
  const load=()=>{
   if(loading||data||document.getElementById('ngramPane')?.hidden!==false)return;
   loading=true;
   api<{dataset:Dataset;summary:Summary}>('/api/ngram/chat/data',undefined,controller.signal).then(value=>{setData(value.dataset);setSummary(value.summary);setError('');}).catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:String(reason));}).finally(()=>{loading=false;});
  };
  load();document.addEventListener('workspace-view',load);
  return()=>{controller.abort();document.removeEventListener('workspace-view',load);};
 },[data]);
 useEffect(()=>()=>request.current?.abort(),[]);
 useEffect(()=>{if(scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight;},[turns,busy]);
 useEffect(()=>{const node=composer.current;if(node){node.style.height='auto';node.style.height=`${Math.min(160,Math.max(56,node.scrollHeight))}px`;}},[draft]);
 async function send() {
  const question=draft.trim();if(!question||pending.current||!data||turns.length>=50)return;
  pending.current=true;setBusy(true);setError('');setDraft('');setTurns(rows=>[...rows,{question}]);
  const controller=request.current=new AbortController();
  try {
   const reply=await api<Reply>('/api/ngram/chat',{question,n:order,dataset:data},controller.signal);
   setTurns(rows=>rows.map((row,index)=>index===rows.length-1?{...row,reply}:row));
  }catch(reason){if(!controller.signal.aborted)setTurns(rows=>rows.map((row,index)=>index===rows.length-1?{...row,error:reason instanceof Error?reason.message:String(reason)}:row));setDraft(question);}
  finally{pending.current=false;setBusy(false);composer.current?.focus({preventScroll:true});}
 }
 async function importData(file:File) {
  if(pending.current)return;
  pending.current=true;setBusy(true);setError('');
  try {
   if(file.size>1024*1024)throw Error('File dataset maksimal 1 MiB.');
   const value=await api<{dataset:Dataset;summary:Summary}>('/api/ngram/chat/data',JSON.parse(await file.text()));
   setData(value.dataset);setSummary(value.summary);setTurns([]);setDraft('');
  }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
  finally{pending.current=false;setBusy(false);}
 }
 return <section className="ngchat" aria-labelledby="ngchatTitle">
  <header className="ngchat-header"><div><p className="workspace-kicker">BAHASA, DARI DATA</p><h1 id="ngchatTitle">Chatbot N-gram</h1><p>Ajukan pertanyaan. Lihat bagaimana kata-katanya menemukan jawaban.</p></div><div className="ngchat-badge"><span/> N-gram · tanpa LLM</div></header>
  <div className="ngchat-shell">
   <div className="ngchat-toolbar"><div className="ngchat-tabs"><button type="button" aria-pressed={tab==='chat'} onClick={()=>setTab('chat')}><MessageSquare size={16} aria-hidden="true"/>Percakapan</button><button type="button" aria-pressed={tab==='data'} onClick={()=>setTab('data')}><Database size={16} aria-hidden="true"/>Data Q&A {summary&&<span>{summary.pairs}</span>}</button></div><div className="ngchat-actions"><button type="button" title="Unduh percakapan dan log" aria-label="Unduh percakapan dan log" disabled={!turns.length||busy} onClick={()=>download({dataset:summary,turns},'ngram-chat-log.json')}><Download size={17} aria-hidden="true"/></button><button type="button" aria-label="Percakapan baru" title="Percakapan baru" disabled={busy||!turns.length} onClick={()=>{setTurns([]);setError('');composer.current?.focus();}}><Plus size={19} aria-hidden="true"/></button></div></div>
   {error&&<p className="error" role="alert">{error} {!data&&<button type="button" className="button button--tertiary" onClick={()=>document.dispatchEvent(new Event('workspace-view'))}>Coba muat data lagi</button>}</p>}
   {tab==='chat'?<>
    <div id="ngchatMessages" className="ngchat-messages" ref={scroll} role="log" aria-label="Percakapan N-gram" aria-live="polite" aria-relevant="additions text">
     {!turns.length&&<div className="ngchat-empty"><div className="ngchat-mark" aria-hidden="true"><i/><i/><i/><i/><Braces size={36}/></div><p className="workspace-kicker">SEBUAH PERTANYAAN. SEBUAH JEJAK.</p><h2>Mulai dari yang<br/>ingin kamu pahami.</h2><p>Jawaban datang dari Q&A yang tersedia.<br/>Setiap kecocokan dapat ditelusuri.</p><div className="ngchat-suggestions">{data?.pairs.slice(0,3).map(pair=><button key={pair.question} type="button" onClick={()=>{setDraft(pair.question);composer.current?.focus();}}>{pair.question}<ArrowUp size={14} aria-hidden="true"/></button>)}</div></div>}
     {turns.map((turn,index)=><div className="ngchat-turn" key={index}>
      <div className="ngchat-user"><p>{turn.question}</p></div>
      {turn.reply&&<div className="ngchat-answer"><div className="ngchat-author"><Braces size={18} aria-hidden="true"/><strong>N-gram</strong><span>{turn.reply.matched?'Dari data Q&A':'Perlu konteks lebih spesifik'}</span></div><Trace reply={turn.reply}/><p className="ngchat-answer-text"><MessageText text={turn.reply.answer} reveal scrollId="ngchatMessages"/></p>{turn.reply.source&&<p className="ngchat-source"><Database size={13} aria-hidden="true"/>{turn.reply.source}</p>}</div>}
      {turn.error&&<p role="alert" className="error">{turn.error} · Pertanyaan dikembalikan ke kotak pesan untuk dicoba lagi.</p>}
     </div>)}
     {busy&&<div className="ngchat-pending" role="status"><span className="typing-dots" aria-hidden="true"><i/><i/><i/></span> Mencocokkan N-gram…</div>}
    </div>
    <div className="ngchat-compose-area"><form className="ngchat-composer" onSubmit={event=>{event.preventDefault();void send();}}><label htmlFor="ngchatQuestion" className="sr-only">Pertanyaan untuk chatbot N-gram</label><textarea ref={composer} id="ngchatQuestion" value={draft} maxLength={2000} rows={2} placeholder={data?'Tulis pertanyaanmu…':'Memuat data Q&A…'} aria-describedby="ngchatHelp" disabled={busy||!data||turns.length>=50} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();void send();}}}/><div className="ngchat-composer-bottom"><label htmlFor="ngchatOrder">Fitur<select id="ngchatOrder" value={order} disabled={busy} onChange={event=>setOrder(Number(event.target.value))}><option value={1}>Unigram</option><option value={2}>Unigram + bigram</option><option value={3}>Hingga trigram</option></select></label><button type="submit" aria-label="Kirim pertanyaan" disabled={!draft.trim()||busy||!data||turns.length>=50}><ArrowUp size={20} aria-hidden="true"/></button></div></form><p id="ngchatHelp">{turns.length>=50?'Batas 50 pertanyaan. Unduh log, lalu mulai percakapan baru.':'Enter untuk kirim · Shift + Enter untuk baris baru. Skor kemiripan bukan tingkat akurasi.'}</p></div>
   </>:<div className="ngchat-data"><h2>Data yang memberi jawaban.</h2><p>Pasangan Q&A adalah sumber jawaban. Impor data topikmu sendiri; isinya dipakai dalam sesi halaman ini.</p><div className="ngchat-data-actions"><label className="button button--secondary"><Upload size={16} aria-hidden="true"/>Impor JSON<input type="file" accept=".json,application/json" disabled={busy} onChange={event=>{const file=event.target.files?.[0];if(file)void importData(file);event.target.value='';}}/></label><button className="button button--outline" type="button" disabled={!data} onClick={()=>download(data,'ngram-qa.json')}><Download size={16} aria-hidden="true"/>Unduh dataset</button></div><p className="hint">Tidak disimpan otomatis. Unduh dataset sebelum memuat ulang. Impor berhasil akan memulai percakapan baru.</p>{summary&&<dl className="ngram-metrics"><div><dt>Dataset</dt><dd>{summary.name}</dd></div><div><dt>Pasangan Q&A</dt><dd>{summary.pairs}</dd></div><div><dt>Kosakata informatif</dt><dd>{summary.vocabulary_size}</dd></div></dl>}<div className="ngchat-qa-list">{data?.pairs.map((pair,index)=><details key={index}><summary><span>{String(index+1).padStart(2,'0')}</span>{pair.question}</summary><p>{pair.answer}</p><small>{pair.source}</small></details>)}</div></div>}
  </div>
 </section>;
}
