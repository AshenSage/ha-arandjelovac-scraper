"""Coverage regressions. Coordinator uses HA doubles, never a real HA runtime."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

import bootstrap
from live_test.common.models import FetchResult, SourceError, SourceState
from live_test.providers.eds.models import EDSSnapshot
from live_test.providers.eds.parser import parse_page, discover_pages
from live_test.providers.eds.provider import EDSProvider
from live_test.providers.eds.source import INDEX_URL, TZ
from test_eds_parser import document, row, URL
from test_coordinator_contract import c, Entry

NOW = datetime(2026, 10, 7, 10, tzinfo=TZ)
FIXTURES = bootstrap.ROOT / 'tests/fixtures/eds'


class PublishedHTTP:
    """Synthetic dated pages behind the real four-link index contract."""
    def __init__(self, offsets=(-1, 0, 1, 2), rows=None):
        self.offsets = offsets
        self.rows = rows or {}
        self.fail = None
        self.bad = {}
        self.observations = []
        self.calls = []
        self.index = (FIXTURES/'2026-10-07/index.html').read_text('utf-8-sig')

    def clear_observations(self):
        self.observations.clear()

    async def get_text(self, url, **kwargs):
        self.calls.append(url)
        if url == INDEX_URL:
            return self.index
        slot = int(url.split('_Dan_')[1][0])
        if self.fail and slot == self.fail[0]:
            raise self.fail[1]
        if slot in self.bad:
            return self.bad[slot]
        offset = self.offsets[slot]
        day = (NOW + timedelta(days=offset)).strftime('%d.%m.%Y.')
        return document(self.rows.get(offset, ''), day=day)


class CoverageTests(unittest.IsolatedAsyncioTestCase):
    async def fetch_view(self, http, now=NOW):
        provider = EDSProvider(http, clock=lambda: now)
        state = SourceState()
        try:
            state.accept(await provider.async_fetch(), now)
        except SourceError as exc:
            state.reject(exc, now)
        except TimeoutError:
            state.reject(SourceError('timeout', 'Gesamtabruf überschreitet das Zeitlimit.'), now)
        return state.render(provider, now), provider, state

    def assert_coverage(self, view, days, count=0):
        self.assertTrue(view['available'])
        self.assertEqual(view['count'], count)
        self.assertEqual(view['items_count'], count)
        self.assertEqual(view['coverage_start'], '2026-10-07')
        self.assertEqual(view['coverage_end'], (NOW+timedelta(days=days-1)).date().isoformat())
        self.assertEqual(view['coverage_days'], days)
        self.assertEqual(view['coverage_complete'], days == 4)
        self.assertIsNone(view['error'])
        self.assertEqual(view['metadata']['coverage_end'], view['coverage_end'])

    def assert_failure(self, view, code):
        self.assertFalse(view['available'])
        self.assertIsNone(view['count'])
        self.assertIsNone(view['items'])
        for name in ('coverage_start', 'coverage_end', 'coverage_days', 'coverage_complete'):
            self.assertIsNone(view[name])
        self.assertEqual(view['error']['code'], code)

    async def test_full_four_days_empty_success(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((0, 1, 2, 3)))
        self.assert_coverage(view, 4)
        self.assertEqual(view['items'], [])

    async def test_partial_three_days_empty_success(self):
        view, _, _ = await self.fetch_view(PublishedHTTP())
        self.assert_coverage(view, 3)
        self.assertEqual(view['items'], [])

    async def test_partial_two_days(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-2, -1, 0, 1)))
        self.assert_coverage(view, 2)

    async def test_partial_one_day_three_valid_past_pages(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-3, -2, -1, 0)))
        self.assert_coverage(view, 1)

    def test_single_trusted_page_date_model(self):
        # Tests the date model, not approval of an index with missing links.
        page = parse_page(document(day='07.10.2026.'), URL)
        state = SourceState()
        state.accept(FetchResult(EDSSnapshot((page,))), NOW)
        self.assert_coverage(state.render(EDSProvider(None), NOW), 1)

    def test_two_trusted_pages_empty_date_model(self):
        pages = tuple(parse_page(document(day=f'{d}.10.2026.'), URL) for d in ('07', '08'))
        state = SourceState()
        state.accept(FetchResult(EDSSnapshot(pages)), NOW)
        self.assert_coverage(state.render(EDSProvider(None), NOW), 2)

    async def test_today_missing(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-1, 1, 2, 3)))
        self.assert_failure(view, 'coverage_expired')

    async def test_future_gap_not_silently_truncated(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-1, 0, 2, 3)))
        self.assert_failure(view, 'coverage_gap')

    async def test_duplicate_current_date(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-1, 0, 0, 1)))
        self.assert_failure(view, 'date_duplicate')

    async def test_duplicate_past_date_not_ignored(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-1, -1, 0, 1)))
        self.assert_failure(view, 'date_duplicate')

    async def test_implausible_future_date(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((0, 1, 2, 4)))
        self.assert_failure(view, 'date_mismatch')

    async def test_http_error_not_partial(self):
        http = PublishedHTTP()
        http.fail = (3, SourceError('http_error', 'HTTP 500'))
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'http_error')

    async def test_past_http_error_not_ignored(self):
        http = PublishedHTTP()
        http.fail = (0, SourceError('http_error', 'HTTP 500'))
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'http_error')

    async def test_timeout_not_partial(self):
        http = PublishedHTTP()
        http.fail = (2, TimeoutError())
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'timeout')

    async def test_missing_table_not_partial(self):
        http = PublishedHTTP()
        http.bad[0] = '<html>maintenance</html>'
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'table_count')

    async def test_parser_error_past_page_not_ignored(self):
        http = PublishedHTTP()
        http.bad[0] = document(row()).split('</table>')[0]
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'truncated_html')

    async def test_changed_headers_not_partial(self):
        http = PublishedHTTP()
        http.bad[3] = document(headers=('Ogranak', 'Region', 'Vreme', 'Ulice'))
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'table_headers')

    async def test_invalid_relevant_time_on_past_page_not_ignored(self):
        view, _, _ = await self.fetch_view(PublishedHTTP(rows={-1: row(times='unknown')}))
        self.assert_failure(view, 'time_format')

    async def test_missing_link_not_shorter_publication(self):
        http = PublishedHTTP()
        http.index = http.index.replace('Kraljevo_Dan_3_Iskljucenja.htm', 'not-a-day.htm')
        view, _, _ = await self.fetch_view(http)
        self.assert_failure(view, 'links_missing')
        self.assertEqual(http.calls, [INDEX_URL])

    async def test_partial_with_current_outage(self):
        view, _, _ = await self.fetch_view(PublishedHTTP(rows={0: row()}))
        self.assert_coverage(view, 3, 1)
        self.assertEqual(view['items'][0]['date'], '2026-10-07')
        self.assertEqual(view['items'][0]['area'], 'Мисача')

    async def test_past_outage_ignored(self):
        view, _, _ = await self.fetch_view(PublishedHTTP(rows={-1: row(), 1: row()}))
        self.assert_coverage(view, 3, 1)
        self.assertEqual(view['items'][0]['day'], 'Morgen')

    async def test_running_outage_retained(self):
        view, _, _ = await self.fetch_view(PublishedHTTP(rows={0: row()}))
        self.assertEqual(view['items'][0]['status'], 'laufend')

    async def test_local_expiry_preserves_coverage_without_http(self):
        http = PublishedHTTP(rows={0: row(times='09:00-10:30')})
        view, provider, state = await self.fetch_view(http)
        self.assert_coverage(view, 3, 1)
        calls = len(http.calls)
        self.assert_coverage(state.render(provider, NOW+timedelta(minutes=30)), 3)
        self.assertEqual(len(http.calls), calls)

    async def test_repeat_partial_fetch_is_success(self):
        http = PublishedHTTP()
        for _ in range(3):
            view, _, _ = await self.fetch_view(http)
            self.assert_coverage(view, 3)
        self.assertEqual(len(http.calls), 15)

    async def test_partial_stale_and_source_failure(self):
        _, provider, state = await self.fetch_view(PublishedHTTP())
        self.assert_coverage(state.render(provider, NOW+timedelta(minutes=65)), 3)
        self.assert_failure(state.render(provider, NOW+timedelta(minutes=66)), 'stale')
        state.reject(SourceError('network', 'Offline'), NOW+timedelta(minutes=15))
        self.assert_failure(state.render(provider, NOW+timedelta(minutes=15)), 'network')

    async def test_no_current_pages(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((-4, -3, -2, -1)))
        self.assert_failure(view, 'coverage_expired')

    def test_empty_snapshot_not_zero(self):
        state = SourceState()
        state.accept(FetchResult(EDSSnapshot(())), NOW)
        self.assert_failure(state.render(EDSProvider(None), NOW), 'coverage_expired')

    async def test_unordered_navigation_sorted_by_explicit_date(self):
        view, _, _ = await self.fetch_view(PublishedHTTP((2, -1, 1, 0), rows={0: row(), 1: row(), 2: row()}))
        self.assert_coverage(view, 3, 3)
        self.assertEqual([i['date'] for i in view['items']], ['2026-10-07','2026-10-08','2026-10-09'])

    async def test_multiple_deduplicated_rows_in_partial(self):
        view, _, _ = await self.fetch_view(PublishedHTTP(rows={0: row()+row()+row(area='Други крај')}))
        self.assert_coverage(view, 3, 2)

    async def test_diagnostics_dates_links_and_ignored_past(self):
        _, provider, state = await self.fetch_view(PublishedHTTP(rows={0: row()}))
        diag = provider.diagnostics()
        self.assertEqual(len(diag['discovered_pages']), 4)
        self.assertEqual([p['date'] for p in diag['parsed_pages']], ['2026-10-06','2026-10-07','2026-10-08','2026-10-09'])
        self.assertEqual(diag['validated_coverage_at_fetch']['ignored_past_dates'], ['2026-10-06'])
        self.assertEqual(state.result.diagnostics['coverage_days'], 3)
        self.assertNotIn('Мисача', json.dumps(diag, ensure_ascii=False))
        self.assertNotIn('<table', repr(diag))

    async def test_both_original_morning_fixture_sets(self):
        for folder in ('2026-10-07', 'live-verification-2026-10-07'):
            with self.subTest(folder=folder):
                http = PublishedHTTP()
                http.index = (FIXTURES/folder/'index.html').read_text('utf-8-sig')
                http.bad = {i: (FIXTURES/folder/f'day{i}.html').read_text('utf-8-sig') for i in range(4)}
                view, _, _ = await self.fetch_view(http, NOW.replace(hour=7, minute=30))
                self.assert_coverage(view, 3)
                self.assertEqual(view['items'], [])

    async def test_new_live_fixture_after_complete_rotation(self):
        folder = FIXTURES/'coverage-live-2026-10-07'
        http = PublishedHTTP()
        http.index = (folder/'index.html').read_text('utf-8-sig')
        http.bad = {i: (folder/f'day{i}.html').read_text('utf-8-sig') for i in range(4)}
        view, _, _ = await self.fetch_view(http)
        self.assert_coverage(view, 4)

    def test_contradictory_item_date_rejected_even_on_past_page(self):
        page = parse_page(document(row(), day='06.10.2026.'), URL)
        page['outages'][0]['date'] = '2026-10-07'
        today = parse_page(document(day='07.10.2026.'), URL)
        state = SourceState()
        state.accept(FetchResult(EDSSnapshot((page,today))), NOW)
        self.assert_failure(state.render(EDSProvider(None), NOW), 'date_mismatch')


class CoverageCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_fetch_partial_without_restored_state(self):
        with patch.object(c, 'utcnow', return_value=NOW):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(PublishedHTTP(), clock=lambda:NOW))
            self.assertIsNone(coord.state.result)
            view = await coord._async_update_data()
        self.assertTrue(view['available'])
        self.assertEqual(view['coverage_days'], 3)
        self.assertEqual(coord.update_interval, timedelta(minutes=15))

    async def test_partial_then_full_rotation_resets_interval(self):
        http = PublishedHTTP()
        with patch.object(c, 'utcnow', return_value=NOW):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(http, clock=lambda:NOW))
            first = await coord._async_update_data()
            self.assertFalse(first['coverage_complete'])
            self.assertEqual(coord.update_interval, timedelta(minutes=15))
            http.offsets = (0, 1, 2, 3)
            second = await coord._async_update_data()
        self.assertTrue(second['coverage_complete'])
        self.assertEqual(second['coverage_days'], 4)
        self.assertEqual(coord.update_interval, timedelta(minutes=30))

    async def test_full_then_failure_is_immediately_unavailable(self):
        http = PublishedHTTP((0, 1, 2, 3))
        with patch.object(c, 'utcnow', return_value=NOW):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(http, clock=lambda:NOW))
            good = await coord._async_update_data()
            http.fail = (3, SourceError('http_error', 'HTTP 500'))
            bad = await coord._async_update_data()
        self.assertFalse(bad['available'])
        self.assertIsNone(bad['count'])
        self.assertIsNone(bad['coverage_end'])
        self.assertEqual(bad['last_success'], good['last_success'])
        self.assertEqual(coord.update_interval, timedelta(minutes=30))

    async def test_partial_then_failure_returns_to_normal_polling(self):
        http = PublishedHTTP()
        with patch.object(c, 'utcnow', return_value=NOW):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(http, clock=lambda:NOW))
            await coord._async_update_data()
            http.fail = (0, SourceError('timeout', 'Timeout'))
            view = await coord._async_update_data()
        self.assertFalse(view['available'])
        self.assertEqual(coord.update_interval, timedelta(minutes=30))

    async def test_local_midnight_reprojects_partial_and_refreshes_once(self):
        before = NOW.replace(hour=23, minute=59)
        after = before+timedelta(minutes=1)
        http = PublishedHTTP()
        with patch.object(c, 'utcnow', return_value=before):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(http, clock=lambda:before))
            coord.data = await coord._async_update_data()
        with patch.object(c, 'utcnow', return_value=after):
            await coord._local_tick(after)
            await coord._local_tick(after)
        self.assertEqual(coord.data['coverage_start'], '2026-10-08')
        self.assertEqual(coord.data['coverage_days'], 2)
        self.assertTrue(coord.data['available'])
        self.assertEqual(coord.refreshes, 1)
        self.assertEqual(len(http.calls), 5)

    async def test_local_expiry_through_coordinator(self):
        http = PublishedHTTP(rows={0: row(times='09:00-10:30')})
        with patch.object(c, 'utcnow', return_value=NOW):
            coord = c.ProviderCoordinator(None, Entry(), EDSProvider(http, clock=lambda:NOW))
            coord.data = await coord._async_update_data()
            self.assertEqual(coord.data['count'], 1)
        with patch.object(c, 'utcnow', return_value=NOW+timedelta(minutes=30)):
            await coord._local_tick(NOW+timedelta(minutes=30))
        self.assertEqual(coord.data['count'], 0)
        self.assertEqual(coord.data['coverage_days'], 3)
        self.assertEqual(coord.notifications, 1)
        self.assertEqual(coord.refreshes, 0)
        self.assertEqual(len(http.calls), 5)
