/* Real browser assertions for the delivered custom card. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const registryPolyfill=require.resolve('@webcomponents/scoped-custom-element-registry');
const code=fs.readFileSync(path.join(__dirname,'../../custom_components/arandjelovac_live/frontend/arandjelovac-live-card.js'),'utf8');
const now=new Date(),future=new Date(now.getTime()+86400000).toISOString();
const states={};
const add=(provider,items,extra={})=>{states['sensor.arandjelovac_'+provider]={entity_id:'sensor.arandjelovac_'+provider,state:String(items.length),attributes:{integration_domain:'arandjelovac_live',provider,available:true,items,last_success:now.toISOString(),metadata:{},...extra}};};
add('eds',[{area:'Vožda Karađorđa',start_at:future,end_at:new Date(Date.parse(future)+3600000).toISOString(),status:'geplant',source_url:'https://www.elektrodistribucija.rs/planirana-iskljucenja/planirana-kv'}],{coverage_end:'2026-10-17',coverage_complete:true});
add('jkp',[{title:'Information',kind:'water_unknown',status:'image_only',published_at:now.toISOString(),description:'Bildbeitrag',source_url:'https://www.jkpbukulja.rs/vesti'}],{metadata:{unreadable_notices:1}});
add('putevi',[{title:'Lazarevac – Darosava',description:'Umleitung',status:'published',kind:'closure',source_url:'https://www.putevi-srbije.rs/'}]);
add('kultura',[{id:'1',title:'Film',start_at:future,kind:'event',status:'scheduled',source_url:'https://centarzakulturuarandjelovac.rs/'}]);
add('tourism',[]);add('opstina',[{title:'News',description:'Information',status:'published',source_url:'https://arandjelovac.rs/'}]);
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{})});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let checks=0;
 // HA replaces the native registry during startup. Extra frontend modules can
 // execute before that replacement, while dashboard resources execute later.
 for(const order of ['before-polyfill','before-host','after-host']){
  await page.goto('about:blank');
  if(order==='before-polyfill')await page.addScriptTag({content:code});
  await page.addScriptTag({path:registryPolyfill});
  if(order==='before-host')await page.addScriptTag({content:code});
  assert.equal(await page.evaluate(()=>customElements.get('arandjelovac-live-card')===undefined),true,order+': wait for HA registry');checks++;
  await page.evaluate(()=>customElements.define('home-assistant',class extends HTMLElement{}));
  if(order==='after-host')await page.addScriptTag({content:code});
  await page.waitForFunction(()=>customElements.get('arandjelovac-live-card'));
  assert.equal(await page.evaluate(()=>{const c=document.createElement('arandjelovac-live-card');c.setConfig({});return !!c.shadowRoot.querySelector('ha-card');}),true,order+': construct with active HTMLElement');checks++;
  // A manual resource and the automatic module may both load the card.
  await page.addScriptTag({content:code});
  assert.equal(await page.evaluate(()=>window.customCards.filter(c=>c.type==='arandjelovac-live-card').length),1,order+': duplicate loading');checks++;
 }
 for(const theme of ['light','dark'])for(const width of [320,440,736]){
  await page.goto('about:blank');
  await page.setViewportSize({width,height:1200});
  await page.setContent(`<html style="color-scheme:${theme}"><body style="margin:0;${theme==='dark'?'--primary-text-color:#edf2f8;--secondary-text-color:#b2c0d1;--ha-card-background:#202b39;--divider-color:#354252;':''}"><div id="mount"></div></body></html>`);
  await page.addScriptTag({path:registryPolyfill});
  await page.evaluate(()=>customElements.define('home-assistant',class extends HTMLElement{}));
  await page.addScriptTag({content:code});
  await page.waitForFunction(()=>customElements.get('arandjelovac-live-card'));
  await page.evaluate(states=>{const card=document.createElement('arandjelovac-live-card');card.setConfig({type:'custom:arandjelovac-live-card'});card.hass={states};document.getElementById('mount').appendChild(card);},states);
  const card=page.locator('arandjelovac-live-card');
  assert.match(await card.locator('ha-card').innerText(),/Veranstaltungen & News/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/6\/6 geprüft/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/Bildmeldungen · Inhalt prüfen/);checks++;
  await card.locator('details[data-panel="eds"] > summary').click();
  assert(await card.locator('details[data-panel="eds"]').evaluate(e=>e.open));checks++;
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states:structuredClone(states)};},states);
  assert(await card.locator('details[data-panel="eds"]').evaluate(e=>e.open));checks++;
  for(const panel of ['jkp','putevi','events','opstina','sources'])await card.locator(`details[data-panel="${panel}"] > summary`).click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);checks++;
  const bad=structuredClone(states);bad['sensor.arandjelovac_jkp'].state='unavailable';bad['sensor.arandjelovac_jkp'].attributes.available=false;bad['sensor.arandjelovac_jkp'].attributes.error={message:'Quelle offline'};
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},bad);
  assert.match(await card.locator('ha-card').innerText(),/Quelle nicht verfügbar/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/5\/6 geprüft/);checks++;
  // Match real HA: unavailable main sensors have no normal extra attributes.
  const diagnosed=structuredClone(states);diagnosed['sensor.arandjelovac_jkp']={state:'unavailable',attributes:{friendly_name:'Wasser'}};
  diagnosed['sensor.arandjelovac_jkp_source']={state:'error',attributes:{integration_domain:'arandjelovac_live',entity_kind:'source_health',provider:'jkp',available:false,count_entity_id:'sensor.arandjelovac_jkp',error:{message:'Diagnose bleibt sichtbar'},last_success:now.toISOString()}};
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},diagnosed);
  assert.match(await card.locator('ha-card').innerText(),/Diagnose bleibt sichtbar/);checks++;
  assert.doesNotMatch(await card.locator('details[data-panel="jkp"]').innerText(),/Quelle nicht eingerichtet/);checks++;
  const attack=structuredClone(states);attack['sensor.arandjelovac_opstina'].attributes.items=[{title:'<img src=x onerror="window.PWNED=true">',description:'<script>BAD</script>',source_url:'javascript:alert(1)'}];
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},attack);
  assert.equal(await card.locator('img').count(),0);assert.equal(await card.locator('a[href^="javascript:"]').count(),0);checks+=2;
  assert.equal(await page.evaluate(()=>window.PWNED),undefined);checks++;
 }
 await page.setViewportSize({width:440,height:1200});
 await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},states);
 fs.mkdirSync('test-results',{recursive:true});
 await page.screenshot({path:'test-results/card-dark.png',fullPage:true});
 assert.deepEqual(errors,[]);checks++;
 await browser.close();console.log(JSON.stringify({browser:'Chromium',themes:2,widths:[320,440,736],assertions:checks,errors}));
})().catch(e=>{console.error(e);process.exit(1)});
