"""Independent bounded fetch/projection for each researched local source."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from typing import Any, Callable
from urllib.parse import urlencode

from ...common.http import HttpClient
from ...common.models import FetchResult, Projection, SourceError, SourceSpec, utcnow
from .parsers import (Article, event_items, item, matches_area, parse_bukulja_article,
                      parse_bukulja_index, parse_feed, parse_manifestations, parse_municipality, parse_traffic,
                      water_notice, water_related)
from .text import TZ, parse_iso

SOURCES = {
    'jkp': {'title':'JKP Bukulja · Wasser','sensor':'arandjelovac_jkp_water','key':'jkp_water','icon':'mdi:water',
            'url':'https://www.jkpbukulja.rs/vesti','minutes':15},
    'putevi': {'title':'Putevi Srbije · Verkehr','sensor':'arandjelovac_putevi_traffic','key':'putevi_traffic','icon':'mdi:road-variant',
               'url':'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt','minutes':15},
    'opstina': {'title':'Opština · Gemeindemeldungen','sensor':'arandjelovac_opstina_news','key':'opstina_news','icon':'mdi:newspaper-variant-outline',
                'url':'https://arandjelovac.rs/','minutes':60},
    'kultura': {'title':'Kulturzentrum · Veranstaltungen','sensor':'arandjelovac_kultura_events','key':'kultura_events','icon':'mdi:theater',
                'url':'https://centarzakulturuarandjelovac.rs/rss','minutes':120},
    'tourism': {'title':'Tourismus · Veranstaltungen','sensor':'arandjelovac_tourism_events','key':'tourism_events','icon':'mdi:calendar-star',
                'url':'https://bukovickabanja.rs/category/vesti/feed/','minutes':180},
    'museum': {'title':'Museum · Kulturprogramm','sensor':'arandjelovac_museum_events','key':'museum_events','icon':'mdi:bank',
               'url':'https://nmar.rs/feed/','minutes':180},
    'library': {'title':'Bibliothek · Lesungen','sensor':'arandjelovac_library_events','key':'library_events','icon':'mdi:bookshelf',
                'url':'https://www.nbssa.rs/feed/','minutes':180},
    'manifestations': {'title':'Feste & Basare · Tourismus','sensor':'arandjelovac_manifestations_events','key':'manifestations_events','icon':'mdi:calendar-month',
                      'url':'https://bukovickabanja.rs/manifestacije/','minutes':360},
}
HOSTS = {
    'jkp':frozenset({'www.jkpbukulja.rs'}),
    'putevi':frozenset({'www.putevi-srbije.rs'}),
    'opstina':frozenset({'arandjelovac.rs'}),
    'kultura':frozenset({'centarzakulturuarandjelovac.rs'}),
    'tourism':frozenset({'bukovickabanja.rs'}),
    'museum':frozenset({'nmar.rs'}),
    'library':frozenset({'www.nbssa.rs'}),
    'manifestations':frozenset({'bukovickabanja.rs'}),
}
EVENT_PROVIDERS=('kultura','tourism','museum','library','manifestations')
HTML = frozenset({'text/html','application/xhtml+xml'})
FEEDS = frozenset({'application/rss+xml','application/xml','text/xml'})
DEFAULT_AREAS = ('Aranđelovac','Darosava','Ranilović')


@dataclass(frozen=True)
class NoticeSnapshot:
    records: tuple[dict,...]
    metadata: dict[str,Any]


class NoticeProvider:
    def __init__(self, provider: str, http: HttpClient, executor=None,
                 options: dict | None = None, clock: Callable[[],datetime] = utcnow) -> None:
        self.http=http;self.executor=executor;self.clock=clock;self.options=dict(options or {})
        info=SOURCES[provider];minutes=info['minutes']
        self.spec=SourceSpec(provider,'arandjelovac',info['title'],info['key'],info['sensor'],
                             info['url'],info['icon'],timedelta(minutes=minutes),
                             timedelta(minutes=minutes*2+15),TZ,cycle_timeout=120,max_items=20)
        self._article_cache: dict[str,tuple[datetime,Article]]={}

    async def _parse(self, fn, *args):
        if self.executor:return await self.executor(fn,*args)
        return await asyncio.to_thread(fn,*args)

    async def async_fetch(self) -> FetchResult[NoticeSnapshot]:
        self.http.clear_observations()
        provider=self.spec.provider;now=self.clock().astimezone(TZ)
        metadata:dict[str,Any]={'source_url':self.spec.source_url,'source_title':self.spec.title,
                              'scope':'Veröffentlichte Meldungen'}
        if provider=='opstina':
            categories=self.options.get('categories','47')
            if not all(part.strip().isdigit() for part in str(categories).split(',')):
                raise SourceError('categories','Ungültige Gemeindekategorien.',scope=provider)
            query=urlencode({'categories':categories,'per_page':30,
                             '_fields':'id,date_gmt,modified_gmt,link,title,content,categories'})
            raw=await self.http.get_text(self.spec.source_url+'wp-json/wp/v2/posts?'+query,
                                         content_types=frozenset({'application/json'}))
            articles=await self._parse(parse_municipality,raw,self.spec.source_url)
            values=tuple(item(a,'news') for a in articles)
            metadata.update(categories=str(categories),window='Neueste 30 Veröffentlichungen der gewählten Kategorien')
        elif provider in ('kultura','tourism','museum','library'):
            raw=await self.http.get_text(self.spec.source_url,content_types=FEEDS)
            articles=await self._parse(parse_feed,raw,self.spec.source_url)
            collected=[]
            for article in articles:
                collected.extend(await self._parse(event_items,article))
            values=tuple(collected)
            metadata.update(window='Aktueller RSS-Ausschnitt; kein vollständiger Veranstaltungskalender',
                            feed_articles=len(articles))
        elif provider=='manifestations':
            raw=await self.http.get_text(self.spec.source_url,content_types=HTML)
            values=await self._parse(parse_manifestations,raw,self.spec.source_url)
            metadata.update(window='Allgemeine Veranstaltungsübersicht; keine bestätigten Termine für ein bestimmtes Jahr',
                            date_confirmed=False)
        elif provider=='putevi':
            raw=await self.http.get_text(self.spec.source_url,content_types=frozenset({'text/plain'}))
            values=await self._parse(parse_traffic,raw,self.spec.source_url,now)
            metadata.update(window='Aktueller veröffentlichter Kartenexport',coordinates='Bildkoordinaten, keine Geolokalisierung')
        else:
            raw=await self.http.get_text(self.spec.source_url,content_types=HTML)
            seeds=await self._parse(parse_bukulja_index,raw,self.spec.source_url,now)
            lookback=int(self.options.get('lookback_days',30))
            candidates=[a for a in seeds if water_related(a) and a.published>=now-timedelta(days=lookback)]
            if len(candidates)>12:
                raise SourceError('article_limit','Mehr als zwölf relevante Artikel; Quellenumfang muss geprüft werden.',scope='jkp')
            semaphore=asyncio.Semaphore(3)
            async def article(seed):
                cached=self._article_cache.get(seed.url)
                if cached and now-cached[0]<timedelta(hours=6):return cached[1]
                async with semaphore:
                    body=await self.http.get_text(seed.url,content_types=HTML)
                    value=await self._parse(parse_bukulja_article,body,seed)
                    self._article_cache[seed.url]=(now,value)
                    return value
            articles=await asyncio.gather(*(article(a) for a in candidates),return_exceptions=True)
            for value in articles:
                if isinstance(value,BaseException):raise value
            # Avoid retaining archives beyond the current bounded index.
            self._article_cache={a.url:self._article_cache[a.url] for a in candidates if a.url in self._article_cache}
            values=tuple([await self._parse(water_notice,a) for a in articles])
            metadata.update(window='Aktuelle öffentliche Meldungsseite, keine Archivvollabfrage',
                            index_articles=len(seeds),article_cache_hours=6)
        # These are source records, not last-known live network/supply measurements.
        return FetchResult(NoticeSnapshot(values,metadata), {'records':len(values),'source':provider})

    def project(self, payload: NoticeSnapshot, now: datetime) -> Projection:
        now=now.astimezone(TZ);kind=self.spec.provider
        lookback=int(self.options.get('lookback_days',30));horizon=int(self.options.get('horizon_days',60))
        metadata={**payload.metadata,'source_url':self.spec.source_url,'source_title':self.spec.title,
                  'lookback_days':lookback,'horizon_days':horizon,
                  'scope':'Gemeinde & Umgebung' if kind=='putevi' else 'Gemeindeweit',
                  'measurement':False,'coverage_label': 'Öffentlicher Meldungsausschnitt'}
        rows=[]
        areas=tuple(s.strip() for s in str(self.options.get('areas','')).split(',') if s.strip()) or DEFAULT_AREAS
        for original in payload.records:
            value=dict(original)
            if kind=='putevi':
                matched=matches_area(value.pop('_match_text'),areas)
                if not matched:continue
                value['matched_areas']=list(matched)
                if value.get('end_at') and parse_iso(value['end_at'])<=now:value['status']='deadline_passed'
            elif kind=='manifestations':
                # This source publishes seasons, not dated 2026/2027 events.
                if value.get('kind')!='seasonal' or value.get('date_confirmed') is not False:
                    raise SourceError('calendar_structure','Saisonhinweis ist nicht eindeutig gekennzeichnet.',scope=kind)
            else:
                published=parse_iso(value['published_at'])
                if published>now+timedelta(days=1):
                    raise SourceError('future_publication','Veröffentlichungsdatum liegt unplausibel in der Zukunft.',scope=kind)
                start=parse_iso(value['start_at']) if value.get('start_at') else None
                event_day=datetime.fromisoformat(value['event_date']).date() if value.get('event_date') else None
                if event_day:
                    if event_day<now.date() or event_day>(now+timedelta(days=horizon)).date():continue
                if start is None and event_day is None and published<now-timedelta(days=lookback):continue
                if kind=='jkp' and value['status']=='unconfirmed' and now-published>timedelta(days=3):
                    value['status']='historical_unconfirmed'
                if start:
                    end=parse_iso(value['end_at']) if value.get('end_at') else None
                    if kind=='jkp':
                        if end and end<=now:continue
                    else:
                        # No invented duration: retain a started event only on its day.
                        if start.date()<now.date():continue
                        if start>now+timedelta(days=horizon):continue
                        if start<=now:value['status']='start_passed'
            rows.append(value)
        if kind in EVENT_PROVIDERS and kind!='manifestations':
            # Preserve non-cinema notices even when a film programme has >20 slots.
            rows.sort(key=lambda x:(x.get('event_type')=='cinema',not bool(x.get('start_at') or x.get('event_date')),x.get('start_at') or x.get('event_date') or '',x['id']))
        else:rows.sort(key=lambda x:x.get('published_at') or '',reverse=True)
        count=len(rows);selected=rows[:self.spec.max_items]
        # Explicit excerpts and list truncation; reserve room for common health fields.
        while selected and len(json.dumps({'items':selected,'metadata':metadata},ensure_ascii=False).encode())>19_000:selected.pop()
        if kind=='putevi':metadata['areas']=list(areas)
        if kind=='jkp':
            metadata['outage_notices']=sum(x['kind']=='water_outage' and x['status'] in ('unconfirmed','scheduled') for x in rows)
            metadata['unconfirmed_notices']=sum(x['status']=='unconfirmed' for x in rows)
            metadata['unreadable_notices']=sum(x['status']=='image_only' for x in rows)
        return Projection(count,tuple(selected),metadata,count>len(selected))

    def diagnostics(self) -> dict:
        return {'http':list(self.http.observations),'cached_articles':len(self._article_cache),
                'source':self.spec.provider}
