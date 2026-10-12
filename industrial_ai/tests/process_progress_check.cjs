"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),esbuild=require('esbuild'),ts=require('typescript'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const compiled=esbuild.buildSync({entryPoints:['frontend/ProcessProgress.tsx'],bundle:true,platform:'node',format:'cjs',jsx:'automatic',packages:'external',write:false}).outputFiles[0].text;
const mod={exports:{}};new Function('require','module','exports',compiled)(require,mod,mod.exports);
const {processStage,ProcessProgress}=mod.exports;
const state=(kind,status,value)=>({kind,status,value});
for(const [input,stage] of [[state('upload','uploading',50),0],[state('upload','validating',null),1],[state('analysis','queued',0),1],[state('analysis','processing',2),1],[state('analysis','processing',5),2],[state('analysis','processing',90),2],[state('analysis','processing',94),3],[state('training','waiting',null),0],[state('training','processing',1),0],[state('training','processing',35),1],[state('reanalysis','processing',2),1],[state('reanalysis','processing',94),2]])assert.equal(processStage(input),stage);
for(const kind of ['upload','analysis','training','reanalysis']){
 const html=renderToStaticMarkup(React.createElement(ProcessProgress,state(kind,'done',100)));assert(html.includes('aria-valuenow="100"'));assert(!html.includes('aria-current="step"'));assert(html.includes('Selesai'));
}
let html=renderToStaticMarkup(React.createElement(ProcessProgress,state('upload','validating',null)));assert(!html.includes('aria-valuenow'));assert(html.includes('indeterminate'));
html=renderToStaticMarkup(React.createElement(ProcessProgress,state('analysis','processing',100)));assert(html.includes('aria-valuenow="99"'),'100% requires a successful backend completion');
for(const status of ['error','cancelled','interrupted','waiting','cancelling']){html=renderToStaticMarkup(React.createElement(ProcessProgress,state('training',status,35)));assert(!html.includes('aria-current="step"'));assert(html.includes('data-state="paused"'));assert(!html.includes('Selesai'));}
(async()=>{
 const studio=ts.transpileModule(fs.readFileSync('frontend/studio.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText;
 const saveButton={},statuses=[];
 const reviewContext={$:()=>saveButton,persistReview:async()=>true,refreshQueue:async()=>({pending:3,group:'objects'}),learningStatus:(message,value,status)=>statuses.push(status)};
 vm.createContext(reviewContext);vm.runInContext(studio.slice(studio.indexOf("$('saveReview').onclick ="),studio.indexOf("$('learnDetector').onclick =")),reviewContext);
 await saveButton.onclick();assert.deepEqual(statuses,['waiting'],'unfinished correction queue must not show active training');
 const auth=ts.transpileModule(fs.readFileSync('frontend/auth.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText;
 let xhr,logins=0;class XHR{constructor(){xhr=this;this.upload={};this.headers={};this.status=200;this.responseText='{"id":"job"}';}open(method,url){this.method=method;this.url=url;}setRequestHeader(key,value){this.headers[key]=value;}getResponseHeader(){return 'application/json';}send(body){this.body=body;}abort(){this.onabort();}}
 const context={Headers,Request,Response,FormData,DOMException,XMLHttpRequest:XHR,session:{user:{role:'reviewer'},csrf_token:'test-csrf'},showLogin(){logins++;},nativeFetch:()=>{throw Error('upload must use byte-aware native transport');}};vm.createContext(context);vm.runInContext(auth.slice(auth.indexOf('async function request('),auth.indexOf('async function readSession(')),context);
 const values=[],body=new FormData();body.append('file',new Blob(['video']),'recording.mp4');
 let pending=context.request('/api/jobs',{method:'POST',body},value=>values.push(value));assert.equal(xhr.headers['x-csrf-token'],'test-csrf');assert.equal(xhr.headers['content-type'],undefined);assert.equal(xhr.body,body);assert.equal(xhr.url,'/api/jobs');
 xhr.upload.onprogress({lengthComputable:true,loaded:40,total:100});xhr.upload.onprogress({lengthComputable:false});xhr.upload.onprogress({lengthComputable:true,loaded:0,total:0});assert.deepEqual(values,[40,null,null]);xhr.onload();assert.equal((await (await pending).json()).id,'job');
 for(const event of ['onerror','ontimeout','onabort']){pending=context.request('/api/jobs',{method:'POST',body},()=>{});xhr[event]();await assert.rejects(pending);}
 const controller=new AbortController();pending=context.request('/api/jobs',{method:'POST',body,signal:controller.signal},()=>{});controller.abort();await assert.rejects(pending,/dibatalkan/);
 pending=context.request('/api/jobs',{method:'POST',body},()=>{});xhr.status=401;xhr.onload();await pending;assert.equal(logins,1,'expired sessions return to login after upload too');
 await assert.rejects(context.request('https://example.com',{method:'POST',body},()=>{}),/tidak valid/);
 context.session.user.role='viewer';await assert.rejects(context.request('/api/jobs',{method:'POST',body},()=>{}),/viewer/);
 console.log('PASS: backend process phases, honest completion/error/wait states, measured upload bytes, CSRF, role boundary, connection failure, timeout, abort and expired session.');
})().catch(error=>{console.error(error);process.exitCode=1;});
