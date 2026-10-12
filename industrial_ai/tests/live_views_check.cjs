"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),{renderToStaticMarkup}=require('react-dom/server');
const nodes={},renders={},events=[];let created=0;
const node=id=>nodes[id]??={id,lastElementChild:{id:'last'},scrollHeight:40,scrollTop:0};
const compiled=require('esbuild').buildSync({entryPoints:['frontend/LiveViews.tsx'],bundle:true,platform:'node',format:'cjs',jsx:'automatic',packages:'external',write:false}).outputFiles[0].text;
const context={exports:{},Map,document:{getElementById:node,dispatchEvent:event=>events.push(event)},CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail;}},require(name){if(name==='react-dom/client')return {createRoot(container){created++;return {render(content){renders[container.id]=content;}};}};if(name==='react-dom')return {flushSync(fn){fn();}};return require(name);}};
context.module={exports:context.exports};vm.createContext(context);vm.runInContext(compiled,context);const views=context.module.exports.studioViews;
(async()=>{
 let seeks=0,edits=0,removes=0,selected=0;
 views.evidence([{key:1,href:'/api/jobs/job/media/image.jpg',imageAlt:'Frame',title:'<script>unsafe</script>',detail:'Evidence',seek(){seeks++;}}]);
 let html=renderToStaticMarkup(renders.evidenceList);assert(html.includes('&lt;script&gt;unsafe&lt;/script&gt;'));assert(!html.includes('<script>'));renders.evidenceList[0].props.children[1].props.children[2].props.onClick();assert.equal(seeks,1);
 views.details([['Label','<img>']]);assert(renderToStaticMarkup(renders.resultDetails).includes('&lt;img&gt;'));
 views.appendMessage({role:'assistant',text:'Answer',detail:'Local',links:[{href:'/proof.jpg',text:'Proof'}]});views.appendMessage({role:'user',text:'Question',detail:'',links:[]});assert.equal(renders.messages.props.children[0].length,2);assert.equal(events.length,2);assert.equal(node('messages').scrollTop,40);const before=created;views.clearMessages();assert.equal(renders.messages,null);assert.equal(created,before,'reuse roots without replacing controller containers');
 views.overlay([{bbox:[.1,.2,.8,.9],color:'#123456',selected:true,text:'T1'}]);html=renderToStaticMarkup(renders.reviewSvg);assert(html.includes('vector-effect="non-scaling-stroke"'));assert(html.includes('stroke-width="3"'));assert(html.includes('T1'));
 views.boxes([{text:'Box',color:'#123456',disabled:false,edit(){edits++;},remove(){removes++;}}]);const box=renders.boxList[0].props.children;box[1].props.onClick();box[2].props.onClick();assert.equal(edits,1);assert.equal(removes,1);
 views.queue([{frame:2,text:'2s',disabled:false,current:true,async select(){selected++;}}]);renders.reviewQueue[0].props.onClick();await Promise.resolve();assert.equal(selected,1);assert(renderToStaticMarkup(renders.reviewQueue).includes('aria-current="true"'));
 views.options('historySelect',[{value:'job1',text:'Actual recording'}]);assert(renderToStaticMarkup(renders.historySelect).includes('value="job1"'));
 console.log('PASS: actual React live evidence/details/messages/SVG/box/queue/options, text escaping, callbacks and root reuse.');
})().catch(error=>{console.error(error);process.exitCode=1;});
