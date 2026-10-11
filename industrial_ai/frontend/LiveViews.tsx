import { Fragment, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { flushSync } from 'react-dom';

interface EvidenceRow {key:number;href:string;imageAlt:string;title:string;detail:string;seek:()=>void}
interface MessageRow {role:string;text:string;detail:string;links:{href:string;text:string;event_id?:string}[]}
interface OverlayRow {bbox:[number,number,number,number];color:string;selected:boolean;text:string}
interface BoxRow {text:string;color:string;disabled:boolean;edit:()=>void;remove:()=>void}
interface QueueRow {frame:number;text:string;disabled:boolean;current:boolean;select:()=>Promise<void>}
interface OptionRow {value:string;text:string}
interface StudioViews {evidence(rows:EvidenceRow[]):void;details(rows:string[][]):void;appendMessage(row:MessageRow):void;clearMessages():void;overlay(rows:OverlayRow[]):void;boxes(rows:BoxRow[]):void;queue(rows:QueueRow[]):void;options(id:string,rows:OptionRow[]):void}

const roots = new Map<Element, Root>();
const messages: MessageRow[] = [];
function render(id: string, content: ReactNode): Element {
 const container = document.getElementById(id);
 if (!container) throw new Error(`Missing live view ${id}`);
 let root = roots.get(container);
 if (!root) { root = createRoot(container); roots.set(container, root); }
 flushSync(() => root.render(content));
 return container;
}
export const studioViews: StudioViews = {
 evidence(rows) { render('evidenceList', rows.length ? rows.map(row => <div className="evidence-row" key={row.key}>
  <a href={row.href} target="_blank" rel="noopener" aria-label={`Buka bukti track ${row.key}`}><img src={row.href} alt={row.imageAlt} loading="lazy" /></a>
  <div><strong>{row.title}</strong><p>{row.detail}</p><button type="button" className="button button--secondary button--sm" onClick={row.seek}>Lihat momen</button></div>
 </div>) : <p className="hint">Belum ada bukti untuk jenis ini. Analisis lama mungkin belum menyimpan foto track orang biasa; analisis ulang melengkapinya.</p>); },
 details(rows) { render('resultDetails', rows.map(([label,value],i) => <Fragment key={`${label}-${i}`}><dt>{label}</dt><dd>{value}</dd></Fragment>)); },
 appendMessage(row) {
  messages.push(row);
  const container=render('messages',messages.map((item,i)=><div key={i} className={`message ${item.role}`}>{item.text}{item.detail&&<small>{item.detail}</small>}{item.links.map((link,j)=>link.event_id?<button key={j} className="button button--tertiary button--sm" type="button" onClick={()=>document.dispatchEvent(new CustomEvent('ledger-proof',{detail:{event_id:link.event_id}}))}>{link.text}</button>:<a key={j} href={link.href} target="_blank" rel="noopener">{link.text}</a>)}</div>));
  document.dispatchEvent(new CustomEvent('workspace-message',{detail:container.lastElementChild}));
  container.scrollTop=container.scrollHeight;
 },
 clearMessages() { messages.length=0;render('messages',null); },
 overlay(rows) {render('reviewSvg',rows.map((row,i)=>{const [x1,y1,x2,y2]=row.bbox;return <g key={i}>
  <rect x={x1} y={y1} width={x2-x1} height={y2-y1} fill={row.color} fillOpacity={.1} stroke={row.color} strokeWidth={row.selected?3:2} vectorEffect="non-scaling-stroke" />
  <text x={x1} y={Math.max(.025,y1-.005)} fontSize=".025" fill={row.color} stroke="#fff" strokeWidth=".003" paintOrder="stroke">{row.text}</text>
 </g>;}));},
 boxes(rows) {render('boxList',rows.map((row,i)=><li key={i}><span className="box-name"><i className="box-swatch" style={{background:row.color}} />{row.text}</span><button type="button" className="button button--secondary button--sm" disabled={row.disabled} onClick={row.edit}>Edit kotak {i+1}</button><button type="button" className="button button--tertiary button--sm" disabled={row.disabled} onClick={row.remove}>Hapus kotak {i+1}</button></li>));},
 queue(rows) {render('reviewQueue',rows.map(row=><button key={row.frame} type="button" className="queue-position button button--outline button--sm" disabled={row.disabled} aria-current={row.current?'true':undefined} onClick={()=>void row.select()}>{row.text}</button>));},
 options(id,rows) {render(id,rows.map(row=><option key={row.value} value={row.value}>{row.text}</option>));}
};
