"""No network access: transport state/error boundaries use fake responses."""
import asyncio
import unittest
import aiohttp

import bootstrap
from live_test.common.http import HttpClient, HttpPolicy, decode_text, validate_url
from live_test.common.models import SourceError

URL='https://source.example/page'
POLICY=HttpPolicy(frozenset({'source.example'}))


class Response:
    def __init__(self,body=b'Hello',status=200,content_type='text/html',charset='utf-8',headers=None):
        self.body,self.status,self.content_type,self.charset=body,status,content_type,charset
        self.headers=headers or {}
        self.content=self
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def iter_chunked(self,size):
        for i in range(0,len(self.body),max(1,size)):
            yield self.body[i:i+size]


class Session:
    def __init__(self,*responses,error=None):
        self.responses=list(responses)
        self.error=error
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if self.error: raise self.error
        return self.responses.pop(0)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def assert_error(self,code,client):
        with self.assertRaises(SourceError) as cm: await client.get_bytes(URL)
        self.assertEqual(cm.exception.code,code)

    async def test_utf8_bom_and_bytes(self):
        raw='\ufeffАранђеловац'.encode()
        client=HttpClient(Session(Response(raw)),POLICY)
        response=await client.get_bytes(URL)
        self.assertEqual(response.body,raw)
        self.assertEqual(response.text(),'Аранђеловац')

    async def test_charset(self):
        self.assertEqual(decode_text('čćš'.encode('cp1250'),'cp1250'),'čćš')
        with self.assertRaises(SourceError): decode_text(b'\xff','utf-8')
        with self.assertRaises(SourceError): decode_text(b'hello','nonexistent-charset')

    async def test_http_errors(self):
        for status in (403,404,429,500):
            client=HttpClient(Session(Response(status=status)),POLICY)
            await self.assert_error('http_error',client)
            self.assertEqual(len(client.session.calls),1)  # no retry storm

    async def test_timeout_and_network(self):
        await self.assert_error('timeout',HttpClient(Session(error=TimeoutError()),POLICY))
        await self.assert_error('network',HttpClient(Session(error=aiohttp.ClientConnectionError()),POLICY))

    async def test_limit_and_empty(self):
        await self.assert_error('response_too_large',HttpClient(Session(Response(b'x'*100)),HttpPolicy(POLICY.allowed_hosts,max_bytes=99)))
        await self.assert_error('empty_response',HttpClient(Session(Response(b'')),POLICY))

    async def test_content_type(self):
        client=HttpClient(Session(Response(content_type='application/json')),POLICY)
        with self.assertRaises(SourceError) as cm:
            await client.get_text(URL,content_types=frozenset({'text/html'}))
        self.assertEqual(cm.exception.code,'content_type')

    async def test_redirect_policy(self):
        redirect=Response(status=302,headers={'Location':'/next'})
        await self.assert_error('redirect',HttpClient(Session(redirect),POLICY))
        session=Session(redirect,Response())
        client=HttpClient(session,HttpPolicy(POLICY.allowed_hosts,max_redirects=1))
        self.assertEqual((await client.get_bytes(URL)).url,'https://source.example/next')
        self.assertTrue(all(kwargs['allow_redirects'] is False for _,kwargs in session.calls))

    async def test_redirect_external_and_downgrade(self):
        for target in ('https://evil.example/','http://source.example/'):
            await self.assert_error('unsafe_url',HttpClient(Session(Response(status=302,headers={'Location':target})),HttpPolicy(POLICY.allowed_hosts,max_redirects=1)))

    async def test_redirect_loop(self):
        response=Response(status=302,headers={'Location':'/page'})
        await self.assert_error('redirect',HttpClient(Session(response,response),HttpPolicy(POLICY.allowed_hosts,max_redirects=1)))

    async def test_no_secrets_in_diagnostics(self):
        client=HttpClient(Session(Response()),POLICY)
        await client.get_bytes(URL+'?token=secret')
        self.assertNotIn('secret',repr(client.observations))
        self.assertNotIn('body',repr(client.observations))

    async def test_invalid_url_ports_and_userinfo(self):
        for url in ('https://source.example:bad/','https://u:p@source.example/','https://source.example/#x'):
            with self.assertRaises(SourceError): validate_url(url,POLICY)

    async def test_cancel_propagates(self):
        class SlowResponse(Response):
            async def iter_chunked(self,size):
                await asyncio.sleep(60)
                yield b'x'
        task=asyncio.create_task(HttpClient(Session(SlowResponse()),POLICY).get_bytes(URL))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
