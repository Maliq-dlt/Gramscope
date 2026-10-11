import { useRef, useState } from 'react';

declare const workspaceAuth:{request(input:RequestInfo|URL,init?:RequestInit):Promise<Response>};
interface LedgerEvent {id:string;category:'observation'|'attendance';symbol:string;status:string;job_id:string|null;track_id:number|null;occurred_at:string|null;verified_at:string;verifier_id?:string;reason:string|null;payload:{subject_id?:string;evidence?:string|null;seconds?:number;schema_version?:number;source_revision?:string;frame_index?:number;helmet_status?:string;class_name?:string}}
interface Facts {crossing_event_count:number;observed_track_count:number;attendance_record_count:number;stale_count:number;retracted_count:number;limitations:string[]}
interface Recording {id:string;filename:string;status:string}
interface Summary {source_revision?:string;annotation_revision?:number;correction_revision?:number;model_id?:string;crossings:{kind:string;track_id:number;direction:string;seconds:number}[];tracks:{id:number;kind:string;evidence?:string}[]}
async function api<T>(url:string,init?:RequestInit):Promise<T>{
 const response=await workspaceAuth.request(url,init),data=await response.json();
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Ledger gagal memproses permintaan.');
 return data as T;
}
const post=(body:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
export function EventLedger(){
 const [role,setRole]=useState(''),[rows,setRows]=useState<LedgerEvent[]>([]),[facts,setFacts]=useState<Facts|null>(null),[jobs,setJobs]=useState<Recording[]>([]);
 const [job,setJob]=useState(''),[summary,setSummary]=useState<Summary|null>(null),[selected,setSelected]=useState<number[]>([]),[recordedAt,setRecordedAt]=useState('');
 const [helmets,setHelmets]=useState<Record<number,{status:string;association:string;head_bbox?:number[]}>>({});
 const [novelty,setNovelty]=useState<{runs:{run_id:string;summary:Record<string,unknown>}[];errors:unknown[]}|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState('');
 const [subject,setSubject]=useState(''),[sourceKind,setSourceKind]=useState('manual'),[sourceId,setSourceId]=useState(''),[occurredAt,setOccurredAt]=useState(''),[action,setAction]=useState('arrived'),[track,setTrack]=useState('');
 const selectionGeneration=useRef(0);
 const reviewer=role==='admin'||role==='reviewer';
 async function refresh(){
  const [events,current,recordings,session]=await Promise.all([api<{events:LedgerEvent[]}>('/api/ledger/events'),api<Facts>('/api/ledger/facts'),api<Recording[]>('/api/jobs'),api<{user:{role:string}}>('/api/auth/session')]);
  setRows(events.events);setFacts(current);setJobs(recordings.filter(item=>item.status==='done'));setRole(session.user.role);
  try{setNovelty(await api('/api/ledger/novelty/runs'));}catch{setNovelty(null);}
 }
 async function run(operation:()=>Promise<void>){
  if(busy)return;setBusy(true);setError('');setStatus('');
  try{await operation();}catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
  finally{setBusy(false);}
 }
 async function chooseRecording(id:string){
  const generation=++selectionGeneration.current;
  setJob(id);setSummary(null);setSelected([]);setHelmets({});setTrack('');setError('');
  if(!id)return;
  try{const value=await api<Summary>(`/api/ledger/jobs/${encodeURIComponent(id)}/preview`);if(generation===selectionGeneration.current)setSummary(value);}
  catch(reason){if(generation===selectionGeneration.current)setError(reason instanceof Error?reason.message:String(reason));}
 }
 const people=summary?.tracks.filter(item=>item.kind==='person')||[];
 const crossings=summary?.crossings.map((value,index)=>({value,index})).filter(({value})=>['person','car','bus','truck','motorcycle','bicycle'].includes(value.kind))||[];
 return <details className="event-ledger" onToggle={event=>{if(event.currentTarget.open&&!facts)void run(refresh);}}>
  <summary>Kejadian terverifikasi</summary>
  <p className="hint">Crossing adalah lintasan track, bukan identitas atau jumlah orang unik. Badge/QR dicatat setelah verifikasi manual administrator; halaman ini bukan scanner.</p>
  <button className="button button--tertiary button--sm" type="button" disabled={busy} onClick={()=>void run(refresh)}>Perbarui ledger</button>
  {error&&<p className="error" role="alert">{error}</p>}<p className="hint" role="status">{busy?'Memproses bukti ledgerâ€¦':status}</p>
  {facts&&<dl className="ngram-metrics"><div><dt>Crossing terverifikasi</dt><dd>{facts.crossing_event_count}</dd></div><div><dt>Track teramati, identitas unknown</dt><dd>{facts.observed_track_count}</dd></div><div><dt>Catatan absensi terverifikasi</dt><dd>{facts.attendance_record_count}</dd></div><div><dt>Bukti stale / ditarik</dt><dd>{facts.stale_count} / {facts.retracted_count}</dd></div></dl>}
  {reviewer&&<section><h3>Tinjau crossing dari rekaman</h3>
   <label>Rekaman yang selesai dianalisis<select value={job} disabled={busy} onChange={event=>void chooseRecording(event.target.value)}><option value="">Pilih rekaman</option>{jobs.map(item=><option key={item.id} value={item.id}>{item.filename}</option>)}</select></label>
   <form onSubmit={event=>{event.preventDefault();void run(async()=>{await api(`/api/ledger/jobs/${encodeURIComponent(job)}/import`,post({schema_version:2,recorded_at:recordedAt||null,expected_fingerprint:summary?.source_revision,crossing_indices:selected,helmet_reviews:Object.fromEntries(selected.filter(index=>helmets[index]).map(index=>[index,helmets[index]]))}));await refresh();setSelected([]);setStatus('Crossing terpilih tercatat. Unknown helm tidak dianggap pelanggaran.');});}}><fieldset disabled={busy}>
    <label>Waktu asli rekaman (opsional, dengan zona waktu)<input type="text" maxLength={80} placeholder="2026-10-10T08:00:00+07:00" value={recordedAt} onChange={event=>setRecordedAt(event.target.value)}/></label>
    {summary&&<div className="ngram-table"><table><caption>Pilih lintasan yang sudah ditinjau. Tanggal kosong memakai offset video.</caption><thead><tr><th>Pilih</th><th>Track / kelas</th><th>Arah</th><th>Detik</th><th>Bukti & helm</th></tr></thead><tbody>{crossings.map(({value,index})=>{return <tr key={index}><td><input className="ledger-check" type="checkbox" checked={selected.includes(index)} aria-label={`Verifikasi crossing ${index}, track ${value.track_id}, detik ${value.seconds}`} onChange={event=>setSelected(values=>event.target.checked?[...values,index]:values.filter(item=>item!==index))}/></td><td>{value.track_id} · {value.kind}</td><td>{value.direction==='down'?'Masuk zona':'Keluar zona'}</td><td>{value.seconds}</td><td>{<button type="button" className="button button--tertiary button--sm" onClick={()=>void run(async()=>{const response=await workspaceAuth.request(`/api/jobs/${encodeURIComponent(job)}/frame/${Math.floor(value.seconds*(await api<{fps:number}>(`/api/jobs/${encodeURIComponent(job)}/summary`)).fps)}`);if(!response.ok)throw Error('Frame tidak tersedia.');const url=URL.createObjectURL(await response.blob());window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),30000);})}>Frame crossing</button>}</td></tr>;})}</tbody></table></div>}
    {summary&&!crossings.length&&<p className="hint">Rekaman ini belum memiliki lintasan yang dapat disahkan.</p>}
    {selected.filter(index=>summary?.crossings[index].kind==='person').map(index=><details key={index}><summary>Review helm · track {summary?.crossings[index].track_id} pada {summary?.crossings[index].seconds}s</summary><label>Status helm<select value={helmets[index]?.status||'unknown'} onChange={event=>setHelmets(values=>({...values,[index]:{status:event.target.value,association:event.target.value==='unknown'?'unreviewed':'head_visible',head_bbox:values[index]?.head_bbox}}))}><option value="unknown">Belum dapat dipastikan</option><option value="worn">Dipakai di kepala</option><option value="not_worn">Kepala jelas tanpa helm</option></select></label><label>Koordinat kepala x1,y1,x2,y2 (0–1)<input placeholder="0.1,0.1,0.3,0.3" onChange={event=>{const box=event.target.value.split(',').map(Number);setHelmets(values=>({...values,[index]:{status:values[index]?.status||'unknown',association:values[index]?.association||'unreviewed',head_bbox:box}}));}}/></label><p className="hint">Sahkan hanya kepala yang jelas terkait track. Helm di tangan atau kepala tertutup tetap unknown.</p></details>)}
    <p className="hint">{summary?.model_id?'Kandidat fine-tuned':'Detector awal'} · koreksi a{summary?.annotation_revision??0}/c{summary?.correction_revision??0}. Simpan koreksi bukan update bobot.</p>
    <button className="button button--primary" type="submit" disabled={!job||!selected.length}>Sahkan crossing terpilih</button>
   </fieldset></form>
  </section>}
  {role==='admin'&&<details><summary>Catat absensi yang sudah diverifikasi</summary><form onSubmit={event=>{event.preventDefault();void run(async()=>{await api('/api/ledger/attendance',post({subject_id:subject,source_kind:sourceKind,source_id:sourceId,occurred_at:occurredAt,action,job_id:track?job:null,track_id:track?Number(track):null}));await refresh();setSourceId('');setStatus('Absensi terverifikasi dicatat, tanpa inferensi biometrik.');});}}><fieldset disabled={busy}>
   <div className="ngram-inline"><label>ID subjek terverifikasi<input required minLength={1} maxLength={80} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" value={subject} onChange={event=>setSubject(event.target.value)}/></label><label>Jenis sumber<select value={sourceKind} onChange={event=>setSourceKind(event.target.value)}><option value="manual">Verifikasi manual</option><option value="badge">Badge, diperiksa manual</option><option value="qr">QR, diperiksa manual</option></select></label></div>
   <label>ID bukti sumber, unik untuk kejadian<input required maxLength={120} pattern="[A-Za-z0-9][A-Za-z0-9_.:-]*" value={sourceId} onChange={event=>setSourceId(event.target.value)}/></label>
   <div className="ngram-inline"><label>Waktu absensi, termasuk zona waktu<input required maxLength={80} placeholder="2026-10-10T08:00:00+07:00" value={occurredAt} onChange={event=>setOccurredAt(event.target.value)}/></label><label>Tindakan<select value={action} onChange={event=>setAction(event.target.value)}><option value="arrived">Datang</option><option value="departed">Pulang</option></select></label></div>
   <label>Relasi track opsional dari rekaman terpilih<select value={track} onChange={event=>setTrack(event.target.value)}><option value="">Tanpa relasi track</option>{people.map(item=><option key={item.id} value={item.id}>Track {item.id}</option>)}</select></label><p className="hint">Relasi memerlukan bukti manual yang cocok. Track ID sendiri tidak mengungkap identitas.</p>
   <button className="button button--primary" type="submit">Simpan absensi terverifikasi</button>
  </fieldset></form></details>}
  {!reviewer&&role&&<p className="hint">Viewer melihat observasi dan agregat absensi. Peninjauan crossing membutuhkan reviewer; identitas absensi hanya tersedia bagi administrator.</p>}
  <div className="ngram-table"><table><caption>Catatan ledger, {rows.length} tersedia; menampilkan maksimal 200 terbaru.</caption><thead><tr><th>Waktu</th><th>Kejadian</th><th>Track / subjek</th><th>Status & bukti</th><th>Penarikan</th></tr></thead><tbody>{rows.slice(-200).reverse().map(row=><tr key={row.id}><td><time dateTime={row.occurred_at||undefined}>{row.occurred_at||`${row.payload.seconds}s sejak awal video`}</time></td><td>{row.symbol}</td><td>{row.category==='attendance'?row.payload.subject_id:`Track ${row.track_id??'unknown'}`}</td><td>{row.status}{row.payload.schema_version===2&&row.status==='verified'&&<> · <a href={`/api/ledger/events/${row.id}/proof`} target="_blank" rel="noreferrer">Frame {row.payload.frame_index} · {row.payload.seconds}s</a></>}{row.payload.evidence&&/^\/api\/jobs\/[a-f0-9-]+\/media\/evidence_\d+\.jpg$/.test(row.payload.evidence)&&<> Â· <a href={row.payload.evidence} target="_blank" rel="noreferrer">Snapshot</a></>}{row.reason&&<small>{row.reason}</small>}</td><td>{reviewer&&row.status!=='retracted'&&(row.category!=='attendance'||role==='admin')?<details><summary>Tarik catatan</summary><form onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget),reason=String(data.get('reason')||'');void run(async()=>{await api(`/api/ledger/events/${encodeURIComponent(row.id)}/retract`,post({reason}));await refresh();setStatus('Catatan ditarik; riwayat tetap tersimpan.');});}}><label>Alasan penarikan<input name="reason" required maxLength={200} disabled={busy}/></label><button className="button button--tertiary button--sm" type="submit" disabled={busy}>Sahkan penarikan</button></form></details>:'â€”'}</td></tr>)}</tbody></table></div>
  {!rows.length&&facts&&<p className="hint">Belum ada observasi terverifikasi dalam workspace ini. Pilih crossing nyata untuk memulai.</p>}
  <details><summary>Novelty kejadian, laporan riset</summary><p className="hint">Skor urutan yang jarang bukan bukti bahaya atau pelanggaran. Hanya run tersimpan dalam workspace ini yang ditampilkan.</p>{novelty?.runs.length?novelty.runs.map(item=><section key={item.run_id}><h3>{item.run_id}</h3><pre>{JSON.stringify(item.summary,null,2)}</pre></section>):<p className="hint">Belum ada laporan novelty kejadian yang tersedia.</p>}{!!novelty?.errors.length&&<p className="error">Sebagian laporan tidak dapat diverifikasi: {JSON.stringify(novelty.errors)}</p>}</details>
  {facts?.limitations.map(value=><p className="hint" key={value}>{value}</p>)}
 </details>;
}
