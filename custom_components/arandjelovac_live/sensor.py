"""Shared bounded count/list sensor; provider determines item semantics."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LiveConfigEntry
from .common.coordinator import ProviderCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: LiveConfigEntry,
                           async_add_entities: AddEntitiesCallback) -> None:
    count=ProviderSensor(entry.runtime_data)
    async_add_entities([count,SourceHealthSensor(entry.runtime_data,count)])


class ProviderSensor(CoordinatorEntity[ProviderCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({
        'items', 'metadata', 'last_attempt', 'last_success', 'error',
        'items_count', 'items_truncated',
    })

    def __init__(self, coordinator: ProviderCoordinator) -> None:
        spec = coordinator.provider.spec
        super().__init__(coordinator, context=spec.unique_id)
        # Initial suggestion only; the entity registry preserves user renames.
        self.entity_id = f'sensor.{spec.suggested_object_id}'
        self._attr_unique_id = f'{spec.unique_id}:count'
        self._attr_translation_key = spec.translation_key
        self._attr_icon = spec.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, spec.unique_id)}, name=spec.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.last_update_success and self.coordinator.data
                    and self.coordinator.data['available'])

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data['count'] if self.available else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**{key: value for key, value in (self.coordinator.data or {}).items() if key != 'count'},
                'integration_domain': DOMAIN,
                'entity_kind': 'count',
                'source_url': self.coordinator.provider.spec.source_url}


class SourceHealthSensor(CoordinatorEntity[ProviderCoordinator], SensorEntity):
    """Always-readable diagnostics while HA hides unavailable count attributes."""
    _attr_has_entity_name = True
    _attr_name = 'Quellenstatus'
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = 'mdi:cloud-check-outline'
    _unrecorded_attributes = frozenset({'metadata','last_attempt','last_success','error'})

    def __init__(self, coordinator: ProviderCoordinator, count: ProviderSensor) -> None:
        spec=coordinator.provider.spec
        super().__init__(coordinator,context=spec.unique_id)
        self._count=count
        self.entity_id=f'sensor.arandjelovac_{spec.provider}_source'
        self._attr_unique_id=f'{spec.unique_id}:source'
        self._attr_device_info=DeviceInfo(identifiers={(DOMAIN,spec.unique_id)})

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        if not self.coordinator.data or not self.coordinator.data.get('available'):return 'error'
        return 'partial' if self.coordinator.data.get('metadata',{}).get('complete_for_window') is False else 'ok'

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**{key:value for key,value in (self.coordinator.data or {}).items()
                   if key not in ('items',)},
                'integration_domain':DOMAIN,'entity_kind':'source_health',
                'count_entity_id':self._count.entity_id,
                'source_url':self.coordinator.provider.spec.source_url}
