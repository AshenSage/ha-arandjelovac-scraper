"""One instance per provider/config entry. No provider-specific imports."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any, Generic, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import FetchResult, Provider, SourceError, SourceState, utcnow, validate_projection

_LOGGER = logging.getLogger(__name__)
Payload = TypeVar('Payload')


class ProviderCoordinator(DataUpdateCoordinator[dict[str, Any]], Generic[Payload]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 provider: Provider[Payload]) -> None:
        super().__init__(hass, _LOGGER, name=provider.spec.unique_id,
                         config_entry=entry, update_interval=provider.spec.poll_interval,
                         always_update=False)
        self.provider = provider
        self.state: SourceState[Payload] = SourceState()
        self._logged_error: tuple[str, str] | None = None
        self._consumed_refresh: datetime | None = None
        self._started = False
        self._closing = False
        self._fetch_task: asyncio.Task[FetchResult[Payload]] | None = None

    async def async_shutdown(self) -> None:
        self._closing = True
        await super().async_shutdown()
        task = self._fetch_task
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @callback
    def start_local_updates(self) -> None:
        if not self._started:
            self._started = True
            assert self.config_entry is not None
            self.config_entry.async_on_unload(async_track_time_interval(
                self.hass, self._local_tick, self.provider.spec.local_interval))

    def _render(self, now: datetime) -> dict[str, Any]:
        try:
            return self.state.render(self.provider, now)
        except Exception as exc:
            # Boundary for programming errors in one provider. Never log payloads.
            _LOGGER.error('Provider %s projection failed (%s)',
                          self.provider.spec.provider, type(exc).__name__)
            self.state.error = SourceError('internal_error', 'Interner Providerfehler; siehe Protokoll.')
            return self.state.render(self.provider, now)

    async def _async_update_data(self) -> dict[str, Any]:
        if self._closing:
            raise asyncio.CancelledError
        try:
            async with asyncio.timeout(self.provider.spec.cycle_timeout):
                self._fetch_task = asyncio.create_task(self.provider.async_fetch())
                result = await self._fetch_task
                finished = utcnow()
                validate_projection(self.provider.project(result.payload, finished), self.provider.spec)
                # Validate the complete public byte budget before accepting success.
                trial = SourceState(result=result, last_attempt=finished, last_success=finished)
                trial_view = trial.render(self.provider, finished)
                if not trial_view['available']:
                    error = trial_view['error']
                    raise SourceError(error['code'], error['message'], scope=error['scope'])
            self.state.accept(result, finished)
        except TimeoutError:
            self.state.reject(SourceError('timeout', 'Gesamtabruf überschreitet das Zeitlimit.'), utcnow())
        except SourceError as exc:
            self.state.reject(exc, utcnow())
        except Exception as exc:
            _LOGGER.error('Provider %s fetch failed (%s)',
                          self.provider.spec.provider, type(exc).__name__)
            self.state.reject(SourceError('internal_error', 'Interner Providerfehler; siehe Protokoll.'), utcnow())
        finally:
            self._fetch_task = None
        view = self._render(utcnow())
        spec = self.provider.spec
        self.update_interval = (spec.partial_poll_interval
                                if view['available'] and view['coverage_complete'] is False
                                and spec.partial_poll_interval is not None
                                else spec.poll_interval)
        self._log_health(view)
        # A valid error envelope is a successful coordinator update. Entity.available
        # explicitly follows its health flag, so diagnostics remain current on failure.
        return view

    @callback
    def _log_health(self, view: dict[str, Any]) -> None:
        error = view['error']
        identity = (error['scope'], error['code']) if error else None
        if identity and identity != self._logged_error:
            _LOGGER.warning('Provider %s unavailable [%s.%s]', self.provider.spec.provider, *identity)
        elif not identity and self._logged_error:
            _LOGGER.info('Provider %s available again', self.provider.spec.provider)
        self._logged_error = identity

    async def _local_tick(self, _now: datetime) -> None:
        if self._closing or not tuple(self.async_contexts()):
            return
        now = utcnow()
        view = self._render(now)
        if view != self.data:
            self.data = view
            self._log_health(view)
            # Deliberately avoid async_set_updated_data: it reschedules the HTTP poll.
            self.async_update_listeners()
        result = self.state.result
        deadline = result.refresh_at if result else None
        if deadline and now >= deadline and deadline != self._consumed_refresh:
            self._consumed_refresh = deadline
            await self.async_request_refresh()

    def diagnostics(self) -> dict[str, Any]:
        spec = self.provider.spec
        return {
            'provider': spec.provider,
            'poll_seconds': spec.poll_interval.total_seconds(),
            'effective_poll_seconds': self.update_interval.total_seconds(),
            'partial_poll_seconds': (spec.partial_poll_interval.total_seconds()
                                     if spec.partial_poll_interval is not None else None),
            'stale_seconds': spec.stale_after.total_seconds(),
            'cycle_timeout_seconds': spec.cycle_timeout,
            'limits': {'items': spec.max_items, 'text_length': spec.max_text_length,
                       'attribute_bytes': spec.max_attribute_bytes},
            'health': {k: v for k, v in self._render(utcnow()).items()
                       if k not in ('items', 'metadata')},
            'last_success_summary': self.state.result.diagnostics if self.state.result else None,
            'transport': self.provider.diagnostics(),
        }
