"""EDS parser refactored from eds_arandjelovac 1.0.0; standard library only."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from ...common.models import SourceError
from .source import INDEX_URL, HOSTS, TZ
from .models import Page, Outage

CYRILLIC = dict(zip(
    'абвгдђежзијклљмнњопрстћуфхцчџш',
    ['a','b','v','g','d','dj','e','z','z','i','j','k','l','lj','m','n','nj',
     'o','p','r','s','t','c','u','f','h','c','c','dz','s'], strict=True))


class EDSError(SourceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, scope='eds')


def clean(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', value).split())


def key(value: str) -> str:
    value = ''.join(CYRILLIC.get(c, c) for c in clean(value).casefold()).replace('đ', 'dj')
    return ''.join(c for c in unicodedata.normalize('NFD', value)
                   if unicodedata.category(c) != 'Mn')



class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


def discover_pages(html: str) -> dict[int, str]:
    """Read published navigation slots, not dates.

    The observed index promises four links and has no shorter-publication
    marker. Missing links remain a source error, independently of date coverage.
    """
    parser = LinkParser()
    parser.feed(html)
    parser.close()
    found = {}
    for href in parser.links:
        url = urljoin(INDEX_URL, href)
        match = re.fullmatch(r'/planirana-iskljucenja-srbija/Kraljevo_Dan_([0-3])_Iskljucenja\.htm',
                             urlsplit(url).path, flags=re.I)
        if match:
            validate_eds_url(url)
            slot = int(match[1])
            if slot in found and found[slot] != url:
                raise EDSError('links_ambiguous', 'Widersprüchliche Links für einen EDS-Tag.')
            found[slot] = url
    if set(found) != set(range(4)):
        raise EDSError('links_missing', 'EDS verlinkt nicht alle vier erwarteten Kraljevo-Tagesseiten.')
    return dict(sorted(found.items()))


class TableParser(HTMLParser):
    """Flat HTML tables, independent of styles, case and td/th choice.

    Unknown table geometry is intentionally rejected instead of guessing.
    """
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ('script', 'style'):
            self.skip += 1
            return
        if self.skip:
            return
        attributes = dict(attrs)
        if tag == 'table':
            if self.table is not None:
                raise EDSError('table_shape', 'Verschachtelte EDS-Tabelle.')
            self.table = []
        elif tag == 'tr' and self.table is not None:
            if self.row is not None:
                raise EDSError('table_shape', 'Nicht abgeschlossene Tabellenzeile.')
            self.row = []
        elif tag in ('td', 'th') and self.table is not None:
            if self.row is None or self.cell is not None:
                raise EDSError('table_shape', 'Ungültige Tabellenzelle.')
            if any(attributes.get(a, '1') != '1' for a in ('rowspan', 'colspan')):
                raise EDSError('table_shape', 'Neue Tabellenstruktur mit verbundenen Zellen.')
            self.cell = []
        elif tag in ('br', 'p', 'div', 'li') and self.cell is not None:
            self.cell.append(' ')

    def handle_endtag(self, tag: str) -> None:
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ('td', 'th') and self.table is not None:
            if self.cell is None or self.row is None:
                raise EDSError('table_shape', 'Tabellenzelle ohne Anfang.')
            self.row.append(clean(''.join(self.cell)))
            self.cell = None
        elif tag == 'tr' and self.table is not None:
            if self.cell is not None or self.row is None:
                raise EDSError('table_shape', 'Unvollständige Tabellenzeile.')
            self.table.append(self.row)
            self.row = None
        elif tag == 'table':
            if self.table is None or self.row is not None or self.cell is not None:
                raise EDSError('table_shape', 'Unvollständige Tabelle.')
            self.tables.append(self.table)
            self.table = None
        elif tag in ('p', 'div', 'li') and self.cell is not None:
            self.cell.append(' ')

    def handle_data(self, data: str) -> None:
        if not self.skip and self.cell is not None:
            self.cell.append(data)

    def finish(self) -> list[list[list[str]]]:
        self.close()
        if self.table is not None or self.row is not None or self.cell is not None:
            raise EDSError('truncated_html', 'HTML endet in einer offenen Tabelle.')
        return self.tables


HEADERS = {
    'ogranak': 'branch', 'opstina': 'municipality', 'vreme': 'time',
    'ulice': 'area', 'ulice / podrucje': 'area', 'ulice/podrucje': 'area',
}
DATE_TITLE = re.compile(
    r'kraljevo\s*[-–—]\s*planirana iskljucenja za datum:\s*'
    r'(\d{1,2})\.(\d{1,2})\.(\d{4})\.?', re.I)
TIME_RANGE = re.compile(r'(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})')


def local_instant(day: date, minutes: int) -> datetime:
    naive = datetime.combine(day, time()) + timedelta(minutes=minutes)
    candidates = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=TZ, fold=fold)
        back = aware.astimezone(timezone.utc).astimezone(TZ)
        if back.replace(tzinfo=None) == naive and aware.utcoffset() not in [c.utcoffset() for c in candidates]:
            candidates.append(aware)
    if len(candidates) != 1:
        raise EDSError('time_ambiguous', 'Uhrzeit bei Zeitumstellung fehlt oder ist doppeldeutig.')
    return candidates[0]


def parse_times(raw: str, day: date) -> tuple[datetime, datetime]:
    match = TIME_RANGE.fullmatch(clean(raw))
    if not match:
        raise EDSError('time_format', f'Unbekannte Zeitangabe für Aranđelovac: {raw!r}')
    h1, m1, h2, m2 = map(int, match.groups())
    if not (0 <= h1 <= 23 and 0 <= m1 <= 59 and 0 <= h2 <= 24 and 0 <= m2 <= 59) or (h2 == 24 and m2):
        raise EDSError('time_format', f'Ungültige Uhrzeit: {raw!r}')
    start, end = h1 * 60 + m1, h2 * 60 + m2
    if end <= start:
        raise EDSError('time_ambiguous', f'Ende liegt nicht nach Beginn; kein Folgetag wird geraten: {raw!r}')
    return local_instant(day, start), local_instant(day, end)


def parse_page(html: str, url: str) -> Page:
    parser = TableParser()
    parser.feed(html)
    tables = parser.finish()
    if len(tables) != 2:
        raise EDSError('table_count', 'Genau eine Datumstabelle und eine Abschaltungstabelle werden erwartet.')
    titles = []
    for table in tables:
        for row in table:
            if len(row) == 1:
                match = DATE_TITLE.fullmatch(key(row[0]))
                if match:
                    try:
                        titles.append(date(int(match[3]), int(match[2]), int(match[1])))
                    except ValueError as exc:
                        raise EDSError('date_invalid', 'Ungültiges Datum in EDS-Überschrift.') from exc
    if len(titles) != 1:
        raise EDSError('date_missing', 'Genau eine datierte Kraljevo-Überschrift wird erwartet.')
    page_date = titles[0]
    candidates = []
    for table in tables:
        if table:
            names = [HEADERS.get(key(c)) for c in table[0]]
            if len(names) == 4 and set(names) == {'branch', 'municipality', 'time', 'area'}:
                candidates.append((table, names))
    if len(candidates) != 1:
        raise EDSError('table_headers', 'Genau eine Tabelle mit Ogranak, Opština, Vreme und Ulice wird erwartet.')
    table, names = candidates[0]
    outages: list[Outage] = []
    seen: set[tuple[str, str, str]] = set()
    for number, row in enumerate(table[1:], start=2):
        if len(row) != 4:
            raise EDSError('row_shape', f'Zeile {number}: unerwartete Spaltenzahl.')
        values = dict(zip(names, row, strict=True))
        if not values['municipality'] or not values['branch']:
            raise EDSError('row_identity', f'Zeile {number}: Gemeinde oder Ogranak fehlt.')
        if key(values['municipality']) != 'arandjelovac':
            continue
        if not values['area']:
            raise EDSError('area_missing', f'Zeile {number}: Gebiet für Aranđelovac fehlt.')
        start, end = parse_times(values['time'], page_date)
        # Preserve original area; merge only exact normalized duplicates.
        identity = (start.isoformat(), end.isoformat(), clean(values['area']).casefold())
        if identity in seen:
            continue
        seen.add(identity)
        outages.append({
            'date': page_date.isoformat(), 'start': start.strftime('%H:%M'),
            'end': '24:00' if end.date() != page_date else end.strftime('%H:%M'),
            'start_at': start.isoformat(), 'end_at': end.isoformat(),
            'area': values['area'], 'municipality': 'Aranđelovac',
            'municipality_original': values['municipality'], 'branch': values['branch'],
            'source_url': url,
        })
    return {'date': page_date.isoformat(), 'url': url, 'rows': len(table) - 1,
            'matched_rows': sum(key(dict(zip(names, r))['municipality']) == 'arandjelovac'
                                for r in table[1:]), 'outages': outages}



def validate_eds_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname in HOSTS
                 and parts.port in (None, 443) and not parts.username
                 and not parts.password and not parts.fragment and not parts.query)
    except ValueError:
        valid = False
    if not valid:
        raise EDSError('unsafe_url', 'Unerwarteter Link ausserhalb der EDS-Tagesseiten.')
    return url
