"""Source-specific parsers, deliberately separate from EDS."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
import re
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from ...common.models import SourceError
from .text import TZ, clock_time, excerpt, local_time, named_date, nearest_date, normalize, parse_iso, parse_rfc, plain, public_link


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    text: str
    url: str
    published: datetime
    modified: datetime | None = None
    image_only: bool = False


def item(article: Article, kind: str, **extra) -> dict:
    return {'id': article.id, 'title': excerpt(article.title,350),
            'description': excerpt(article.text), 'description_is_excerpt': True,
            'source_url': article.url, 'published_at': article.published.isoformat(),
            'modified_at': article.modified.isoformat() if article.modified else None,
            'kind':kind, 'status':'published', 'start_at':None, 'end_at':None, **extra}


def parse_feed(raw: str, base: str) -> tuple[Article,...]:
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',raw,re.I):
        raise SourceError('feed_structure','XML-DTD wird nicht unterstützt.',scope='notices')
    try: root=ET.fromstring(raw)
    except ET.ParseError as exc: raise SourceError('feed_structure','RSS/XML ist beschädigt.',scope='notices') from exc
    if root.tag != 'rss' or root.find('channel') is None:
        raise SourceError('feed_structure','Erwarteter RSS-Kanal fehlt.',scope='notices')
    channel=root.find('channel')
    if not channel.findtext('title') or not channel.findtext('link'):
        raise SourceError('feed_structure','RSS-Kanal ist unvollständig.',scope='notices')
    nodes=channel.findall('item')
    if len(nodes)>100: raise SourceError('feed_structure','Zu viele RSS-Einträge.',scope='notices')
    articles=[];seen=set()
    for node in nodes:
        title=plain(node.findtext('title') or '')
        url=public_link(node.findtext('link') or '',base)
        if not title or url==base:
            raise SourceError('feed_structure','RSS-Meldung ohne Titel oder Link.',scope='notices')
        uid=node.findtext('guid') or url
        if uid in seen: continue
        seen.add(uid)
        content=node.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or node.findtext('description') or ''
        text=plain(content)
        articles.append(Article(sha256(uid.encode()).hexdigest()[:20], title,text,url,parse_rfc(node.findtext('pubDate')),image_only=not bool(text) and '<img' in content.lower()))
    return tuple(articles)


def parse_municipality(raw: str, base: str) -> tuple[Article,...]:
    try:
        data=json.loads(raw)
        if not isinstance(data,list) or len(data)>100: raise ValueError
        articles=[];seen=set()
        for record in data:
            if not isinstance(record,dict) or type(record.get('id')) is not int: raise ValueError
            title=plain(record['title']['rendered'])
            content=plain(record.get('content',{}).get('rendered',''))
            # The site's naive `date` currently differs from date_gmt by one hour.
            # Always consume the explicit UTC field; do not guess its WP timezone.
            published=parse_iso(record['date_gmt']+'Z')
            modified=parse_iso(record['modified_gmt']+'Z') if record.get('modified_gmt') else None
            url=public_link(record['link'],base)
            if not title: raise ValueError
            if record['id'] in seen: continue
            seen.add(record['id'])
            articles.append(Article('opstina:'+str(record['id']),title,content,url,published,modified))
        return tuple(articles)
    except (KeyError,TypeError,ValueError) as exc:
        if isinstance(exc,SourceError): raise
        raise SourceError('news_structure','Gemeindemeldungen haben eine unbekannte Struktur.',scope='opstina') from exc


class BukuljaIndex(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.links={};self.current=None;self.parts=[];self.heading=[];self.in_heading=False;self.headers=[];self.h1=False;self.title='';self.next_link=None;self.page_link=None;self.page_parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='h1':self.h1=True
        if tag=='a' and attrs.get('href','').startswith('/vesti?'):
            self.page_link=attrs['href'];self.page_parts=[]
        if tag=='a' and re.fullmatch(r'/vesti/[a-z0-9-]+',attrs.get('href','')):
            self.current=attrs['href'];self.parts=[];self.heading=[]
        if self.current and tag in ('h2','h3'):self.in_heading=True
    def handle_data(self,data):
        if self.h1:self.title+=data
        if self.page_link:self.page_parts.append(data)
        if self.current:
            self.parts.append(data+' ')
            if self.in_heading:self.heading.append(data)
    def handle_endtag(self,tag):
        if tag=='h1':self.h1=False
        if tag in ('h2','h3'):self.in_heading=False
        if tag=='a' and self.current:
            text=' '.join(''.join(self.parts).split());title=' '.join(''.join(self.heading).split())
            if title and self.current not in self.links:self.links[self.current]=(title,text)
            self.current=None
        if tag=='a' and self.page_link:
            if normalize(''.join(self.page_parts).strip()) in ('sledeca','sledece','next'):
                self.next_link=self.page_link
            self.page_link=None


def bukulja_next_page(raw: str, base: str) -> str | None:
    parser=BukuljaIndex();parser.feed(raw)
    if not parser.next_link:return None
    url=public_link(parser.next_link,base);parts=urlsplit(url);query=parse_qs(parts.query)
    if parts.path!='/vesti' or set(query)!={'page'} or len(query['page'])!=1 or not query['page'][0].isdigit():
        raise SourceError('pagination','Unbekannte Bukulja-Folgeseite.',scope='jkp')
    return url


def parse_bukulja_index(raw: str, base: str, now: datetime) -> tuple[Article,...]:
    parser=BukuljaIndex();parser.feed(raw)
    if not parser.links or 'vesti' not in normalize(parser.title):
        raise SourceError('index_structure','Bukulja-Meldungsliste nicht erkannt.',scope='jkp')
    result=[]
    for path,(title,text) in parser.links.items():
        published=named_date(text,now)
        if published is None: raise SourceError('published_date','Bukulja-Datum fehlt.',scope='jkp')
        result.append(Article('jkp:'+path.rsplit('/',1)[-1],title,text,public_link(path,base),published))
    if len(result)>50:raise SourceError('index_structure','Unerwartet grosse Bukulja-Liste.',scope='jkp')
    return tuple(result)


class BukuljaArticle(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.content_depth=None;self.parts=[];self.h1=False;self.title='';self.content_seen=False;self.images=0
    def handle_starttag(self,tag,attrs):
        # void elements do not change HTML element depth
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.depth+=1
        attrs=dict(attrs)
        if tag=='h1':self.h1=True
        if 'page-content' in attrs.get('class','').split() and self.content_depth is None:
            self.content_depth=self.depth;self.content_seen=True
        if self.content_depth is not None and tag=='img':self.images+=1
        if self.content_depth is not None and tag in ('p','br','li','div'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag=='h1':self.h1=False
        if self.content_depth is not None and tag in ('p','li','div'):self.parts.append('\n')
        if self.content_depth==self.depth:self.content_depth=None
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.depth=max(0,self.depth-1)
    def handle_data(self,data):
        if self.h1:self.title+=data
        if self.content_depth is not None:self.parts.append(data)


def parse_bukulja_article(raw: str, seed: Article) -> Article:
    parser=BukuljaArticle();parser.feed(raw)
    text='\n'.join(' '.join(s.split()) for s in ''.join(parser.parts).splitlines() if s.strip())
    if not parser.title or not parser.content_seen or (not text and not parser.images):
        raise SourceError('article_structure','Bukulja-Artikeltext nicht erkannt.',scope='jkp')
    return Article(seed.id,' '.join(parser.title.split()),text,seed.url,seed.published,image_only=not bool(text))


def water_related(article: Article) -> bool:
    return bool(re.search(r'vodovod|vodosnab|cevovod|\bvod(?:a|e|i|u|om)\b|\bvik\b',normalize(article.title+' '+article.text)))


def water_service_related(article: Article) -> bool:
    """Keep service news, not school visits that merely mention water."""
    heading=normalize(article.title)
    return water_related(article) and not re.search(r'(?:student|ucenic).{0,60}poset|poset.{0,60}(?:student|ucenic)',heading)


def local_works_related(article: Article) -> bool:
    text=normalize(article.title+' '+article.text)
    return not water_related(article) and bool(re.search(
        r'kolovoz|udarni[hme]*\s+rup|saobracaj|niskograd|odvoz|otpad|gasovod|cistoc',text))


def municipality_relevant(article: Article) -> bool:
    """Citizen notices span categories; procurement and internal jobs are separate."""
    title=normalize(article.title)
    return not re.search(r'javn\w*\s+nabav\w*|\bjn\s*[-–]?\s*\d|interni\s+konkurs',title)


def _asserted(text: str, pattern: str) -> bool:
    # Do not turn an expected, conditional, negative or future outcome into fact.
    for sentence in re.split(r'[.!?;\n]+',normalize(text)):
        if re.search(pattern,sentence) and not re.search(
            r'\b(?:nije|nisu|nece|bice|ukoliko|ako)\b|ocekuj|planir|trebalo|\bce\s+biti\b',sentence):
            return True
    return False


def water_notice(article: Article) -> dict:
    if article.image_only:
        return item(article,'water_unknown',status='image_only',description='Bildbeitrag: Der Inhalt wurde nicht automatisch ausgewertet. Bitte Original öffnen.')
    text=normalize(article.title+'\n'+article.text)
    outage=bool(re.search(r'(?:prekid|obustav).{0,90}(?:vodosnab|snabdevanj.{0,15}vod)|bez\s+(?:snabdevanja\s+)?vod(?:e|om)\b|vodosnab.{0,50}(?:prekid|obustav)',text,re.S))
    restored=_asserted(article.title+'\n'+article.text,r'vodosnabdevanje\s+(?:je\s+)?(?:ponovo\s+)?(?:normalizovano|uspostavljeno)|uspostavljeno\s+(?:je\s+)?(?:redovno\s+)?vodosnabdevanje')
    completed=_asserted(article.title+'\n'+article.text,
        r'(?:nakon|posle)\s+uspesno\s+(?:izvedenih|zavrsenih)\s+radova|radovi\s+(?:su\s+)?(?:uspesno\s+)?zavrseni|kvar\s+(?:je\s+)?(?:uspesno\s+)?(?:saniran|otklonjen)')
    result=item(article,'water_outage' if outage or restored else 'water_info',status='restored' if restored else 'repair_completed' if completed else 'unconfirmed' if outage else 'information')
    if outage and not restored and not completed:
        # A calendar date and an explicit time range are necessary for a plan.
        day=numeric_event_date(article.title) or named_date(article.title,article.published) or numeric_event_date(article.text) or named_date(article.text,article.published)
        times=re.search(r'(?:od|periodu\s+od)\s*(\d{1,2})(?::(\d{2}))?\s*do\s*(\d{1,2})(?::(\d{2}))?\s*(?:cas|sat|h\b)',text)
        if day and times and ('plan' in text or 'doci ce' in text):
            start=local_time(day.year,day.month,day.day,int(times[1]),int(times[2] or 0))
            end=local_time(day.year,day.month,day.day,int(times[3]),int(times[4] or 0))
            if end<=start: raise SourceError('event_date','Wasser-Zeitfenster ist widersprüchlich.',scope='jkp')
            result.update(status='scheduled',start_at=start.isoformat(),end_at=end.isoformat())
    return result


def parse_traffic(raw: str, base: str, now: datetime) -> tuple[dict,...]:
    reader=csv.DictReader(StringIO(raw),delimiter='\t')
    expected=['point','title','description','iconSize','iconOffset','icon']
    if reader.fieldnames!=expected:raise SourceError('traffic_headers','Kartenexport hat unbekannte Spalten.',scope='putevi')
    result=[];seen=set()
    for row in reader:
        if None in row or any(value is None for value in row.values()):raise SourceError('traffic_row','Kartenexport enthält eine unvollständige Zeile.',scope='putevi')
        raw_title=plain(row['title']);description=plain(row['description'])
        if not raw_title or not description:raise SourceError('traffic_row','Verkehrsmeldung ist leer.',scope='putevi')
        category,sep,title=raw_title.partition(':')
        if not sep or category not in ('ZABRANE','OBUSTAVE','RADOVI','ODRONI/KLIZIŠTA'):
            raise SourceError('traffic_category','Unbekannte Verkehrskategorie.',scope='putevi')
        uid=sha256((normalize(title)+'|'+normalize(description)).encode()).hexdigest()[:20]
        if uid in seen:continue
        seen.add(uid)
        # Publication date is optional: some permanent restrictions have none.
        pub=re.match(r'\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})\.',title)
        published=local_time(int(pub[3]),int(pub[2]),int(pub[1])) if pub else None
        value={'id':'putevi:'+uid,'title':excerpt(title.strip(),350),'description':excerpt(description,850),
               'description_is_excerpt':True,'source_url':base,'published_at':published.isoformat() if published else None,
               'kind':'closure' if category=='OBUSTAVE' else 'landslide' if category=='ODRONI/KLIZIŠTA' else 'restriction' if category=='ZABRANE' else 'roadworks',
               'status':'published','start_at':None,'end_at':None,'category':category,
               # `point` is an image coordinate, deliberately not a latitude/longitude.
               'geolocation':None,'_match_text':normalize(title+' '+description)}
        # Preserve names exactly as published; only the category is translated
        # by the card. Do not guess a route from the configured place filter.
        for field,pattern in (
            ('route',r'\b(?:deonic[aeiu]|деониц[аеиу])\s+([^,;\n]+)'),
            ('place',r'\b(?:mest[ou]|мест[оу])\s+([^,;.\n]+)'),
        ):
            match=re.search(pattern,title,re.I) or re.search(pattern,description,re.I)
            if match:value[field]=excerpt(match[1].strip().rstrip('.'),160)
        # Parse only explicit "do DD.MM.YYYY" deadlines, never the article date.
        end_match=re.search(r'\bdo\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})',normalize(description))
        if end_match:
            end=local_time(int(end_match[3]),int(end_match[2]),int(end_match[1]))+timedelta(days=1)
            value.update(end_at=end.isoformat(),deadline_date=f'{int(end_match[3]):04d}-{int(end_match[2]):02d}-{int(end_match[1]):02d}',end_precision='date',status='deadline_passed' if now>=end else 'published')
        result.append(value)
        if len(result)>2000:raise SourceError('traffic_row','Zu viele Verkehrsmeldungen.',scope='putevi')
    return tuple(result)


def matches_area(text: str, areas: tuple[str,...]) -> tuple[str,...]:
    normalized=normalize(text)
    # A distinct northern town must never match the local municipality Topola.
    normalized=re.sub(r'\bback(?:a|oj|e)\s+topol\w*','',normalized)
    found=[]
    for area in areas:
        name=normalize(area.strip())
        if not name:continue
        if name=='arandjelovac':pattern=r'\barandjelov(?:ac|ca|cu|cem)\b'
        elif name.endswith('a'):pattern=r'\b'+re.escape(name[:-1])+r'(?:a|e|i|u|om)\b'
        elif name=='ranilovic':pattern=r'\branilovic(?:a|u|i|ima)?\b'
        else:pattern=r'\b'+re.escape(name)+r'(?:a|u|om)?\b'
        if re.search(pattern,normalized):found.append(area)
    return tuple(found)


class ManifestationsParser(HTMLParser):
    """Read published heading/detail-link pairs, without inventing a year."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading=None;self.parts=[];self.pending=None;self.link=None;self.link_parts=[];self.records=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='h2':self.heading=True;self.parts=[];self.pending=None
        elif tag=='br' and self.heading:self.parts.append('\n')
        elif tag=='a' and self.pending:
            self.link=attrs.get('href');self.link_parts=[]
    def handle_data(self,data):
        if self.heading:self.parts.append(data)
        if self.link:self.link_parts.append(data)
    def handle_endtag(self,tag):
        if tag=='h2' and self.heading:
            self.pending=[' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip()]
            self.heading=False
        elif tag=='a' and self.link:
            if normalize(''.join(self.link_parts).strip())=='detaljnije':
                self.records.append((self.pending,self.link));self.pending=None
            self.link=None


def parse_manifestations(raw: str,base: str) -> tuple[dict,...]:
    parser=ManifestationsParser();parser.feed(raw)
    if not parser.records:raise SourceError('calendar_structure','Veranstaltungsübersicht enthält keine erkennbaren Einträge.',scope='manifestations')
    rows=[];seen=set()
    for heading,link in parser.records:
        if not heading:continue
        url=public_link(link,base)
        if url in seen:continue
        seen.add(url)
        rows.append({'id':'manifestations:'+sha256(url.encode()).hexdigest()[:20],
                     'title':excerpt(heading[0],350),'description':'',
                     'description_is_excerpt':True,'source_url':url,'published_at':None,
                     'kind':'seasonal','status':'seasonal','start_at':None,'end_at':None,
                     'season_label':excerpt(' · '.join(heading[1:]),180) or 'Zeitraum nicht angegeben',
                     'date_confirmed':False})
    if not rows or len(rows)>50:raise SourceError('calendar_structure','Unplausibler Umfang der Veranstaltungsübersicht.',scope='manifestations')
    return tuple(rows)


class MuseumListingsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tag=None;self.parts=[];self.headers=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('h1','h2'):self.tag=tag;self.parts=[]
    def handle_data(self,data):
        if self.tag:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag==self.tag:self.headers.append((tag,' '.join(''.join(self.parts).split())));self.tag=None


def parse_museum_listings(raw: str, base: str) -> tuple[dict,...]:
    """Undated official exhibition listings, never invented calendar events."""
    parser=MuseumListingsParser();parser.feed(raw)
    if not any(tag=='h1' and 'aktuelne izlozbe' in normalize(text) for tag,text in parser.headers):
        raise SourceError('exhibition_structure','Museums-Ausstellungsseite nicht erkannt.',scope='museum')
    result=[];seen=set()
    for tag,title in parser.headers:
        if tag!='h2' or not title.startswith(('„','“','"','«')):continue
        text=normalize(title)
        if re.search(r'promocij|predstavlj|knjig|\d{1,2}\.\s*\d{1,2}\.\s*20\d{2}',text):continue
        if title in seen:continue
        seen.add(title)
        result.append({'id':'museum-listing:'+sha256(title.encode()).hexdigest()[:20],
                       'title':excerpt(title,350),'description':'Von der Museumsseite als Ausstellung aufgeführt; Beginn, Ende und aktuelle Laufzeit sind nicht bestätigt.',
                       'description_is_excerpt':True,'source_url':base,'published_at':None,
                       'kind':'listing','status':'listing_unconfirmed','event_type':'exhibition',
                       'start_at':None,'end_at':None,'date_confirmed':False})
    if not result or len(result)>30:
        raise SourceError('exhibition_structure','Museums-Ausstellungen nicht eindeutig lesbar.',scope='museum')
    return tuple(result)


def numeric_event_date(text: str) -> datetime | None:
    match=re.search(r'(?<!\d)(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})\.?(?!\d)',text)
    return local_time(int(match[3]),int(match[2]),int(match[1])) if match else None


def event_items(article: Article) -> tuple[dict,...]:
    # Classify only an explicit article heading/URL, not incidental body words.
    heading=normalize(article.title+' '+article.url)
    event_type=next((kind for kind,pattern in (
        ('cinema',r'filmski[-\s]+program|bioskop'),('theatre',r'pozoris|(?:^|[\s/-])predstava\b'),
        ('concert',r'koncert'),('exhibition',r'izlozb'),('reading',r'knjig|knjizev|roman|tribin|trilog'),
        ('market',r'bazar|sajam|vasar'),('festival',r'festival|svecanost'),
    ) if re.search(pattern,heading)),None)
    extra={'event_type':event_type} if event_type else {}
    if re.search(r'\b(?:konkurs|prijav\w*|rok)\b',normalize(article.title)):
        return (item(article,'announcement',status='announcement',**extra),)
    lines=article.text.splitlines();day=None;events=[]
    for line in lines:
        dm=re.fullmatch(r'\s*(\d{1,2})\.(\d{1,2})\.(?:(20\d{2})\.?)?\s*',line)
        if dm:
            day=nearest_date(int(dm[1]),int(dm[2]),article.published,int(dm[3]) if dm[3] else None);continue
        tm=re.fullmatch(r'\s*(\d{1,2})[:.](\d{2})\s*[-–—]\s*(.+)',line)
        if day is not None and tm:
            start=local_time(day.year,day.month,day.day,int(tm[1]),int(tm[2]))
            events.append(item(article,'event',id=article.id+':'+start.isoformat(),title=excerpt(tm[3],350),
                               description='',program_split=True,program_title=excerpt(article.title,350),
                               start_at=start.isoformat(),status='scheduled',date_inferred_year=True,**extra))
    if events:return tuple(events)
    # Prefer the title. A ticket-sale date in body text is not an event date.
    day=numeric_event_date(article.title) or named_date(article.title,article.published)
    time=clock_time(article.title)
    if day is None and not re.search(r'prodaj|rezerv|ulaznic|karat|prijav|konkurs|\brok\b',normalize(article.text)):
        day=numeric_event_date(article.text) or named_date(article.text,article.published);time=clock_time(article.text)
    if day and time:
        start=local_time(day.year,day.month,day.day,*time)
        return (item(article,'event',start_at=start.isoformat(),status='scheduled',**extra),)
    if day:
        return (item(article,'event',event_date=day.date().isoformat(),status='date_only',**extra),)
    return (item(article,'announcement',status='image_only' if article.image_only else 'announcement',**extra),)
