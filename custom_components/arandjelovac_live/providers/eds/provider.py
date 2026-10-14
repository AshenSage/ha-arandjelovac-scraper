"""EDS index -> validated dated pages -> contiguous coverage -> outage projection."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
import hashlib
from typing import Any

from ...common.http import HttpClient
from ...common.models import FetchResult, Projection, SourceSpec
from .models import EDSSnapshot, Page
from .parser import EDSError, clean, discover_pages, parse_page
from .source import INDEX_URL, TZ

HTML_TYPES = frozenset({'text/html', 'application/xhtml+xml'})
SPEC = SourceSpec(
    provider='eds', location='arandjelovac', title='Aranđelovac EDS',
    translation_key='eds_outages', suggested_object_id='arandjelovac_eds_outages',
    source_url=INDEX_URL, icon='mdi:transmission-tower-off',
    poll_interval=timedelta(minutes=30), stale_after=timedelta(minutes=65),
    time_zone=TZ, partial_poll_interval=timedelta(minutes=15),
)


def validated_coverage(pages: tuple[Page, ...], today: date) -> tuple[Page, ...]:
    """Validate the entire parsed set before excluding past publication dates.

    Link discovery separately enforces the observed index contract. This date
    calculation also accepts smaller trusted sets without treating missing
    navigation links as proof of a deliberately shorter publication.
    """
    if not 1 <= len(pages) <= 4:
        raise EDSError('coverage_expired', 'Keine vertrauenswürdige Tagesabdeckung vorhanden.')
    dates = []
    for page in pages:
        try:
            day = date.fromisoformat(page['date'])
        except (TypeError, ValueError) as exc:
            raise EDSError('date_invalid', 'Ungültiges Tagesdatum im Abrufsatz.') from exc
        if day.isoformat() != page['date'] or day > today + timedelta(days=3):
            raise EDSError('date_mismatch', 'Tagesdatum ausserhalb des vorgesehenen Zukunftshorizonts.')
        if any(item['date'] != page['date'] for item in page['outages']):
            raise EDSError('date_mismatch', 'Meldungsdatum widerspricht dem Datum der Tagesseite.')
        dates.append(day)
    if len(set(dates)) != len(dates):
        raise EDSError('date_duplicate', 'Mehrere EDS-Tagesseiten tragen dasselbe Datum.')
    current = tuple(p for d, p in sorted(zip(dates, pages), key=lambda pair: pair[0]) if d >= today)
    if not current or current[0]['date'] != today.isoformat():
        raise EDSError('coverage_expired', 'Keine vollständig geprüfte EDS-Tagesseite für heute.')
    if any(page['date'] != (today + timedelta(days=i)).isoformat() for i, page in enumerate(current)):
        raise EDSError('coverage_gap', 'Lücke zwischen heute und dem letzten veröffentlichten Zukunftstag.')
    return current


class EDSProvider:
    spec = SPEC

    def __init__(self, http: HttpClient,
                 parse_runner: Callable[..., Awaitable[Any]] = asyncio.to_thread,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.http = http
        self._run = parse_runner
        self._clock = clock or (lambda: datetime.now(TZ))
        self._links: dict[int, str] = {}
        self._parsed: dict[int, dict[str, Any]] = {}
        self._coverage: dict[str, Any] | None = None

    async def async_fetch(self) -> FetchResult[EDSSnapshot]:
        self.http.clear_observations()
        self._links = {}
        self._parsed = {}
        self._coverage = None
        today = self._clock().astimezone(TZ).date()
        links = await self._run(discover_pages, await self.http.get_text(INDEX_URL, content_types=HTML_TYPES))
        self._links = links
        semaphore = asyncio.Semaphore(2)

        async def one(slot: int, url: str) -> Page:
            async with semaphore:
                html = await self.http.get_text(url, content_types=HTML_TYPES)
                page = await self._run(parse_page, html, url)
                self._parsed[slot] = {k: v for k, v in page.items() if k != 'outages'}
                return page

        tasks = [asyncio.create_task(one(slot, url)) for slot, url in links.items()]
        try:
            pages = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._clock().astimezone(TZ).date() != today:
            raise EDSError('midnight_race', 'Abruf überschreitet Mitternacht; neuer Abruf erforderlich.')
        current = validated_coverage(tuple(pages), today)
        pages.sort(key=lambda page: page['date'])
        snapshot = EDSSnapshot(tuple(pages))
        self._coverage = {
            'coverage_start': current[0]['date'], 'coverage_end': current[-1]['date'],
            'coverage_days': len(current), 'coverage_complete': len(current) == 4,
            'ignored_past_dates': [p['date'] for p in pages if p['date'] < today.isoformat()],
        }
        tomorrow = datetime.combine(today + timedelta(days=1), time(), TZ)
        return FetchResult(snapshot,
                           diagnostics={'coverage': [{k: v for k, v in p.items() if k != 'outages'} for p in pages],
                                        **self._coverage},
                           refresh_at=tomorrow)

    def project(self, payload: EDSSnapshot, now: datetime) -> Projection:
        now = now.astimezone(TZ)
        current = validated_coverage(payload.pages, now.date())
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for page in current:
            for outage in page['outages']:
                start = datetime.fromisoformat(outage['start_at'])
                end = datetime.fromisoformat(outage['end_at'])
                if end <= now:
                    continue
                identity = (outage['start_at'], outage['end_at'], clean(outage['area']).casefold())
                if identity in seen:
                    continue
                seen.add(identity)
                offset = (date.fromisoformat(outage['date']) - now.date()).days
                label = {0: 'Heute', 1: 'Morgen', 2: 'Übermorgen', 3: 'In 3 Tagen'}[offset]
                uid = hashlib.sha256('\x1f'.join(identity).encode('utf-8')).hexdigest()[:20]
                items.append(dict(outage, id=uid, day=label,
                                  status='laufend' if start <= now else 'geplant'))
        items.sort(key=lambda item: (item['start_at'], item['end_at'], item['area']))
        return Projection(len(items), tuple(items), metadata={
            'timezone': 'Europe/Belgrade', 'municipality': 'Aranđelovac',
            # Preserve the existing metadata aliases for older cards.
            'coverage_start': current[0]['date'], 'coverage_end': current[-1]['date'],
        }, coverage_start=current[0]['date'], coverage_end=current[-1]['date'],
            coverage_days=len(current), coverage_complete=len(current) == 4)

    def diagnostics(self) -> dict[str, Any]:
        return {'requests': list(self.http.observations),
                'discovered_pages': [{'slot': slot, 'url': url} for slot, url in self._links.items()],
                'parsed_pages': [self._parsed[slot] for slot in sorted(self._parsed)],
                'validated_coverage_at_fetch': self._coverage}
