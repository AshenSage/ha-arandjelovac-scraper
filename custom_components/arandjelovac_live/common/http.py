"""Bounded HTTPS transport. The caller owns the supplied HA aiohttp session."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp

from .models import SourceError

USER_AGENT = 'Mozilla/5.0 (compatible; ArandjelovacLive/1.0; HomeAssistant)'


@dataclass(frozen=True)
class HttpPolicy:
    allowed_hosts: frozenset[str]
    timeout: float = 15
    max_bytes: int = 2_000_000
    max_redirects: int = 0


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.hostname or '', parts.path, '', ''))


def validate_url(url: str, policy: HttpPolicy) -> str:
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname in policy.allowed_hosts
                 and parts.port in (None, 443) and not parts.username
                 and not parts.password and not parts.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise SourceError('unsafe_url', 'Quelle verweist auf eine nicht erlaubte HTTPS-Adresse.')
    return url


def decode_text(body: bytes, charset: str | None = None) -> str:
    if not body:
        raise SourceError('empty_response', 'Die Datenquelle liefert eine leere Antwort.')
    encoding = 'utf-8-sig' if body.startswith(b'\xef\xbb\xbf') else (charset or 'utf-8')
    try:
        value = body.decode(encoding, errors='strict')
    except (UnicodeError, LookupError, TypeError) as exc:
        raise SourceError('decode_error', 'Zeichenkodierung der Datenquelle nicht lesbar.') from exc
    if '\ufffd' in value or '\x00' in value:
        raise SourceError('decode_error', 'Ungültige Zeichen in der Textantwort.')
    return value


@dataclass(frozen=True)
class Response:
    body: bytes
    url: str
    content_type: str
    charset: str | None

    def text(self) -> str:
        return decode_text(self.body, self.charset)


class HttpClient:
    def __init__(self, session: aiohttp.ClientSession, policy: HttpPolicy) -> None:
        self.session = session
        self.policy = policy
        self.observations: list[dict[str, object]] = []

    def clear_observations(self) -> None:
        self.observations.clear()

    async def get_bytes(self, url: str) -> Response:
        validate_url(url, self.policy)
        started = monotonic()
        observation: dict[str, object] = {'url': safe_url(url)}
        try:
            async with asyncio.timeout(self.policy.timeout):
                current = url
                for redirect in range(self.policy.max_redirects + 1):
                    validate_url(current, self.policy)
                    async with self.session.get(
                        current, allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=self.policy.timeout),
                        headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity',
                                 'Cache-Control': 'no-cache'},
                    ) as response:
                        observation['status'] = response.status
                        if response.status in (301, 302, 303, 307, 308):
                            target = response.headers.get('Location')
                            if redirect == self.policy.max_redirects or not target:
                                raise SourceError('redirect', 'Unerwartete oder zu viele HTTP-Weiterleitungen.')
                            current = validate_url(urljoin(current, target), self.policy)
                            continue
                        if response.status != 200:
                            raise SourceError('http_error', f'Datenquelle antwortet mit HTTP {response.status}.')
                        data = bytearray()
                        async for chunk in response.content.iter_chunked(32768):
                            data.extend(chunk)
                            if len(data) > self.policy.max_bytes:
                                raise SourceError('response_too_large', 'HTTP-Antwort überschreitet das Grössenlimit.')
                        if not data:
                            raise SourceError('empty_response', 'Die Datenquelle liefert eine leere Antwort.')
                        observation.update(bytes=len(data), content_type=response.content_type,
                                           charset=response.charset)
                        return Response(bytes(data), current, response.content_type, response.charset)
                raise SourceError('redirect', 'HTTP-Weiterleitung konnte nicht aufgelöst werden.')
        except TimeoutError as exc:
            observation['error'] = 'timeout'
            raise SourceError('timeout', 'Zeitüberschreitung beim Abruf der Datenquelle.') from exc
        except aiohttp.ClientError as exc:
            observation['error'] = 'network'
            raise SourceError('network', 'Verbindung zur Datenquelle fehlgeschlagen.') from exc
        except SourceError as exc:
            observation['error'] = exc.code
            raise
        finally:
            observation['duration_ms'] = round((monotonic() - started) * 1000)
            self.observations.append(observation)
            del self.observations[:-8]

    async def get_text(self, url: str, *, content_types: frozenset[str]) -> str:
        response = await self.get_bytes(url)
        if response.content_type not in content_types:
            raise SourceError('content_type', 'Unerwarteter Content-Type der Datenquelle.')
        return response.text()
