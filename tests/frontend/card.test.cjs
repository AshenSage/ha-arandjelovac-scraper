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
add('putevi',[{title:'31.8.2026.Obustava na putu, deonica Lazarevac – Darosava (Belanovica), mesto Kruševica',route:'Lazarevac – Darosava (Belanovica)',place:'Kruševica',deadline_date:'2026-12-26',end_precision:'date',end_at:'2026-12-27T00:00:00+01:00',description:'Umleitung',status:'published',kind:'closure',source_url:'https://www.putevi-srbije.rs/'}]);
add('kultura',[{id:'1',title:'Film',start_at:future,kind:'event',event_type:'cinema',program_split:true,description:'WEEKLY_PROGRAM_SHOULD_NOT_REPEAT',status:'scheduled',source_url:'https://centarzakulturuarandjelovac.rs/'}]);
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
 const palettes={light:'',dark:'--primary-text-color:#edf2f8;--secondary-text-color:#b2c0d1;--ha-card-background:#202b39;--divider-color:#354252;',green:'--primary-text-color:#e7f4e8;--secondary-text-color:#b9cfc2;--ha-card-background:#355347;--divider-color:#607d6e;--primary-color:#a0d9b7;--success-color:#4caf50;--warning-color:#ffc107;'};
 fs.mkdirSync('test-results',{recursive:true});
 for(const [theme,palette] of Object.entries(palettes))for(const width of [320,440,736]){
  await page.goto('about:blank');
  await page.setViewportSize({width,height:1200});
  await page.setContent(`<html style="color-scheme:${theme==='light'?'light':'dark'}"><body style="margin:0;${palette}"><div id="mount"></div></body></html>`);
  await page.addScriptTag({path:registryPolyfill});
  await page.evaluate(()=>customElements.define('home-assistant',class extends HTMLElement{}));
  await page.addScriptTag({content:code});
  await page.waitForFunction(()=>customElements.get('arandjelovac-live-card'));
  await page.evaluate(states=>{const card=document.createElement('arandjelovac-live-card');card.setConfig({type:'custom:arandjelovac-live-card'});card.hass={states};document.getElementById('mount').appendChild(card);},states);
  const card=page.locator('arandjelovac-live-card');
  assert.match(await card.locator('ha-card').innerText(),/Veranstaltungen & News/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/6\/6 Quellen erreichbar/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/Teilweise als Bild – Original öffnen/);checks++;
  assert.match(await card.locator('details[data-panel="jkp"] > summary').innerText(),/1 Wassermeldung/);checks++;
  const trafficSummary=card.locator('details[data-panel="putevi"] > summary');
  assert.match(await trafficSummary.innerText(),/Sperrung Lazarevac – Darosava/);checks++;
  assert.match(await trafficSummary.innerText(),/Kruševica · angekündigt bis 26\.12\.2026/);checks++;
  assert.doesNotMatch(await trafficSummary.innerText(),/31\.8\.2026/);checks++;
  assert.equal(await trafficSummary.locator('ha-icon[icon="mdi:road-variant"]').count(),1);checks++;
  assert.match(await card.locator('details[data-panel="events"] > summary').innerText(),/Kino ·/);checks++;
  if(width===440)await page.screenshot({path:`test-results/card-${theme}-collapsed.png`,fullPage:true});
  await card.locator('details[data-panel="eds"] > summary').click();
  assert(await card.locator('details[data-panel="eds"]').evaluate(e=>e.open));checks++;
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states:structuredClone(states)};},states);
  assert(await card.locator('details[data-panel="eds"]').evaluate(e=>e.open));checks++;
  for(const panel of ['jkp','putevi','events','opstina','sources'])await card.locator(`details[data-panel="${panel}"] > summary`).click();
  assert.doesNotMatch(await card.locator('details[data-panel="events"]').innerText(),/WEEKLY_PROGRAM_SHOULD_NOT_REPEAT/);checks++;
  const contrast=await card.evaluate(card=>{
    const root=card.shadowRoot,canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
    const rgb=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].slice(0,3).map(x=>x/255);};
    const luminance=color=>rgb(color).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
    const background=getComputedStyle(root.querySelector('ha-card')).backgroundColor;
    const ratio=color=>{const a=luminance(color),b=luminance(background);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
    const warning=root.querySelector('.warning');
    return {text:ratio(getComputedStyle(root.querySelector('.provider-state.good')).color),icon:ratio(getComputedStyle(root.querySelector('.good ha-icon')).color),neutralWarnings:getComputedStyle(warning).backgroundColor===background};
  });
  assert(contrast.text>=4.5,`${theme}: readable source status ${contrast.text}`);checks++;
  assert(contrast.icon>=3,`${theme}: readable success icon ${contrast.icon}`);checks++;
  assert(contrast.neutralWarnings,`${theme}: warnings retain card surface`);checks++;
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);checks++;
  if(width===440)await page.screenshot({path:`test-results/card-${theme}-expanded.png`,fullPage:true});
  const bad=structuredClone(states);bad['sensor.arandjelovac_jkp'].state='unavailable';bad['sensor.arandjelovac_jkp'].attributes.available=false;bad['sensor.arandjelovac_jkp'].attributes.error={message:'Quelle offline'};
  await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},bad);
  assert.match(await card.locator('ha-card').innerText(),/Quelle nicht verfügbar/);checks++;
  assert.match(await card.locator('ha-card').innerText(),/5\/6 Quellen erreichbar/);checks++;
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
 const expired=structuredClone(states);
 expired['sensor.arandjelovac_putevi'].attributes.items[0].status='deadline_passed';
 await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},expired);
 assert.match(await page.locator('arandjelovac-live-card').locator('details[data-panel="putevi"] > summary').innerText(),/Frist abgelaufen · Freigabe unbestätigt/);checks++;
 const incident=structuredClone(states);incident['sensor.arandjelovac_jkp'].attributes.items[0].status='unconfirmed';
 await page.evaluate(states=>{document.querySelector('arandjelovac-live-card').hass={states};},incident);
 assert.match(await page.locator('arandjelovac-live-card').locator('details[data-panel="jkp"] > summary').innerText(),/Unterbruch gemeldet · Ende prüfen/);checks++;
 assert.deepEqual(errors,[]);checks++;
 await browser.close();console.log(JSON.stringify({browser:'Chromium',themes:Object.keys(palettes),widths:[320,440,736],assertions:checks,errors}));
})().catch(e=>{console.error(e);process.exit(1)});
