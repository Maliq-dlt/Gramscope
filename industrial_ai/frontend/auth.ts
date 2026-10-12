declare function setView(view:string):Promise<boolean>;
interface WorkspaceUser {id:string;username:string;role:'admin'|'reviewer'|'viewer';tenant_id:string;tenant_name:string;display_name:string;avatar_url:string|null}
interface AuthSession {user:WorkspaceUser;csrf_token:string}
const workspaceAuth=(()=>{
 let session:AuthSession|null=null;
 let entered=false;
 let explicitTransition=false,loadingStarted=0,loadingGeneration=0,loadingTimer:number|undefined,resolveLoading:(()=>void)|undefined;
 function authTransition(active:boolean):void{document.dispatchEvent(new CustomEvent('workspace-auth-transition',{detail:{active}}));}
 function cancelLoading():void{loadingGeneration++;window.clearTimeout(loadingTimer);loadingTimer=undefined;resolveLoading?.();resolveLoading=undefined;}
 const nativeFetch=window.fetch.bind(window);
 function el<T extends HTMLElement>(id:string,type:{new():T}):T{const node=document.getElementById(id);if(!(node instanceof type))throw new Error(`Missing element ${id}`);return node;}
 const gate=el('authGate',HTMLElement),landing=el('landingPage',HTMLElement);
 document.getElementById('reviewSvg')?.addEventListener('pointerdown',event=>{if(session?.user.role==='viewer'){event.preventDefault();event.stopImmediatePropagation();}},true);
 let entryTransition:ViewTransition|undefined,entryAnimation:Animation|undefined;
 function showEntry():void{
   if(session||!el('loginTransitionLoader',HTMLElement).hidden)return;
   entryTransition?.skipTransition();entryAnimation?.cancel();
   const login=location.hash==='#login',changed=login?gate.hidden:landing.hidden;
   const render=()=>{
     if(session||!el('loginTransitionLoader',HTMLElement).hidden)return;
     // Read the latest hash inside the deferred callback so rapid Back/Forward cannot reveal a stale page.
     const nextLogin=location.hash==='#login',didChange=nextLogin?gate.hidden:landing.hidden;
     gate.hidden=!nextLogin;landing.hidden=nextLogin;
     if(didChange)el(nextLogin?'loginUsername':'landingTitle',HTMLElement).focus({preventScroll:true});
   };
   const animate=changed&&(!gate.hidden||!landing.hidden)&&!matchMedia('(prefers-reduced-motion: reduce)').matches;
   if(animate&&document.startViewTransition){
     const transition=entryTransition=document.startViewTransition(render);
     void transition.ready.catch(()=>{});
     void transition.finished.finally(()=>{if(entryTransition===transition)entryTransition=undefined;}).catch(()=>{});
   }else{
     render();
     if(animate)entryAnimation=(login?gate:landing).animate?.({opacity:[0,1],transform:['translateY(10px)','translateY(0)']},{duration:380,easing:'cubic-bezier(.22,1,.36,1)'});
   }
 }
 function showLogin(home=false):void{cancelLoading();authTransition(false);session=null;el('loginTransitionLoader',HTMLElement).hidden=true;document.body.classList.add('signed-out');if(!home)history.replaceState(null,'',location.pathname+location.search+'#login');showEntry();}
 window.addEventListener('hashchange',showEntry);
 function applyRole():void{if(session?.user.role!=='viewer')return;document.getElementById('reviewSvg')?.setAttribute('aria-label','Kotak anotasi tersimpan. Akun viewer hanya dapat melihat.');for(const id of ['newVideoButton','emptyUploadButton','uploadButton','reanalyzeButton','retryJob','cancelJob','saveReview','suggestBoxes','applyBoxButton','learnDetector','exportCorrectedVideo','cancelExport','cancelLearning','startTraining','openReview','prepareCorrections','resultCorrections','reviewPlayback','boxControls','metadataControls']){const node=document.getElementById(id);if((node instanceof HTMLButtonElement||node instanceof HTMLFieldSetElement||node instanceof HTMLInputElement)&&!node.disabled)node.disabled=true;}for(const node of document.querySelectorAll<HTMLButtonElement>('[data-view=annotation]')){if(!node.disabled)node.disabled=true;node.title='Viewer dapat melihat hasil; koreksi membutuhkan reviewer.';}for(const node of document.querySelectorAll<HTMLButtonElement>('#boxList button'))if(!node.disabled)node.disabled=true;}
 async function request(input:RequestInfo|URL,init:RequestInit={},onUpload?:(value:number|null)=>void):Promise<Response>{const headers=new Headers(init.headers),method=(init.method||'GET').toUpperCase();if(!['GET','HEAD','OPTIONS'].includes(method)){if(!session){showLogin();throw new Error('Silakan masuk kembali.');}const url=input instanceof Request?input.url:String(input);if(session.user.role==='viewer'&&!url.includes('/api/auth/')&&!['/api/chat','/api/ngram/explore','/api/ngram/chat','/api/ngram/chat/data','/api/ledger/query','/api/ledger/report'].includes(url))throw new Error('Akun viewer hanya dapat melihat hasil.');headers.set('X-CSRF-Token',session.csrf_token);}const response=onUpload ? await new Promise<Response>((resolve,reject)=>{
   if(String(input)!=='/api/jobs'||method!=='POST'||!(init.body instanceof FormData)){reject(new Error('Permintaan upload tidak valid.'));return;}
   const xhr=new XMLHttpRequest();xhr.open(method,String(input));xhr.timeout=180000;
   headers.forEach((value,key)=>xhr.setRequestHeader(key,value));
   xhr.upload.onprogress=event=>onUpload(event.lengthComputable && event.total>0 ? 100*event.loaded/event.total : null);
   const cleanup=()=>init.signal?.removeEventListener('abort',abort);
   const abort=()=>xhr.abort();
   xhr.onload=()=>{cleanup();resolve(new Response(xhr.responseText,{status:xhr.status,headers:{'Content-Type':xhr.getResponseHeader('Content-Type')||'application/json'}}));};
   xhr.onerror=()=>{cleanup();reject(new Error('Upload terputus. Periksa koneksi dan coba lagi.'));};
   xhr.ontimeout=()=>{cleanup();reject(new Error('Upload melewati batas waktu. Coba lagi.'));};
   xhr.onabort=()=>{cleanup();reject(new DOMException('Upload dibatalkan.','AbortError'));};
   if(init.signal?.aborted){reject(new DOMException('Upload dibatalkan.','AbortError'));return;}
   init.signal?.addEventListener('abort',abort,{once:true});xhr.send(init.body);
  }) : await nativeFetch(input,{...init,headers,credentials:'same-origin'});if(response.status===401)showLogin();return response;}
 async function readSession(response:Response):Promise<AuthSession>{const data:unknown=await response.json();if(!response.ok)throw new Error(typeof data==='object'&&data!==null&&'detail'in data?String(data.detail):'Tidak dapat masuk.');if(typeof data!=='object'||data===null||!('user'in data)||!('csrf_token'in data))throw new Error('Respons sesi tidak valid.');const user:unknown=data.user;if(typeof user!=='object'||user===null||!('role'in user)||!['admin','reviewer','viewer'].includes(String(user.role))||typeof data.csrf_token!=='string'||!data.csrf_token)throw new Error('Respons sesi tidak valid.');for(const field of ['id','username','tenant_id','tenant_name'])if(!(field in user)||typeof Reflect.get(user,field)!=='string')throw new Error('Respons akun tidak valid.');if(!('display_name'in user)||typeof user.display_name!=='string'||!('avatar_url'in user)||(user.avatar_url!==null&&(typeof user.avatar_url!=='string'||!/^\/api\/auth\/avatar\?v=[a-f0-9]+$/.test(user.avatar_url))))throw new Error('Respons profil tidak valid.');return data as AuthSession;}
 function renderProfile():void {
   if(!session)return;
   const user=session.user,name=user.display_name||user.username;
   for(const id of ['profileAvatar','accountAvatar']){
     const node=el(id,HTMLElement);node.textContent=Array.from(name.trim()).slice(0,2).join('').toLocaleUpperCase('id');
     node.style.backgroundImage=user.avatar_url?`url("${user.avatar_url}")`:'';
     node.classList.toggle('has-custom-avatar',Boolean(user.avatar_url));
   }
   el('accountIdentity',HTMLElement).textContent=name;
   el('profileDisplayName',HTMLElement).textContent=name;
   el('profileNameInput',HTMLInputElement).value=user.display_name;
   el('profileUsername',HTMLElement).textContent=user.username;
   el('profileWorkspace',HTMLElement).textContent=user.tenant_name;
   el('profileRole',HTMLElement).textContent={admin:'Administrator',reviewer:'Reviewer',viewer:'Viewer'}[user.role];
 }
 async function signedIn(value:AuthSession,explicit=false):Promise<boolean>{
   landing.hidden=true;
   if(entered){
     if(!explicit){location.reload();return false;}
     cancelLoading();session=value;explicitTransition=true;loadingStarted=Date.now();
     const generation=loadingGeneration,loader=el('loginTransitionLoader',HTMLElement);loader.hidden=false;gate.hidden=true;document.body.classList.add('signed-out');
     const heading=loader.querySelector('h1');if(heading)heading.textContent='Menyiapkan studio Anda.';el('loginTransitionStatus',HTMLElement).textContent='Memuat rekaman dan pengaturan workspace…';el('loginTransitionRetry',HTMLButtonElement).hidden=true;authTransition(true);
     if(!matchMedia('(prefers-reduced-motion: reduce)').matches)await new Promise<void>(resolve=>{resolveLoading=resolve;loadingTimer=window.setTimeout(()=>{loadingTimer=undefined;resolveLoading=undefined;resolve();},3200);});
     if(session&&generation===loadingGeneration)location.reload();
     return false;
   }
   entered=true;session=value;explicitTransition=explicit;loadingStarted=Date.now();loadingGeneration++;gate.hidden=true;
   el('loginTransitionLoader',HTMLElement).hidden=!explicit;
   if(explicit){const heading=el('loginTransitionLoader',HTMLElement).querySelector('h1');if(heading)heading.textContent='Menyiapkan studio Anda.';el('loginTransitionStatus',HTMLElement).textContent='Memuat rekaman dan pengaturan workspace…';el('loginTransitionRetry',HTMLButtonElement).hidden=true;authTransition(true);}else document.body.classList.remove('signed-out');
   renderProfile();applyRole();return true;
 }
 async function finishLoading(error?:string):Promise<void>{
   if(!session||logoutPending)return;
   const loader=el('loginTransitionLoader',HTMLElement);
   if(error){cancelLoading();authTransition(false);loader.hidden=false;const status=el('loginTransitionStatus',HTMLElement);status.textContent=error;const retry=document.getElementById('loginTransitionRetry');if(retry){retry.hidden=false;retry.focus();}return;}
   const generation=loadingGeneration,remaining=!explicitTransition||matchMedia('(prefers-reduced-motion: reduce)').matches?0:Math.max(0,3200-(Date.now()-loadingStarted));
   if(remaining)await new Promise<void>(resolve=>{resolveLoading=resolve;loadingTimer=window.setTimeout(()=>{loadingTimer=undefined;resolveLoading=undefined;resolve();},remaining);});
   if(!session||generation!==loadingGeneration)return;
   loader.hidden=true;authTransition(false);document.body.classList.remove('signed-out');applyRole();(document.getElementById('workspaceTitle')||document.getElementById('mainContent'))?.focus();
   document.dispatchEvent(new Event('workspace-ready'));
 }
 const ready=(async()=>{try{await signedIn(await readSession(await nativeFetch('/api/auth/session',{credentials:'same-origin'})));}catch{showLogin(true);await new Promise<void>(resolve=>document.addEventListener('workspace-login',()=>resolve(),{once:true}));}})();
 el('loginForm',HTMLFormElement).onsubmit=async event=>{
   event.preventDefault();const button=el('loginSubmit',HTMLButtonElement),error=el('loginError',HTMLElement);button.disabled=true;error.hidden=true;
   try{
     const value=await readSession(await nativeFetch('/api/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:el('loginUsername',HTMLInputElement).value,password:el('loginPassword',HTMLInputElement).value})}));
     el('loginPassword',HTMLInputElement).value='';
     if(await signedIn(value,true))document.dispatchEvent(new Event('workspace-login'));
   }catch(reason:unknown){error.textContent=reason instanceof Error?reason.message:'Tidak dapat masuk.';error.hidden=false;}
   finally{button.disabled=false;}
 };
 el('logoutButton',HTMLButtonElement).onclick=async()=>{
   if(logoutPending||profilePending||passwordPending)return;
   logoutPending=true;syncProfilePending();cancelLoading();explicitTransition=true;loadingStarted=Date.now();
   const generation=loadingGeneration,loader=el('loginTransitionLoader',HTMLElement);loader.hidden=false;const heading=loader.querySelector('h1');if(heading)heading.textContent='Sampai jumpa.';gate.hidden=true;document.body.classList.add('signed-out');el('loginTransitionStatus',HTMLElement).textContent='Mengakhiri sesi…';authTransition(true);
   try{
     const response=await request('/api/auth/logout',{method:'POST'});if(!response.ok)throw new Error('Gagal keluar.');
     const remaining=matchMedia('(prefers-reduced-motion: reduce)').matches?0:Math.max(0,3200-(Date.now()-loadingStarted));
     if(remaining)await new Promise<void>(resolve=>{resolveLoading=resolve;loadingTimer=window.setTimeout(()=>{loadingTimer=undefined;resolveLoading=undefined;resolve();},remaining);});
     if(generation!==loadingGeneration)return;
     session=null;authTransition(false);location.reload();
   }catch(reason:unknown){
     cancelLoading();authTransition(false);loader.hidden=true;if(session)document.body.classList.remove('signed-out');
     const alert=el(session?'authError':'loginError',HTMLElement);alert.textContent=session?(reason instanceof Error?reason.message:'Gagal keluar.'):'Sesi berakhir. Silakan masuk kembali.';alert.hidden=false;if(session)el('logoutButton',HTMLButtonElement).focus();else el('loginUsername',HTMLInputElement).focus();
   }finally{logoutPending=false;syncProfilePending();}
 };
 const passwordForm=el('passwordForm',HTMLFormElement);
 const passwordSubmit=el('passwordSubmit',HTMLButtonElement);
 let passwordPending=false,profilePending=false,logoutPending=false;
 function syncProfilePending():void{
   const pending=passwordPending||profilePending||logoutPending;el('logoutButton',HTMLButtonElement).disabled=pending;passwordSubmit.disabled=pending;
   for(const id of ['saveNameBtn','removeAvatarBtn','avatarFileInput']){const node=el(id,HTMLElement);if(pending)node.setAttribute('disabled','');else node.removeAttribute('disabled');}
 }
 function resetPasswordForm():void {
   passwordForm.reset();
   for(const id of ['currentPassword','newPassword','confirmPassword'])el(id,HTMLInputElement).type='password';
   for(const button of document.querySelectorAll<HTMLButtonElement>('[data-password-target]')){button.setAttribute('aria-pressed','false');button.setAttribute('aria-label','Tampilkan password');}
   el('confirmPassword',HTMLInputElement).setCustomValidity('');
   updatePasswordMeter('');
   el('passwordStatus',HTMLElement).textContent='';
 }
 el('profileButton',HTMLButtonElement).onclick=async()=>{
   if(!(await setView('profile')))return;resetPasswordForm();renderProfile();el('profileTitle',HTMLElement).focus();
 };
 el('confirmPassword',HTMLInputElement).oninput=()=>el('confirmPassword',HTMLInputElement).setCustomValidity('');
 passwordForm.onsubmit=async event=>{
   event.preventDefault();
   if(passwordPending||profilePending||logoutPending)return;
   const status=el('passwordStatus',HTMLElement),confirmation=el('confirmPassword',HTMLInputElement);
   const newPassword=el('newPassword',HTMLInputElement).value;
   status.textContent='';
   if(newPassword!==confirmation.value){
     confirmation.setCustomValidity('Konfirmasi password tidak cocok.');
     status.textContent='Konfirmasi password tidak cocok.';confirmation.reportValidity();return;
   }
   confirmation.setCustomValidity('');
   if(!passwordForm.reportValidity())return;
   passwordPending=true;syncProfilePending();
   try {
     const response=await request('/api/auth/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:el('currentPassword',HTMLInputElement).value,new_password:newPassword})});
     const nextSession=await readSession(response);
     session=nextSession;
     resetPasswordForm();
     status.textContent='Password diperbarui. Sesi lain telah keluar; Anda tetap masuk di sini.';
   } catch(reason:unknown) {
     status.textContent=reason instanceof Error?reason.message:'Gagal mengubah password.';
   } finally {passwordPending=false;syncProfilePending();}
 };
 new MutationObserver(applyRole).observe(document.body,{subtree:true,attributes:true,attributeFilter:['disabled'],childList:true});
 // Adapted from 21st.dev ddoemonn/password-strength: rules, pattern detection, segmented meter and debounced live feedback.
 function evaluatePassword(val:string){
   const COMMON=/^(?:password|passw0rd|qwerty|letmein|welcome|admin|iloveyou|monkey|dragon|abc123|111111|123123|123456)/i;
   const RUN=/(.)\1{3,}/;
   const RUN_UP=/(?:0123|1234|2345|3456|4567|5678|6789|abcd|bcde|cdef|defg|qwer|wert|erty|asdf)/i;
   const SYMBOL=/[!-/:-@[-`{-~]/;
   const rules=[
     {id:'ruleLen',met:val.length>=12},
     {id:'ruleCase',met:/[a-z]/.test(val)&&/[A-Z]/.test(val)},
     {id:'ruleDigit',met:/\d/.test(val)},
     {id:'ruleSymbol',met:SYMBOL.test(val)}
   ];
   const passed=rules.filter(r=>r.met).length;
   const guessable=val.length>0&&(COMMON.test(val)||RUN.test(val)||RUN_UP.test(val));
   const score=val.length===0?0:guessable?1:Math.min(rules.length,Math.max(1,passed));
   const labels=['Kosong','Lemah','Cukup','Baik','Sangat Kuat'];
   return {score,label:labels[Math.min(score,4)],rules,guessable};
 }
 let announcementTimer:number|undefined;
 function updatePasswordMeter(val:string,prefix=''){
   if(typeof document==='undefined')return;
   const res=evaluatePassword(val);
   const meter=document.getElementById(prefix+'passwordMeter');
   if(!meter)return;
   meter.setAttribute('aria-valuemin','0');meter.setAttribute('aria-valuemax','4');meter.setAttribute('aria-valuenow',String(res.score));meter.setAttribute('aria-valuetext',res.label);
   window.clearTimeout(announcementTimer);const announcement=el('passwordStrengthAnnouncement',HTMLElement);if(!val)announcement.textContent='';else announcementTimer=window.setTimeout(()=>{announcement.textContent=`Kekuatan password: ${res.label}.${res.guessable?' Pola mudah ditebak.':''}`;},700);
   meter.className='password-meter '+(res.score<=1?'meter--danger':res.score<=2?'meter--caution':'meter--safe');
   const cells=meter.querySelectorAll('.password-meter-cell');
   cells.forEach((cell,idx)=>{
     if(idx<res.score)cell.classList.add('filled');
     else cell.classList.remove('filled');
   });
   const label=meter.querySelector('.password-meter-label');
   if(label)label.textContent=res.score===0?'Kosong':res.label;
   const common=meter.querySelector<HTMLElement>('.password-meter-common');
   if(common)common.hidden=!res.guessable;
   for(const r of res.rules){
     const item=document.getElementById(prefix+r.id);
     if(item){
       item.className='password-rule-item '+(r.met?'met':'');
       const icon=item.querySelector('.password-rule-icon');
       if(icon)icon.textContent=r.met?'✓':'○';
     }
   }
 }
 async function saveProfile(input:string,init:RequestInit,statusId:string,success:string):Promise<void>{
   if(profilePending||passwordPending||logoutPending)return;
   profilePending=true;
   const status=el(statusId,HTMLElement);status.textContent='Menyimpan...';
   syncProfilePending();
   try{session=await readSession(await request(input,init));renderProfile();status.textContent=success;}
   catch(reason:unknown){status.textContent=reason instanceof Error?reason.message:'Gagal menyimpan profil.';}
   finally{profilePending=false;syncProfilePending();}
 }
 el('newPassword',HTMLInputElement).addEventListener('input',event=>updatePasswordMeter((event.target as HTMLInputElement).value));
 el('avatarFileInput',HTMLInputElement).addEventListener('change',()=>{
   const input=el('avatarFileInput',HTMLInputElement),file=input.files?.[0];
   if(!file||!session)return;
   if(file.size>2*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type)){el('avatarStatus',HTMLElement).textContent='Pilih PNG, JPEG, atau WebP maksimal 2 MB.';input.value='';return;}
   const body=new FormData();body.append('file',file);
   void saveProfile('/api/auth/avatar',{method:'PUT',body},'avatarStatus','Foto profil disimpan.').finally(()=>{input.value='';});
 });
 el('removeAvatarBtn',HTMLButtonElement).addEventListener('click',()=>void saveProfile('/api/auth/avatar',{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'},'avatarStatus','Foto profil dihapus.'));
 el('saveNameBtn',HTMLButtonElement).addEventListener('click',()=>{
   const name=el('profileNameInput',HTMLInputElement).value.trim();
   if(!name||Array.from(name).length>80){el('nameSaveStatus',HTMLElement).textContent='Nama tampilan wajib diisi, maksimal 80 karakter.';return;}
   void saveProfile('/api/auth/profile',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:name})},'nameSaveStatus','Nama tampilan disimpan.');
 });
 for(const button of document.querySelectorAll<HTMLButtonElement>('[data-password-target]'))button.addEventListener('click',()=>{const id=button.dataset.passwordTarget;if(!id)return;const input=el(id,HTMLInputElement),show=input.type==='password';input.type=show?'text':'password';button.setAttribute('aria-pressed',String(show));button.setAttribute('aria-label',show?'Sembunyikan password':'Tampilkan password');});
 el('toggleLoginPassword',HTMLButtonElement).addEventListener('click',()=>{
   const input=el('loginPassword',HTMLInputElement),button=el('toggleLoginPassword',HTMLButtonElement),show=input.type==='password';
   input.type=show?'text':'password';button.setAttribute('aria-pressed',String(show));button.setAttribute('aria-label',show?'Sembunyikan password':'Tampilkan password');
 });
 // The typed media controller keeps the same DOM nodes during session rotation.
 return {ready,request,applyRole,resetPasswordForm,renderProfile,finishLoading};
})();
