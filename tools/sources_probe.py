#!/usr/bin/env python3
"""Explicit live or historical offline verification of all configured sources."""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
import types
import aiohttp

ROOT=Path(__file__).resolve().parents[1]
pkg=types.ModuleType('live_sources');pkg.__path__=[str(ROOT/'custom_components/arandjelovac_live')];sys.modules['live_sources']=pkg
from live_sources.common.http import HttpClient,HttpPolicy
from live_sources.common.models import SourceState,SourceError
from live_sources.providers.eds.provider import EDSProvider
from live_sources.providers.eds.source import HOSTS as EDS_HOSTS,TZ
from live_sources.providers.notices.provider import HOSTS,SOURCES,NoticeProvider

async def main(args):
    folder=args.capture
    if folder:folder.mkdir(parents=True,exist_ok=True)
    class CaptureHTTP(HttpClient):
        async def get_bytes(self,url):
            response=await super().get_bytes(url)
            if folder:
                from hashlib import sha256
                name=sha256(url.encode()).hexdigest()[:20]+'.txt'
                await asyncio.to_thread((folder/name).write_bytes,response.body)
                await asyncio.to_thread((folder/(name+'.url')).write_text,url)
            return response
    async with aiohttp.ClientSession(trust_env=args.proxy_env) as session:
        async def evaluate(key):
            client=CaptureHTTP(session,HttpPolicy(EDS_HOSTS if key=='eds' else HOSTS[key],timeout=30,max_redirects=0 if key=='eds' else 1))
            provider=EDSProvider(client) if key=='eds' else NoticeProvider(key,client)
            state=SourceState()
            try:
                async with asyncio.timeout(150):result=await provider.async_fetch()
                state.accept(result,datetime.now(TZ))
            except SourceError as error:state.reject(error,datetime.now(TZ))
            except TimeoutError:state.reject(SourceError('timeout','Probe-Zeitlimit überschritten.'),datetime.now(TZ))
            view=state.render(provider,datetime.now(TZ))
            summary={'provider':key,'available':view['available'],'count':view['count'],'items_count':view['items_count'],
                     'error':view['error'],'coverage_end':view['coverage_end'],'http':provider.diagnostics(),
                     'kinds':sorted({x.get('kind','eds_outage') for x in view['items'] or []})}
            if folder:
                await asyncio.to_thread((folder/(key+'-result.json')).write_text,json.dumps(view,ensure_ascii=False,indent=2))
            print(json.dumps(summary,ensure_ascii=False),flush=True)
            return summary
        results=await asyncio.gather(*(evaluate(key) for key in ['eds',*SOURCES]))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'checked_at':datetime.now(TZ).isoformat(),'sources':results},ensure_ascii=False,indent=2)+'\n')
    return 0 if all(s['available'] for s in results) else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',required=True,action='store_true')
    parser.add_argument('--proxy-env',action='store_true')
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    raise SystemExit(asyncio.run(main(args)))
