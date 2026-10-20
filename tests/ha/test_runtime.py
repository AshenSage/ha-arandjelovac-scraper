"""Exercise real HA 2026.10.1 config flows, platform setup and unload."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arandjelovac_live.common.models import FetchResult, SourceError
from custom_components.arandjelovac_live.const import DOMAIN
from custom_components.arandjelovac_live.providers.notices.provider import NoticeSnapshot
from custom_components.arandjelovac_live.config_flow import PROVIDERS


def test_card_and_provider_icons_exist_in_supported_frontend():
    """Catch blank icon boxes against HA's actual bundled MDI catalogue."""
    import json
    import re
    from pathlib import Path
    import hass_frontend
    from custom_components.arandjelovac_live.providers.notices.provider import SOURCES
    names={entry['name'] for entry in json.loads((Path(hass_frontend.__file__).parent/'static/mdi/iconList.json').read_text())}
    card=(Path(__file__).parents[2]/'custom_components/arandjelovac_live/frontend/arandjelovac-live-card.js').read_text()
    used=set(re.findall(r'mdi:([a-z0-9-]+)',card))|{source['icon'].removeprefix('mdi:') for source in SOURCES.values()}
    assert used<=names,f'Unknown HA icons: {used-names}'


async def test_complete_package_creates_independent_entries(hass):
    with patch('custom_components.arandjelovac_live.async_setup_entry',return_value=True):
        first=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_USER})
        assert first['type']=='form'
        result=await hass.config_entries.flow.async_configure(first['flow_id'],{'provider':'all'})
        await hass.async_block_till_done()
    assert result['type']=='create_entry'
    entries=hass.config_entries.async_entries(DOMAIN)
    assert len(entries)==len(PROVIDERS)
    assert {e.unique_id for e in entries}=={f'{p}:arandjelovac' for p in PROVIDERS}
    again=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_USER})
    again=await hass.config_entries.flow.async_configure(again['flow_id'],{'provider':'all'})
    assert again['type']=='abort'
    assert again['reason']=='already_configured'


@pytest.mark.parametrize('provider',list(PROVIDERS))
async def test_individual_flow_and_duplicate(hass,provider):
    with patch('custom_components.arandjelovac_live.async_setup_entry',return_value=True):
        result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_IMPORT},data={'provider':provider})
        assert result['type']=='create_entry'
        again=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_IMPORT},data={'provider':provider})
        assert again['type']=='abort'
        assert again['reason']=='already_configured'
        await hass.async_block_till_done()


async def test_missing_sources_can_complete_existing_eds(hass):
    entry=MockConfigEntry(domain=DOMAIN,unique_id='eds:arandjelovac',data={'provider':'eds','location':'arandjelovac'})
    entry.add_to_hass(hass)
    with patch('custom_components.arandjelovac_live.async_setup_entry',return_value=True):
        result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_USER})
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'provider':'all'})
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN))==len(PROVIDERS)
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry


async def test_upgrade_adds_missing_sources_to_existing_six(hass):
    old=[]
    for key in ['eds','jkp','putevi','opstina','kultura','tourism']:
        entry=MockConfigEntry(domain=DOMAIN,unique_id=f'{key}:arandjelovac',data={'provider':key,'location':'arandjelovac'})
        entry.add_to_hass(hass);old.append(entry)
    with patch('custom_components.arandjelovac_live.async_setup_entry',return_value=True):
        result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_USER})
        await hass.config_entries.flow.async_configure(result['flow_id'],{'provider':'all'})
        await hass.async_block_till_done()
    entries=hass.config_entries.async_entries(DOMAIN)
    assert len(entries)==len(PROVIDERS)
    assert {e.data['provider'] for e in entries}-{e.data['provider'] for e in old}=={'museum','library','manifestations','jkp_works'}
    assert all(hass.config_entries.async_get_entry(e.entry_id) is e for e in old)


async def test_sensor_lifecycle_and_failed_source_isolation(hass):
    await async_setup_component(hass,'sensor',{})
    entry=MockConfigEntry(domain=DOMAIN,unique_id='jkp:arandjelovac',data={'provider':'jkp','location':'arandjelovac'})
    entry.add_to_hass(hass)
    result=FetchResult(NoticeSnapshot((),{}))
    with patch('custom_components.arandjelovac_live.providers.notices.provider.NoticeProvider.async_fetch',return_value=result),patch('custom_components.arandjelovac_live.async_setup',return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state=hass.states.get('sensor.arandjelovac_jkp_water')
        assert state is not None
        assert state.state=='0'
        assert state.attributes['integration_domain']==DOMAIN
        registry=er.async_get(hass)
        entity=registry.async_get('sensor.arandjelovac_jkp_water')
        assert entity.unique_id=='jkp:arandjelovac:count'
        coordinator=entry.runtime_data
        with patch.object(coordinator.provider,'async_fetch',side_effect=SourceError('network','Offline')):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        state=hass.states.get(entity.entity_id)
        assert state.state=='unavailable'
        assert 'items' not in state.attributes
        health=hass.states.get('sensor.arandjelovac_jkp_source')
        assert health.state=='error'
        assert health.attributes['error']['code']=='network'
        assert health.attributes['count_entity_id']==entity.entity_id
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert coordinator._closing
        assert entry.state is ConfigEntryState.NOT_LOADED
        # Same registry identity on a clean reload, no cached source truth restored.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(entity.entity_id).state=='0'
        assert er.async_get(hass).async_get(entity.entity_id).unique_id==entity.unique_id
        await hass.config_entries.async_unload(entry.entry_id)


async def test_frontend_static_path_and_module_registration(hass):
    from custom_components.arandjelovac_live import async_setup,CARD_URL
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL,UrlManager
    from unittest.mock import AsyncMock,MagicMock
    # Actual integration setup function against HA and the real URL manager.
    # HTTP transport registration is isolated; a separate browser test exercises JS.
    hass.http=MagicMock()
    hass.http.async_register_static_paths=AsyncMock()
    hass.data[DATA_EXTRA_MODULE_URL]=UrlManager(lambda *args:None,[])
    await async_setup(hass,{})
    hass.http.async_register_static_paths.assert_awaited_once()
    paths=hass.http.async_register_static_paths.call_args.args[0]
    assert paths[0].url_path=='/arandjelovac_live/arandjelovac-live-card.js'
    assert CARD_URL in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_all_sources_real_setup_http_card_and_independence(hass,freezer,hass_client):
    """Real HA entry/platform/HTTP lifecycle; only upstream HTTP is replaced."""
    from pathlib import Path
    from custom_components.arandjelovac_live.common.http import HttpClient
    from custom_components.arandjelovac_live.providers.eds.source import INDEX_URL
    freezer.move_to('2026-10-06T08:00:00+00:00')
    fixtures=Path(__file__).parents[1]/'fixtures/eds/2026-10-06'
    async def upstream(self,url,**kwargs):
        if url==INDEX_URL:return (fixtures/'index.html').read_text('utf-8-sig')
        if '_Dan_' in url:return (fixtures/f"day{url.split('_Dan_')[1][0]}.html").read_text('utf-8-sig')
        if url=='https://www.jkpbukulja.rs/vesti':
            return '<h1>Вести</h1><a href="/vesti/primer"><span>6. октобар 2026.</span><h2>Radovi na vodovodu</h2></a>'
        if '/vesti/primer' in url:return '<h1>Radovi na vodovodu</h1><div class="page-content"><p>Informacija o cevovodu.</p></div>'
        if url.endswith('/manifestacije/'):
            return '<h2>Novogodisnji bazar<br>decembar</h2><a href="/bazar/">detaljnije</a>'
        if '/wp-json/' in url:return '[]'
        if url.endswith('textfile.txt'):return 'point\ttitle\tdescription\ticonSize\ticonOffset\ticon\n'
        return '<rss><channel><title>News</title><link>https://example.test/</link></channel></rss>'
    with patch.object(HttpClient,'get_text',upstream):
        start=await hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_USER})
        result=await hass.config_entries.flow.async_configure(start['flow_id'],{'provider':'all'})
        await hass.async_block_till_done()
        entries=hass.config_entries.async_entries(DOMAIN)
        assert len(entries)==len(PROVIDERS)
        assert all(entry.state is ConfigEntryState.LOADED for entry in entries)
        coordinators={e.data['provider']:e.runtime_data for e in entries}
        assert len({id(c) for c in coordinators.values()})==len(PROVIDERS)
        assert hass.states.get('sensor.arandjelovac_eds_outages').state=='1'
        assert len([s for s in hass.states.async_all('sensor') if s.attributes.get('integration_domain')==DOMAIN])==2*len(PROVIDERS)
        client=await hass_client()
        response=await client.get('/arandjelovac_live/arandjelovac-live-card.js')
        assert response.status==200
        card_code=await response.text()
        assert 'data-event-tab' in card_code and 'calendar-day' in card_code
        with patch.object(coordinators['jkp'].provider,'async_fetch',side_effect=SourceError('network','Offline')):
            await coordinators['jkp'].async_refresh()
            await hass.async_block_till_done()
        assert hass.states.get('sensor.arandjelovac_jkp_water').state=='unavailable'
        assert hass.states.get('sensor.arandjelovac_jkp_source').state=='error'
        assert hass.states.get('sensor.arandjelovac_eds_outages').state=='1'
        for entry in entries:assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert all(c._closing for c in coordinators.values())


async def test_options_flow_reconfigures_filters(hass):
    entry=MockConfigEntry(domain=DOMAIN,unique_id='putevi:arandjelovac',data={'provider':'putevi','location':'arandjelovac'})
    entry.add_to_hass(hass)
    result=await hass.config_entries.options.async_init(entry.entry_id)
    assert result['type']=='form'
    result=await hass.config_entries.options.async_configure(result['flow_id'],{'areas':'Aranđelovac, Topola'})
    assert result['type']=='create_entry'
    assert entry.options['areas']=='Aranđelovac, Topola'


async def test_empty_municipal_categories_means_all(hass):
    entry=MockConfigEntry(domain=DOMAIN,unique_id='opstina:arandjelovac',data={'provider':'opstina','location':'arandjelovac'})
    entry.add_to_hass(hass)
    result=await hass.config_entries.options.async_init(entry.entry_id)
    result=await hass.config_entries.options.async_configure(result['flow_id'],{'categories':'','lookback_days':30})
    assert result['type']=='create_entry'
    assert entry.options['categories']==''


async def test_source_health_distinguishes_incomplete_window(hass):
    from custom_components.arandjelovac_live.sensor import SourceHealthSensor
    from unittest.mock import MagicMock
    coordinator=MagicMock()
    coordinator.provider.spec.provider='jkp'
    coordinator.provider.spec.unique_id='jkp:arandjelovac'
    coordinator.data={'available':True,'metadata':{'complete_for_window':False}}
    sensor=SourceHealthSensor(coordinator,MagicMock())
    assert sensor.native_value=='partial'
    coordinator.data['metadata']['complete_for_window']=True
    assert sensor.native_value=='ok'
