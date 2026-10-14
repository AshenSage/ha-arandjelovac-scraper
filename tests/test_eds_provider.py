"""Provider orchestration with offline HTML, no Home Assistant runtime."""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import unittest

import bootstrap
from live_test.common.models import SourceError, SourceState
from live_test.providers.eds.provider import EDSProvider
from live_test.providers.eds.source import INDEX_URL, TZ

FIXTURES=bootstrap.ROOT/'tests/fixtures/eds/2026-10-06'
NOW=datetime(2026,10,6,10,tzinfo=TZ)


class FixtureHTTP:
    def __init__(self,fail=None):
        self.fail=fail
        self.observations=[]
        self.calls=[]
        self.active=0
        self.max_active=0
    def clear_observations(self): self.observations.clear()
    async def get_text(self,url,**kwargs):
        self.calls.append(url)
        if url == INDEX_URL: return (FIXTURES/'index.html').read_text('utf-8-sig')
        self.active+=1
        self.max_active=max(self.max_active,self.active)
        try:
            await asyncio.sleep(0.002)
            slot=int(url.split('_Dan_')[1][0])
            if slot==self.fail: raise SourceError('http_error','HTTP 500')
            return (FIXTURES/f'day{slot}.html').read_text('utf-8-sig')
        finally: self.active-=1


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_four_pages_concurrency_and_metadata(self):
        http=FixtureHTTP()
        provider=EDSProvider(http,clock=lambda:NOW)
        result=await provider.async_fetch()
        self.assertEqual(len(result.payload.pages),4)
        self.assertEqual(len(http.calls),5)
        self.assertLessEqual(http.max_active,2)
        self.assertEqual(result.refresh_at,datetime(2026,10,7,0,tzinfo=TZ))
        self.assertEqual(len(result.diagnostics['coverage']),4)

    async def test_one_page_failure_no_partial_result(self):
        http=FixtureHTTP(fail=2)
        provider=EDSProvider(http,clock=lambda:NOW)
        with self.assertRaises(SourceError) as cm: await provider.async_fetch()
        self.assertEqual(cm.exception.code,'http_error')
        self.assertEqual(http.active,0)

    async def test_end_time_local_projection_without_fetch(self):
        http=FixtureHTTP()
        provider=EDSProvider(http,clock=lambda:NOW)
        result=await provider.async_fetch()
        before=provider.project(result.payload,NOW)
        after=provider.project(result.payload,NOW.replace(hour=13))
        self.assertEqual(before.count,1)
        self.assertEqual(after.count,0)
        self.assertEqual(len(http.calls),5)
        self.assertEqual(before.items[0]['status'],'laufend')
        self.assertEqual(before.items[0]['day'],'Heute')

    async def test_stable_id_and_no_mutation(self):
        provider=EDSProvider(FixtureHTTP(),clock=lambda:NOW)
        result=await provider.async_fetch()
        first=provider.project(result.payload,NOW)
        second=provider.project(result.payload,NOW+timedelta(minutes=1))
        self.assertEqual(first.items[0]['id'],second.items[0]['id'])
        self.assertNotIn('id',result.payload.pages[0]['outages'][0])

    async def test_rollover_retains_contiguous_partial_coverage(self):
        provider=EDSProvider(FixtureHTTP(),clock=lambda:NOW)
        result=await provider.async_fetch()
        projection=provider.project(result.payload,NOW+timedelta(days=1))
        self.assertEqual(projection.coverage_days,3)
        self.assertFalse(projection.coverage_complete)

    async def test_midnight_during_fetch(self):
        times=iter([NOW,NOW+timedelta(days=1)])
        provider=EDSProvider(FixtureHTTP(),clock=lambda:next(times))
        with self.assertRaises(SourceError) as cm: await provider.async_fetch()
        self.assertEqual(cm.exception.code,'midnight_race')

    async def test_live_rotated_window_is_valid_partial(self):
        provider=EDSProvider(FixtureHTTP(),clock=lambda:NOW+timedelta(days=1))
        state=SourceState()
        try: state.accept(await provider.async_fetch(),NOW+timedelta(days=1))
        except SourceError as exc: state.reject(exc,NOW+timedelta(days=1))
        view=state.render(provider,NOW+timedelta(days=1))
        self.assertTrue(view['available'])
        self.assertEqual(view['count'],0)
        self.assertEqual(view['coverage_start'],'2026-10-07')
        self.assertEqual(view['coverage_end'],'2026-10-09')
        self.assertEqual(view['coverage_days'],3)
        self.assertFalse(view['coverage_complete'])
        self.assertIsNone(view['error'])
