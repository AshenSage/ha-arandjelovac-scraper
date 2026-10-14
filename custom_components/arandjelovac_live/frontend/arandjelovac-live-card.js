/* Aranđelovac Live 1.2.2 — self-contained HA card, no browser-side scraping. */
// HA's scoped-registry polyfill replaces both customElements and HTMLElement.
// Wait before creating the class, not just before defining its tag. A native
// whenDefined promise also resolves when HA registers its polyfill stand-in.
// See home-assistant/frontend#53890. Scope everything for duplicate resources.
customElements.whenDefined('home-assistant').then(() => {
const PROVIDERS = {
  eds: {name:'EDS · Strom',icon:'mdi:lightning-bolt',title:'Strom',url:'https://www.elektrodistribucija.rs/planirana-iskljucenja/planirana-kv'},
  jkp: {name:'JKP Bukulja · Wasser',icon:'mdi:water',title:'Wasser',url:'https://www.jkpbukulja.rs/vesti'},
  putevi: {name:'Putevi Srbije · Verkehr',icon:'mdi:road-variant',title:'Verkehr · Umgebung',url:'https://www.putevi-srbije.rs/index.php/sr/stanje-na-drzavnim-putevima'},
  opstina: {name:'Opština · Gemeinde',icon:'mdi:newspaper-variant-outline',title:'Neu aus der Gemeinde',url:'https://arandjelovac.rs/category/informator/novosti/'},
  kultura: {name:'Kulturzentrum',icon:'mdi:theater',title:'Veranstaltungen',url:'https://centarzakulturuarandjelovac.rs/'},
  tourism: {name:'Tourismusorganisation',icon:'mdi:calendar-star',title:'Tourismus',url:'https://bukovickabanja.rs/category/vesti/'}
};
const HOSTS=new Set(Object.values(PROVIDERS).map(p=>new URL(p.url).hostname));
const TZ='Europe/Belgrade';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const validDate=v=>typeof v==='string'&&Number.isFinite(Date.parse(v));
const dateFormat=(v,opts)=>validDate(v)?new Intl.DateTimeFormat('de-CH',{timeZone:TZ,...opts}).format(new Date(v)):'';
const dateKey=v=>dateFormat(v,{year:'numeric',month:'2-digit',day:'2-digit'});
const dayLabel=v=>{
  if(!validDate(v))return 'Datum nicht angegeben';
  const now=new Date();if(dateKey(v)===dateKey(now.toISOString()))return 'Heute';
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:TZ,year:'numeric',month:'numeric',day:'numeric'}).formatToParts(now).map(p=>[p.type,p.value]));
  const tomorrow=new Date(Date.UTC(Number(parts.year),Number(parts.month)-1,Number(parts.day)+1,12));
  if(dateKey(v)===dateKey(tomorrow.toISOString()))return 'Morgen';
  return dateFormat(v,{weekday:'short',day:'numeric',month:'short'});
};
const timeLabel=v=>dateFormat(v,{hour:'2-digit',minute:'2-digit'});
const ago=v=>{
  if(!validDate(v))return 'Noch kein erfolgreicher Abruf';
  const minutes=Math.floor((Date.now()-Date.parse(v))/60000);
  if(minutes<0)return 'Zeitstempel prüfen';
  if(minutes<1)return 'Gerade geprüft';if(minutes<60)return `vor ${minutes} Min.`;
  const hours=Math.floor(minutes/60);if(hours<24)return `vor ${hours} Std.`;
  return dateFormat(v,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
};
const safeLink=v=>{try{const u=new URL(v);return u.protocol==='https:'&&HOSTS.has(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443')?u.href:'';}catch{return '';}};
const icon=name=>`<ha-icon icon="${esc(name)}" aria-hidden="true"></ha-icon>`;
const cyr='АБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШабвгдђежзијклљмнњопрстћуфхцчџш';
const latin=['A','B','V','G','D','Đ','E','Ž','Z','I','J','K','L','Lj','M','N','Nj','O','P','R','S','T','Ć','U','F','H','C','Č','Dž','Š','a','b','v','g','d','đ','e','ž','z','i','j','k','l','lj','m','n','nj','o','p','r','s','t','ć','u','f','h','c','č','dž','š'];
const translit=Object.fromEntries([...cyr].map((c,i)=>[c,latin[i]]));
const statuses={in_window:'Im geplanten Zeitfenster',image_only:'Bildbeitrag · Inhalt nicht ausgewertet',scheduled:'Geplant',unconfirmed:'Ende unbestätigt',historical_unconfirmed:'Ältere Meldung · Ende unbestätigt',restored:'Normalisierung gemeldet',information:'Information',published:'Veröffentlicht',deadline_passed:'Frist abgelaufen · weiterhin veröffentlicht',announcement:'Ankündigung ohne bestätigten Termin',start_passed:'Beginn vergangen · Ende nicht angegeben'};
const eventTypes={cinema:'Kino',theatre:'Theater',concert:'Konzert',exhibition:'Ausstellung'};
const trafficKinds={closure:'Sperrung',landslide:'Erdrutsch',restriction:'Beschränkung',roadworks:'Bauarbeiten'};
const deadlineLabel=record=>/^\d{4}-\d{2}-\d{2}$/.test(record?.deadline_date||'')?dateFormat(record.deadline_date+'T12:00:00Z',{day:'2-digit',month:'2-digit',year:'numeric'}):'';

class ArandjelovacLiveCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._states={};this._config={};this._unsubscribe=null;this._timer=null;this._signature='';}
  setConfig(config){
    if(config.entities&&typeof config.entities!=='object')throw Error('entities muss eine Zuordnung von Quelle zu Entitäts-ID sein.');
    this._config={title:'Aranđelovac Live',max_items:8,transliterate:true,...config};
    this._config.max_items=Math.min(20,Math.max(1,Number(this._config.max_items)||8));this._render();
  }
  set hass(hass){this._states=hass?.states||{};this._render();}
  connectedCallback(){
    const request=new CustomEvent('context-request',{bubbles:true,composed:true,cancelable:true});
    request.context='states';request.subscribe=true;
    request.callback=(states,unsubscribe)=>{this._states=states||{};if(unsubscribe)this._unsubscribe=unsubscribe;this._render();};
    this.dispatchEvent(request);this._render();
    this._timer=setInterval(()=>this._render(true),60000);
  }
  disconnectedCallback(){clearInterval(this._timer);this._timer=null;if(this._unsubscribe){this._unsubscribe();this._unsubscribe=null;}}
  getCardSize(){return 12;}
  getGridOptions(){return {columns:12,min_columns:6};}
  static getStubConfig(){return {type:'custom:arandjelovac-live-card',title:'Aranđelovac Live'};}
  _text(v){const value=String(v??'');return this._config.transliterate===false?value:[...value].map(c=>translit[c]??c).join('');}
  _source(key){
    const override=this._config.entities?.[key];
    const diagnostic=Object.values(this._states).find(s=>s.attributes?.provider===key&&s.attributes?.integration_domain==='arandjelovac_live'&&s.attributes?.entity_kind==='source_health');
    const linked=diagnostic?.attributes?.count_entity_id;
    const entity=override?this._states[override]:(linked&&this._states[linked])||Object.entries(this._states).filter(([id,s])=>id.startsWith('sensor.')&&s.attributes?.provider===key&&s.attributes?.entity_kind!=='source_health'&&(s.attributes.integration_domain==='arandjelovac_live'||id.startsWith('sensor.arandjelovac_'))).sort(([a],[b])=>a.localeCompare(b))[0]?.[1];
    const a={...(diagnostic?.attributes||{}),...(entity?.attributes||{})};
    const healthy=!!entity&&!['unknown','unavailable'].includes(entity.state)&&a.available===true&&/^\d+$/.test(String(entity.state));
    return {entity,a,healthy,missing:!entity&&!diagnostic,items:healthy&&Array.isArray(a.items)?a.items:[],count:healthy?Number(entity.state):null};
  }

  _link(url,label='Original öffnen'){
    const safe=safeLink(url);return safe?`<a class="source" href="${esc(safe)}" target="_blank" rel="noopener noreferrer">${esc(label)} ${icon('mdi:open-in-new')}</a>`:'';
  }
  _unavailable(source){return `<div class="notice">${esc(source.missing?'Diese Quelle ist noch nicht eingerichtet.':source.a.error?.message||'Die Quelle kann derzeit nicht zuverlässig ausgewertet werden.')}<div class="small">${esc(ago(source.a.last_success))}</div></div>`;}
  _panel(key,title,headline,meta,content,{warn=false,iconName=null}={}){
    return `<details data-panel="${esc(key)}" class="panel ${warn?'warning':''}"><summary><span class="symbol">${icon(iconName||PROVIDERS[key]?.icon||'mdi:calendar-month')}</span><span class="copy"><span class="label">${esc(title)}</span><span class="headline">${esc(headline)}</span><span class="meta">${esc(meta)}</span></span>${icon('mdi:chevron-down')}</summary><div class="body">${content}</div></details>`;
  }
  _record(record){
    const time=record.start_at?`${dayLabel(record.start_at)} · ${timeLabel(record.start_at)}${record.end_at&&record.end_precision!=='date'?'–'+timeLabel(record.end_at):''}`:dateFormat(record.published_at,{day:'numeric',month:'long',year:'numeric'});
    const type=eventTypes[record.event_type]||(record.kind==='event'?'Veranstaltung':'');
    const status=statuses[record.status]||'Veröffentlichte Meldung';
    const deadline=deadlineLabel(record);
    const description=record.program_split?'':record.description||'';
    return `<article class="record"><div class="when">${esc([type,time].filter(Boolean).join(' · '))}</div><div class="record-title">${esc(this._text(record.title||record.area||'Meldung'))}</div>${description?`<div class="description">${esc(this._text(description))}</div>`:''}<span class="tag">${esc(status)}</span>${deadline?`<div class="small">Genannte Frist: ${esc(deadline)}</div>`:''}${record.program_split?'<div class="small">Einzeltermin aus dem veröffentlichten Programm.</div>':''}${this._link(record.source_url)}</article>`;
  }
  _trafficHeadline(record){
    const kind=trafficKinds[record.kind]||'Verkehrsmeldung';
    return record.route?`${kind} ${this._text(record.route)}`:this._text(String(record.title||kind).replace(/^\s*\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\.\s*/,''));
  }
  _trafficMeta(record){
    const deadline=deadlineLabel(record);
    const timing=record.status==='deadline_passed'?'Frist abgelaufen · Freigabe unbestätigt':deadline?`angekündigt bis ${deadline}`:'Ende nicht angegeben';
    return [this._text(record.place||''),timing].filter(Boolean).join(' · ');
  }
  _limit(source){return source.a.items_truncated||source.items.length>this._config.max_items?'<div class="small">Die Übersicht zeigt einen Ausschnitt. Weitere Informationen stehen in der Originalquelle.</div>':'';}
  _render(force=false){
    const src=Object.fromEntries(Object.keys(PROVIDERS).map(k=>[k,this._source(k)]));
    const signature=JSON.stringify([this._config,...Object.values(src).map(s=>[s.entity,s.a])]);
    if(!force&&signature===this._signature)return;this._signature=signature;
    const open=new Set([...this.shadowRoot.querySelectorAll('details[open]')].map(e=>e.dataset.panel));
    const max=this._config.max_items;let cards='';
    const eds=src.eds,first=eds.items[0];
    const coverage=eds.a.coverage_end?dateFormat(eds.a.coverage_end+'T12:00:00+02:00',{day:'numeric',month:'short'}):'';
    let body=eds.healthy?eds.items.slice(0,max).map(record=>this._record({...record,title:record.area,description:'',status:record.status==='laufend'?'in_window':record.status==='geplant'?'scheduled':record.status})).join('')||'<div class="description">Keine noch nicht abgelaufenen Einträge im geprüften Zeitraum.</div>':this._unavailable(eds);
    if(eds.healthy)body+=`<div class="small">EDS-Veröffentlichungen geprüft bis ${esc(coverage)}.${eds.a.coverage_complete===false?' Für spätere Tage liegt noch keine vollständig geprüfte Abdeckung vor.':''} Gemeindeweite Liste; den betroffenen Strassenabschnitt prüfen.</div>`+this._limit(eds)+this._link(PROVIDERS.eds.url,'EDS · Quelle öffnen');
    cards+=this._panel('eds',eds.healthy?`Strom · ${eds.count} geplante ${eds.count===1?'Abschaltung':'Abschaltungen'}`:'Strom',eds.healthy?(first?`${dayLabel(first.start_at)}, ${timeLabel(first.start_at)}–${timeLabel(first.end_at)}`:'Keine geplanten Einträge'):(eds.missing?'Quelle nicht eingerichtet':'Quelle nicht verfügbar'),eds.healthy?(first?this._text(first.area):`Geprüft bis ${coverage}`):'Keine verlässliche Zählung',body,{warn:eds.healthy&&eds.count>0});
    const water=src.jkp;const incident=water.items.find(i=>['unconfirmed','scheduled'].includes(i.status));
    body=water.healthy?water.items.slice(0,max).map(i=>this._record(i)).join('')||'<div class="description">Keine Wassermeldungen im geprüften Ausschnitt und Anzeigezeitraum.</div>':this._unavailable(water);
    if(water.healthy)body+='<div class="small">Veröffentlichte Meldungen; keine Messung der Versorgung im Haus. Ältere Meldungen ohne Entwarnung werden als solche gekennzeichnet.</div>'+this._limit(water);
    const waterLabel=water.healthy?`${water.count} ${water.count===1?'Wassermeldung':'Wassermeldungen'}`:'Wasser';
    const waterImages=!!water.a.metadata?.unreadable_notices;
    cards+=this._panel('jkp','Wasser · JKP Bukulja',water.healthy?(incident?'Unterbruch gemeldet · Ende prüfen':waterLabel):(water.missing?'Quelle nicht eingerichtet':'Quelle nicht verfügbar'),water.healthy?(incident?[waterLabel,waterImages?'Teilweise als Bild – Original öffnen':dateFormat(incident.published_at,{day:'numeric',month:'long'})].join(' · '):waterImages?'Teilweise als Bild – Original öffnen':'Keine neue Unterbruchsmeldung'):'Meldungsstand unbekannt',body,{warn:!!incident});
    const traffic=src.putevi;
    body=traffic.healthy?traffic.items.slice(0,max).map(i=>this._record(i)).join('')||'<div class="description">Keine veröffentlichten Treffer für die eingestellten Orte.</div>':this._unavailable(traffic);
    if(traffic.healthy)body+=`<div class="small">Ortsfilter: ${esc((traffic.a.metadata?.areas||[]).join(', '))}. Eine Meldung ohne bestätigte Aufhebung ist kein gemessener Verkehrszustand.</div>`+this._limit(traffic);
    const trafficFirst=traffic.items.find(i=>i.kind==='closure'&&i.status!=='deadline_passed')||traffic.items.find(i=>i.status!=='deadline_passed')||traffic.items[0];
    cards+=this._panel('putevi','Verkehr · Umgebung'+(traffic.healthy&&traffic.count>1?` · ${traffic.count} Meldungen`:''),traffic.healthy?(trafficFirst?this._trafficHeadline(trafficFirst):'Keine passenden Meldungen'):(traffic.missing?'Quelle nicht eingerichtet':'Quelle nicht verfügbar'),trafficFirst?this._trafficMeta(trafficFirst):'Putevi Srbije',body,{warn:traffic.healthy&&traffic.items.some(i=>i.kind==='closure'&&i.status!=='deadline_passed')});
    cards+='<div class="section-title">Veranstaltungen &amp; News</div>';
    const eventSources=[src.kultura,src.tourism],eventRows=[];const seen=new Set();
    for(const [index,s]of eventSources.entries())for(const i of s.items){const id=`${i.source_url}|${i.start_at||''}|${i.title}`;if(!seen.has(id)){seen.add(id);eventRows.push({...i,_provider:index?'tourism':'kultura'});}}
    eventRows.sort((a,b)=>(!a.start_at)-(!b.start_at)||(a.start_at||'').localeCompare(b.start_at||''));
    const upcoming=eventRows.find(i=>validDate(i.start_at)&&Date.parse(i.start_at)>Date.now());
    const healthyEvents=eventSources.filter(s=>s.healthy).length;
    body=eventRows.slice(0,max).map(i=>this._record(i)).join('');
    if(!eventRows.length&&healthyEvents)body='<div class="description">Keine Termine oder Ankündigungen im aktuellen Feed-Ausschnitt und Anzeigezeitraum.</div>';
    if(!src.kultura.healthy)body+=`<div class="small">Kulturzentrum</div>${this._unavailable(src.kultura)}`;
    if(!src.tourism.healthy)body+=`<div class="small">Tourismusorganisation</div>${this._unavailable(src.tourism)}`;
    body+='<div class="small">Kulturzentrum &amp; Tourismus · aktueller Feed-Ausschnitt. Vorankündigungen ohne bestätigten Termin werden separat bezeichnet.</div>';
    if(eventRows.length>max||eventSources.some(s=>s.a.items_truncated))body+='<div class="small">Weitere Meldungen in den Originalquellen.</div>';
    cards+=this._panel('events','Kultur & Veranstaltungen',upcoming?`${eventTypes[upcoming.event_type]||'Veranstaltung'} · ${dayLabel(upcoming.start_at)}, ${timeLabel(upcoming.start_at)}`:healthyEvents?'Termine & Ankündigungen':'Quellen nicht verfügbar',upcoming?this._text(upcoming.title):`${healthyEvents}/2 Quellen auswertbar`,body,{iconName:'mdi:calendar-star'});
    const news=src.opstina;
    body=news.healthy?news.items.slice(0,max).map(i=>this._record(i)).join('')||'<div class="description">Keine Gemeindemeldungen im Anzeigezeitraum.</div>':this._unavailable(news);
    if(news.healthy)body+=this._limit(news);
    cards+=this._panel('opstina','Neu aus der Gemeinde',news.healthy?(news.items[0]?this._text(news.items[0].title):'Keine neuen Meldungen'):(news.missing?'Quelle nicht eingerichtet':'Quelle nicht verfügbar'),news.items[0]?dateFormat(news.items[0].published_at,{day:'numeric',month:'long'}):'Opština Aranđelovac',body);
    const healthy=Object.values(src).filter(s=>s.healthy).length;
    const health=Object.entries(src).map(([key,s])=>`<div class="provider"><span>${esc(PROVIDERS[key].name)}</span><span class="provider-state ${s.healthy?'good':''}">${icon(s.healthy?'mdi:check-circle-outline':'mdi:help-circle-outline')}${esc(s.healthy?ago(s.a.last_success):s.missing?'Nicht eingerichtet':'Nicht verfügbar')}</span></div>`).join('');
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;--ar-text:var(--primary-text-color,#253448);--ar-sub:var(--secondary-text-color,#647488);--ar-surface:var(--ha-card-background,var(--card-background-color,#fff));--ar-line:var(--divider-color,#e3e8ef);--ar-accent:var(--primary-color,#3678bb);--ar-warn:color-mix(in srgb,var(--warning-color,#d39b25) 65%,var(--ar-text));--ar-good:color-mix(in srgb,var(--success-color,#438664) 55%,var(--ar-text))}
      *{box-sizing:border-box}ha-card{display:block;padding:17px 14px 13px;background:var(--ar-surface);color:var(--ar-text);font-family:var(--primary-font-family,Roboto,Arial,sans-serif);font-size:14px;line-height:1.5}h2{font-size:24px;font-weight:500;letter-spacing:-.5px;margin:3px 0 4px}.kicker{display:flex;gap:5px;align-items:center;font-size:12px;color:var(--ar-sub)}.kicker ha-icon{--mdc-icon-size:14px}.intro{font-size:13px;color:var(--ar-sub);margin-bottom:13px}.panel{background:var(--ar-surface);border:1px solid var(--ar-line);border-radius:14px;margin-bottom:9px;overflow:hidden}summary{display:flex;align-items:flex-start;gap:10px;min-height:72px;padding:12px;list-style:none;cursor:pointer}summary::-webkit-details-marker{display:none}.symbol{flex:0 0 34px;height:34px;border-radius:10px;display:grid;place-items:center;background:color-mix(in srgb,var(--ar-accent) 12%,var(--ar-surface));color:var(--ar-accent)}.symbol ha-icon{--mdc-icon-size:20px}.copy{display:flex;flex:1;min-width:0;flex-direction:column;gap:2px}.label,.meta{color:var(--ar-sub);font-size:12px}.headline{font-size:15px;font-weight:500;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.meta{overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}summary>ha-icon{--mdc-icon-size:17px;flex:0 0 17px;margin-top:13px;color:var(--ar-sub);transition:transform .15s}details[open]>summary>ha-icon{transform:rotate(180deg)}.warning{border-color:var(--ar-warn);box-shadow:inset 3px 0 0 var(--ar-warn)}.warning .symbol{background:color-mix(in srgb,var(--ar-warn) 10%,var(--ar-surface));color:var(--ar-warn)}.body{padding:0 14px 15px}.body:before{content:'';display:block;border-top:1px solid var(--ar-line);margin-bottom:13px}.record{margin-bottom:17px}.record:last-child{margin-bottom:0}.when{color:var(--ar-sub);font-size:12px;margin-bottom:4px}.record-title{font-weight:500;overflow-wrap:anywhere}.description{font-size:13px;color:var(--ar-sub);margin-top:5px;white-space:pre-line;overflow-wrap:anywhere}.source{display:flex;align-items:center;gap:5px;width:fit-content;min-height:44px;font-size:12px;color:var(--ar-accent);text-decoration:none}.source:hover{text-decoration:underline}.source ha-icon{--mdc-icon-size:13px}.tag{display:inline-block;margin-top:7px;padding:3px 7px;border-radius:6px;background:color-mix(in srgb,var(--ar-accent) 9%,var(--ar-surface));font-size:11px}.small{font-size:12px;color:var(--ar-sub);margin-top:8px;overflow-wrap:anywhere}.notice{font-size:13px;color:var(--ar-sub)}.section-title{margin:19px 2px 10px;font-size:13px;color:var(--ar-sub);font-weight:500}.health summary{align-items:center;min-height:52px;padding:12px;gap:8px}.health summary>ha-icon{margin:0}.health-label{flex:1;font-size:12px;color:var(--ar-sub)}.health-count{font-size:12px;color:var(--ar-text);text-align:right}.provider{display:flex;justify-content:space-between;gap:8px;padding:9px 0;border-bottom:1px solid var(--ar-line);font-size:12px}.provider:last-child{border:0}.provider-state{display:flex;gap:4px;align-items:center;text-align:right;color:var(--ar-sub)}.provider-state ha-icon{--mdc-icon-size:14px;flex:0 0 14px}.good{color:var(--ar-text)}.good ha-icon{color:var(--ar-good)}.footer{font-size:11px;color:var(--ar-sub);margin:9px 2px 0}@media(max-width:350px){ha-card{padding:14px 10px}.provider{flex-direction:column;gap:2px}summary{padding:11px 10px;gap:9px}.headline{font-size:14px}}@media(prefers-reduced-motion:reduce){summary>ha-icon{transition:none}}
    </style><ha-card><div class="kicker">${icon('mdi:map-marker-outline')}Stadt &amp; Umgebung</div><h2>${esc(this._config.title)}</h2><div class="intro">${esc(dateFormat(new Date().toISOString(),{weekday:'long',day:'numeric',month:'long'}))} · Gemeindeweit</div>${cards}<details class="panel health" data-panel="sources"><summary>${icon('mdi:information-outline')}<span class="health-label">Quellen &amp; Aktualität</span><span class="health-count">${healthy}/6 Quellen erreichbar</span>${icon('mdi:chevron-down')}</summary><div class="body">${health}</div></details><div class="footer">Zeiten in Europe/Belgrade · Öffentliche Meldungen</div></ha-card>`;
    for(const details of this.shadowRoot.querySelectorAll('details'))if(open.has(details.dataset.panel))details.open=true;
  }
}
if(!customElements.get('arandjelovac-live-card'))customElements.define('arandjelovac-live-card',ArandjelovacLiveCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='arandjelovac-live-card'))window.customCards.push({type:'arandjelovac-live-card',name:'Aranđelovac Live',description:'Strom, Wasser, Verkehr, Veranstaltungen & News',preview:true});
}).catch(error=>console.error('Aranđelovac Live: Karte konnte nicht registriert werden.',error));
