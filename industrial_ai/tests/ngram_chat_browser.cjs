// Run with playwright-cli on an authenticated, isolated studio fixture.
async (page) => {
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.setViewportSize({width:1440,height:1000});
 await page.reload();await page.getByRole('heading',{name:'Analisis rekaman',exact:true}).waitFor();
 await page.locator('[data-view=ngram]').click();
 await page.locator('.ngchat-suggestions button').first().waitFor();
 await page.screenshot({path:'.tmp/landing-expand/ngram-chat-desktop.png'});
 const composer=page.locator('#ngchatQuestion');
 await page.getByRole('button',{name:'Apa itu bigram?',exact:true}).click();
 if(await composer.inputValue()!=='Apa itu bigram?')throw Error('Suggestion did not populate composer');
 await page.route('**/api/ngram/chat',async route=>{await new Promise(resolve=>setTimeout(resolve,700));await route.continue();});
 await composer.press('Enter');
 await page.locator('.ngchat-pending').waitFor();
 await page.locator('[data-view=evidence]').click();
 if(await page.locator('#pageTitle').textContent()!=='Bukti & hasil')throw Error('Navigation blocked during Q&A request');
 await page.locator('[data-view=ngram]').click();
 await page.locator('.ngchat-answer').first().waitFor();
 const partial=await page.locator('.ngchat-answer-text [aria-hidden=true]').first().textContent();
 if(partial.length>190)throw Error('Answer did not reveal progressively');
 await page.getByRole('button',{name:'Tampilkan langsung',exact:true}).click();
 if(!await page.locator('.ngchat-answer-text').first().textContent().then(text=>text.includes('Bigram memakai dua token')))throw Error('Incorrect real Q&A answer');
 await page.locator('.ngchat-trace summary').first().click();
 await page.getByText('03 · Peringkat jawaban', {exact:true}).waitFor();
 if(await page.locator('.ngchat-candidate').count()!==3)throw Error('Expected three measured candidates');
 await page.screenshot({path:'.tmp/landing-expand/ngram-chat-trace.png'});
 await page.unroute('**/api/ngram/chat');
 await composer.fill('ramalan cuaca mars besok');await composer.press('Enter');
 await page.locator('.ngchat-answer').nth(1).waitFor();
 if(await page.locator('.ngchat-author').nth(1).textContent()!=='N-gramPerlu konteks lebih spesifik')throw Error('Out-of-corpus question must not invent an answer');
 const downloadPromise=page.waitForEvent('download');
 await page.getByRole('button',{name:'Unduh percakapan dan log',exact:true}).click();
 await (await downloadPromise).saveAs('.tmp/landing-expand/ngram-chat-log.json');
 await page.getByRole('button',{name:/Data Q&A/}).click();
 const importDataset=async value=>page.evaluate(dataset=>{
  const input=document.querySelector('.ngchat-data input[type=file]'),transfer=new DataTransfer();
  transfer.items.add(new File([JSON.stringify(dataset)],'qa.json',{type:'application/json'}));
  input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
 },value);
 await importDataset({name:'Invalid',pairs:[]});
 await page.getByRole('alert').filter({hasText:'Data Q&A tidak valid'}).waitFor();
 if(await page.locator('.ngchat-qa-list details').count()!==12)throw Error('Invalid import replaced existing dataset');
 const custom={name:'Manual toko',pairs:[{question:'kapan toko buka',answer:'Toko buka pukul 09.00.',source:'Jadwal pemilik'},{question:'kapan toko tutup',answer:'Toko tutup pukul 18.00.',source:'Jadwal pemilik'}]};
 await importDataset(custom);await page.getByText('Manual toko',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Percakapan',exact:true}).click();
 await composer.fill('kapan toko buka');await composer.press('Enter');
 await page.locator('.ngchat-answer').waitFor();
 await page.waitForFunction(()=>document.querySelector('.ngchat-answer-text [aria-hidden=true]')?.textContent==='Toko buka pukul 09.00.');
 if(!await page.locator('.ngchat-answer-text').textContent().then(text=>text.includes('Toko buka pukul 09.00.')))throw Error('Custom Q&A did not supply the answer');
 // Session data is deliberately ephemeral; reload restores the authored learning corpus.
 await page.reload();await page.getByRole('heading',{name:'Analisis rekaman',exact:true}).waitFor();await page.locator('[data-view=ngram]').click();
 await page.locator('.ngchat-suggestions button').first().waitFor();
 const responsive=[];
 for(const width of [1440,768,390,320]){
  await page.setViewportSize({width,height:width<600?844:1000});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  if(overflow)throw Error(`Chat overflow at ${width}px`);
  await composer.scrollIntoViewIfNeeded();
  await page.screenshot({path:`.tmp/landing-expand/ngram-chat-${width}.png`});
  responsive.push({width,overflow});
 }
 await page.setViewportSize({width:1440,height:1000});
 await page.evaluate(()=>{window.scrollTo({top:0,behavior:'instant'});document.documentElement.dataset.theme='dark';});
 await page.screenshot({path:'.tmp/landing-expand/ngram-chat-dark.png'});
 await page.emulateMedia({reducedMotion:'reduce'});
 const animation=await page.locator('.ngchat-mark i').last().evaluate(el=>getComputedStyle(el).animationName);
 if(animation!=='none')throw Error('Decorative animation ignored reduced motion');
 await composer.fill('Apa itu bigram?');await composer.press('Enter');
 await page.locator('.ngchat-answer').waitFor();
 await page.waitForFunction(()=>!document.querySelector('.ngchat-answer .reveal-skip'));
 if(!await page.locator('.ngchat-answer-text [aria-hidden=true]').textContent().then(text=>text.startsWith('Bigram memakai')))throw Error('Reduced-motion answer incomplete');
 await page.locator('.ngchat-trace summary').first().click();
 await page.screenshot({path:'.tmp/landing-expand/ngram-chat-dark-trace.png'});
 if(errors.length)throw Error(errors.join('; '));
 return {realQAMatch:true,pendingNavigation:true,progressiveReveal:true,measuredTrace:true,noMatch:true,importValidation:true,customQA:true,logDownload:true,responsive,reducedMotion:true,pageErrors:errors};
}
