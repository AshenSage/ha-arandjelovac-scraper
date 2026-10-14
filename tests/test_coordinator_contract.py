"""Coordinator contract tests with minimal HA doubles, NOT HA runtime tests."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

import bootstrap
from live_test.common.models import FetchResult, Projection, SourceError, SourceSpec, utcnow


class DataUpdateCoordinatorDouble:
    def __class_getitem__(cls,item): return cls
    def __init__(self,hass,logger,**kwargs):
        self.hass=hass
        self.config_entry=kwargs['config_entry']
        self.update_interval=kwargs['update_interval']
        self.data=None
        self.notifications=0
        self.refreshes=0
        self.last_update_success=True
    def async_contexts(self): return iter(['test'])
    def async_update_listeners(self): self.notifications+=1
    async def async_request_refresh(self): self.refreshes+=1
    async def async_shutdown(self): pass


def load_coordinator():
    replacements={}
    for name in ('homeassistant','homeassistant.config_entries','homeassistant.core',
                 'homeassistant.helpers','homeassistant.helpers.event','homeassistant.helpers.update_coordinator'):
        replacements[name]=types.ModuleType(name)
    replacements['homeassistant.config_entries'].ConfigEntry=object
    replacements['homeassistant.core'].HomeAssistant=object
    replacements['homeassistant.core'].callback=lambda f:f
    replacements['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator=DataUpdateCoordinatorDouble
    replacements['homeassistant.helpers.event'].async_track_time_interval=lambda *args: lambda: None
    with patch.dict(sys.modules,replacements):
        spec=importlib.util.spec_from_file_location('live_test.common.coordinator_contract',bootstrap.PACKAGE/'common/coordinator.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


c=load_coordinator()


class Entry:
    def __init__(self): self.callbacks=[]
    def async_on_unload(self,callback): self.callbacks.append(callback)


class Provider:
    spec=SourceSpec('fake','town','Fake','fake','fake','https://example.com','mdi:water',
                    timedelta(minutes=15),timedelta(minutes=35))
    def __init__(self,fail=False): self.fail=fail; self.fetches=0
    async def async_fetch(self):
        self.fetches+=1
        if self.fail: raise SourceError('network','Offline')
        return FetchResult([{'water_field':'test'}],diagnostics={'rows':1})
    def project(self,payload,now): return Projection(len(payload),tuple(payload))
    def diagnostics(self): return {'requests':[]}


class CoordinatorContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_isolated_and_intervals_independent(self):
        one,two=Provider(),Provider(fail=True)
        two.spec=replace(two.spec,provider='other',poll_interval=timedelta(minutes=60))
        a,b=c.ProviderCoordinator(None,Entry(),one),c.ProviderCoordinator(None,Entry(),two)
        va,vb=await asyncio.gather(a._async_update_data(),b._async_update_data())
        self.assertTrue(va['available'])
        self.assertFalse(vb['available'])
        self.assertEqual(a.update_interval,timedelta(minutes=15))
        self.assertEqual(b.update_interval,timedelta(minutes=60))

    async def test_recovery_and_success_timestamp(self):
        provider=Provider()
        coordinator=c.ProviderCoordinator(None,Entry(),provider)
        first=await coordinator._async_update_data()
        provider.fail=True
        failed=await coordinator._async_update_data()
        self.assertEqual(first['last_success'],failed['last_success'])
        self.assertIsNone(failed['items'])
        provider.fail=False
        self.assertTrue((await coordinator._async_update_data())['available'])

    async def test_local_timer_does_not_fetch_or_reschedule_http(self):
        provider=Provider()
        coordinator=c.ProviderCoordinator(None,Entry(),provider)
        coordinator.data=await coordinator._async_update_data()
        await coordinator._local_tick(utcnow())
        self.assertEqual(provider.fetches,1)
        self.assertEqual(coordinator.refreshes,0)
        self.assertEqual(coordinator.notifications,0)
        coordinator.state.last_success-=timedelta(minutes=40)
        await coordinator._local_tick(utcnow())
        self.assertEqual(coordinator.notifications,1)
        self.assertFalse(coordinator.data['available'])

    async def test_deadline_consumed_once(self):
        provider=Provider()
        coordinator=c.ProviderCoordinator(None,Entry(),provider)
        coordinator.data=await coordinator._async_update_data()
        coordinator.state.result=FetchResult([],refresh_at=utcnow()-timedelta(seconds=1))
        await coordinator._local_tick(utcnow())
        await coordinator._local_tick(utcnow())
        self.assertEqual(coordinator.refreshes,1)

    async def test_callback_registration_once(self):
        entry=Entry()
        coordinator=c.ProviderCoordinator(None,entry,Provider())
        coordinator.start_local_updates()
        coordinator.start_local_updates()
        self.assertEqual(len(entry.callbacks),1)

    async def test_cycle_timeout(self):
        class SlowProvider(Provider):
            async def async_fetch(self): await asyncio.sleep(60)
        provider=SlowProvider()
        provider.spec=replace(provider.spec,cycle_timeout=0.005)
        view=await c.ProviderCoordinator(None,Entry(),provider)._async_update_data()
        self.assertEqual(view['error']['code'],'timeout')

    async def test_unexpected_exception_is_provider_local(self):
        class BrokenProvider(Provider):
            async def async_fetch(self): raise RuntimeError('DO NOT LOG SECRET')
        with self.assertLogs(c._LOGGER,level='ERROR') as logs:
            view=await c.ProviderCoordinator(None,Entry(),BrokenProvider())._async_update_data()
        self.assertNotIn('DO NOT LOG SECRET',' '.join(logs.output))
        self.assertEqual(view['error']['code'],'internal_error')

    async def test_cancel_not_swallowed(self):
        class SlowProvider(Provider):
            async def async_fetch(self): await asyncio.sleep(60)
        task=asyncio.create_task(c.ProviderCoordinator(None,Entry(),SlowProvider())._async_update_data())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_diagnostics_contains_no_item_payload(self):
        coordinator=c.ProviderCoordinator(None,Entry(),Provider())
        coordinator.data=await coordinator._async_update_data()
        diagnostics=coordinator.diagnostics()
        self.assertNotIn('water_field',repr(diagnostics))
        self.assertEqual(diagnostics['last_success_summary'],{'rows':1})

    async def test_shutdown_cancels_inflight_provider(self):
        started=asyncio.Event()
        stopped=asyncio.Event()
        class SlowProvider(Provider):
            async def async_fetch(self):
                started.set()
                try: await asyncio.sleep(60)
                finally: stopped.set()
        coordinator=c.ProviderCoordinator(None,Entry(),SlowProvider())
        task=asyncio.create_task(coordinator._async_update_data())
        await started.wait()
        await coordinator.async_shutdown()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(stopped.is_set())
        await coordinator._local_tick(utcnow())
        self.assertEqual(coordinator.refreshes,0)
