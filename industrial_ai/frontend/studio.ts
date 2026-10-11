'use strict';
interface EvidenceRow {key:number;href:string;imageAlt:string;title:string;detail:string;seek:()=>void}
interface MessageRow {role:string;text:string;detail:string;links:{href:string;text:string}[]}
interface OverlayRow {bbox:[number,number,number,number];color:string;selected:boolean;text:string}
interface BoxRow {text:string;color:string;disabled:boolean;edit:()=>void;remove:()=>void}
interface QueueRow {frame:number;text:string;disabled:boolean;current:boolean;select:()=>Promise<void>}
interface OptionRow {value:string;text:string}
interface StudioViews {evidence(rows:EvidenceRow[]):void;details(rows:string[][]):void;appendMessage(row:MessageRow):void;clearMessages():void;overlay(rows:OverlayRow[]):void;boxes(rows:BoxRow[]):void;queue(rows:QueueRow[]):void;options(id:string,rows:OptionRow[]):void}
declare const studioViews:StudioViews;
type View = 'analysis'|'evidence'|'annotation'|'profile'|'ngram';
type Counts = Record<string,number>;
interface Box {label:string;name?:string|null;color?:string|null;bbox:[number,number,number,number];track_id?:number;source?:string}
interface Frame {frame_index:number;boxes:Box[];lost?:Box[];merged?:boolean;complete?:boolean;helmets_complete?:boolean}
interface Track {id:number;kind:string;helmet_candidate?:boolean;helmet_evidence?:string;evidence:string;evidence_seconds:number;helmet_seconds?:number;evidence_status?:string;status:string}
interface Summary {frames:number;fps:number;duration:number;occupancy:Counts[];reviewed_occupancy?:Counts[];review_status?:{saved_positions:number;draft_positions:number;latest?:{counts:Counts;seconds:number}};crossings:{kind:string}[];tracks:Track[];object_classes?:string[];object_names?:Record<string,string>;processing_seconds:number;device_reason?:string;device?:string;model_id?:string;learning_evidence?:{checkpoint_sha256:string;training_seconds:number}}
interface Job {id:string;status:string;filename:string;summary:Summary;progress:number;message:string;model_id?:string;group:string;followup_job_id?:string}
interface Review {revision:number;frames:Frame[]}
interface Queue {reviewed:number;total:number;pending:number;group:string;positions:{reviewed:boolean;frame_index:number;seconds:number;reasons:string[]}[]}
interface ChatReply {mode:string;answer:string;truncated?:boolean;seconds:number;device?:string;evidence:{file:string;kind:string;track_id:number;seconds:number}[]}
interface Health {vision_ready:boolean;chat_ready:boolean;device:string;adapter_ready?:boolean}
interface TrackingStep extends Review {next_frame:number;ended:boolean}
interface TrackingStart {id:string;revision:number;frame:Frame}
interface ExportState {status:string;progress:number;message:string;media_url:string;filename:string}
interface TrainingJob {id:string;status:string;group:string;progress:number;message:string;followup_job_id?:string;result_job_id?:string;checkpoint_sha256?:string}
interface LearnReply {id:string;status:string;message:string;result_job_id?:string}
type ApiResponse=Job|Review|Queue|ChatReply|Health|TrackingStep|TrackingStart|ExportState|TrainingJob|LearnReply|{id:string}|{boxes:Box[]}|Record<string,unknown>;

declare const workspaceAuth:{ready:Promise<void>;request(input:RequestInfo|URL,init?:RequestInit):Promise<Response>;resetPasswordForm():void;finishLoading(error?:string):Promise<void>};
interface StudioDom {
 'loginTransitionLoader':HTMLElement;
 'loginTransitionStatus':HTMLElement;
 'loginCrowdCanvas':HTMLCanvasElement;
 'loginTransitionRetry':HTMLButtonElement;
 'authGate':HTMLElement;
 'loginForm':HTMLFormElement;
 'loginTitle':HTMLElement;
 'loginUsername':HTMLInputElement;
 'loginPassword':HTMLInputElement;
 'toggleLoginPassword':HTMLButtonElement;
 'loginError':HTMLElement;
 'loginSubmit':HTMLButtonElement;
 'pageTitle':HTMLElement;
 'themeToggleBtn':HTMLButtonElement;
 'profileButton':HTMLButtonElement;
 'accountAvatar':HTMLElement;
 'accountIdentity':HTMLElement;
 'mainContent':HTMLElement;
 'authError':HTMLElement;
 'videoWorkspace':HTMLElement;
 'ngramPane':HTMLElement;
 'workspaceTitle':HTMLElement;
 'newVideoButton':HTMLButtonElement;
 'historySelect':HTMLSelectElement;
 'deviceMode':HTMLSelectElement;
 'analysisModel':HTMLSelectElement;
 'reanalyzeButton':HTMLButtonElement;
 'modelHelp':HTMLElement;
 'systemStatus':HTMLElement;
 'learningProgress':HTMLElement;
 'learningProgressBar':HTMLProgressElement;
 'learningStatus':HTMLElement;
 'cancelLearning':HTMLButtonElement;
 'showLearnedResult':HTMLButtonElement;
 'progressArea':HTMLElement;
 'jobProgress':HTMLProgressElement;
 'jobStatus':HTMLElement;
 'cancelJob':HTMLButtonElement;
 'retryJob':HTMLButtonElement;
 'exportProgress':HTMLElement;
 'exportProgressBar':HTMLProgressElement;
 'exportStatus':HTMLElement;
 'cancelExport':HTMLButtonElement;
 'uploadError':HTMLElement;
 'analysisPane':HTMLElement;
 'compare':HTMLElement;
 'comparisonTitle':HTMLElement;
 'currentFile':HTMLElement;
 'comparisonLayout':HTMLSelectElement;
 'resultAi':HTMLInputElement;
 'resultCorrections':HTMLInputElement;
 'resultMode':HTMLSelectElement;
 'correctedOption':HTMLOptionElement;
 'emptyVideos':HTMLElement;
 'emptyUploadButton':HTMLButtonElement;
 'videoContent':HTMLElement;
 'originalVideo':HTMLVideoElement;
 'trackingPaneTitle':HTMLElement;
 'trackedVideo':HTMLVideoElement;
 'playBoth':HTMLButtonElement;
 'restartVideos':HTMLButtonElement;
 'videoTime':HTMLElement;
 'openReview':HTMLButtonElement;
 'visibleNow':HTMLElement;
 'comparisonBadge':HTMLElement;
 'stats':HTMLElement;
 'peakPeople':HTMLElement;
 'peakCars':HTMLElement;
 'crossingCount':HTMLElement;
 'candidateCount':HTMLElement;
 'correctionCounts':HTMLElement;
 'prepareCorrections':HTMLButtonElement;
 'evidencePane':HTMLElement;
 'resultsTitle':HTMLElement;
 'resultsEmpty':HTMLElement;
 'resultsContent':HTMLElement;
 'resultDetails':HTMLElement;
 'evidenceFilter':HTMLSelectElement;
 'evidenceList':HTMLElement;
 'downloadTracked':HTMLAnchorElement;
 'downloadSummary':HTMLAnchorElement;
 'downloadOriginal':HTMLAnchorElement;
 'reviewPanel':HTMLElement;
 'reviewTitle':HTMLElement;
 'fullscreenReview':HTMLButtonElement;
 'closeReview':HTMLButtonElement;
 'reviewGroup':HTMLSelectElement;
 'suggestBoxes':HTMLButtonElement;
 'reviewPlayback':HTMLButtonElement;
 'reviewTimeline':HTMLInputElement;
 'reviewPlayTime':HTMLElement;
 'drawingStatus':HTMLElement;
 'reviewControls':HTMLFieldSetElement;
 'reviewSeconds':HTMLInputElement;
 'loadReviewFrame':HTMLButtonElement;
 'previousReviewFrame':HTMLButtonElement;
 'nextReviewFrame':HTMLButtonElement;
 'reviewStage':HTMLElement;
 'reviewVideo':HTMLVideoElement;
 'reviewImage':HTMLElement;
 'reviewSvg':SVGSVGElement;
 'boxForm':HTMLFormElement;
 'boxControls':HTMLFieldSetElement;
 'boxX':HTMLInputElement;
 'boxY':HTMLInputElement;
 'boxW':HTMLInputElement;
 'boxH':HTMLInputElement;
 'addManualBox':HTMLButtonElement;
 'queueFilter':HTMLSelectElement;
 'nextPending':HTMLButtonElement;
 'queueStatus':HTMLElement;
 'reviewQueue':HTMLElement;
 'metadataControls':HTMLFieldSetElement;
 'reviewLabel':HTMLSelectElement;
 'customLabelField':HTMLElement;
 'customLabel':HTMLInputElement;
 'reviewName':HTMLInputElement;
 'reviewColorMode':HTMLSelectElement;
 'reviewColor':HTMLInputElement;
 'editActions':HTMLElement;
 'applyBoxButton':HTMLButtonElement;
 'cancelEditButton':HTMLButtonElement;
 'reviewCounts':HTMLElement;
 'boxList':HTMLElement;
 'saveReview':HTMLButtonElement;
 'reloadReview':HTMLButtonElement;
 'exportCorrectedVideo':HTMLButtonElement;
 'exportDataset':HTMLButtonElement;
 'reviewStatus':HTMLElement;
 'reviewError':HTMLElement;
 'learnDetector':HTMLButtonElement;
 'chatTitle':HTMLElement;
 'clearChat':HTMLButtonElement;
 'messages':HTMLElement;
 'chatThinkingOrb':HTMLElement;
 'chatOrbCanvas':HTMLCanvasElement;
 'chatForm':HTMLFormElement;
 'chatInput':HTMLTextAreaElement;
 'sendChat':HTMLButtonElement;
 'chatStatus':HTMLElement;
 'chatError':HTMLElement;
 'chatContext':HTMLElement;
 'profilePane':HTMLElement;
 'profileBack':HTMLButtonElement;
 'profileAvatar':HTMLElement;
 'profileTitle':HTMLElement;
 'profileDisplayName':HTMLElement;
 'personalTitle':HTMLElement;
 'profileNameInput':HTMLInputElement;
 'saveNameBtn':HTMLButtonElement;
 'nameSaveStatus':HTMLElement;
 'avatarFileInput':HTMLInputElement;
 'removeAvatarBtn':HTMLButtonElement;
 'avatarStatus':HTMLElement;
 'identityTitle':HTMLElement;
 'profileUsername':HTMLElement;
 'profileWorkspace':HTMLElement;
 'profileRole':HTMLElement;
 'passwordTitle':HTMLElement;
 'passwordHelp':HTMLElement;
 'passwordForm':HTMLFormElement;
 'currentPassword':HTMLInputElement;
 'newPassword':HTMLInputElement;
 'passwordLength':HTMLElement;
 'passwordMeter':HTMLElement;
 'ruleLen':HTMLElement;
 'ruleCase':HTMLElement;
 'ruleDigit':HTMLElement;
 'ruleSymbol':HTMLElement;
 'passwordStrengthAnnouncement':HTMLElement;
 'confirmPassword':HTMLInputElement;
 'passwordStatus':HTMLElement;
 'passwordSubmit':HTMLButtonElement;
 'appearanceTitle':HTMLElement;
 'themeSelect':HTMLSelectElement;
 'signoutTitle':HTMLElement;
 'logoutButton':HTMLButtonElement;
 'uploadDialog':HTMLDialogElement;
 'uploadTitle':HTMLElement;
 'closeUpload':HTMLButtonElement;
 'uploadForm':HTMLFormElement;
 'videoFile':HTMLInputElement;
 'uploadHelp':HTMLElement;
 'lineValue':HTMLElement;
 'countLine':HTMLInputElement;
 'uploadButton':HTMLButtonElement;
}
function $<K extends keyof StudioDom>(id:K):StudioDom[K]{const node=document.getElementById(id);if(!node)throw Error(`Missing element ${id}`);return node as StudioDom[K];}

let job:Job|null=null, summary:Summary|null=null, pollTimer:number|undefined, chatHistory:{role:string;content:string}[]=[], generation=0;
let currentView:View='analysis', previousWorkspaceView:View='analysis', uploading=false, exporting=false;
const objectNames:Record<string,string>={karung:'Karung',person:'Orang',car:'Mobil',bus:'Bus',truck:'Truk',motorcycle:'Motor',bicycle:'Sepeda'};
const vehicles = (frame:Counts) => Object.keys(frame).filter(k=>!['person','seconds'].includes(k)).reduce((n,k)=>n+(frame[k] || 0),0);
function syncResultSwitch() {
  const mode=$('resultMode').value;
  $('trackingPaneTitle').textContent=mode==='corrections' ? 'Koreksi saya' : 'Model AI';
  for(const [id,value] of [['resultAi','ai'],['resultCorrections','corrections']] as const) {
    $(id).checked=mode===value;
    $(id).disabled=!summary || uploading || sending || reviewBusy || exporting;
  }
}
function syncControls() {
  const blocked=uploading || sending || reviewBusy || currentView==='annotation' || ['uploading','queued','processing','cancelling'].includes(job?.status||'');
  for(const id of ['newVideoButton','emptyUploadButton','uploadButton'] as const) $(id).disabled=blocked;
  $('historySelect').disabled=uploading || sending || reviewBusy || currentView==='annotation';
  $('closeUpload').disabled=uploading; $('sendChat').disabled=sending || reviewBusy; for(const button of document.querySelectorAll<HTMLButtonElement>('[data-question]'))button.disabled=sending || reviewBusy;
  $('reanalyzeButton').disabled=blocked || !summary;
  $('retryJob').hidden=!['error','cancelled'].includes(job?.status||'');
  $('cancelJob').hidden=!['queued','processing','cancelling'].includes(job?.status||'');
  $('cancelJob').disabled=job?.status==='cancelling';
  for(const button of document.querySelectorAll<HTMLButtonElement>('[data-view]')) button.disabled=uploading || reviewBusy;
  $('profileButton').disabled=uploading || sending || reviewBusy;
  syncResultSwitch();
}
async function setView(view:View) {
  if(view===currentView) return true;
  if(reviewBusy || uploading || sending) return false;
  if(currentView==='annotation' && !(await persistReview(false))) return false;
  if(view==='annotation' && !summary) {showError('uploadError','Pilih rekaman yang selesai dianalisis untuk membuat anotasi.'); return false;}
  if(document.fullscreenElement===$('reviewPanel')) await document.exitFullscreen();
  cancelDrawing(); pauseComparison();
  await stopReviewTracking();
  if(view==='profile')previousWorkspaceView=currentView;
  if(currentView==='profile')workspaceAuth.resetPasswordForm();
  currentView=view; reviewVideo.pause();
  $('videoWorkspace').hidden=view==='profile'||view==='ngram'; $('profilePane').hidden=view!=='profile'; $('ngramPane').hidden=view!=='ngram';
  $('analysisPane').hidden=view!=='analysis'; $('evidencePane').hidden=view!=='evidence'; $('reviewPanel').hidden=view!=='annotation';
  $('pageTitle').textContent={analysis:'Analisis video',evidence:'Bukti & hasil',annotation:'Anotasi manual',profile:'Profil',ngram:'Lab N-gram'}[view];
  for(const button of document.querySelectorAll<HTMLButtonElement>('[data-view]')) {if(button.dataset.view===view) button.setAttribute('aria-current','page'); else button.removeAttribute('aria-current');}
  syncControls();
  document.dispatchEvent?.(new Event('workspace-view'));
  if(view==='annotation') await loadManualFrame(Math.min(summary!.frames-1,Math.round(original.currentTime*summary!.fps)));
  return true;
}
for(const button of document.querySelectorAll<HTMLButtonElement>('[data-view]')) button.onclick=()=>setView(button.dataset.view as View);
for(const id of ['newVideoButton','emptyUploadButton'] as const) $(id).onclick=()=>{showError('uploadError','');$('uploadDialog').showModal();};
$('closeUpload').onclick=()=>$('uploadDialog').close();
$('uploadDialog').addEventListener('cancel',event=>{if(uploading) event.preventDefault();});
const original = $('originalVideo'), tracked = $('trackedVideo');
const showError = (id:Exclude<keyof StudioDom,'reviewSvg'>, text:string) => { $(id).textContent = text; $(id).hidden = !text; };
const mediaUrl = (name:string) => `/api/jobs/${job!.id}/media/${encodeURIComponent(name)}`;
const timestamp = (value:number) => { const s = Math.max(0, Math.floor(value || 0)); return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`; };
type FieldType='string'|'number'|'boolean'|'array'|'object';
function requireFields(value:unknown,fields:Record<string,FieldType>):Record<string,unknown>{
  if(typeof value!=='object'||value===null||Array.isArray(value))throw Error('Respons API tidak valid.');
  const record=value as Record<string,unknown>;
  for(const [key,type] of Object.entries(fields)){
    const field=record[key],valid=type==='array'?Array.isArray(field):type==='object'?typeof field==='object'&&field!==null&&!Array.isArray(field):typeof field===type&&(type!=='number'||Number.isFinite(field));
    if(!valid)throw Error(`Respons API tidak valid: ${key}.`);
  }
  return record;
}
function validateBoxes(value:unknown):void{
  if(!Array.isArray(value))throw Error('Respons kotak tidak valid.');
  for(const item of value){const box=requireFields(item,{label:'string',bbox:'array'});const bbox=box.bbox as unknown[];if(bbox.length!==4||bbox.some(n=>typeof n!=='number'||!Number.isFinite(n)))throw Error('Koordinat kotak tidak valid.');}
}
function validateFrames(value:unknown):void{
  if(!Array.isArray(value))throw Error('Respons frame tidak valid.');
  for(const item of value){const frame=requireFields(item,{frame_index:'number',boxes:'array'});validateBoxes(frame.boxes);if(frame.lost!==undefined)validateBoxes(frame.lost);}
}
function validateSummary(value:unknown):void{
  const data=requireFields(value,{frames:'number',fps:'number',duration:'number',occupancy:'array',crossings:'array',tracks:'array',processing_seconds:'number'});
  if(Number(data.frames)<1||Number(data.fps)<=0)throw Error('Metadata video tidak valid.');
  for(const row of [...data.occupancy as unknown[],...Array.isArray(data.reviewed_occupancy)?data.reviewed_occupancy:[]]){const counts=requireFields(row,{});if(Object.values(counts).some(n=>typeof n!=='number'||!Number.isFinite(n)))throw Error('Hitungan tidak valid.');}
  for(const row of data.tracks as unknown[]){const track=requireFields(row,{id:'number',kind:'string'});for(const key of ['evidence','helmet_evidence','evidence_status','status'])if(track[key]!==undefined&&typeof track[key]!=='string')throw Error('Metadata bukti tidak valid.');for(const key of ['evidence_seconds','helmet_seconds'])if(track[key]!==undefined&&(typeof track[key]!=='number'||!Number.isFinite(track[key])))throw Error('Waktu bukti tidak valid.');}
  if(data.object_names){const names=requireFields(data.object_names,{});if(Object.values(names).some(value=>typeof value!=='string'))throw Error('Nama objek tidak valid.');}
  for(const row of data.crossings as unknown[])requireFields(row,{kind:'string'});
  if(data.review_status){const status=requireFields(data.review_status,{saved_positions:'number',draft_positions:'number'});if(status.latest){const latest=requireFields(status.latest,{seconds:'number',counts:'object'});if(Object.values(latest.counts as Record<string,unknown>).some(value=>typeof value!=='number'||!Number.isFinite(value)))throw Error('Hitungan koreksi tidak valid.');}}
  if(data.learning_evidence)requireFields(data.learning_evidence,{checkpoint_sha256:'string',training_seconds:'number'});
}
function validateApi(url:string,value:unknown):Record<string,unknown>{
  const data=requireFields(value,{}),path=url.split('?')[0];
  if(path==='/api/health')requireFields(data,{vision_ready:'boolean',chat_ready:'boolean',device:'string'});
  else if(path==='/api/chat'){requireFields(data,{mode:'string',answer:'string',evidence:'array'});for(const item of data.evidence as unknown[])requireFields(item,{file:'string',kind:'string',track_id:'number',seconds:'number'});}
  else if(path.endsWith('/annotations')||path.endsWith('/corrections')||path.endsWith('/overlays')){requireFields(data,{frames:'array'});validateFrames(data.frames);if(!path.endsWith('/overlays'))requireFields(data,{revision:'number'});}
  else if(path.includes('/suggestions/'))validateBoxes(data.boxes);
  else if(path.endsWith('/review-queue')){requireFields(data,{reviewed:'number',total:'number',pending:'number',group:'string',positions:'array'});for(const item of data.positions as unknown[])requireFields(item,{frame_index:'number',seconds:'number',reviewed:'boolean',reasons:'array'});}
  else if(path.endsWith('/tracking')){requireFields(data,{id:'string',revision:'number',frame:'object'});validateFrames([data.frame]);}
  else if(path.endsWith('/step')){requireFields(data,{frames:'array',next_frame:'number',ended:'boolean'});validateFrames(data.frames);}
  else if(/\/api\/jobs\/[^/]+$/.test(path)){requireFields(data,{id:'string',status:'string',filename:'string',progress:'number',message:'string'});if(data.status==='done')validateSummary(data.summary);}
  else if(/\/(exports|training)\/[^/]+$/.test(path)){requireFields(data,{status:'string',progress:'number',message:'string'});if(path.includes('/exports/')&&data.status==='done')requireFields(data,{media_url:'string',filename:'string'});}
  else if(path==='/api/jobs'||path.endsWith('/exports')||path.endsWith('/retry')||path.endsWith('/reanalyze'))requireFields(data,{id:'string'});
  else if(path.endsWith('/learn')){requireFields(data,{status:'string'});requireFields(data,data.status==='waiting'?{message:'string'}:{id:'string'});}
  return data;
}
async function api<T extends ApiResponse=Record<string,unknown>>(url:string, options?:RequestInit):Promise<T> {
  const response=await workspaceAuth.request(url,options),data:unknown=await response.json();
  if(!response.ok){const detail=typeof data==='object'&&data!==null&&'detail'in data?data.detail:undefined;throw Error(typeof detail==='string'?detail:'Input tidak valid. Periksa isian dan coba lagi.');}
  return validateApi(url,data) as unknown as T;
}
async function apiList(url:'/api/jobs'):Promise<Job[]>;
async function apiList(url:'/api/training'):Promise<TrainingJob[]>;
async function apiList(url:string):Promise<(Job|TrainingJob)[]>{
  const response=await workspaceAuth.request(url),data:unknown=await response.json();
  if(!response.ok||!Array.isArray(data))throw Error('Respons daftar tidak valid.');
  for(const item of data)requireFields(item,url==='/api/jobs'?{id:'string',status:'string',filename:'string'}:{id:'string',status:'string',group:'string'});
  return data as Job[];
}
function resetChat() { chatHistory = []; studioViews.clearMessages(); showError('chatError',''); stopThinkingOrb(); }
function clearResults() {
  $('workspaceTitle').textContent='Analisis rekaman'; $('workspaceTitle').removeAttribute('title');
  pauseComparison(); original.removeAttribute('src'); tracked.removeAttribute('src'); original.load(); tracked.load(); summary = null;
  exporting=false; $('resultMode').value='ai'; $('correctedOption').disabled=true; syncResultSwitch();
  (['videoContent','stats','resultsContent'] as const).forEach(id => $(id).hidden = true);
  $('emptyVideos').hidden = false; $('resultsEmpty').hidden = false;
  $('resultsEmpty').textContent = 'Hasil akan tersedia setelah video selesai dianalisis.';
  $('comparisonBadge').textContent = 'Menunggu hasil';
  $('chatContext').textContent = 'Chat umum tersedia. Tunggu analisis video untuk bertanya tentang hasilnya.';
}
async function refreshHistory(selected?:string) {
  const jobs = await apiList('/api/jobs');
  studioViews.options('historySelect',[{value:'',text:jobs.length?'Pilih video tersimpan':'Belum ada video'},...jobs.map(item=>({value:item.id,text:`${item.filename} · ${{done:'Selesai',processing:'Diproses',queued:'Antrean',error:'Gagal',uploading:'Upload',cancelled:'Dibatalkan',cancelling:'Membatalkan'}[item.status]}`}))]);
  $('historySelect').value = selected || '';
  return jobs;
}
function refreshCounts() {
  const occupancy=summary!.reviewed_occupancy || summary!.occupancy;
  $('peakPeople').textContent=String(Math.max(0,...occupancy.map(f=>f.person || 0)));
  $('peakCars').textContent=String(Math.max(0,...occupancy.map(vehicles)));
  const status=summary!.review_status, latest=status?.latest;
  const latestCounts=latest ? Object.entries(latest.counts).filter(([,n])=>n>0).map(([k,n])=>`${n} ${(objectNames[k] || k).toLowerCase()}`).join(' · ') || '0 objek' : '';
  $('correctionCounts').textContent=status ? `${status.saved_positions} posisi koreksi disahkan · ${status.draft_positions} draft belum dihitung${latest ? ` · Terakhir detik ${latest.seconds}: ${latestCounts}` : ''}. Track dan lintasan tetap dari analisis AI awal.` : '';
  updateMoment();
}
function displayResults(data:Job) {
  $('progressArea').hidden=true;
  summary = data.summary; Object.assign(objectNames,summary!.object_names || {});
  $('workspaceTitle').textContent='Analisis rekaman';
  $('workspaceTitle').title=data.filename;
  const filters=Array.from($('evidenceFilter').options).map(option=>({value:option.value,text:option.text}));for(const kind of summary!.object_classes||[])if(!filters.some(option=>option.value===kind))filters.push({value:kind,text:objectNames[kind]||kind});studioViews.options('evidenceFilter',filters);
  $('videoContent').hidden = false; $('emptyVideos').hidden = true; $('stats').hidden = false;
  $('resultsContent').hidden = false; $('resultsEmpty').hidden = true; $('comparisonBadge').textContent = 'Analisis selesai';
  original.src = mediaUrl('original.mp4'); tracked.src = mediaUrl('tracked.mp4');
  $('chatContext').textContent = `Konteks: ${data.filename}. Chat hanya membaca hasil video ini.`;
  refreshCounts();
  $('crossingCount').textContent = String(summary!.crossings.length);
  $('candidateCount').textContent = String(summary!.tracks.filter(t => t.kind === 'person' && t.helmet_candidate).length);
  const count = (kind:string) => summary!.tracks.filter(t => t.kind === kind).length;
  const crossing = (kind:string) => summary!.crossings.filter(t => t.kind === kind).length;
  const kinds=summary!.object_classes || ['person','car'];
  const details = [['Durasi / frame analisis',`${summary!.duration} detik / ${summary!.frames}`],...kinds.map(k=>[`Track / lintasan ${objectNames[k].toLowerCase()}`,`${count(k)} / ${crossing(k)}`]),['Waktu pemrosesan',`${summary!.processing_seconds} detik`],['Perangkat analisis',summary!.device_reason || summary!.device || 'CPU (analisis lama)']];
  studioViews.details(details);
  renderEvidence();
  for (const [id,name] of [['downloadTracked','tracked.mp4'],['downloadSummary','summary_reviewed.json'],['downloadOriginal','upload.bin']] as const) { $(id).href = mediaUrl(name); $(id).setAttribute('download',name); }
  $('downloadSummary').href=`/api/jobs/${job!.id}/summary`;
  $('analysisModel').value=summary!.model_id || '';
  $('resultMode').value='ai'; $('correctedOption').disabled=true;
  const evidence=summary!.learning_evidence;
  $('modelHelp').textContent=evidence ? `Hasil fine-tuning nyata · checkpoint ${evidence.checkpoint_sha256.slice(0,12)} · ${evidence.training_seconds} detik training. Akurasi perlu evaluasi terpisah.` : 'Hasil model dasar. Koreksi manual ditampilkan melalui Tampilan koreksi.';
  refreshQueue().catch(error=>showError('reviewError',error.message));
  updateMoment(); syncControls();
}
function renderEvidence() {
 if(!summary)return;
 const filter=$('evidenceFilter').value,evidence=summary.tracks.filter(item=>filter==='helmet'?item.helmet_candidate&&(item.helmet_evidence||item.evidence):item.evidence&&(filter==='all'||item.kind===filter));
 studioViews.evidence(evidence.map(item=>({key:item.id,href:mediaUrl(filter==='helmet'?(item.helmet_evidence||item.evidence):item.evidence),imageAlt:`Bukti track ${item.id} pada detik ${item.evidence_seconds}`,title:`ID #${item.id} · ${objectNames[item.kind]||item.kind}${filter==='helmet'?' · Kandidat tanpa helm':''}`,detail:`Detik ${filter==='helmet'?(item.helmet_seconds??item.evidence_seconds):item.evidence_seconds} · ${item.kind!=='person'?'Objek ditandai pada foto':({helmet:'Helm terdeteksi',no_helmet:'Tanpa helm terdeteksi',unknown:'Helm belum jelas'}[item.evidence_status||item.status]||'Helm belum jelas')}`,seek:()=>{pauseComparison();const at=filter==='helmet'?(item.helmet_seconds??item.evidence_seconds):item.evidence_seconds;original.currentTime=at;tracked.currentTime=at;void setView('analysis');original.scrollIntoView({block:'center'});}})));
}
$('evidenceFilter').onchange=renderEvidence;
async function selectJob(id:string) {
  const current = ++generation;
  clearTimeout(pollTimer);clearTimeout(trainingPoll);clearTimeout(exportPoll);$('learningProgress').hidden=true;$('exportProgress').hidden=true;$('showLearnedResult').hidden=true; resetChat(); clearResults();
  $('currentFile').textContent='Pilih rekaman untuk mulai.';
  if (!id) { job = null; $('progressArea').hidden = true; $('comparisonBadge').textContent = 'Menunggu video'; syncControls(); return; }
  async function check() {
    try {
      const data = await api<Job>(`/api/jobs/${id}`);
      if (current !== generation) return;
      job = data; $('currentFile').textContent=data.filename; syncControls(); $('progressArea').hidden = false; $('jobProgress').value = data.progress; $('jobStatus').textContent = data.message;
      syncControls();
      if (data.status === 'done') { displayResults(data); await refreshHistory(id); }
      else if (['error','cancelled'].includes(data.status)) { $('comparisonBadge').textContent = 'Analisis gagal'; showError('uploadError',data.message); await refreshHistory(id); }
      else { $('comparisonBadge').textContent = 'Sedang diproses'; pollTimer = setTimeout(check,1500); }
    } catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason)); if (current === generation) { showError('uploadError',error.message); syncControls(); } }
  }
  await check();
}
$('countLine').oninput = () => $('lineValue').textContent = `${$('countLine').value}%`;
$('uploadForm').onsubmit = async event => {
  event.preventDefault(); showError('uploadError','');
  const file = $('videoFile').files?.[0];
  if (!file) return;
  if (file.size > 250*1024*1024) { showError('uploadError','Ukuran video maksimal 250 MB.'); return; }
  uploading=true; syncControls(); $('progressArea').hidden = false; $('jobStatus').textContent = 'Mengunggah video…'; $('jobProgress').removeAttribute('value');
  const form = new FormData(); form.append('file',file); form.append('line',String(Number($('countLine').value)/100)); form.append('device',$('deviceMode').value); form.append('model_id',$('analysisModel').value);
  try { const data = await api<{id:string}>('/api/jobs',{method:'POST',body:form}); $('uploadDialog').close(); uploading=false; await setView('analysis'); await refreshHistory(data.id); await selectJob(data.id); }
  catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason)); showError('uploadError',error.message); $('uploadDialog').close(); $('jobProgress').value = 0; }
  finally {uploading=false; syncControls();}
};
$('historySelect').onchange = () => { showError('uploadError',''); selectJob($('historySelect').value); };
function updateMoment() {
  if (!summary) return;
  $('videoTime').textContent = `${timestamp(original.currentTime)} / ${timestamp(summary!.duration)}`;
  const occupancy=summary!.reviewed_occupancy || summary!.occupancy;
  const index = Math.min(occupancy.length-1, Math.round(original.currentTime*summary!.fps));
  const frame = occupancy[index]; if(!frame) return; $('visibleNow').textContent = `Frame: ${frame.person || 0} orang · ${vehicles(frame)} objek lain`;
  $('playBoth').textContent = original.paused ? 'Putar bersama' : 'Jeda bersama';
}
let playbackEpoch=0;
function pauseComparison() {
  ++playbackEpoch; original.pause(); tracked.pause(); updateMoment();
}
async function playComparison(source=original) {
  if(currentView!=='analysis') return;
  const epoch=++playbackEpoch, other=source===original ? tracked : original;
  if(source.ended || other.ended) {original.currentTime=0; tracked.currentTime=0;}
  else if(Math.abs(source.currentTime-other.currentTime)>.08) other.currentTime=source.currentTime;
  showError('uploadError','');
  try {await Promise.all([source.play(),other.play()]);}
  catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));
    if(epoch!==playbackEpoch || currentView!=='analysis' || error.name==='AbortError') return;
    pauseComparison(); showError('uploadError','Video gagal diputar. Periksa apakah kedua video dapat dimuat.');
  }
  updateMoment();
}
for (const [source,other] of [[original,tracked],[tracked,original]]) {
  source.addEventListener('play',() => {
    if(source.paused || currentView!=='analysis') return;
    if(other.paused) playComparison(source);
    updateMoment();
  });
  source.addEventListener('pause',() => {if(source.paused) pauseComparison();});
  source.addEventListener('seeking',() => {if(Math.abs(source.currentTime-other.currentTime)>.08) other.currentTime=source.currentTime; updateMoment();});
  source.addEventListener('ratechange',() => {if(source.playbackRate!==other.playbackRate) other.playbackRate=source.playbackRate;});
  source.addEventListener('error',() => {if(source.getAttribute('src')) {pauseComparison();showError('uploadError','Video gagal dimuat. Periksa koneksi server lokal.');}});
}
original.addEventListener('timeupdate',() => {if(!original.paused && !tracked.paused && Math.abs(original.currentTime-tracked.currentTime)>.3) tracked.currentTime=original.currentTime; updateMoment();});
$('playBoth').onclick=()=>{if(!original.paused || !tracked.paused) pauseComparison(); else playComparison();};
$('restartVideos').onclick=()=>{pauseComparison();original.currentTime=0;tracked.currentTime=0;updateMoment();};
function addMessage(role:string,text:string,detail='',evidence:ChatReply['evidence']=[]) {
 studioViews.appendMessage({role,text,detail,links:evidence.map(item=>({href:mediaUrl(item.file),text:`Bukti ${(objectNames[item.kind]||item.kind).toLowerCase()} ID #${item.track_id} · ${timestamp(item.seconds)}`}))});
}
$('clearChat').onclick = resetChat;
// Dotted sphere adapted from anark17r/ai-thiking-orb-and-input, confined to chat.
let orbAnimId:number|null=null;
const orbMotion=matchMedia('(prefers-reduced-motion: reduce)');
const orbPoints:{x:number;y:number;z:number;phase:number}[]=[];
for(let ring=1;ring<16;ring++) {
 const latitude=Math.PI*ring/16, count=Math.max(5,Math.round(30*Math.sin(latitude)));
 for(let i=0;i<count;i++){const longitude=2*Math.PI*i/count;orbPoints.push({x:Math.sin(latitude)*Math.cos(longitude),y:Math.cos(latitude),z:Math.sin(latitude)*Math.sin(longitude),phase:longitude});}
}
function startThinkingOrb() {
 stopThinkingOrb();
 const container=$('chatThinkingOrb'),canvas=$('chatOrbCanvas');container.hidden=false;
 const ctx=canvas.getContext('2d');if(!ctx)return;
 const started=performance.now();
 function render(now:number) {
  if(container.hidden){orbAnimId=null;return;}
  const time=orbMotion.matches?0:(now-started)/1000,yaw=time*.4,pitch=.3;
  const points=orbPoints.map(p=>{const x=p.x*Math.cos(yaw)+p.z*Math.sin(yaw),z=-p.x*Math.sin(yaw)+p.z*Math.cos(yaw);return {x,y:p.y*Math.cos(pitch)-z*Math.sin(pitch),z:p.y*Math.sin(pitch)+z*Math.cos(pitch),phase:p.phase};}).sort((a,b)=>a.z-b.z);
  ctx!.clearRect(0,0,canvas.width,canvas.height);
  const dark=document.documentElement.dataset.theme==='dark';
  for(const p of points){const scale=1+p.z*.14,pulse=(Math.sin(p.phase-time*2.2)+1)/2,alpha=.16+(p.z+1)*.27+pulse*.15;ctx!.beginPath();ctx!.arc(72+p.x*49*scale,72+p.y*49*scale,1.1+(p.z+1)*.45,0,Math.PI*2);ctx!.fillStyle=`rgba(${dark?'126,167,255':'31,97,221'},${Math.min(1,alpha)})`;ctx!.fill();}
  orbAnimId=orbMotion.matches?null:requestAnimationFrame(render);
 }
 render(started);
}
function stopThinkingOrb() {
 if(orbAnimId!==null)cancelAnimationFrame(orbAnimId);orbAnimId=null;
 const container=$('chatThinkingOrb');if(container)container.hidden=true;
}
orbMotion.addEventListener('change',()=>{if(!$('chatThinkingOrb').hidden)startThinkingOrb();if(crowdWanted)startLoginCrowd();});
// Native canvas adaptation of Skiper UI skiper39 (Open Peeps), only while real startup runs.
let crowdAnimId:number|null=null,crowdGeneration=0,crowdWanted=false;
function startLoginCrowd() {
 stopLoginCrowd();crowdWanted=true;const current=crowdGeneration;
 const canvas=$('loginCrowdCanvas'),ctx=canvas.getContext('2d'),image=new Image();if(!ctx)return;
 image.onload=()=>{
  if(current!==crowdGeneration || !crowdWanted || $('loginTransitionLoader').hidden)return;
  const sw=image.naturalWidth/15,sh=image.naturalHeight/7,started=performance.now();
  function render(now:number){
   if(current!==crowdGeneration || !crowdWanted || $('loginTransitionLoader').hidden){crowdAnimId=null;return;}
   const time=orbMotion.matches?0:(now-started)/1000;ctx!.clearRect(0,0,900,280);
   for(let i=0;i<12;i++){const h=138+(i%4)*20,w=sw/sh*h,x=((i*89+time*(18+(i%3)*7))%1080)-100,y=280-h-8-Math.abs(Math.sin(time*5+i))*4,index=(i*7+3)%105;ctx!.drawImage(image,(index%15)*sw,Math.floor(index/15)*sh,sw,sh,x,y,w,h);}
   crowdAnimId=orbMotion.matches?null:requestAnimationFrame(render);
  }
  render(started);
 };
 image.src='/assets/crowd.png';
}
function stopLoginCrowd(){crowdWanted=false;crowdGeneration++;if(crowdAnimId!==null)cancelAnimationFrame(crowdAnimId);crowdAnimId=null;}
document.addEventListener('workspace-auth-transition',event=>{const detail=(event as CustomEvent<{active:boolean}>).detail;if(detail?.active&&!$('loginTransitionLoader').hidden)startLoginCrowd();else stopLoginCrowd();});
$('loginTransitionRetry').onclick=()=>location.reload();
let sending = false;
$('chatForm').onsubmit = async event => {
  event.preventDefault(); if(currentView==='annotation'){if(trackingWanted || !reviewVideo.paused)await pauseReview();if(!(await persistReview(false)))return;} let message=$('chatInput').value.trim(); if(currentView==='annotation' && !/\b(detik|second|menit|minute)\b/i.test(message) && /(berapa|jumlah|siapa)/i.test(message)) message+=` pada detik ${(reviewFrame/summary!.fps).toFixed(2)}`; if (!message || sending) return;
  sending=true; syncControls(); const current=generation; $('sendChat').disabled=true; $('clearChat').disabled=true; $('historySelect').disabled=true; showError('chatError','');
  addMessage('user',message); $('chatInput').value=''; $('chatStatus').textContent='AI sedang menyiapkan jawaban…';
  startThinkingOrb();
  try {
    const data=await api<ChatReply>('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,device:$('deviceMode').value,job_id:summary ? job!.id : null,history:chatHistory.slice(-6)})});
    if (current!==generation) return;
    const label=data.mode==='reviewed' ? 'Hitungan AI + koreksi pengguna' : data.mode==='facts' ? 'Data analisis AI tersimpan' : data.mode==='manual' ? 'Koreksi manual pengguna' : data.mode==='guide' ? 'Panduan kemampuan aplikasi' : `${data.mode==='lora' ? 'Qwen lokal + LoRA pilot' : 'Qwen lokal · base model'} · ${data.seconds} detik${data.device ? ' · '+(data.device.startsWith('cuda') ? 'GPU' : 'CPU') : ''}`;
    addMessage('assistant',data.answer,label+(data.truncated ? ' · batas panjang respons tercapai' : ''),data.evidence); chatHistory.push({role:'user',content:message},{role:'assistant',content:data.answer.slice(0,2000)}); chatHistory=chatHistory.slice(-6);
  } catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason)); showError('chatError',error.message); }
  finally { sending=false; $('sendChat').disabled=false; $('clearChat').disabled=false; syncControls(); $('chatStatus').textContent=''; stopThinkingOrb(); }
};
$('chatInput').addEventListener('keydown',event => { if (event.key==='Enter' && !event.shiftKey) {event.preventDefault(); $('chatForm').requestSubmit();} });
for (const button of document.querySelectorAll<HTMLButtonElement>('[data-question]')) button.onclick = () => { $('chatInput').value=button.dataset.question||''; $('chatForm').requestSubmit(); };
const manualNames:Record<string,string>={...objectNames,Hardhat:'Helm','NO-Hardhat':'Kepala tanpa helm'};
const labelColors:Record<string,string>={person:'#0f766e',car:'#2563eb',bus:'#7c3aed',truck:'#c2410c',motorcycle:'#0369a1',bicycle:'#a16207',Hardhat:'#15803d','NO-Hardhat':'#dc2626'};
function automaticColor(label:string) {
  const palette=['#0f766e','#2563eb','#7c3aed','#c2410c','#0369a1','#a16207'];
  let hash=0; for(const char of label) hash=(hash*31+char.charCodeAt(0))>>>0;
  return labelColors[label] || palette[hash%palette.length];
}
let reviewData:Review={revision:0,frames:[]}, reviewBoxes:Box[]=[], reviewFrame=0, reviewDirty=false, reviewBusy=false, reviewReady=false, editBox=-1, unsavedAdds:Box[]=[], reviewBaseline:Box[]=[];
const reviewSvg=$('reviewSvg'); let dragStart:[number,number]|null=null, dragBox:Box|null=null, pointerDown=false, secondClick=false;
function boxMetadata() {
  const label=$('reviewLabel').value==='__custom__' ? $('customLabel').value.trim() : $('reviewLabel').value;
  const name=$('reviewName').value.trim();
  if(!/^[A-Za-z][A-Za-z0-9_-]{0,39}$/.test(label)) throw new Error('Isi label: huruf, angka, _ atau -, maksimal 40 karakter.');
  if(name.length>60 || /[\x00-\x1f\x7f]/.test(name)) throw new Error('Nama maksimal 60 karakter tanpa karakter kontrol.');
  return {label,name:name || null,color:$('reviewColorMode').value==='custom' ? $('reviewColor').value : null};
}
function syncMetadata() {
  $('customLabelField').hidden=$('reviewLabel').value!=='__custom__';
  const label=$('reviewLabel').value==='__custom__' ? $('customLabel').value.trim() : $('reviewLabel').value;
  $('reviewColor').disabled=reviewBusy || $('reviewColorMode').value!=='custom';
  if($('reviewColorMode').value==='auto') $('reviewColor').value=automaticColor(label);
  if(dragBox) {try {Object.assign(dragBox,boxMetadata());} catch {} drawManualBoxes();}
}
for(const id of ['reviewLabel','customLabel','reviewName','reviewColorMode','reviewColor'] as const) $(id).addEventListener('input',syncMetadata);
function reviewBusyState(value:boolean) {
  reviewBusy=value; for(const button of $('reviewQueue').querySelectorAll('button'))button.disabled=value; $('nextPending').disabled=value; for(const button of $('boxList').querySelectorAll('button')) button.disabled=value;
  for(const id of ['reviewControls','boxControls','metadataControls'] as const) $(id).disabled=value;
  for(const id of ['saveReview','reloadReview','exportDataset','exportCorrectedVideo','closeReview','suggestBoxes','reviewGroup','applyBoxButton','cancelEditButton','reviewPlayback','reviewTimeline','learnDetector'] as const) $(id).disabled=value;
  syncMetadata(); syncControls();
}
function cancelDrawing() {
  dragStart=null; dragBox=null; pointerDown=false; secondClick=false; editBox=-1;
  $('addManualBox').textContent='Tambah kotak'; $('editActions').hidden=true;
  $('drawingStatus').textContent='Tarik kotak atau klik dua titik.';
  drawManualBoxes();
}
function renderReviewOverlay(boxes:Box[]) {
 studioViews.overlay(boxes.map((box,i)=>({bbox:box.bbox,color:box.color||automaticColor(box.label),selected:i===editBox,text:`${box.track_id?(box.source==='prompt_tracker'?'T':'#')+box.track_id:i+1}: ${manualNames[box.label]||box.label}${box.name?' · '+box.name:''}`})));
}
function drawManualBoxes() {
  renderReviewOverlay([...reviewBoxes,...(dragBox ? [dragBox] : [])]);
  studioViews.boxes(reviewBoxes.map((box,i)=>({text:`${i+1} · ${manualNames[box.label]||box.label}${box.name?' / '+box.name:''}`,color:box.color||automaticColor(box.label),disabled:reviewBusy,edit:()=>{
      cancelDrawing(); editBox=i; const [x1,y1,x2,y2]=box.bbox;
      $('reviewLabel').value=Array.from($('reviewLabel').options).some(o=>o.value===box.label) ? box.label : '__custom__'; $('customLabel').value=box.label;
      $('reviewName').value=box.name || ''; $('reviewColorMode').value=box.color ? 'custom' : 'auto';
      $('reviewColor').value=box.color || automaticColor(box.label); syncMetadata();
      for(const [id,v] of [['boxX',x1],['boxY',y1],['boxW',x2-x1],['boxH',y2-y1]] as const) $(id).value=(100*v).toFixed(4);
      $('addManualBox').textContent='Perbarui kotak'; $('editActions').hidden=false;
      $('drawingStatus').textContent=`Mengedit kotak ${i+1}. Terapkan perubahan atau klik kanan/Escape untuk batal.`;
      drawManualBoxes(); $('reviewLabel').focus();
    },remove:()=>{const removed=reviewBoxes.splice(i,1)[0];unsavedAdds=unsavedAdds.filter(item=>item!==removed);reviewDirty=true;cancelDrawing();}})));
  const kinds=[...new Set(reviewBoxes.map(b=>b.label))];
  $('reviewCounts').textContent=`${reviewBoxes.length} kotak${kinds.length ? ' · '+kinds.map(k=>`${reviewBoxes.filter(b=>b.label===k).length} ${(manualNames[k] || k).toLowerCase()}`).join(' · ') : ''}${reviewDirty ? ' · belum disimpan' : ''}`;
}
function cancelInteraction() {
  if(!dragStart && editBox<0 && unsavedAdds.length) {
    const box=unsavedAdds.pop(), at=reviewBoxes.indexOf(box!);
    if(at>=0) {
      reviewBoxes.splice(at,1);
      reviewDirty=JSON.stringify(reviewBoxes)!==JSON.stringify(reviewBaseline);
    }
  }
  cancelDrawing();
}
const reviewVideo=$('reviewVideo');
for(const button of document.querySelectorAll<HTMLButtonElement>('[data-label]')) button.onclick=()=>{$('reviewLabel').value=button.dataset.label||'';syncMetadata();};
reviewVideo.ontimeupdate=()=>{$('reviewTimeline').value=String(reviewVideo.currentTime); $('reviewPlayTime').textContent=timestamp(reviewVideo.currentTime);};
let reviewPlaybackEpoch=0, trackingSession:string|null=null, trackingJob:string|null=null, trackingFrames=new Map<number,Frame>(), trackingCursor=0, trackingEnd=false, trackingWanted=false, trackingBuffering=false, trackingFetch:Promise<TrackingStep>|null=null, analyzedFrames=new Map<number,Frame>(), overlayJob:string|null=null, trackingSuppressed=new Set<number|undefined>(), savedTrackingFrames=new Map<number,Frame>(), trackingRevision=0;
function currentReviewFrame() {return Math.min(summary!.frames-1,Math.floor(reviewVideo.currentTime*summary!.fps+.0001));}
function overlap(a:Box['bbox'],b:Box['bbox']) {
  const w=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0])), h=Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));
  return w*h/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-w*h || 1);
}
function overlayAt(index:number):Frame|undefined {
  const row=(trackingWanted && trackingJob===job!.id ? trackingFrames.get(index) : null) || savedTrackingFrames.get(index);
  if(row?.merged)return row;
  const prompts=row?.boxes || [], detected=(analyzedFrames.get(index)?.boxes || []).filter(b=>!row || !trackingSuppressed.has(b.track_id));
  return row ? {frame_index:index,boxes:[...prompts,...detected.filter(b=>!prompts.some(p=>p.label===b.label && overlap(p.bbox,b.bbox)>.3))],lost:row.lost} : analyzedFrames.get(index);
}
function lostTracks(row:Frame|undefined|null) {return (row?.lost || []).map(b=>`T${b.track_id} ${b.name || manualNames[b.label] || b.label}`).join(', ');}
async function stopReviewTracking() {
  trackingWanted=false; trackingBuffering=false; ++reviewPlaybackEpoch;
  const id=trackingSession, owner=trackingJob; trackingSession=null; trackingFetch=null;
  if(id) {try {await api<Record<string,unknown>>(`/api/jobs/${owner}/tracking/${id}/stop`,{method:'POST'});} catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}}
}
async function pauseReview() {
  trackingWanted=false; trackingBuffering=false; ++reviewPlaybackEpoch; reviewVideo.pause();
  await loadManualFrame(currentReviewFrame());
}
async function prefetchTracking(epoch:number) {
  if(trackingFetch || !trackingSession || !trackingWanted || trackingEnd || trackingCursor>=currentReviewFrame()+20)return;
  const id=trackingSession;
  const pending=trackingFetch=api<TrackingStep>(`/api/jobs/${job!.id}/tracking/${id}/step`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({after_frame:trackingCursor,count:10})});
  try {
    const data=await pending;
    if(epoch!==reviewPlaybackEpoch || id!==trackingSession)return;
    for(const row of data.frames)trackingFrames.set(row.frame_index,row);
    if(Number.isInteger(data.revision))trackingRevision=data.revision;
    trackingCursor=data.next_frame; trackingEnd=data.ended || trackingCursor>=summary!.frames-1;
    if(trackingWanted && trackingBuffering && reviewVideo.paused && trackingFrames.has(currentReviewFrame())) {
      trackingBuffering=false; $('drawingStatus').textContent='Mengikuti kotak · jeda untuk koreksi.';
      await reviewVideo.play(); scheduleTrackingPaint(epoch);
    }
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));
    if(epoch===reviewPlaybackEpoch) {trackingWanted=false;reviewVideo.pause();showError('reviewError','Tracker berhenti. '+error.message);await loadManualFrame(currentReviewFrame());}
  }finally{if(trackingFetch===pending)trackingFetch=null;}
  if(epoch===reviewPlaybackEpoch && trackingWanted)prefetchTracking(epoch);
}
function scheduleTrackingPaint(epoch:number) {
  const paint=(_now:number,metadata?:VideoFrameCallbackMetadata)=>{
    if(epoch!==reviewPlaybackEpoch || !trackingWanted || currentView!=='annotation')return;
    const index=Math.min(summary!.frames-1,Math.floor((metadata?.mediaTime ?? reviewVideo.currentTime)*summary!.fps+.0001)), row=overlayAt(index);
    if(!trackingFrames.has(index)) {
      trackingBuffering=true;reviewVideo.pause();renderReviewOverlay([]);if(trackingEnd){trackingWanted=false;showError('reviewError','Tracker sudah mencapai akhir video.');loadManualFrame(index);return;}$('drawingStatus').textContent='Menunggu tracker; video dijeda agar kotak tetap selaras.';prefetchTracking(epoch);return;
    }
    renderReviewOverlay(row!.boxes);
    $('reviewCounts').textContent=`${row!.boxes.length} kotak diikuti${row!.lost?.length ? ' · '+'hilang: '+lostTracks(row)+'; jeda dan tandai ulang' : ''}`;
    prefetchTracking(epoch);
    if(!reviewVideo.paused)scheduleTrackingPaint(epoch);
  };
  if(reviewVideo.requestVideoFrameCallback)reviewVideo.requestVideoFrameCallback(paint);
  else requestAnimationFrame(paint);
}
reviewVideo.onpause=()=>{$('reviewPlayback').textContent=trackingWanted ? 'Jeda & anotasi' : 'Putar & ikuti kotak';};
reviewVideo.onended=()=>{if(trackingWanted)pauseReview();};
$('reviewPlayback').onclick=async()=>{
  if(reviewBusy)return;
  if(trackingWanted || !reviewVideo.paused) {await pauseReview();return;}
  if((reviewVideo.ended || reviewFrame>=summary!.frames-1) && !(await loadManualFrame(0)))return;
  if(!(await persistReview(false)))return;
  await stopReviewTracking();
  const epoch=++reviewPlaybackEpoch; reviewBusyState(true); showError('reviewError','');
  try {
    const unchanged=new Set(reviewBoxes.filter(b=>b.source==='detector').map(b=>b.track_id));
    trackingSuppressed=new Set((analyzedFrames.get(reviewFrame)?.boxes || []).filter(b=>b.track_id!=null && !unchanged.has(b.track_id)).map(b=>b.track_id));
    const data=await api<TrackingStart>(`/api/jobs/${job!.id}/tracking`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame_index:reviewFrame,boxes:analyzedFrames.size ? reviewBoxes.filter(b=>b.source!=='detector') : reviewBoxes,revision:trackingRevision,suppressed_ids:[...trackingSuppressed]})});
    if(epoch!==reviewPlaybackEpoch)return;
    trackingRevision=data.revision;
    trackingSession=data.id;trackingJob=job!.id;trackingFrames=new Map([[reviewFrame,data.frame]]);trackingCursor=reviewFrame;trackingEnd=reviewFrame>=summary!.frames-1;trackingWanted=true;trackingBuffering=false;
    reviewReady=false;cancelDrawing();reviewSvg.removeAttribute('hidden');
    await prefetchTracking(epoch);
    if(epoch!==reviewPlaybackEpoch || !trackingWanted)return;
    await reviewVideo.play();scheduleTrackingPaint(epoch);
    $('reviewStatus').textContent='Tracking koreksi otomatis tersimpan saat frame disiapkan. Jeda untuk ekspor video; kotak masih perlu diperiksa sebelum masuk dataset.';
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));if(epoch!==reviewPlaybackEpoch || error.name==='AbortError')return;trackingWanted=false;showError('reviewError',error.message);await stopReviewTracking();}
  finally {
    reviewBusyState(false);
    if(trackingWanted){for(const id of ['metadataControls','boxControls','reviewControls','saveReview','suggestBoxes','reloadReview','exportDataset','exportCorrectedVideo','learnDetector'] as const)$(id).disabled=true;for(const button of $('boxList').querySelectorAll('button'))button.disabled=true;$('reviewPlayback').textContent='Jeda & anotasi';$('drawingStatus').textContent='Mengikuti kotak · jeda untuk koreksi.';}
    else reviewReady=true;
  }
};
$('reviewTimeline').onchange=async()=>{
  if(reviewBusy)return;
  const index=Math.min(summary!.frames-1,Math.round(Number($('reviewTimeline').value)*summary!.fps));
  if(!(await persistReview(false))) {$('reviewTimeline').value=String(reviewFrame/summary!.fps);return;}
  await loadManualFrame(index);
};
$('applyBoxButton').onclick=()=>{if(editBox<0)return; try {commitManualBox({...boxMetadata(),bbox:[...reviewBoxes[editBox].bbox]});} catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}};
$('cancelEditButton').onclick=cancelDrawing;
async function loadManualFrame(index:number,discard=false) {
  if (!summary || reviewBusy) return;
  if (!discard && !(await persistReview(false))) return;
  if (!Number.isInteger(index) || index<0 || index>=summary!.frames) {showError('reviewError','Frame di luar video.'); return;}
  reviewBusyState(true); reviewReady=false; showError('reviewError',''); $('reviewStatus').textContent='Memuat frame dan koreksi tersimpan…'; $('reviewStage').hidden=true;
  try {
    await stopReviewTracking(); reviewVideo.pause();
    if(overlayJob!==job!.id){const data=await api<Review>(`/api/jobs/${job!.id}/overlays`);analyzedFrames=new Map(data.frames.map(f=>[f.frame_index,f]));overlayJob=job!.id;trackingSuppressed=new Set();}
    const corrections=await api<Review>(`/api/jobs/${job!.id}/corrections`);
    savedTrackingFrames=new Map(corrections.frames.map(f=>[f.frame_index,f]));trackingRevision=corrections.revision;
    reviewData=await api<Review>(`/api/jobs/${job!.id}/annotations`); reviewFrame=index;
    if(reviewVideo.getAttribute('src')!==mediaUrl('original.mp4')) {
      await new Promise<void>((resolve,reject)=>{reviewVideo.onloadedmetadata=()=>resolve(); reviewVideo.onerror=()=>reject(new Error('Video anotasi gagal dimuat.')); reviewVideo.src=mediaUrl('original.mp4');});
    }
    $('reviewStage').style.setProperty('--video-ratio',String(reviewVideo.videoWidth/reviewVideo.videoHeight));
    const at=index/summary!.fps;
    if(Math.abs(reviewVideo.currentTime-at)>.001 || reviewVideo.seeking) {
      await new Promise<void>((resolve,reject)=>{
        const timer=setTimeout(()=>{cleanup();reject(new Error('Video belum selesai berpindah posisi. Coba kembali.'));},10000);
        const cleanup=()=>{clearTimeout(timer);reviewVideo.removeEventListener('seeked',done);reviewVideo.removeEventListener('error',failed);};
        const done=()=>{cleanup();resolve();}, failed=()=>{cleanup();reject(new Error('Video anotasi gagal dibaca.'));};
        reviewVideo.addEventListener('seeked',done);reviewVideo.addEventListener('error',failed);reviewVideo.currentTime=at;
      });
    }
    $('reviewTimeline').max=(summary!.duration-1/summary!.fps).toString(); $('reviewTimeline').value=(index/summary!.fps).toString();
    const saved=reviewData.frames.find(f=>f.frame_index===index);
    const predicted=overlayAt(index);
    reviewBoxes=(saved?.boxes || predicted?.boxes || []).map(b=>({...b,bbox:[...b.bbox]}));
    if(!saved && !predicted) {
      try {const suggested=await api<{boxes:Box[]}>(`/api/jobs/${job!.id}/suggestions/${index}?group=${$('reviewGroup').value}`);reviewBoxes=suggested.boxes;}
      catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message+' Anda tetap bisa menggambar kotak sendiri.');}
    }
    reviewBaseline=structuredClone(reviewBoxes);reviewDirty=false; unsavedAdds=[]; cancelDrawing(); $('reviewSeconds').value=(index/summary!.fps).toFixed(2); $('reviewSeconds').max=(summary!.duration-1/summary!.fps).toFixed(2);
    original.currentTime=index/summary!.fps; tracked.currentTime=original.currentTime; reviewReady=true; renderQueue(); $('reviewPlayback').textContent='Putar & ikuti kotak'; $('reviewStage').hidden=false; reviewSvg.toggleAttribute('hidden',false); drawManualBoxes();
    $('reviewStatus').textContent=`Frame ${index} · detik ${(index/summary!.fps).toFixed(2)} · ${saved ? 'koreksi tersimpan dimuat' : predicted?.lost?.length ? 'hilang: '+lostTracks(predicted)+'; tandai ulang' : predicted?.merged ? 'tracking tersimpan dimuat; periksa sebelum Simpan koreksi' : 'kotak AI/tracker sebagai saran; koreksi sebelum disimpan'}`;
    return true;
  } catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);} finally {reviewBusyState(false);}
}
$('openReview').onclick=()=>setView('annotation');
$('profileBack').onclick=async()=>{if(await setView(previousWorkspaceView))$('profileButton').focus();};
$('comparisonLayout').onchange=()=>{$('compare').dataset.layout=$('comparisonLayout').value;};
$('loadReviewFrame').onclick=()=>loadManualFrame(Math.round(Number($('reviewSeconds').value)*summary!.fps));
$('previousReviewFrame').onclick=()=>loadManualFrame(reviewFrame-1);
$('nextReviewFrame').onclick=()=>loadManualFrame(reviewFrame+1);
$('reloadReview').onclick=()=>loadManualFrame(reviewFrame,true);
window.addEventListener('beforeunload',event=>{if(reviewDirty){event.preventDefault();event.returnValue='';}});
$('closeReview').onclick=()=>setView('analysis');
$('fullscreenReview').onclick=async()=>{
  showError('reviewError','');
  try {
    if(document.fullscreenElement===$('reviewPanel')) await document.exitFullscreen();
    else await $('reviewPanel').requestFullscreen();
  }catch {showError('reviewError','Browser menolak layar penuh. Anotasi tetap bisa dipakai pada tampilan biasa.');}
};
document.addEventListener('fullscreenchange',()=>{
  const active=document.fullscreenElement===$('reviewPanel'), button=$('fullscreenReview');
  button.textContent=active ? 'Keluar layar penuh' : 'Layar penuh';
  button.setAttribute('aria-pressed',String(active));
  button.focus({preventScroll:true});
});
function commitManualBox(box:Box) {
  if (!reviewReady || reviewBusy) return;
  const [x1,y1,x2,y2]=box.bbox;
  if (!(0<=x1 && x1<x2 && x2<=1 && 0<=y1 && y1<y2 && y2<=1)) {showError('reviewError','Kotak harus mempunyai luas positif dan berada dalam gambar.');return;}
  if(editBox>=0) {const previous=reviewBoxes[editBox]; reviewBoxes[editBox]=box; unsavedAdds=unsavedAdds.map(b=>b===previous?box:b);}
  else if(reviewBoxes.length<100) {reviewBoxes.push(box); unsavedAdds.push(box);}
  else {showError('reviewError','Maksimal 100 kotak per frame.');return;}
  reviewDirty=true; showError('reviewError',''); cancelDrawing();
}
$('boxForm').onsubmit=e=>{
  e.preventDefault(); try {
    const x=Number($('boxX').value)/100,y=Number($('boxY').value)/100,w=Number($('boxW').value)/100,h=Number($('boxH').value)/100;
    commitManualBox({...boxMetadata(),bbox:[x,y,x+w,y+h]});
  } catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}
};
function pointerPosition(e:PointerEvent):[number,number] { const r=reviewSvg.getBoundingClientRect(); return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]; }
function previewBox(at:[number,number]):Box {return {...boxMetadata(),bbox:[Math.min(dragStart![0],at[0]),Math.min(dragStart![1],at[1]),Math.max(dragStart![0],at[0]),Math.max(dragStart![1],at[1])]};}
reviewSvg.onpointerdown=e=>{
  if(reviewBusy || !reviewReady || e.button!==0)return;
  e.preventDefault();
  try {boxMetadata();} catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);return;}
  if(!dragStart) {cancelDrawing(); dragStart=pointerPosition(e); secondClick=false;} else secondClick=true;
  pointerDown=true; reviewSvg.setPointerCapture(e.pointerId);
  $('drawingStatus').textContent='Pilih sudut kedua. Klik kanan/Escape untuk batal.';
};
reviewSvg.onpointermove=e=>{if(!dragStart)return; try {dragBox=previewBox(pointerPosition(e)); drawManualBoxes();} catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);cancelDrawing();}};
reviewSvg.onpointerup=e=>{
  if(!dragStart || !pointerDown || e.button!==0)return;
  pointerDown=false; const at=pointerPosition(e), r=reviewSvg.getBoundingClientRect();
  const moved=Math.hypot((at[0]-dragStart![0])*r.width,(at[1]-dragStart![1])*r.height)>5;
  if(secondClick || moved) {
    try {const box=previewBox(at); cancelDrawing(); commitManualBox(box);} catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);cancelDrawing();}
  }
};
reviewSvg.oncontextmenu=e=>{e.preventDefault(); if(!reviewBusy && reviewReady) cancelInteraction();};
reviewSvg.onpointercancel=cancelDrawing;
$('reviewPanel').addEventListener('keydown',e=>{if(e.key==='Escape' && !reviewBusy && reviewReady){e.preventDefault();cancelInteraction();}});
async function persistReview(learn:boolean) {
  if(reviewBusy) return false;
  if(!reviewReady) return !reviewDirty;
  try {
    if(editBox>=0) commitManualBox({...boxMetadata(),bbox:[...reviewBoxes[editBox].bbox]});
    if(dragBox) {const box=dragBox;cancelDrawing();commitManualBox(box);}
    else if(dragStart) cancelDrawing();
    if(!learn && !reviewDirty) return true;
    reviewBusyState(true);showError('reviewError','');
    const saved=reviewData.frames.find(f=>f.frame_index===reviewFrame), group=$('reviewGroup').value;
    reviewData=await api<Review>(`/api/jobs/${job!.id}/annotations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame_index:reviewFrame,revision:reviewData.revision,complete:learn ? group==='objects' || !!saved?.complete : false,helmets_complete:learn ? group==='helmets' || !!saved?.helmets_complete : false,learn_group:learn ? group : null,boxes:reviewBoxes})});
    reviewBaseline=structuredClone(reviewBoxes);reviewDirty=false;unsavedAdds=[];cancelDrawing();
    try {const data=await api<Job>(`/api/jobs/${job!.id}`);summary=data.summary;refreshCounts();}
    catch {showError('reviewError','Koreksi tersimpan, tetapi hitungan belum berhasil dimuat. Buka kembali rekaman untuk memperbaruinya.');}
    $('reviewStatus').textContent=learn ? 'Koreksi tersimpan. Hitungan pada posisi ini, puncak dashboard, dan ringkasan chat sudah diperbarui.' : 'Draft disimpan otomatis. Putar untuk mengikuti kotak; Simpan koreksi setelah posisi ini diperiksa.';
    return true;
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);return false;}
  finally{reviewBusyState(false);drawManualBoxes();}
}
$('saveReview').onclick=async()=>{
  if(!(await persistReview(true)))return;
  try {
    const queue=await refreshQueue();
    if(queue?.pending) learningStatus(`Koreksi tersimpan. ${queue.pending} posisi ${queue.group==='objects'?'objek':'helm'} belum disahkan. Training dimulai setelah antrean selesai.`);
    else {startExport(false); await startLearning(job!.id,$('reviewGroup').value);}
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}
};
$('learnDetector').onclick=async()=>{if(trackingWanted)await pauseReview();if(await persistReview(true))startLearning(job!.id,$('reviewGroup').value);};
$('suggestBoxes').onclick=async()=>{
  if(reviewBusy || !reviewReady)return;
  reviewBusyState(true);showError('reviewError','');
  try{
    const data=await api<{boxes:Box[]}>(`/api/jobs/${job!.id}/suggestions/${reviewFrame}?group=${$('reviewGroup').value}`);
    // Append only suggestions not already represented; saved/manual edits win.
    for(const box of data.boxes){
      const overlap=reviewBoxes.some(b=>b.label===box.label && b.bbox.every((n,i)=>Math.abs(n-box.bbox[i])<.03));
      if(!overlap && reviewBoxes.length<100){reviewBoxes.push(box);unsavedAdds.push(box);reviewDirty=true;}
    }
    cancelDrawing();$('reviewStatus').textContent='Kotak AI dapat diedit/dihapus. Lengkapi yang terlewat, lalu Simpan koreksi.';
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}finally{reviewBusyState(false);drawManualBoxes();}
};
$('exportDataset').onclick=async()=>{if(reviewDirty){showError('reviewError','Simpan koreksi terlebih dahulu.');return;} reviewBusyState(true); showError('reviewError',''); try{const response=await workspaceAuth.request(`/api/jobs/${job!.id}/dataset`); if(!response.ok){const data=await response.json();throw new Error(data.detail);} const url=URL.createObjectURL(await response.blob()), a=document.createElement('a'); a.href=url;a.download=`koreksi_${job!.id}.zip`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); $('reviewStatus').textContent='Dataset YOLO diekspor. Pisahkan train/val/test berdasarkan video sebelum training.';}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}finally{reviewBusyState(false);}};
let exportPoll:number|undefined,currentExport:{source:string;id:string}|null=null;
async function startExport(download=false) {
  if(!job || !summary || exporting)return;
  const source=job!.id, current=generation;
  exporting=true; syncResultSwitch();
  try {
    const data=await api<{id:string}>(`/api/jobs/${source}/exports`,{method:'POST'});
    currentExport={source,id:data.id};$('exportProgress').hidden=false;
    async function poll(){
      if(current!==generation)return;
      try {
        const state=await api<ExportState>(`/api/jobs/${source}/exports/${data.id}`);
        if(current!==generation)return;
        $('exportProgressBar').value=state.progress;$('exportStatus').textContent=state.message;
        $('cancelExport').hidden=!['queued','processing','cancelling'].includes(state.status);
        $('cancelExport').disabled=state.status==='cancelling';
        if(['queued','processing','cancelling'].includes(state.status)){exportPoll=setTimeout(poll,1000);return;}
        exporting=false; syncResultSwitch();
        if(state.status==='done'){
          $('correctedOption').disabled=false; $('correctedOption').dataset.url=state.media_url;
          if(download){const a=document.createElement('a');a.href=state.media_url;a.download=state.filename;a.click();}
          else {$('resultMode').value='corrections';switchResultMode();}
        }
      }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));if(current===generation){exporting=false; syncResultSwitch();$('exportStatus').textContent=error.message;}}
    }
    clearTimeout(exportPoll);await poll();
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));if(current===generation){exporting=false;syncResultSwitch();$('exportProgress').hidden=false;$('exportStatus').textContent=error.message;}}
}
$('exportCorrectedVideo').onclick=async()=>{if(reviewBusy || trackingWanted || !(await persistReview(false)))return;await startExport(true);};
$('cancelExport').onclick=async()=>{if(currentExport)try{await api<Record<string,unknown>>(`/api/jobs/${currentExport.source}/exports/${currentExport.id}/cancel`,{method:'POST'});}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));$('exportStatus').textContent=error.message;}};
function switchResultMode(){
  syncResultSwitch();
  if(!job || !summary)return;
  pauseComparison();const at=original.currentTime;
  tracked.src=$('resultMode').value==='corrections' ? ($('correctedOption').dataset.url||'') : mediaUrl('tracked.mp4');
  tracked.addEventListener('loadedmetadata',()=>{tracked.currentTime=Math.min(at,tracked.duration);},{once:true});
  $('comparisonBadge').textContent=$('resultMode').value==='corrections' ? 'Koreksi pengguna · belum bukti training' : (summary!.model_id ? 'Hasil kandidat fine-tuned' : 'Hasil detector awal');
}
$('resultMode').onchange=()=>{if($('resultMode').value==='corrections' && $('correctedOption').disabled){$('resultMode').value='ai';syncResultSwitch();startExport(false);}else switchResultMode();};
for(const id of ['resultAi','resultCorrections'] as const) $(id).onchange=()=>{if($(id).disabled || !$(id).checked)return;$('resultMode').value=$(id).value;$('resultMode').dispatchEvent(new Event('change'));};
$('prepareCorrections').onclick=()=>startExport(false);
let queueData:Queue|null=null;
async function refreshQueue(){
  if(!job || !summary)return null;
  const source=job!.id,group=$('reviewGroup').value;
  const data=await api<Queue>(`/api/jobs/${source}/review-queue?group=${group}`);
  if(job?.id!==source || $('reviewGroup').value!==group)return null;
  queueData=data;renderQueue();return data;
}
function renderQueue(){
  if(!queueData)return;
  $('queueStatus').textContent=`${queueData.reviewed}/${queueData.total} posisi disahkan · ${queueData.pending} perlu review`;
  studioViews.queue(queueData.positions.filter(row=>$('queueFilter').value==='all'||!row.reviewed).map(row=>({frame:row.frame_index,text:`${row.reviewed?'✓ ':''}${row.seconds.toFixed(1)}s · ${row.reasons.join(' · ')}`,disabled:reviewBusy,current:row.frame_index===reviewFrame,select:async()=>{try{if(trackingWanted)await pauseReview();await loadManualFrame(row.frame_index);}catch(reason:unknown){showError('reviewError',reason instanceof Error?reason.message:String(reason));}}})));

}
$('queueFilter').onchange=renderQueue;
$('nextPending').onclick=async()=>{if(trackingWanted)await pauseReview();const data=await refreshQueue(),pending=data?.positions.filter(r=>!r.reviewed);if(pending?.length)await loadManualFrame((pending.find(r=>r.frame_index>reviewFrame)||pending[0]).frame_index);};
$('reviewGroup').onchange=async()=>{try{await refreshQueue();}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('reviewError',error.message);}};
$('retryJob').onclick=async()=>{try{const data=await api<{id:string}>(`/api/jobs/${job!.id}/retry`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_id:job!.model_id || '',device:$('deviceMode').value})});await refreshHistory(data.id);await selectJob(data.id);}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('uploadError',error.message);}};
$('cancelJob').onclick=async()=>{try{await api<Record<string,unknown>>(`/api/jobs/${job!.id}/cancel`,{method:'POST'});}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('uploadError',error.message);}};
const themeMedia=matchMedia('(prefers-color-scheme: dark)');
try {$('themeSelect').value=localStorage.getItem('video-theme') || 'system';} catch {}
function applyTheme() {
 const choice=$('themeSelect').value,dark=choice==='system'?themeMedia.matches:choice==='dark';
 document.documentElement.dataset.theme=dark?'dark':'light';
 $('themeToggleBtn').setAttribute('aria-checked',String(dark));
 try {localStorage.setItem('video-theme',choice);} catch {}
}
function revealTheme() {
 if(!document.dispatchEvent){applyTheme();return;}
 const event=new CustomEvent('workspace-theme',{cancelable:true,detail:applyTheme});
 if(document.dispatchEvent(event))applyTheme();
}
$('themeSelect').onchange=revealTheme;themeMedia.addEventListener('change',()=>{if($('themeSelect').value==='system')applyTheme();});applyTheme();
$('themeToggleBtn').onclick=()=>{$('themeSelect').value=document.documentElement.dataset.theme==='dark'?'light':'dark';revealTheme();};
let trainingPoll:number|undefined;
async function refreshTraining(resume=true) {
  const current=generation;
  const selected=$('analysisModel').value, jobs=await apiList('/api/training');
  if(current!==generation)return;
  studioViews.options('analysisModel',[{value:'',text:'YOLO dasar · pretrained'},...jobs.filter(item=>item.status==='done').map(item=>({value:item.id,text:`${item.group==='objects'?'Objek':'Helm'} · ${item.id.slice(0,6)} · hasil koreksi`}))]);
  if(Array.from($('analysisModel').options).some(o=>o.value===selected)) $('analysisModel').value=selected;
  const active=jobs.find(j=>j.followup_job_id && ['queued','processing','cancelling'].includes(j.status));
  if(active && resume) pollTraining(active.id);
}
function learningStatus(message:string,progress=0){$('learningProgress').hidden=false;$('learningProgressBar').value=progress;$('learningStatus').textContent=message;}
async function startLearning(source:string,group:string){
  const current=generation;
  try{
    $('showLearnedResult').hidden=true;
    const data=await api<LearnReply>(`/api/jobs/${source}/learn`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group,device:$('deviceMode').value})});
    if(current!==generation)return;
    if(data.status==='waiting'){learningStatus(data.message);return;}
    pollTraining(data.id,data.result_job_id);
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));learningStatus('Koreksi tersimpan. '+error.message+' Klik Coba belajar lagi untuk mencoba kembali.');}
}
async function pollTraining(id:string,resultJobId:string|null=null,current=generation){
  if(current!==generation)return;clearTimeout(trainingPoll);
  try{
    const data=await api<TrainingJob>('/api/training/'+id);if(current!==generation)return;learningStatus(data.message,data.progress);
    $('cancelLearning').hidden=!['queued','processing','cancelling'].includes(data.status);$('cancelLearning').disabled=data.status==='cancelling';$('cancelLearning').onclick=async()=>{try{await api<TrainingJob>('/api/training/'+id+'/cancel',{method:'POST'});}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));learningStatus(error.message);}};
    if(['queued','processing','cancelling'].includes(data.status)){trainingPoll=setTimeout(()=>pollTraining(id,resultJobId,current),1500);return;}
    if(['error','cancelled'].includes(data.status)){learningStatus(data.message);$('cancelLearning').hidden=true;return;}
    $('cancelLearning').hidden=true;await refreshTraining(false);if(current!==generation)return;
    if(resultJobId || data.result_job_id){
      const result=await api<Job>('/api/jobs/'+(resultJobId || data.result_job_id));
      if(['queued','processing','cancelling'].includes(result.status)){learningStatus('Belajar selesai. '+result.message,result.progress);trainingPoll=setTimeout(()=>pollTraining(id,resultJobId,current),1500);return;}
      if(current!==generation)return;
      learningStatus(result.status==='done' ? 'Belajar dan analisis ulang selesai. Hasil baru siap dilihat; koreksi tetap bisa ditanya.' : result.message,100);
      $('showLearnedResult').hidden=result.status!=='done';$('showLearnedResult').onclick=async()=>{if(!(await persistReview(false)))return;await setView('analysis');await refreshHistory(result.id);await selectJob(result.id);};
      if(result.status==='done' && data.followup_job_id===job?.id && !reviewDirty && !reviewBusy && !trackingWanted && reviewVideo.paused && !sending){
        await setView('analysis');await refreshHistory(result.id);await selectJob(result.id);
        learningStatus(`Fine-tuning dan analisis ulang selesai · checkpoint ${data.checkpoint_sha256?.slice(0,12)}. Hasil baru sedang ditampilkan.`,100);
      }
    }
  }catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));learningStatus(error.message);}
}
$('analysisModel').onchange=()=>{$('modelHelp').textContent=$('analysisModel').value ? 'Kandidat pilot dipilih. Klik Analisis ulang untuk mencoba pada video ini.' : 'Model dasar dipilih. Hasil lama tetap tersimpan.';};
$('reanalyzeButton').onclick=async()=>{if(!job || !summary)return; showError('uploadError',''); try {const data=await api<{id:string}>(`/api/jobs/${job!.id}/reanalyze`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_id:$('analysisModel').value,device:$('deviceMode').value})});await setView('analysis');await refreshHistory(data.id);await selectJob(data.id);}catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason));showError('uploadError',error.message);}};
syncMetadata();
(async () => {
  await workspaceAuth.ready;
  try { const health=await api<Health>('/api/health'); $('systemStatus').textContent=health.vision_ready && health.chat_ready ? `Model lokal siap · ${health.device.startsWith('cuda') ? 'RTX / CUDA' : 'CPU'}${health.adapter_ready ? ' · LoRA' : ''}` : 'Model belum lengkap · lihat README'; await refreshTraining(); const jobs=await refreshHistory(); if (jobs.length) { const preferred=jobs.find(j=>['queued','processing','cancelling'].includes(j.status)) || jobs.find(j=>j.status==='done') || jobs[0]; $('historySelect').value=preferred.id; await selectJob(preferred.id); } await workspaceAuth.finishLoading(); }
  catch(reason:unknown) {const error=reason instanceof Error?reason:new Error(String(reason)); $('systemStatus').textContent='Server tidak terhubung'; showError('uploadError',error.message); workspaceAuth.finishLoading('Studio belum dapat dimuat. '+error.message); }
})();
