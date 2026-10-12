"use strict";
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('frontend/motion.ts', 'utf8');
const compiled = require('typescript').transpileModule(source, {compilerOptions:{target:7,module:1}}).outputText;
function fixture() {
 const docEvents={}, windowEvents={}, mediaEvents={}, instances=[], controls=[], reveals=[], wipes=[];
 const media={matches:false,addEventListener:(name,fn)=>mediaEvents[name]=fn};
 class Element {
  constructor(){this.id='root';this.scrollTop=0;this.scrollLeft=0;this.dataset={theme:'dark'};this.value='light';this.hidden=false;this.disabled=false;this.removed=[];this.style={removeProperty:name=>this.removed.push(name)};this.classes=new Set();this.classList={contains:name=>this.classes.has(name),add:name=>this.classes.add(name),remove:name=>this.classes.delete(name)};}
  getClientRects(){return this.hidden?[]:[{}];}
  getBoundingClientRect(){return {left:900,top:20,width:60,height:32};}
  setAttribute(name,value){this[name]=value;}
  removeAttribute(name){delete this[name];}
  querySelectorAll(){return [];}
  cloneNode(){return new Element();}
  append(element){this.child=element;if(this===body)wipes.push(element);}
  remove(){this.detached=true;}
  animate(keys,options){let resolve,reject;const finished=new Promise((yes,no)=>{resolve=yes;reject=no;});finished.catch(()=>{});const result={keys,options,finished,cancelled:false,finish:resolve,cancel(){this.cancelled=true;reject(Error('cancelled'));}};reveals.push(result);return result;}
 }
 const root=new Element(),body=new Element(),heading=new Element(),bar=new Element(),toggle=new Element(),select=new Element(),profile=new Element();profile.hidden=true;body.classes.add('signed-out');
 const nodes={root:new Element(),themeToggleBtn:toggle,themeSelect:select,profilePane:profile};
 let modal=false,mutation;
 const document={createElement:()=>new Element(),body,documentElement:root,fullscreenElement:null,visibilityState:'visible',getElementById:id=>nodes[id],querySelector:()=>modal?{}:null,querySelectorAll:()=>[heading,bar],addEventListener:(name,fn)=>docEvents[name]=fn};
 const context={exports:{},console,getComputedStyle:()=>({position:'static',color:'#182133',getPropertyValue:()=>root.dataset.theme==='dark'?'#07090f':'#f5f7fa'}),HTMLInputElement:class extends Element{},HTMLTextAreaElement:class extends Element{},HTMLSelectElement:class extends Element{},HTMLCanvasElement:class extends Element{},HTMLVideoElement:class extends Element{},document,HTMLElement:Element,innerWidth:1000,innerHeight:700,matchMedia:()=>media,MutationObserver:class{constructor(fn){mutation=fn;}observe(){}},window:{scrollY:80,addEventListener:(name,fn)=>windowEvents[name]=fn},require(name){if(name==='lenis')return {default:class {constructor(options){this.options=options;this.actualScroll=200;this.resets=[];instances.push(this);}scrollTo(target,options){this.resets.push({target,options});}resize(){this.resized=true;}destroy(){this.destroyed=true;}}};return {animate(element,keys,options){const control={element,keys,options,stopped:false,then(fn){this.finish=fn;return Promise.resolve();},stop(){throw Error('stop() cannot commit styles on a hidden view');},cancel(){this.stopped=true;}};controls.push(control);return control;}};}};
 vm.createContext(context);vm.runInContext(compiled,context);
 return {context,document,docEvents,windowEvents,media,mediaEvents,instances,controls,reveals,wipes,root,body,toggle,select,heading,mutation:()=>mutation(),setModal(value){modal=value;}};
}
(async()=>{
 const hidden=fixture();hidden.body.classes.delete('signed-out');hidden.docEvents['workspace-ready']();hidden.heading.hidden=true;hidden.docEvents['workspace-view']();assert.equal(hidden.controls.length,3,'hidden heading is skipped while the visible bar animates');assert(hidden.controls[0].stopped,'old entrance is cancelled without committing styles to hidden DOM');
 const f=fixture();assert.equal(f.instances.length,0,'signed-out page keeps native scroll');
 f.body.classes.delete('signed-out');f.docEvents['workspace-ready']();assert.equal(f.instances.length,1);assert.equal(f.instances[0].options.autoRaf,true);assert.equal(f.controls.length,2);
 const scroller=f.instances[0],target=new f.context.HTMLElement();target.closest=()=>null;
 for(const deltaY of [300,300,-100,-100,120,-80])scroller.options.virtualScroll({deltaY,event:{type:'wheel',ctrlKey:false,target}});
 assert.equal(scroller.resets.length,3,'each direction reversal discards old target exactly once');assert(scroller.resets.every(x=>x.target===200&&x.options.immediate&&x.options.force));
 target.closest=()=>({});assert.equal(scroller.options.virtualScroll({deltaY:100,event:{type:'wheel',ctrlKey:false,target}}),false,'nested controls retain native scrolling');assert.equal(scroller.resets.length,3);
 const prior=f.controls[0];f.context.enter(f.heading);const latest=f.controls.at(-1);prior.finish();assert.equal(f.heading.removed.length,0,'stale entrance cannot clear the new animation');latest.finish();assert.deepEqual(f.heading.removed,['opacity','transform']);
 f.document.fullscreenElement={};f.docEvents.fullscreenchange();assert.equal(f.instances[0].destroyed,true,'fullscreen editor disables Lenis');f.document.fullscreenElement=null;f.docEvents.fullscreenchange();assert.equal(f.instances.length,2);
 f.setModal(true);f.docEvents.toggle();assert.equal(f.instances[1].destroyed,true,'modal disables page scroll');f.setModal(false);f.docEvents.toggle();assert.equal(f.instances.length,3);
 f.document.visibilityState='hidden';f.docEvents.visibilitychange();assert.equal(f.instances[2].destroyed,true);f.document.visibilityState='visible';f.docEvents.visibilitychange();assert.equal(f.instances.length,4);
 f.media.matches=true;f.mediaEvents.change();assert.equal(f.instances[3].destroyed,true);assert(f.controls.every(c=>c.stopped||c===latest));const count=f.controls.length;f.context.enter(f.heading);assert.equal(f.controls.length,count,'reduced motion has no entrance animation');
 let changes=0;await f.context.revealTheme(()=>changes++);assert.equal(changes,1);assert.equal(f.reveals.length,0,'reduced motion changes theme immediately');
 f.media.matches=false;
 const wipePending=f.context.revealTheme(()=>{changes++;f.root.dataset.theme='light';});
 assert.equal(changes,1,'unsupported browser waits for the circle before applying');assert.equal(f.root.dataset.theme,'dark','live theme stays unchanged during reveal');
 assert.equal(f.wipes.length,1);assert.equal(f.wipes[0].dataset.theme,'light','snapshot contains selected theme');assert.equal(f.wipes[0].inert,true);assert.equal(f.wipes[0]['aria-hidden'],'true');assert.equal(f.toggle.disabled,true);
 assert.equal(f.reveals[0].options.duration,900);assert.equal(f.reveals[0].keys.clipPath[0],'circle(0px at 930px 36px)');
 const wipeRadius=Number(f.reveals[0].keys.clipPath[1].match(/circle\(([^p]+)px/)[1]);assert(wipeRadius>=Math.hypot(930,664));
 await f.context.revealTheme(()=>changes++);assert.equal(f.wipes.length,1,'rapid clicks cannot stack theme snapshots');
 f.reveals[0].finish();await wipePending;assert.equal(changes,2);assert.equal(f.wipes[0].detached,true);assert.equal(f.toggle.disabled,false);assert.equal(f.select.disabled,false);assert.equal(f.root.classes.has('theme-reveal'),false);
 const changed=fixture();let changedApplied=0;const changedPending=changed.context.revealTheme(()=>changedApplied++);changed.docEvents.scroll();await changedPending;assert.equal(changedApplied,1);assert.equal(changed.wipes[0].detached,true,'scroll cancels a frozen snapshot without blocking new input');
 const resized=fixture();const resizedPending=resized.context.revealTheme(()=>{});resized.windowEvents.resize();await resizedPending;assert.equal(resized.toggle.disabled,false,'resize cannot leave theme locked');
 const cancelled=fixture();let cancelledChanges=0;const cancelledPending=cancelled.context.revealTheme(()=>cancelledChanges++);
 cancelled.media.matches=true;cancelled.mediaEvents.change();await cancelledPending;assert.equal(cancelledChanges,1,'reduced-motion cancellation still commits chosen theme');assert.equal(cancelled.wipes[0].detached,true);assert.equal(cancelled.toggle.disabled,false);
 const system=fixture();system.select.value='system';const systemPending=system.context.revealTheme(()=>{});assert.equal(system.wipes[0].dataset.theme,'light','system palette follows OS preference');system.windowEvents.pagehide();await systemPending;assert.equal(system.wipes[0].detached,true,'pagehide cleans up pending theme snapshot');
 const full=fixture();full.document.fullscreenElement={};let direct=0;await full.context.revealTheme(()=>direct++);assert.equal(direct,1);assert.equal(full.wipes.length,0,'fullscreen uses immediate theme without covering editor');
 const failed=fixture();failed.document.createElement=()=>{throw Error('snapshot unavailable');};let applied=0;await failed.context.revealTheme(()=>applied++);assert.equal(applied,1,'failed snapshot still commits selected theme');assert.equal(failed.toggle.disabled,false);
 const safe=fixture(),live=safe.document.getElementById('root'),copy=new safe.context.HTMLElement(),file=new safe.context.HTMLInputElement(),fileCopy=new safe.context.HTMLInputElement();
 file.type='file';file.id='videoFile';fileCopy.type='file';fileCopy.id='videoFile';Object.defineProperty(file,'value',{get:()=> 'C:/fakepath/clip.mp4'});let fileValue='';Object.defineProperty(fileCopy,'value',{set:value=>{assert.equal(value,'','selected file input must be empty in visual copy');fileValue=value;},get:()=>fileValue});
 live.querySelectorAll=()=>[file];copy.querySelectorAll=()=>[fileCopy];live.cloneNode=()=>copy;safe.context.themeSnapshot('light');assert.equal(fileValue,'');assert.equal(fileCopy.id,undefined,'visual copies cannot duplicate live IDs');assert.equal(fileCopy.dataset.snapshotId,'videoFile');
 const radios=fixture(),radioRoot=radios.document.getElementById('root'),radioClone=new radios.context.HTMLElement(),radio=new radios.context.HTMLInputElement(),radioCopy=new radios.context.HTMLInputElement();radio.type=radioCopy.type='radio';radio.name=radioCopy.name='resultView';radio.checked=true;radioRoot.querySelectorAll=()=>[radio];radioClone.querySelectorAll=()=>[radioCopy];radioRoot.cloneNode=()=>radioClone;radios.context.themeSnapshot('light');assert.equal(radioCopy.name,undefined,'snapshot radio cannot join live result group');assert.equal(radio.checked,true);assert.equal(radioCopy.checked,true);
 const geometry=fixture(),mediaRoot=geometry.document.getElementById('root'),mediaClone=new geometry.context.HTMLElement(),video=new geometry.context.HTMLVideoElement(),videoCopy=new geometry.context.HTMLVideoElement(),nested=new geometry.context.HTMLElement(),nestedCopy=new geometry.context.HTMLElement();
 video.id='originalVideo';videoCopy.id='originalVideo';video.readyState=2;video.videoWidth=1920;video.videoHeight=1080;nested.scrollTop=120;nested.scrollLeft=30;
 const mediaStyle={position:'static',width:'640px',height:'480px',objectFit:'contain',objectPosition:'50% 50%',backgroundColor:'#141518'};geometry.context.getComputedStyle=()=>mediaStyle;
 let frame;geometry.document.createElement=tag=>{const item=new geometry.context.HTMLElement();if(tag==='canvas'){frame=item;item.getContext=()=>({drawImage(){}});}return item;};videoCopy.replaceWith=item=>assert.equal(item,frame);
 Object.defineProperty(nestedCopy,'scrollTop',{set:value=>{assert.equal(geometry.wipes.length,1,'restore nested scroll only after snapshot is mounted');nestedCopy.savedTop=value;}});
 Object.defineProperty(nestedCopy,'scrollLeft',{set:value=>{assert.equal(geometry.wipes.length,1);nestedCopy.savedLeft=value;}});
 mediaRoot.querySelectorAll=()=>[video,nested];mediaClone.querySelectorAll=()=>[videoCopy,nestedCopy];mediaRoot.cloneNode=()=>mediaClone;geometry.context.themeSnapshot('light');
 assert.equal(frame.style.width,'640px');assert.equal(frame.style.height,'480px','widescreen frame preserves displayed 4/3 video pane');assert.equal(frame.style.objectFit,'contain');assert.equal(frame.style.display,'block');assert.equal(frame.dataset.snapshotId,'originalVideo');assert.equal(nestedCopy.savedTop,120);assert.equal(nestedCopy.savedLeft,30);
 f.media.matches=false;f.context.syncScroll();const last=f.instances.at(-1);f.windowEvents.pagehide();assert.equal(last.destroyed,true);f.windowEvents.pageshow();assert.equal(f.instances.length,6,'back-forward restoration creates one fresh Lenis');
 console.log('PASS: Lenis login/modal/fullscreen/visibility/reduced-motion lifecycle, Motion stale cleanup, real-UI circle geometry, rapid clicks, cancellation, pagehide, fullscreen and cleanup.');
})().catch(error=>{console.error(error);process.exitCode=1;});
