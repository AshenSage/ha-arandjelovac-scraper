"""Small source contract and availability logic; no HA or HTTP imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
import json
from typing import Any, Generic, Protocol, TypeVar

Payload = TypeVar('Payload')


class SourceError(ValueError):
    def __init__(self, code: str, message: str, *, scope: str = 'common') -> None:
        super().__init__(message)
        self.code = code
        self.scope = scope

    def as_dict(self) -> dict[str, str]:
        return {'scope': self.scope, 'code': self.code, 'message': str(self)[:300]}


@dataclass(frozen=True)
class SourceSpec:
    provider: str
    location: str
    title: str
    translation_key: str
    suggested_object_id: str
    source_url: str
    icon: str
    poll_interval: timedelta
    stale_after: timedelta
    time_zone: tzinfo = timezone.utc
    cycle_timeout: float = 50
    local_interval: timedelta = timedelta(minutes=1)
    max_items: int = 50
    max_text_length: int = 2000
    max_attribute_bytes: int = 24_000
    partial_poll_interval: timedelta | None = None

    @property
    def unique_id(self) -> str:
        return f'{self.provider}:{self.location}'


@dataclass(frozen=True)
class FetchResult(Generic[Payload]):
    payload: Payload
    diagnostics: dict[str, Any] = field(default_factory=dict)
    refresh_at: datetime | None = None


@dataclass(frozen=True)
class Projection:
    count: int
    items: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    coverage_start: str | None = None
    coverage_end: str | None = None
    coverage_days: int | None = None
    coverage_complete: bool | None = None


class Provider(Protocol[Payload]):
    spec: SourceSpec

    async def async_fetch(self) -> FetchResult[Payload]: ...
    def project(self, payload: Payload, now: datetime) -> Projection: ...
    def diagnostics(self) -> dict[str, Any]: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_projection(projection: Projection, spec: SourceSpec) -> None:
    coverage = (projection.coverage_start, projection.coverage_end,
                projection.coverage_days, projection.coverage_complete)
    if any(value is not None for value in coverage):
        try:
            start = date.fromisoformat(projection.coverage_start)
            end = date.fromisoformat(projection.coverage_end)
            valid = (start.isoformat() == projection.coverage_start
                     and end.isoformat() == projection.coverage_end
                     and type(projection.coverage_days) is int
                     and projection.coverage_days == (end - start).days + 1
                     and projection.coverage_days > 0
                     and type(projection.coverage_complete) is bool)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise SourceError('invalid_projection', 'Ungültige Datumsabdeckung.')
    if (type(projection.count) is not int or projection.count < len(projection.items)
            or projection.count < 0
            or projection.truncated != (projection.count > len(projection.items))):
        raise SourceError('invalid_projection', 'Ungültige Anzahl oder unmarkierte Teilliste.')
    if len(projection.items) > spec.max_items:
        raise SourceError('attribute_limit', 'Zu viele Meldungen für die Sensorattribute.')

    def check(value: Any, depth: int = 0) -> None:
        if depth > 8:
            raise SourceError('attribute_limit', 'Zu tief verschachtelte Sensorattribute.')
        if isinstance(value, str) and len(value) > spec.max_text_length:
            raise SourceError('attribute_limit', 'Ein Meldungstext überschreitet das Attributlimit.')
        if isinstance(value, dict):
            for name, child in value.items():
                if not isinstance(name, str):
                    raise SourceError('invalid_projection', 'Attributschlüssel muss Text sein.')
                check(name, depth + 1)
                check(child, depth + 1)
        elif isinstance(value, (list, tuple)):
            for child in value:
                check(child, depth + 1)
    check(projection.items)
    check(projection.metadata)


@dataclass
class SourceState(Generic[Payload]):
    """Attempt health is independent of a retained last successful payload."""
    result: FetchResult[Payload] | None = None
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    error: SourceError | None = None

    def accept(self, result: FetchResult[Payload], at: datetime) -> None:
        self.result = result
        self.last_attempt = self.last_success = at
        self.error = None

    def reject(self, error: SourceError, at: datetime) -> None:
        self.last_attempt = at
        self.error = error

    def render(self, provider: Provider[Payload], now: datetime) -> dict[str, Any]:
        spec = provider.spec
        error = self.error
        if error is None and (self.result is None or self.last_success is None):
            error = SourceError('initializing', 'Noch keine vollständig geprüften Quelldaten.')
        if error is None and self.last_success is not None:
            age = now - self.last_success
            if age > spec.stale_after or age < -timedelta(minutes=5):
                error = SourceError('stale', 'Daten veraltet oder Systemzeit zurückgestellt.')
        base: dict[str, Any] = {
            'schema_version': 1, 'provider': spec.provider, 'available': False,
            'count': None,
            'coverage_start': None, 'coverage_end': None,
            'coverage_days': None, 'coverage_complete': None,
            'last_attempt': self.last_attempt.astimezone(spec.time_zone).isoformat() if self.last_attempt else None,
            'last_success': self.last_success.astimezone(spec.time_zone).isoformat() if self.last_success else None,
            'items': None, 'items_count': None, 'items_truncated': False,
            'metadata': {}, 'error': None,
        }
        if error is None:
            assert self.result is not None
            try:
                projection = provider.project(self.result.payload, now)
                validate_projection(projection, spec)
                base.update(available=True, count=projection.count,
                            coverage_start=projection.coverage_start,
                            coverage_end=projection.coverage_end,
                            coverage_days=projection.coverage_days,
                            coverage_complete=projection.coverage_complete,
                            items=list(projection.items), items_count=len(projection.items),
                            items_truncated=projection.truncated, metadata=projection.metadata)
                encoded = json.dumps(base, ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(encoded) > spec.max_attribute_bytes:
                    raise SourceError('attribute_limit', 'Sensorattribute überschreiten das Byte-Limit.')
            except SourceError as exc:
                error = exc
            except (TypeError, ValueError) as exc:
                error = SourceError('invalid_projection', 'Sensordaten sind nicht JSON-kompatibel.')
        if error is not None:
            base.update(available=False, count=None, items=None, items_count=None,
                        coverage_start=None, coverage_end=None,
                        coverage_days=None, coverage_complete=None,
                        items_truncated=False, metadata={}, error=error.as_dict())
        return base
