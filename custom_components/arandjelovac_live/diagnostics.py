"""Explicit allowlist: no config-entry dump, raw HTML, items or headers."""
from typing import Any

from homeassistant.core import HomeAssistant

from . import LiveConfigEntry
from .const import VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LiveConfigEntry,
) -> dict[str, Any]:
    return {'integration_version': VERSION, 'source': entry.runtime_data.diagnostics()}
