import { useEffect, useState } from 'react';
import { EventLedger } from './EventLedger';
import { NgramChat } from './NgramChat';

declare const workspaceAuth: {request(input: RequestInfo | URL, init?: RequestInit): Promise<Response>};
interface Catalog { methods: string[]; models: {id:string;name:string;n:number;method:string;corpus:string}[]; runs:{run_id:string;summary:Record<string,unknown>}[]; boundary:string; validation?:{source:string;training_sentences:number;discount:number;padding:string;epsilon:string;rows:{n:number;queries:number;max_absolute_difference:number;mean_absolute_difference:number;default_epsilon_max_difference:number}[]} }
interface ResearchRuns {schema_version:1;runs:{run_id:string;status:string;source_name:string;metrics:{n:number;method:string;dev_cross_entropy:number|null;test_cross_entropy:number|null;test_perplexity:number|null}[];comparison:unknown[]}[];errors:unknown[]}
interface EventScore {word:string;context:string[];probability:number;nll:number|null}
interface Exploration {
 model:{name:string;method:string;n:number;vocabulary_size:number;parameters:Record<string,unknown>;source:string};
 score:{tokens:string[];mapped_tokens:string[];events:EventScore[];predicted_tokens:number;nll:number|null;cross_entropy:number|null;perplexity:number|null;probabilistic:boolean;zero_probability:boolean};
 top_k:{word:string;probability:number}[];
 generated:{word:string;context:string[];probability:number}[];
 stop_reason:string;context_window_size:number;formula_details:string[];boundary:string;
}
const number = (value:number|null) => value === null ? 'Tidak tersedia' : value.toLocaleString('id-ID',{maximumSignificantDigits:7});
const detail = (value:unknown) => typeof value === 'string' ? value : JSON.stringify(value);
async function request<T>(url:string,init?:RequestInit):Promise<T> {
 const response=await workspaceAuth.request(url,init);
 const data=await response.json();
 if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Permintaan Lab gagal.');
 return data as T;
}
function NgramResearch() {
 const [catalog,setCatalog]=useState<Catalog|null>(null),[result,setResult]=useState<Exploration|null>(null);
 const [runs,setRuns]=useState<ResearchRuns|null>(null);
 const [modelId,setModelId]=useState('demo'),[method,setMethod]=useState('add_k'),[order,setOrder]=useState(2);
 const [text,setText]=useState('the cat sits'),[prefix,setPrefix]=useState(''),[seed,setSeed]=useState(42),[limit,setLimit]=useState(12);
 const [reload,setReload]=useState(0),[generationStep,setGenerationStep]=useState(0),[orderFilter,setOrderFilter]=useState(''),[methodFilter,setMethodFilter]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[runId,setRunId]=useState('');
 useEffect(()=>{
  let ignore=false;
  const load=()=>{
   if(document.getElementById('ngramPane')?.hidden!==false)return;
   setError('');
   request<Catalog>('/api/ngram/catalog').then(data=>{if(!ignore)setCatalog(data);}).catch(reason=>{if(!ignore)setError(reason instanceof Error?reason.message:String(reason));});
   request<ResearchRuns>('/api/ngram/runs').then(data=>{if(!ignore)setRuns(data);}).catch(reason=>{if(!ignore)setError(reason instanceof Error?reason.message:String(reason));});
  };
  load();
  document.addEventListener('workspace-view',load);
  return()=>{ignore=true;document.removeEventListener('workspace-view',load);};
 },[reload]);
 const reset=()=>{setResult(null);setError('');};
 async function explore(event:React.FormEvent) {
  event.preventDefault(); if(busy)return;
  setBusy(true);setError('');setResult(null);setGenerationStep(0);
  try {
   const data=await request<Exploration>('/api/ngram/explore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_id:modelId,method,n:order,text,prefix,max_length:limit,seed})});
   setResult(data);
  }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
  finally{setBusy(false);}
 }
 const run=runs?.runs.find(item=>item.run_id===runId);
 const selectedStep=result?.generated[generationStep];
 const filteredMetrics=run?.metrics.filter(row=>(!orderFilter||row.n===Number(orderFilter))&&(!methodFilter||row.method===methodFilter))||[];
 const entropyValues=filteredMetrics.filter(row=>row.method!=='stupid_backoff'&&row.test_cross_entropy!==null).map(row=>row.test_cross_entropy as number);
 const entropyMin=Math.min(...entropyValues),entropyMax=Math.max(...entropyValues);
 const product=result?.score.events.reduce((value,event)=>value*event.probability,1);
 return <section className="ngram-lab" aria-label="Lab N-gram">
  <div className="ngram-heading"><span className="eyebrow">LAB BAHASA</span><h1>N-gram, satu kata berikutnya</h1><p>Uji konteks, lihat peluang kata, lalu telusuri generasi dari model yang sama.</p></div>
  <p className="hint">{catalog?.boundary||'Eksplorasi pendidikan lokal. Model demo memakai corpus kecil; hasil riset hanya tampil jika artefaknya tersedia.'}</p>
  {error&&<p className="error" role="alert">{error}</p>}
  {!catalog&&<button className="button button--tertiary" type="button" onClick={()=>setReload(value=>value+1)}>Muat model Lab</button>}
  <div className="ngram-columns">
   <section aria-labelledby="ngramPlaygroundTitle"><h2 id="ngramPlaygroundTitle">Playground</h2>
    <form onSubmit={explore} aria-busy={busy}>
     <fieldset disabled={busy||!catalog}><legend className="sr-only">Pengaturan model</legend>
      <label htmlFor="ngramModel">Sumber model</label><select id="ngramModel" value={modelId} onChange={event=>{setModelId(event.target.value);const selected=catalog?.models.find(model=>model.id===event.target.value);if(selected){setMethod(selected.method);setOrder(selected.n);}reset();}}><option value="demo">Demo pendidikan, corpus kecil</option>{catalog?.models.filter(model=>model.id!=='demo').map(model=><option key={model.id} value={model.id}>{model.name} · {model.method} · {model.n}-gram</option>)}</select>
      <div className="ngram-inline"><div><label htmlFor="ngramMethod">Smoothing</label><select id="ngramMethod" disabled={modelId!=='demo'} value={method} onChange={event=>{setMethod(event.target.value);reset();}}>{(catalog?.methods||['add_k']).map(value=><option key={value} value={value}>{value.replace(/_/g,' ')}</option>)}</select></div><div><label htmlFor="ngramOrder">Orde n</label><select id="ngramOrder" disabled={modelId!=='demo'} value={order} onChange={event=>{setOrder(Number(event.target.value));reset();}}>{[1,2,3,4].map(value=><option key={value}>{value}</option>)}</select></div></div>
      <label htmlFor="ngramText">Konteks atau kalimat</label><textarea id="ngramText" rows={3} required maxLength={6000} value={text} onChange={event=>{setText(event.target.value);reset();}} aria-describedby="ngramTextHelp"/><p id="ngramTextHelp" className="hint">Huruf dinormalisasi menjadi lowercase. Kata di luar vocabulary dipetakan ke &lt;UNK&gt;; akhir kalimat ikut dinilai.</p>
      <label>Awalan kata berikutnya, opsional<input maxLength={256} value={prefix} onChange={event=>{setPrefix(event.target.value);reset();}} placeholder="Kosong untuk semua kata"/></label>
      <div className="ngram-inline"><div><label htmlFor="ngramSeed">Seed generasi</label><input id="ngramSeed" type="number" min={0} max={4294967295} required value={seed} onChange={event=>{setSeed(Number(event.target.value));reset();}}/></div><div><label htmlFor="ngramLimit">Batas langkah</label><input id="ngramLimit" type="number" min={1} max={40} required value={limit} onChange={event=>{setLimit(Number(event.target.value));reset();}}/></div></div>
      <button className="button button--primary" type="submit">{busy?'Menghitung…':'Hitung & telusuri'}</button>
     </fieldset>
    </form>
    <p role="status" className="hint">{busy?'Model sedang menghitung peluang dan generasi.':!catalog?'Buka Lab untuk memuat model yang tersedia.':result?`${result.model.name} · ${result.model.vocabulary_size} kata · ${result.model.n}-gram`: 'Siap. Masukkan kalimat untuk memulai.'}</p>
    {result&&<><h3>Generasi per langkah</h3>{selectedStep&&<><label>Langkah generasi<input type="range" min={0} max={result.generated.length-1} value={generationStep} onChange={event=>setGenerationStep(Number(event.target.value))}/></label><div className="ngram-step-controls"><button className="button button--tertiary button--sm" type="button" disabled={generationStep===0} onClick={()=>setGenerationStep(value=>value-1)}>Langkah sebelumnya</button><output aria-live="polite">{generationStep+1} / {result.generated.length}</output><button className="button button--tertiary button--sm" type="button" disabled={generationStep===result.generated.length-1} onClick={()=>setGenerationStep(value=>value+1)}>Langkah berikutnya</button></div><p>Jendela konteks: <mark>{selectedStep.context.slice(-result.context_window_size).join(' ')||'Tanpa konteks'}</mark> → <code>{selectedStep.word}</code> ({number(selectedStep.probability)})</p></>}<ol className="ngram-steps">{result.generated.map((step,index)=><li key={index} aria-current={index===generationStep?'step':undefined}><span><code>{step.word}</code><small>{step.context.join(' ')||'Tanpa konteks'}</small></span><span>{number(step.probability)}</span></li>)}</ol><p className="hint">Berhenti: {result.stop_reason}. Jendela konteks: {result.context_window_size} token.</p></>}
   </section>
   <section aria-labelledby="ngramProbabilityTitle"><h2 id="ngramProbabilityTitle">Probability explorer</h2>
    {!result?<p className="hint">Setelah dihitung, peluang kata berikutnya dan kontribusi setiap token muncul di sini.</p>:<>
     <h3>{result.score.probabilistic?'Peluang kata berikutnya':'Skor kata berikutnya'}</h3><p className="hint">Pilih kata untuk menambahkannya ke input, lalu hitung kembali.</p><ol className="ngram-probabilities">{result.top_k.map(row=><li key={row.word}><button className="ngram-word" type="button" disabled={busy||row.word==='<UNK>'||row.word==='</s>'} onClick={()=>{setText(value=>`${value.trim()} ${row.word}`.trim());reset();}} aria-label={`Tambahkan ${row.word} ke input`}><code>{row.word}</code></button><meter min={0} max={Math.max(1,...result.top_k.map(item=>item.probability))} value={row.probability} aria-label={`${result.score.probabilistic?'Peluang':'Skor'} ${row.word}`}/><span>{number(row.probability)}</span></li>)}</ol>
     <dl className="ngram-metrics"><div><dt>{result.score.probabilistic?'Log likelihood (LL)':'Log skor kalimat'}</dt><dd>{number(result.score.nll===null?null:-result.score.nll)}</dd></div><div><dt>{result.score.probabilistic?'NLL, log natural':'Negative log score'}</dt><dd>{number(result.score.nll)}</dd></div><div><dt>Cross entropy</dt><dd>{number(result.score.cross_entropy)}</dd></div><div><dt>Perplexity</dt><dd>{number(result.score.perplexity)}</dd></div><div><dt>Token dinilai, termasuk EOS</dt><dd>{result.score.predicted_tokens}</dd></div></dl>
     {!result.score.probabilistic&&<p className="hint">Stupid Backoff menghasilkan skor tanpa normalisasi. Perplexity tidak berlaku.</p>}
     {result.score.zero_probability&&<p role="status">Ada peluang nol: NLL tak terhingga dan perplexity tidak tersedia.</p>}
     <details><summary>Trace token & rumus</summary><div className="ngram-table"><table><caption>Kontribusi token, termasuk akhir kalimat</caption><thead><tr><th>Konteks</th><th>Kata</th><th>p / skor</th><th>{result.score.probabilistic?'−ln(p)':'−ln(skor)'}</th><th>{result.score.probabilistic?'ln(p), logP':'ln(skor)'}</th></tr></thead><tbody>{result.score.events.map((row,index)=><tr key={index}><td><code>{row.context.join(' ')||'∅'}</code></td><td><code>{row.word}</code></td><td>{number(row.probability)}</td><td>{number(row.nll)}</td><td>{number(row.nll===null?null:-row.nll)}</td></tr>)}</tbody></table></div><p>Input: <code>{result.score.tokens.join(' ')}</code><br/>Mapping: <code>{result.score.mapped_tokens.join(' ')}</code></p>{result.formula_details.map((formula,index)=><p key={index}><code>{detail(formula)}</code></p>)}<p>NLL = −Σ ln(p); CE = NLL / token; PP = exp(CE).</p><p>Produk peluang langsung: {product===0?'0 (nol atau underflow)':product?.toExponential(6)}. Penjumlahan log menghindari underflow pada perkalian rangkaian panjang.</p><details><summary>Parameter & jejak seleksi dev</summary><p className="hint">{modelId==='demo'?'Parameter demo ditetapkan untuk pendidikan; bobot tetap bukan hasil tuning dev.':'Parameter dan jejak tuning berasal dari checkpoint terpilih. Seleksi memakai dev, sebelum evaluasi test.'}</p><pre>{JSON.stringify(result.model.parameters,null,2)}</pre></details></details>
    </>}
   </section>
  </div>
  <section className="ngram-experiments" aria-labelledby="ngramExperimentTitle"><h2 id="ngramExperimentTitle">Experiment dashboard</h2>
   <label htmlFor="ngramRun">Run tersimpan</label><select id="ngramRun" value={runId} onChange={event=>setRunId(event.target.value)}><option value="">Pilih run riset</option>{runs?.runs.map(item=><option key={item.run_id} value={item.run_id}>{item.run_id}</option>)}</select>
   {!runs?.runs.length?<p className="hint">Belum ada run riset terverifikasi. Jalankan pipeline akademik untuk menghasilkan split, model, evaluasi dan laporan; demo pendidikan tidak menjadi hasil eksperimen.</p>:run?<><h3>{run.run_id}</h3><p className="hint">{run.source_name} · {run.status}</p><a className="button button--tertiary button--sm" href={`/api/ngram/runs/${encodeURIComponent(run.run_id)}/csv`} download>Unduh CSV metrik run</a><div className="ngram-inline"><label>Filter orde<select value={orderFilter} onChange={event=>setOrderFilter(event.target.value)}><option value="">Semua orde</option>{Array.from(new Set(run.metrics.map(row=>row.n))).map(n=><option key={n}>{n}</option>)}</select></label><label>Filter metode<select value={methodFilter} onChange={event=>setMethodFilter(event.target.value)}><option value="">Semua metode</option>{Array.from(new Set(run.metrics.map(row=>row.method))).map(value=><option key={value} value={value}>{value.replace(/_/g,' ')}</option>)}</select></label></div><div className="ngram-table"><table><caption>Dev memilih model; test melaporkan hasil model beku. CE memakai log natural.</caption><thead><tr><th>Orde</th><th>Metode</th><th>Dev CE</th><th>Test CE</th><th>Test PP</th></tr></thead><tbody>{filteredMetrics.map(row=><tr key={`${row.n}-${row.method}`}><td>{row.n}</td><td>{row.method.replace(/_/g,' ')}</td><td>{number(row.dev_cross_entropy)}</td><td>{number(row.test_cross_entropy)}</td><td>{number(row.test_perplexity)}</td></tr>)}</tbody></table></div><details><summary>Heatmap cross entropy test</summary><p className="hint">Warna lebih kuat berarti CE lebih rendah dalam run ini. Angka tetap menjadi acuan; skor Stupid Backoff tidak dibandingkan sebagai perplexity.</p><div className="ngram-table"><table><caption>Metode × orde, mengikuti filter</caption><thead><tr><th>Metode</th>{Array.from(new Set(filteredMetrics.map(row=>row.n))).map(n=><th key={n}>{n}-gram</th>)}</tr></thead><tbody>{Array.from(new Set(filteredMetrics.map(row=>row.method))).map(value=><tr key={value}><th>{value.replace(/_/g,' ')}</th>{Array.from(new Set(filteredMetrics.map(row=>row.n))).map(n=>{const row=filteredMetrics.find(item=>item.n===n&&item.method===value),ce=row?.test_cross_entropy;return <td key={n} style={{backgroundColor:ce!==null&&ce!==undefined&&value!=='stupid_backoff'?`color-mix(in oklab, var(--accent) ${12+28*(entropyMax===entropyMin?1:(entropyMax-ce)/(entropyMax-entropyMin))}%, var(--surface))`:undefined}}>{value==='stupid_backoff'?'Skor saja':ce===undefined?'—':number(ce)}</td>;})}</tr>)}</tbody></table></div></details>{run.comparison.length>0&&<details><summary>Perbandingan berpasangan & ketidakpastian</summary>{run.comparison.map((row,index)=><pre key={index}>{JSON.stringify(row,null,2)}</pre>)}</details>}</>:<p className="hint">Pilih run untuk meninjau ringkasan artefak nyata.</p>}
   {!!runs?.errors.length&&<p className="error" role="status">Sebagian run tidak dapat diverifikasi: {runs.errors.map(detail).join('; ')}</p>}
  </section>
  <details><summary>Validasi historis terhadap NLTK</summary>{catalog?.validation?<><p className="hint">{catalog.validation.source}. Pembandingan ini hanya ordinary Kneser–Ney; bukan bukti ekuivalensi Modified Kneser–Ney atau run baru.</p><p>{catalog.validation.training_sentences} kalimat train · discount {catalog.validation.discount}</p><p className="hint">Padding: {catalog.validation.padding}. Epsilon: {catalog.validation.epsilon}.</p><div className="ngram-table"><table><caption>Perbedaan absolut peluang terhadap referensi ordinary KN</caption><thead><tr><th>n</th><th>Query</th><th>Maksimum</th><th>Rata-rata</th><th>Maks ε default</th></tr></thead><tbody>{catalog.validation.rows.map(row=><tr key={row.n}><td>{row.n}</td><td>{row.queries}</td><td>{number(row.max_absolute_difference)}</td><td>{number(row.mean_absolute_difference)}</td><td>{number(row.default_epsilon_max_difference)}</td></tr>)}</tbody></table></div></>:<p className="hint">Artefak validasi historis belum tersedia.</p>}</details>
  <EventLedger />
 </section>;
}

export function NgramLab() {
 return <><NgramChat/><details className="ngram-research"><summary>Analisis & eksperimen N-gram</summary><NgramResearch/></details></>;
}
