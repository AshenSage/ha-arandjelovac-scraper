"""Aranđelovac Live: independent source entries plus the bundled dashboard card."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .common.coordinator import ProviderCoordinator
from .common.http import HttpClient, HttpPolicy
from .const import DOMAIN, VERSION
from .providers.eds.provider import EDSProvider
from .providers.eds.source import HOSTS as EDS_HOSTS
from .providers.notices.provider import HOSTS, SOURCES, NoticeProvider

PLATFORMS = [Platform.SENSOR]
type LiveConfigEntry = ConfigEntry[ProviderCoordinator[Any]]
CARD_URL = f'/{DOMAIN}/arandjelovac-live-card.js?v={VERSION}'


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve and automatically load the card; no manual resource copy required."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths([
        StaticPathConfig(f'/{DOMAIN}/arandjelovac-live-card.js',
                         str(Path(__file__).parent/'frontend'/'arandjelovac-live-card.js'),
                         cache_headers=False)
    ])
    add_extra_js_url(hass,CARD_URL)
    return True


async def _options_updated(hass: HomeAssistant, entry: LiveConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: LiveConfigEntry) -> bool:
    key=entry.data.get('provider')
    if entry.data.get('location')!='arandjelovac' or key not in ('eds',*SOURCES):
        raise ConfigEntryError('Unsupported provider or location')
    session=async_get_clientsession(hass)
    if key=='eds':
        provider=EDSProvider(HttpClient(session,HttpPolicy(EDS_HOSTS)),hass.async_add_executor_job)
    else:
        provider=NoticeProvider(key,HttpClient(session,HttpPolicy(HOSTS[key],timeout=30,max_redirects=1)),
                                hass.async_add_executor_job,dict(entry.options))
    coordinator=entry.runtime_data=ProviderCoordinator(hass,entry,provider)
    await coordinator.async_refresh()
    try:
        await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    except Exception:
        await coordinator.async_shutdown()
        raise
    coordinator.start_local_updates()
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LiveConfigEntry) -> bool:
    unloaded=await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
    if unloaded:await entry.runtime_data.async_shutdown()
    return unloaded
