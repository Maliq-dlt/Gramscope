// Run against a signed-out fixture: playwright-cli run-code --filename industrial_ai/tests/landing_check.cjs
async (page) => {
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(new URL('/#landingOverview',page.url()).href);
 await page.reload();
 await page.getByRole('heading',{name:'Dari rekaman, jadi pemahaman.'}).waitFor();
 await page.waitForFunction(()=>document.getElementById('landingPage').classList.contains('lenis'));
 const root=page.locator('#landingPage'),results=[];
 const scrollTo=async target=>{
  await root.evaluate((el,selector)=>{el.scrollTo({top:selector?el.querySelector(selector).getBoundingClientRect().top+el.scrollTop-300:0,behavior:'instant'});},target);
 };
 await scrollTo(null);
 await page.screenshot({path:'.tmp/landing-expand/hero-desktop.png'});
 for(const step of [0,1,2,1,0]){
  await scrollTo(`.story-chapter:nth-child(${step+1})`);
  await page.waitForFunction(index=>document.querySelector('.landing-stage').dataset.phase===String(index),step);
  await page.waitForFunction(()=>!window.gsap?.isTweening(document.querySelector('.landing-stage .scene-orbit')));
  if(step===2)await page.waitForFunction(()=>[...document.querySelectorAll('.landing-stage .scene-evidence')].every(el=>+getComputedStyle(el).opacity>.98));
  const box=await page.locator('.landing-stage').boundingBox();
  if(!box||box.y<100||box.y+box.height>1000)throw Error('Sticky scene is outside the usable viewport');
  if(!results.includes(step))await page.screenshot({path:`.tmp/landing-expand/chapter-${step+1}.png`});
  results.push(step);
 }
 // Pointer parallax responds without obscuring narrative text or resurrecting old captions.
 const frame=await page.locator('.landing-stage-frame').boundingBox();
 await page.mouse.move(frame.x+frame.width*.8,frame.y+frame.height*.4);
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('.story-focus-lens')).opacity==='1'&&getComputedStyle(document.querySelector('.story-focus-lens')).transform!=='none');
 const lens=await page.locator('.story-focus-lens').evaluate(el=>getComputedStyle(el).transform);
 await scrollTo('.story-chapter:nth-child(3)');
 await page.waitForFunction(()=>[...document.querySelectorAll('.landing-stage .scene-evidence')].every(el=>+getComputedStyle(el).opacity>.98));
 await page.mouse.move(600,240);
 const lastStage=await page.locator('.landing-stage').boundingBox();
 if(!lastStage||lastStage.y<100||lastStage.y+lastStage.height>1000)throw Error('Final choreography completes after the stage leaves the viewport');
 const ghost=await page.locator('.landing-stage .story-scene--0').evaluate(el=>({isolation:getComputedStyle(el).isolation,opacity:+getComputedStyle(el).opacity}));
 if(ghost.isolation!=='isolate'||ghost.opacity>.01)throw Error('Earlier caption leaks over the last scene');
 if(await page.locator('.story-controls,.story-scrubber,.story-interaction-hint').count())throw Error('Removed illustration controls returned');
 await scrollTo(null);
 await page.mouse.move(400,400);await page.mouse.wheel(0,500);
 await page.waitForFunction(()=>document.getElementById('landingPage').scrollTop>450);
 if(!await root.evaluate(el=>el.classList.contains('lenis')))throw Error('Smooth scrolling not active');
 await scrollTo('#landingQuestions');await page.screenshot({path:'.tmp/landing-expand/questions.png'});
 // An entry transition must animate, remove landing listeners/styles, then preserve login focus.
 await page.evaluate(()=>{
  const start=document.startViewTransition.bind(document);window.__entryTransitions=[];
  document.startViewTransition=update=>{
   const transition=start(update),record={ready:false,finished:false,error:null};window.__entryTransitions.push(record);
   transition.ready.then(()=>{record.ready=true;record.duration=getComputedStyle(document.documentElement,'::view-transition-new(studio-entry)').animationDuration;}).catch(error=>record.error=error.message);
   transition.finished.then(()=>record.finished=true);return transition;
  };
 });
 await page.getByRole('link',{name:'Masuk',exact:true}).click();
 await page.getByRole('heading',{name:'Selamat datang kembali.'}).waitFor();
 await page.waitForFunction(()=>window.__entryTransitions.at(-1)?.finished);
 const transition=await page.evaluate(()=>window.__entryTransitions.at(-1));
 if(!transition.ready||transition.error||parseFloat(transition.duration)<=0)throw Error(JSON.stringify(transition));
 if(await root.evaluate(el=>el.classList.contains('lenis')||[...el.querySelectorAll('.landing-stage .story-scene')].some(scene=>Boolean(scene.style.cssText))))throw Error('Hidden landing retained smooth scroll or GSAP styles');
 if(!await page.locator('#loginUsername').evaluate(el=>el===document.activeElement))throw Error('Login focus missing');
 if(await page.locator('#loginTransitionLoader').isVisible())throw Error('Entry navigation showed the real session loader');
 await page.getByRole('link',{name:'Kembali ke halaman awal'}).click();
 await page.waitForFunction(()=>window.__entryTransitions.at(-1)?.finished);
 await page.waitForFunction(()=>document.getElementById('landingPage').classList.contains('lenis'));
 await page.goBack();await page.getByRole('heading',{name:'Selamat datang kembali.'}).waitFor();
 await page.waitForFunction(()=>window.__entryTransitions.at(-1)?.finished);
 await page.goForward();await page.getByRole('heading',{name:'Dari rekaman, jadi pemahaman.'}).waitFor();
 await page.waitForFunction(()=>window.__entryTransitions.at(-1)?.finished);
 // Reduced motion restores all three figures to normal document flow.
 await page.emulateMedia({reducedMotion:'reduce',contrast:'more'});
 await page.waitForFunction(()=>!document.getElementById('landingPage').classList.contains('lenis'));
 if(await page.locator('.landing-stage').isVisible()||await page.locator('.landing-inline-scene:visible').count()!==3)throw Error('Reduced motion hid story content');
 if(await page.locator('.story-chapter-copy').evaluateAll(elements=>elements.some(el=>Boolean(el.style.cssText))))throw Error('Reduced motion retained GSAP transforms');
 if(await page.locator('.landing-header').evaluate(el=>getComputedStyle(el).backdropFilter)!=='none')throw Error('Contrast preference ignored');
 const responsive=[];
 for(const size of [{width:1440,height:1000},{width:768,height:1024},{width:390,height:844},{width:320,height:680}]){
  await page.setViewportSize(size);await scrollTo(null);
  const overflow=await root.evaluate(el=>el.scrollWidth>el.clientWidth);
  if(overflow)throw Error(`Horizontal overflow at ${size.width}`);
  const cta=await page.getByRole('link',{name:'Masuk ke studio',exact:true}).boundingBox();
  if(!cta||cta.y+cta.height>size.height)throw Error('Hero CTA outside initial viewport');
  for(const element of await page.locator('.landing-inline-scene .story-scene').all()){
   const fits=await element.evaluate(el=>{const box=el.getBoundingClientRect();return [...el.querySelectorAll('.scene-topline,.scene-bottomline,.scene-source')].every(child=>{const r=child.getBoundingClientRect();return r.left>=box.left-1&&r.right<=box.right+1;});});
   if(!fits)throw Error(`Illustration text overflow at ${size.width}`);
  }
  await page.screenshot({path:`.tmp/landing-expand/landing-${size.width}.png`});
  if(size.width===390){await scrollTo('.story-chapter');await page.screenshot({path:'.tmp/landing-expand/story-mobile.png'});}
  responsive.push({width:size.width,overflow,primaryCTAVisible:true});
 }
 await page.setViewportSize({width:1440,height:1000});
 await page.getByRole('link',{name:'Cara kerja',exact:true}).click();
 await page.waitForFunction(()=>Math.abs(document.getElementById('landingWorkflow').getBoundingClientRect().top-128)<3);
 await page.getByRole('link',{name:'Tentang',exact:true}).click();
 await page.waitForFunction(()=>document.getElementById('landingPage').scrollTop<160);
 const count=await page.evaluate(()=>window.__entryTransitions.length);
 await page.getByRole('link',{name:'Masuk',exact:true}).click();
 await page.getByRole('heading',{name:'Selamat datang kembali.'}).waitFor();
 if(await page.evaluate(()=>window.__entryTransitions.length)!==count)throw Error('Reduced motion still captured transition');
 await page.getByRole('link',{name:'Kembali ke halaman awal'}).click();
 await page.emulateMedia({reducedMotion:'no-preference',contrast:'no-preference'});
 await page.setViewportSize({width:1440,height:580});
 if(await page.locator('.landing-stage').isVisible()||await page.locator('.landing-inline-scene:visible').count()!==3)throw Error('Short desktop should have stacked story');
 await page.setViewportSize({width:1440,height:1000});
 await page.waitForFunction(()=>document.getElementById('landingPage').classList.contains('lenis'));
 await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide')));
 if(await root.evaluate(el=>el.classList.contains('lenis')))throw Error('pagehide retained landing ticker');
 await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow')));
 await page.waitForFunction(()=>document.getElementById('landingPage').classList.contains('lenis'));
 await page.getByRole('link',{name:'Tentang',exact:true}).click();
 await page.keyboard.press('Tab');
 const focus=await page.evaluate(()=>({text:document.activeElement.textContent,outline:getComputedStyle(document.activeElement).outlineStyle}));
 if(focus.outline==='none')throw Error('Keyboard focus invisible');
 if(errors.length)throw Error(errors.join('\n'));
 return {sceneOrder:results,responsive,entryTransition:transition,interactiveLens:lens,finalSceneVisible:true,captionIsolation:ghost,cleanup:true,history:true,reducedMotion:true,shortDesktop:true,keyboardFocus:focus,pageErrors:errors};
}
