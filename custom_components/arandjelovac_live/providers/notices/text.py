"""Text, dates and safe public links for the researched notice sources."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from ...common.models import SourceError

TZ = ZoneInfo('Europe/Belgrade')
_CYR = dict(zip('абвгдђежзијклљмнњопрстћуфхцчџш',
                ['a','b','v','g','d','dj','e','z','z','i','j','k','l','lj','m','n','nj','o','p','r','s','t','c','u','f','h','c','c','dz','s']))
MONTHS = {'januar':1,'februar':2,'mart':3,'april':4,'maj':5,'jun':6,
          'jul':7,'avgust':8,'septembar':9,'septembr':9,'oktobar':10,
          'oktobr':10,'novembar':11,'novembr':11,'decembar':12,'decembr':12}


def normalize(value: str) -> str:
    value = ''.join(_CYR.get(c, c) for c in value.casefold()).replace('đ', 'dj')
    return ''.join(c for c in unicodedata.normalize('NFKD', value)
                   if not unicodedata.combining(c))


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if not self.skip and tag in ('p','div','br','li','h1','h2','h3','tr'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip: self.skip -= 1
        if not self.skip and tag in ('p','div','li','h1','h2','h3','tr'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def plain(value: str) -> str:
    parser = TextParser()
    parser.feed(value)
    return '\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())


def excerpt(value: str, limit: int = 550) -> str:
    text = ' '.join(value.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def public_link(value: str, base: str) -> str:
    url = urljoin(base, value)
    source = urlsplit(base)
    parts = urlsplit(url)
    if (parts.scheme not in ('http','https') or parts.hostname != source.hostname
            or parts.username or parts.password or parts.port not in (None,80,443)):
        raise SourceError('article_url', 'Nicht erlaubter Quellenlink.', scope='notices')
    return parts._replace(scheme='https', netloc=parts.hostname or '', fragment='').geturl()


def parse_iso(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None: raise ValueError
        return result.astimezone(TZ)
    except (ValueError, AttributeError, TypeError) as exc:
        raise SourceError('published_date', 'Veröffentlichungsdatum nicht lesbar.', scope='notices') from exc


def parse_rfc(value: str) -> datetime:
    try:
        result = parsedate_to_datetime(value)
        if result.tzinfo is None: raise ValueError
        return result.astimezone(TZ)
    except (ValueError, TypeError, AttributeError) as exc:
        raise SourceError('published_date', 'RSS-Datum nicht lesbar.', scope='notices') from exc


def local_time(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    try:
        naive = datetime(year, month, day, hour, minute)
        candidates = []
        for fold in (0,1):
            aware = naive.replace(tzinfo=TZ, fold=fold)
            if aware.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None) == naive:
                if all(aware.utcoffset() != c.utcoffset() for c in candidates): candidates.append(aware)
        if len(candidates) != 1: raise ValueError
        return candidates[0]
    except ValueError as exc:
        raise SourceError('event_date', 'Ungültige oder mehrdeutige Ortszeit.', scope='notices') from exc


def nearest_date(day: int, month: int, published: datetime, year: int | None = None) -> datetime:
    if year is not None: return local_time(year,month,day)
    choices = []
    for y in (published.year-1, published.year, published.year+1):
        try: choices.append(local_time(y,month,day))
        except SourceError: pass
    if not choices: raise SourceError('event_date', 'Ungültiges Datum.', scope='notices')
    result = min(choices, key=lambda d: abs((d-published).total_seconds()))
    if abs((result-published).days) > 183:
        raise SourceError('event_date', 'Jahr eines Termins nicht eindeutig.', scope='notices')
    return result


def named_date(text: str, published: datetime) -> datetime | None:
    text = normalize(text)
    for match in re.finditer(r'(?<!\d)(\d{1,2})\.?\s*([a-z]+)\s*(?:(20\d{2})\.?)?', text):
        day, name, year = match.groups()
        month = next((n for stem,n in MONTHS.items() if name.startswith(stem)), None)
        if month: return nearest_date(int(day),month,published,int(year) if year else None)
    return None


def clock_time(text: str) -> tuple[int,int] | None:
    match = re.search(r'\b(?:od|u)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(?:cas|sat|h\b)', normalize(text))
    if match:
        hour,minute = int(match[1]),int(match[2] or 0)
        if hour < 24 and minute < 60: return hour,minute
    return None
