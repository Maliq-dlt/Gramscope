"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('dashboard.js','utf8');
function fixture(reduced=false){
 const nodes={},frames=new Map(),cancelled=[],listeners={},draws={dots:0,people:0,sprites:[]};let next=0;
 const transforms=[];
 const ctx={sx:1,tx:0,ty:0,save(){transforms.push([this.sx,this.tx,this.ty,this.globalAlpha]);},restore(){[this.sx,this.tx,this.ty,this.globalAlpha]=transforms.pop();},translate(x,y){this.tx+=x;this.ty+=y;},scale(x){this.sx*=x;},clearRect(){},beginPath(){},arc(){draws.dots++;},fill(){},setTransform(){this.sx=1;this.tx=0;this.ty=0;},drawImage(...args){draws.people++;draws.sprites.push({x:this.tx+this.sx*args[5]-(this.sx<0?args[7]:0),y:this.ty+args[6],w:args[7],h:args[8],ratio:args[3]/args[4],alpha:this.globalAlpha,mirrored:this.sx<0});}};
 const node=id=>nodes[id]??=(id.includes('Canvas')?{width:144,height:144,clientWidth:1440,clientHeight:480,getContext(){return ctx;}}:{hidden:true,value:'system',setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];},focus(){this.focused=true;}});
 const media={matches:reduced,addEventListener(name,fn){listeners[name]=fn;}};
 const context={Error,devicePixelRatio:2,$:node,document:{documentElement:{dataset:{theme:'light'}},addEventListener(name,fn){listeners[name]=fn;}},matchMedia(){return media;},performance:{now(){return 100;}},requestAnimationFrame(fn){frames.set(++next,fn);return next;},cancelAnimationFrame(id){cancelled.push(id);frames.delete(id);},Image:class{constructor(){this.naturalWidth=1500;this.naturalHeight=700;context.image=this;}set src(value){this.url=value;}},location:{reload(){context.reloaded=true;}},localStorage:{getItem(){return 'system';},setItem(k,v){context.saved=v;}}};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('let orbAnimId ='),source.indexOf('let sending = false;')),context);
 return {context,node,frames,cancelled,draws,media,listeners};
}
(async()=>{
 for(const reduced of [false,true]){
  const f=fixture(reduced);f.context.startThinkingOrb();assert.equal(f.node('chatThinkingOrb').hidden,false);assert(f.draws.dots>200);assert.equal(f.frames.size,reduced?0:1);
  f.media.matches=true;f.listeners.change();assert.equal(f.frames.size,0,'motion change cancels orb loop');f.context.stopThinkingOrb();assert.equal(f.node('chatThinkingOrb').hidden,true);
  f.node('loginTransitionLoader').hidden=false;f.context.startLoginCrowd();f.context.image.onload();assert.equal(f.draws.people,33);assert.equal(f.frames.size,0,'reduced crowd renders one frame');f.context.stopLoginCrowd();
 }
 const geometry=fixture();geometry.node('loginTransitionLoader').hidden=false;geometry.context.startLoginCrowd();geometry.context.image.onload();
 const canvas=geometry.node('loginCrowdCanvas'),first=geometry.draws.sprites.slice();
 assert.equal(canvas.width,2880);assert.equal(canvas.height,960);
 for(const sprite of first)assert(Math.abs(sprite.w/sprite.h-sprite.ratio)<1e-9,'canvas uses equal horizontal and vertical scale');
 for(const sprite of first.slice(21))assert(sprite.y+sprite.h*.87>=canvas.clientHeight,'front bodies reach past transparent sprite padding at bottom');
 assert(first[0].alpha<first[10].alpha&&first[10].alpha<first[21].alpha,'rear layers remain lighter');
 assert(first.slice(0,10).every(s=>!s.mirrored)&&first.slice(10,21).every(s=>s.mirrored)&&first.slice(21).every(s=>!s.mirrored),'only left-moving people face left; transforms never leak into other sprites');
 geometry.frames.values().next().value(2100);const second=geometry.draws.sprites.slice(33);
 assert(second[2].x>first[2].x&&second[12].x<first[12].x&&second[23].x>first[23].x,'layers move in both directions');
 canvas.clientWidth=702;canvas.clientHeight=388;geometry.frames.values().next().value(3100);
 assert.equal(canvas.width,1404);assert.equal(canvas.height,776,'canvas updates its backing dimensions on viewport resize');geometry.context.stopLoginCrowd();
 const moving=fixture();moving.node('loginTransitionLoader').hidden=false;moving.context.startLoginCrowd();moving.context.image.onload();assert.equal(moving.frames.size,1);moving.context.stopLoginCrowd();assert.equal(moving.frames.size,0);
 const late=fixture();late.node('loginTransitionLoader').hidden=false;late.context.startLoginCrowd();late.context.stopLoginCrowd();late.context.image.onload();assert.equal(late.draws.people,0,'stopped startup ignores late image even with visible error loader');assert.equal(late.frames.size,0);late.listeners.change();assert.equal(late.frames.size,0,'motion change cannot revive stopped crowd');
 const stale=fixture();stale.node('loginTransitionLoader').hidden=false;stale.context.startLoginCrowd();const oldImage=stale.context.image;stale.context.startLoginCrowd();oldImage.onload();assert.equal(stale.draws.people,0,'repeated start rejects stale image callback');stale.context.image.onload();assert.equal(stale.draws.people,33);assert.equal(stale.frames.size,1);stale.media.matches=true;stale.listeners.change();stale.context.image.onload();assert.equal(stale.frames.size,0,'active crowd switches to static reduced frame');stale.media.matches=false;stale.listeners.change();stale.context.image.onload();assert.equal(stale.frames.size,1,'active crowd resumes when reduced motion turns off');stale.context.stopLoginCrowd();assert.equal(stale.frames.size,0);
 const preference=fixture(true);preference.context.startThinkingOrb();assert.equal(preference.frames.size,0);preference.media.matches=false;preference.listeners.change();assert.equal(preference.frames.size,1,'static orb resumes when reduced motion turns off');preference.context.stopThinkingOrb();assert.equal(preference.frames.size,0);
 const authEvent=fixture();assert.equal(authEvent.draws.people,0);authEvent.node('loginTransitionLoader').hidden=false;authEvent.listeners['workspace-auth-transition']({detail:{active:true}});authEvent.context.image.onload();assert.equal(authEvent.draws.people,33);authEvent.listeners['workspace-auth-transition']({detail:{active:false}});assert.equal(authEvent.frames.size,0);authEvent.context.image.onload();assert.equal(authEvent.draws.people,33,'stopped explicit-auth crowd rejects stale callbacks');
 for(const fails of [false,true]){
  const f=fixture();let stopped=0,started=0,finished;
  Object.assign(f.context,{workspaceAuth:{ready:Promise.resolve(),finishLoading(error){finished=error||'success';f.listeners['workspace-auth-transition']({detail:{active:false}});}},startLoginCrowd(){started++;},stopLoginCrowd(){stopped++;},api:async()=>{if(fails)throw Error('offline');return {vision_ready:true,chat_ready:true,device:'cpu'};},refreshTraining:async()=>{},refreshHistory:async()=>[],showError(){}});
  const boot=source.slice(source.lastIndexOf('(async () => {'));await vm.runInContext(boot,f.context);
  assert.equal(started,0,'restored startup never starts crowd');assert.equal(stopped,1);assert.equal(finished,fails?'Studio belum dapat dimuat. offline':'success');
 }
 for(const outcome of ['success','error','stale']){
  const f=fixture();Object.assign(f.context,{studioViews:{thinking(){}},sending:false,currentView:'analysis',generation:1,summary:{frames:100,fps:10},job:{id:'recording1',status:'done'},chatHistory:[],uploading:false,reviewBusy:false,exporting:false,reviewVideo:{pause(){}},original:{currentTime:0},workspaceAuth:{resetPasswordForm(){}},persistReview:async()=>true,cancelDrawing(){},pauseComparison(){},stopReviewTracking:async()=>{},loadManualFrame:async()=>{},showError(){},messages:[],addMessage(role,text){f.context.messages.push({role,text});}});
  const nav=['analysis','evidence','annotation','ngram'].map(view=>({...f.node(view),dataset:{view}}));f.context.document.querySelectorAll=selector=>selector==='[data-view]'?nav:[];
  vm.runInContext(source.slice(source.indexOf('function syncResultSwitch()'),source.indexOf("for (const button of document.querySelectorAll('[data-view]'))\n    button.onclick")),f.context);
  let reply;f.context.api=async(_url,init)=>{const payload=JSON.parse(init.body);assert(Array.isArray(payload.history),'chat history contract preserved');assert.equal(payload.job_id,'recording1');assert.equal(payload.chatHistory,undefined);return new Promise((resolve,reject)=>reply=()=>outcome==='error'?reject(Error('chat failed')):resolve({mode:'guide',answer:'Answer',evidence:[]}));};
  vm.runInContext(source.slice(source.indexOf("$('chatForm').onsubmit ="),source.indexOf("$('chatInput').addEventListener('keydown'")),f.context);
  f.node('chatInput').value='Question';const pending=f.node('chatForm').onsubmit({preventDefault(){}});
  assert.equal(f.context.sending,true);assert.equal(f.node('historySelect').disabled,true);assert.equal(f.node('newVideoButton').disabled,true,'pending chat cannot change the recording');assert(nav.every(button=>!button.disabled));assert.equal(f.node('profileButton').disabled,false);
  for(const view of ['evidence','ngram','annotation','profile','analysis']){assert.equal(await f.context.setView(view),true,view);assert.equal(f.context.currentView,view);assert.equal(f.context.sending,true);assert.equal(f.context.generation,1,'view navigation preserves the pending recording');}
  for(const guard of ['uploading','reviewBusy']){f.context[guard]=true;assert.equal(await f.context.setView('ngram'),false,guard);f.context[guard]=false;}
  if(outcome==='stale')f.context.generation++;
  reply();await pending;
  assert.equal(f.context.messages.filter(m=>m.role==='assistant').length,outcome==='success'?1:0,'only a successful reply for the same recording is appended');
  assert.equal(f.context.chatHistory.length,outcome==='success'?2:0);
  assert.equal(f.node('historySelect').disabled,false);assert.equal(f.node('newVideoButton').disabled,false);
  assert.equal(f.node('chatThinkingOrb').hidden,true);assert.equal(f.frames.size,0,'chat finally clears RAF on success and failure');assert.equal(f.node('sendChat').disabled,false);assert.equal(f.node('chatStatus').textContent,'');
 }
 const theme=fixture();vm.runInContext(source.slice(source.indexOf('const themeMedia ='),source.indexOf('let trainingPoll')),theme.context);
 assert.equal(theme.context.document.documentElement.dataset.theme,'light');theme.node('themeToggleBtn').onclick();assert.equal(theme.context.document.documentElement.dataset.theme,'dark');assert.equal(theme.node('themeToggleBtn')['aria-checked'],'true');assert.equal(theme.context.saved,'dark');
 theme.node('themeSelect').value='system';theme.media.matches=true;theme.context.applyTheme();assert.equal(theme.context.document.documentElement.dataset.theme,'dark');theme.media.matches=false;theme.context.applyTheme();assert.equal(theme.context.document.documentElement.dataset.theme,'light');
 console.log('PASS: actual orb/crowd reduced motion and cleanup, startup success/error cleanup, theme switch/system state.');
})().catch(error=>{console.error(error);process.exitCode=1;});
