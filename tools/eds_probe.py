#!/usr/bin/env python3
"""Explicit live verification or deterministic offline provider run."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
import types
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
package=types.ModuleType('live_probe')
package.__path__=[str(ROOT/'custom_components/arandjelovac_live')]
sys.modules['live_probe']=package

import aiohttp
from live_probe.common.http import HttpClient, HttpPolicy, decode_text
from live_probe.common.models import SourceError, SourceState
from live_probe.providers.eds.provider import EDSProvider
from live_probe.providers.eds.parser import discover_pages
from live_probe.providers.eds.source import HOSTS, INDEX_URL, TZ


class FixtureHTTP:
    def __init__(self,folder: Path) -> None:
        self.folder=folder
        self.observations=[]
    def clear_observations(self) -> None: self.observations.clear()
    async def get_text(self,url: str,**kwargs: Any) -> str:
        name='index.html' if url==INDEX_URL else f"day{url.split('_Dan_')[1][0]}.html"
        return decode_text((self.folder/name).read_bytes())


class CaptureHTTP(HttpClient):
    def __init__(self,session: aiohttp.ClientSession,folder: Path | None) -> None:
        super().__init__(session,HttpPolicy(HOSTS))
        self.folder=folder
        self.saved: dict[str,dict[str,Any]]={}
    async def get_bytes(self,url: str):
        response=await super().get_bytes(url)
        if self.folder:
            name='index.html' if url==INDEX_URL else f"day{url.split('_Dan_')[1][0]}.html"
            await asyncio.to_thread((self.folder/name).write_bytes,response.body)
            self.saved[url]={'file':name,'url':url,'at':datetime.now(TZ).isoformat(),
                             'bytes':len(response.body),'sha256':hashlib.sha256(response.body).hexdigest(),
                             'content_type':response.content_type,'charset':response.charset}
        return response


async def evaluate(provider: EDSProvider,clock) -> dict[str,Any]:
    state=SourceState()
    try:
        async with asyncio.timeout(provider.spec.cycle_timeout):
            result=await provider.async_fetch()
        state.accept(result,clock())
    except SourceError as exc:
        state.reject(exc,clock())
    except TimeoutError:
        state.reject(SourceError('timeout','Gesamtabruf überschreitet das Zeitlimit.'),clock())
    return state.render(provider,clock())


async def run(args) -> dict[str,Any]:
    if args.fixtures:
        instant=datetime.fromisoformat(args.at)
        if instant.tzinfo is None:
            raise ValueError('--at benötigt einen UTC-Offset')
        return await evaluate(EDSProvider(FixtureHTTP(args.fixtures),clock=lambda:instant),lambda:instant)
    if args.save_dir: args.save_dir.mkdir(parents=True,exist_ok=True)
    async with aiohttp.ClientSession(trust_env=args.proxy_env) as session:
        http=CaptureHTTP(session,args.save_dir)
        provider=EDSProvider(http)
        result=await evaluate(provider,lambda:datetime.now(TZ))
        if args.save_dir:
            # Complete evidence collection after a failed provider attempt.
            index=(args.save_dir/'index.html')
            if index.exists():
                try:
                    links=discover_pages(decode_text(index.read_bytes()))
                except SourceError as exc:
                    print(f'Capture: {exc.scope}.{exc.code}',file=sys.stderr)
                    links={}
                for url in links.values():
                    if url not in http.saved:
                        try: await http.get_bytes(url)
                        except SourceError as exc: print(f'Capture: {exc.scope}.{exc.code}',file=sys.stderr)
            (args.save_dir/'capture.json').write_text(json.dumps(list(http.saved.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (args.save_dir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (args.save_dir/'diagnostics.json').write_text(json.dumps(provider.diagnostics(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live',action='store_true')
    mode.add_argument('--fixtures',type=Path)
    parser.add_argument('--at',help='ISO time with offset; required for offline fixtures')
    parser.add_argument('--save-dir',type=Path,help='Live HTML evidence directory')
    parser.add_argument('--proxy-env',action='store_true',help='Diagnostic tool only: use environment proxy')
    args=parser.parse_args()
    if bool(args.fixtures)!=bool(args.at): parser.error('--at is required only with --fixtures')
    if args.fixtures and args.save_dir: parser.error('--save-dir is live-only')
    sys.stdout.reconfigure(encoding='utf-8')
    result=asyncio.run(run(args))
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0 if result['available'] else 2


if __name__=='__main__':
    raise SystemExit(main())
