/* Real browser assertions for the delivered custom card. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const registryPolyfill=require.resolve('@webcomponents/scoped-custom-element-registry');
const code=fs.readFileSync(path.join(__dirname,'../../custom_components/arandjelovac_live/frontend/arandjelovac-live-card.js'),'utf8');
const now=new Date('2026-10-14T17:00:00+02:00'),future=new Date(now.getTime()+86400000).toISOString();
const states={};
const add=(provider,items,extra={})=>{states['sensor.arandjelovac_'+provider]={entity_id:'sensor.arandjelovac_'+provider,state:String(items.length),attributes:{integration_domain:'arandjelovac_live',provider,available:true,items,last_success:now.toISOString(),metadata:{},...extra}};};
add('eds',[{area:'Vožda Karađorđa',start_at:future,end_at:new Date(Date.parse(future)+3600000).toISOString(),status:'geplant',source_url:'https://www.elektrodistribucija.rs/planirana-iskljucenja/planirana-kv'}],{coverage_end:'2026-10-17',coverage_complete:true});
add('jkp',[{title:'Information',kind:'water_unknown',status:'image_only',published_at:now.toISOString(),description:'Bildbeitrag',source_url:'https://www.jkpbukulja.rs/vesti'}],{metadata:{unreadable_notices:1}});
add('putevi',[{title:'31.8.2026.Obustava na putu, deonica Lazarevac – Darosava (Belanovica), mesto Kruševica',route:'Lazarevac – Darosava (Belanovica)',place:'Kruševica',deadline_date:'2026-12-26',end_precision:'date',end_at:'2026-12-27T00:00:00+01:00',description:'Umleitung',status:'published',kind:'closure',source_url:'https://www.putevi-srbije.rs/'}]);
add('kultura',[{id:'1',title:'KINOFILM_UNSICHTBAR',start_at:future,kind:'event',event_type:'cinema',program_split:true,description:'WEEKLY_PROGRAM_SHOULD_NOT_REPEAT',status:'scheduled',source_url:'https://centarzakulturuarandjelovac.rs/'}]);
states['sensor.arandjelovac_kultura'].attributes.items.push(
 {id:'legacy',title:'LEGACY_KINO_UNSICHTBAR',start_at:future,kind:'event',source_url:'https://centarzakulturuarandjelovac.rs/filmski-program-od-12-do-17-oktobra'},
 {id:'theatre',title:'Theaterabend',start_at:future,kind:'event',event_type:'theatre',program_split:true,description:'WEEKLY_PROGRAM_SHOULD_NOT_REPEAT',status:'scheduled',source_url:'https://centarzakulturuarandjelovac.rs/theater/'},
 ...Array.from({length:9},(_,i)=>({id:'notice-'+i,title:'Kulturankündigung '+(i+1),kind:'announcement',status:'announcement',published_at:now.toISOString(),source_url:'https://centarzakulturuarandjelovac.rs/notice-'+i}))
);
states['sensor.arandjelovac_kultura'].state=String(states['sensor.arandjelovac_kultura'].attributes.items.length);
add('museum',[]);
add('library',[{id:'reading',title:'Lesung im November',event_date:'2026-11-02',kind:'event',event_type:'reading',status:'date_only',published_at:now.toISOString(),source_url:'https://www.nbssa.rs/lesung/'}]);
add('manifestations',[{id:'market',title:'Novogodišnji bazar',kind:'seasonal',status:'seasonal',season_label:'decembar',date_confirmed:false,source_url:'https://bukovickabanja.rs/bazar/'}]);
const newsTitle='Gemeindemeldung mit einer längeren Überschrift';
const longDescription='Zusätzliche Informationen aus der öffentlichen Quelle. '.repeat(12)+'ENDE_DES_LANGEN_TEXTES';
add('tourism',[]);add('opstina',[{id:'news',title:newsTitle,description:newsTitle+' '+longDescription,status:'published',published_at:now.toISOString(),source_url:'https://arandjelovac.rs/'}]);
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{})});
 const page=await browser.newPage();await page.clock.install({time:now});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let checks=0;const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++;},has=(text,pattern)=>{assert.match(text,pattern);checks++;},lacks=(text,pattern)=>{assert.doesNotMatch(text,pattern);checks++;};
 for(const order of ['before-polyfill','before-host','after-host']){
  await page.goto('about:blank');if(order==='before-polyfill')await page.addScriptTag({content:code});
  await page.addScriptTag({path:registryPolyfill});if(order==='before-host')await page.addScriptTag({content:code});
  eq(await page.evaluate(()=>customElements.get('arandjelovac-live-card')===undefined),true,order+': wait for HA registry');
  await page.evaluate(()=>customElements.define('home-assistant',class extends HTMLElement{}));if(order==='after-host')await page.addScriptTag({content:code});
  await page.waitForFunction(()=>customElements.get('arandjelovac-live-card'));
  eq(await page.evaluate(()=>{const c=document.createElement('arandjelovac-live-card');c.setConfig({});return !!c.shadowRoot.querySelector('ha-card');}),true,order+': active HTMLElement');
  await page.addScriptTag({content:code});eq(await page.evaluate(()=>window.customCards.filter(c=>c.type==='arandjelovac-live-card').length),1,order+': duplicate loading');
 }
 const palettes={light:'',dark:'--primary-text-color:#edf2f8;--secondary-text-color:#b2c0d1;--ha-card-background:#202b39;--divider-color:#354252;',green:'--primary-text-color:#e7f4e8;--secondary-text-color:#b9cfc2;--ha-card-background:#355347;--divider-color:#607d6e;--primary-color:#a0d9b7;--success-color:#4caf50;--warning-color:#ffc107;'};
 fs.mkdirSync('test-results',{recursive:true});
 const setStates=async value=>page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},value);
 const force=async()=>page.evaluate(()=>document.querySelector('arandjelovac-live-card')._render(true));
 for(const [theme,palette] of Object.entries(palettes))for(const width of [320,440,736]){
  await page.goto('about:blank');await page.setViewportSize({width,height:1200});
  await page.setContent(`<html style="color-scheme:${theme==='light'?'light':'dark'}"><body style="margin:0;${palette}"><div id="mount"></div></body></html>`);
  await page.addScriptTag({path:registryPolyfill});await page.evaluate(()=>customElements.define('home-assistant',class extends HTMLElement{}));await page.addScriptTag({content:code});
  await page.waitForFunction(()=>customElements.get('arandjelovac-live-card'));
  await page.evaluate(states=>{const c=document.createElement('arandjelovac-live-card');c.setConfig({type:'custom:arandjelovac-live-card'});c.hass={states};document.getElementById('mount').appendChild(c);},states);
  const card=page.locator('arandjelovac-live-card').first(),events=card.locator('section[data-panel="events"]');
  const tab=key=>events.locator(`button[data-event-tab="${key}"]`),pane=key=>events.locator(`#events-pane-${key}`);
  has(await card.locator('ha-card').innerText(),/Versorgung & Verkehr/);has(await card.locator('ha-card').innerText(),/Nachrichten aus der Gemeinde/);has(await card.locator('ha-card').innerText(),/9\/9 Quellen erreichbar/);
  has(await card.locator('ha-card').innerText(),/Teilweise als Bild verfügbar/);has(await card.locator('details[data-panel="jkp"] > summary').innerText(),/1 Wassermeldung/);
  const traffic=card.locator('details[data-panel="putevi"] > summary');has(await traffic.innerText(),/Sperrung Lazarevac – Darosava/);has(await traffic.innerText(),/Kruševica · angekündigt bis 26\.12\.2026/);lacks(await traffic.innerText(),/31\.8\.2026/);eq(await traffic.locator('ha-icon[icon="mdi:road-variant"]').count(),1);
  eq(await tab('dates').getAttribute('aria-selected'),'true');eq(await tab('dates').locator('.tab-count').innerText(),'2');eq(await tab('preview').locator('.tab-count').innerText(),'9');eq(await tab('season').locator('.tab-count').innerText(),'1');
  eq(await pane('dates').isVisible(),true);eq(await pane('preview').isVisible(),false);eq(await pane('season').isVisible(),false);
  lacks(await events.textContent(),/KINOFILM_UNSICHTBAR|LEGACY_KINO_UNSICHTBAR|WEEKLY_PROGRAM_SHOULD_NOT_REPEAT/);
  eq(await pane('dates').locator('time').evaluateAll(items=>items.map(e=>e.dateTime)),['2026-10-15','2026-11-02']);
  const theatre=pane('dates').locator('.event-record').filter({hasText:'Theaterabend'}),reading=pane('dates').locator('.event-record').filter({hasText:'Lesung im November'});
  eq(await theatre.locator('.calendar-day').innerText(),'15');eq(await theatre.locator('.calendar-month').innerText(),'OKT');eq(await theatre.locator('.event-type ha-icon').getAttribute('icon'),'mdi:drama-masks');
  has(await reading.locator('summary').innerText(),/Uhrzeit offen/);lacks(await reading.locator('summary').innerText(),/00:00/);eq(await reading.locator('.event-type ha-icon').getAttribute('icon'),'mdi:book-open-page-variant');
  eq(await theatre.locator('.event-body').isVisible(),false);await theatre.locator('summary').click();eq(await theatre.locator('.event-body').isVisible(),true);has(await theatre.locator('.event-body').innerText(),/Einzeltermin aus dem veröffentlichten Programm/);
  await theatre.locator('summary').click();
  if(width===440)await page.screenshot({path:`test-results/card-${theme}-collapsed.png`,fullPage:true});
  await tab('dates').focus();await page.keyboard.press('ArrowRight');eq(await tab('preview').getAttribute('aria-selected'),'true');eq(await tab('preview').evaluate(e=>e===e.getRootNode().activeElement),true);
  has(await pane('preview').innerText(),/Kulturankündigung 9/);eq(await pane('dates').isVisible(),false);
  const notice=pane('preview').locator('.event-record').filter({hasText:'Kulturankündigung 9'});
  await notice.locator('summary').focus();await page.keyboard.press('Enter');has(await notice.locator('.event-body').innerText(),/Veröffentlicht am 14\. Oktober 2026/);
  const refreshed=structuredClone(states);refreshed['sensor.arandjelovac_opstina'].attributes.last_success=new Date(now.getTime()+60000).toISOString();await setStates(refreshed);await force();
  eq(await tab('preview').getAttribute('aria-selected'),'true');eq(await notice.evaluate(e=>e.open),true);eq(await notice.locator('summary').evaluate(e=>e===e.getRootNode().activeElement),true);
  await card.evaluate(c=>c.setConfig({max_items:1}));has(await pane('preview').innerText(),/Kulturankündigung 9/);await card.evaluate(c=>c.setConfig({}));
  await tab('preview').focus();await setStates(states);eq(await tab('preview').evaluate(e=>e===e.getRootNode().activeElement),true);
  await page.keyboard.press('End');eq(await tab('season').getAttribute('aria-selected'),'true');eq(await pane('season').isVisible(),true);has(await pane('season').innerText(),/Genaue Termine für ein bestimmtes Jahr sind nicht bestätigt/);
  const market=pane('season').locator('.event-record');eq(await market.locator('.season-month').innerText(),'DEZ');eq(await market.locator('time').count(),0);eq(await market.locator('.event-type ha-icon').getAttribute('icon'),'mdi:store-outline');
  eq(await market.locator('.event-body').isVisible(),false);await market.locator('summary').click();has(await market.locator('.event-body').innerText(),/Dezember/);has(await market.locator('.event-body').innerText(),/Jahrestermin nicht bestätigt/);lacks(await pane('season').textContent(),/2026|2027/);
  await force();eq(await tab('season').getAttribute('aria-selected'),'true');eq(await market.evaluate(e=>e.open),true);eq(await notice.evaluate(e=>e.open),true);
  eq(await events.locator('button[tabindex="0"]').count(),1);await tab('season').focus();await page.keyboard.press('Home');eq(await tab('dates').getAttribute('aria-selected'),'true');eq(await market.locator('.event-body').isVisible(),false);
  for(const key of ['eds','jkp','putevi','opstina','sources'])await card.locator(`details[data-panel="${key}"] > summary`).click();
  await force();eq(await card.locator('details[data-panel="eds"]').evaluate(e=>e.open),true);
  const news=card.locator('details[data-panel="opstina"]'),textToggle=news.locator('.description-toggle');
  has(await news.innerText(),/Veröffentlicht am 14\. Oktober 2026/);eq(await news.locator('.description-preview').innerText().then(t=>t.includes(newsTitle)),false);eq(await textToggle.locator(':scope > .description').isVisible(),false);
  await textToggle.locator('summary').click();has(await textToggle.innerText(),/ENDE_DES_LANGEN_TEXTES/);has(await textToggle.locator('summary').innerText(),/Weniger anzeigen/);await force();eq(await textToggle.evaluate(e=>e.open),true);
  const contrast=await card.evaluate(c=>{
    const root=c.shadowRoot,ctx=document.createElement('canvas').getContext('2d');
    const luminance=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].slice(0,3).map(x=>x/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);};
    const ratio=(a,b)=>{a=luminance(a);b=luminance(b);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
    const background=getComputedStyle(root.querySelector('ha-card')).backgroundColor,selected=getComputedStyle(root.querySelector('button[aria-selected="true"]'));
    return {text:ratio(getComputedStyle(root.querySelector('.provider-state.good')).color,background),icon:ratio(getComputedStyle(root.querySelector('.good ha-icon')).color,background),tab:ratio(selected.color,selected.backgroundColor),neutral:getComputedStyle(root.querySelector('.warning')).backgroundColor===background,tabsFit:[...root.querySelectorAll('.event-tabs button')].every(e=>e.scrollWidth<=e.clientWidth)};
  });
  eq(contrast.text>=4.5,true,theme+': source text');eq(contrast.icon>=3,true,theme+': source icons');eq(contrast.tab>=4.5,true,theme+': active tab');eq(contrast.neutral,true);eq(contrast.tabsFit,true);eq(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(width===440)await page.screenshot({path:`test-results/card-${theme}-expanded.png`,fullPage:true});
  const bad=structuredClone(states);bad['sensor.arandjelovac_jkp'].state='unavailable';bad['sensor.arandjelovac_jkp'].attributes.available=false;bad['sensor.arandjelovac_jkp'].attributes.error={message:'Quelle offline'};await setStates(bad);has(await card.locator('ha-card').innerText(),/Quelle nicht verfügbar/);has(await card.locator('ha-card').innerText(),/8\/9 Quellen erreichbar/);
  const diagnosed=structuredClone(states);diagnosed['sensor.arandjelovac_jkp']={state:'unavailable',attributes:{friendly_name:'Wasser'}};diagnosed['sensor.arandjelovac_jkp_source']={state:'error',attributes:{integration_domain:'arandjelovac_live',entity_kind:'source_health',provider:'jkp',available:false,count_entity_id:'sensor.arandjelovac_jkp',error:{message:'Diagnose bleibt sichtbar'},last_success:now.toISOString()}};await setStates(diagnosed);has(await card.locator('ha-card').innerText(),/Diagnose bleibt sichtbar/);lacks(await card.locator('details[data-panel="jkp"]').innerText(),/Quelle nicht eingerichtet/);
  const partial=structuredClone(states);partial['sensor.arandjelovac_kultura'].state='unavailable';partial['sensor.arandjelovac_kultura'].attributes.available=false;await setStates(partial);has(await events.locator('.event-errors > summary').innerText(),/1\/5 Veranstaltungsquellen nicht verfügbar/);eq(await tab('dates').locator('.tab-count').innerText(),'1');
  const allFailed=structuredClone(partial);for(const key of ['tourism','museum','library','manifestations']){allFailed['sensor.arandjelovac_'+key].state='unavailable';allFailed['sensor.arandjelovac_'+key].attributes.available=false;}await setStates(allFailed);eq(await tab('dates').locator('.tab-count').innerText(),'–');has(await events.innerText(),/Veranstaltungsquellen derzeit nicht verfügbar/);
  const attack=structuredClone(states);attack['sensor.arandjelovac_opstina'].attributes.items=[{title:'<img src=x onerror="window.PWNED=true">',description:'<script>BAD</script>',source_url:'javascript:alert(1)'}];await setStates(attack);eq(await card.locator('img').count(),0);eq(await card.locator('a[href^="javascript:"]').count(),0);eq(await page.evaluate(()=>window.PWNED),undefined);
 }
 const card=page.locator('arandjelovac-live-card').first(),events=card.locator('section[data-panel="events"]'),tab=key=>events.locator(`button[data-event-tab="${key}"]`);
 const expired=structuredClone(states);expired['sensor.arandjelovac_putevi'].attributes.items[0].status='deadline_passed';await setStates(expired);has(await card.locator('details[data-panel="putevi"] > summary').innerText(),/Frist abgelaufen · Freigabe unbestätigt/);
 const incident=structuredClone(states);incident['sensor.arandjelovac_jkp'].attributes.items[0].status='unconfirmed';await setStates(incident);has(await card.locator('details[data-panel="jkp"] > summary').innerText(),/Unterbruch gemeldet · Ende prüfen/);
 const categories=structuredClone(states);
 categories['sensor.arandjelovac_kultura'].attributes.items=['theatre','concert','exhibition','reading','market','festival'].map((type,i)=>({id:'type-'+i,title:'Kategorie '+type,event_type:type,kind:'event',start_at:future,status:'scheduled',source_url:'https://centarzakulturuarandjelovac.rs/type-'+i}));
 categories['sensor.arandjelovac_manifestations'].attributes.items=[['Sommer','JUL - AVGUST'],['Sommermonate','u toku letnjih meseci'],['Gulasch','poslednja nedelja septembra'],['Kyrillischer Monat','децембар'],['Konzert','1.06. - 4.06.']].map(([title,season_label],i)=>({id:'season-'+i,title,season_label,kind:'seasonal',status:'seasonal',source_url:'https://bukovickabanja.rs/season-'+i}));
 await setStates(categories);await tab('dates').click();
 for(const [type,symbol] of Object.entries({theatre:'drama-masks',concert:'music',exhibition:'palette-outline',reading:'book-open-page-variant',market:'store-outline',festival:'party-popper'}))eq(await events.locator('.event-record').filter({hasText:'Kategorie '+type}).locator('.event-type ha-icon').getAttribute('icon'),'mdi:'+symbol);
 await tab('season').click();eq(await events.locator('.season-month').allTextContents(),['JUL–AUG','SOMMER','SEP','DEZ','JUN']);lacks(await events.locator('#events-pane-season').textContent(),/2026|2027/);
 const temporal=structuredClone(states);temporal['sensor.arandjelovac_library'].attributes.items=[];temporal['sensor.arandjelovac_kultura'].attributes.items=[
  {id:'midnight',title:'Nach Mitternacht',start_at:'2026-10-14T22:30:00Z',kind:'event'},
  {id:'old',title:'GESTERN_UNSICHTBAR',event_date:'2026-10-13',kind:'event'},
  {id:'ended',title:'BEENDET_UNSICHTBAR',start_at:'2026-10-14T10:00:00Z',end_at:'2026-10-14T14:00:00Z',kind:'event'},
  {id:'past-start',title:'Schon begonnen',start_at:'2026-10-14T12:00:00Z',kind:'event'},
  {id:'today',title:'Nur heutiges Datum',event_date:'2026-10-14',kind:'event'}
 ];await setStates(temporal);await tab('dates').click();
 lacks(await events.textContent(),/GESTERN_UNSICHTBAR|BEENDET_UNSICHTBAR/);const midnight=events.locator('.event-record').filter({hasText:'Nach Mitternacht'});eq(await midnight.locator('time').getAttribute('datetime'),'2026-10-15');has(await midnight.locator('summary').innerText(),/Morgen · 00:30/);has(await events.locator('.event-record').filter({hasText:'Schon begonnen'}).locator('summary').innerText(),/Beginn vergangen/);
 await page.clock.setFixedTime(new Date('2026-10-15T00:05:00+02:00'));await force();lacks(await events.textContent(),/Schon begonnen|Nur heutiges Datum/);has(await midnight.locator('summary').innerText(),/Heute · 00:30/);await page.clock.setFixedTime(now);
 const unsafe=structuredClone(states);unsafe['sensor.arandjelovac_kultura'].attributes.items=[{id:'"><img src=x onerror="window.PWNED=true">',title:'<script>EVENT_ATTACK</script>',description:longDescription+' <img src=x onerror="window.PWNED=true">',source_url:'javascript:alert(1)',kind:'announcement'}];await setStates(unsafe);await tab('preview').click();const unsafeRow=events.locator('#events-pane-preview .event-record');await unsafeRow.locator('summary').click();eq(await events.locator('img,script').count(),0);eq(await unsafeRow.locator('a').count(),0);has(await unsafeRow.locator('.event-body').innerText(),/<img src=x/);eq(await page.evaluate(()=>window.PWNED),undefined);
 const announcementsOnly=structuredClone(states);announcementsOnly['sensor.arandjelovac_library'].attributes.items=[];announcementsOnly['sensor.arandjelovac_kultura'].attributes.items=announcementsOnly['sensor.arandjelovac_kultura'].attributes.items.filter(i=>!i.start_at);
 await page.evaluate(states=>{const c=document.createElement('arandjelovac-live-card');c.id='second-card';c.setConfig({});c.hass={states};document.getElementById('mount').appendChild(c);},announcementsOnly);
 const second=page.locator('#second-card');eq(await second.locator('button[data-event-tab="preview"]').getAttribute('aria-selected'),'true');await second.locator('button[data-event-tab="season"]').click();eq(await tab('preview').getAttribute('aria-selected'),'true');await second.evaluate(c=>c.remove());
 const emptyPreview=structuredClone(states);emptyPreview['sensor.arandjelovac_kultura'].attributes.items=[];await setStates(emptyPreview);eq(await tab('preview').getAttribute('aria-selected'),'true');has(await events.locator('#events-pane-preview').innerText(),/Keine Kulturmeldungen ohne Datum/);
 eq(errors,[]);await browser.close();console.log(JSON.stringify({browser:'Chromium',themes:Object.keys(palettes),widths:[320,440,736],assertions:checks,errors}));
})().catch(error=>{console.error(error);process.exit(1)});
