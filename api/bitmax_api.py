from .default_api import DefaultAPI
from config import config

import datetime
import collections
import json

import asyncio
import aiohttp

import hmac
import hashlib
import base64

class Util:
    @classmethod
    def get_signature(cls, path, key):
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        timestamp = str(timestamp)

        path = path.split('/')
        path = path[-1] if path else ''
        msg = f'{timestamp}+{path}'
        msg = bytearray(msg.encode("utf-8"))
        hmac_key = base64.b64decode(key)
        signature = hmac.new(hmac_key, msg, hashlib.sha256)
        signature = base64.b64encode(signature.digest()).decode("utf-8")
        return signature
    @classmethod
    def make_headers(cls, path, api_token):

        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        headers = {
            'x-auth-timestamp': str(timestamp),
            "x-auth-signature": cls.get_signature(path, api_token),
        }
        return headers

class BitmaxREST_API(DefaultAPI):
    api_url = 'bitmax.io'
    api_path = '/api/pro/v1'
    account_group = None

    def __init__(self, api_token, account_group=None):
        self.api_token = api_token
        self.account_group = None

    async def create_session(self):
        headers = {
            'x-auth-key': self.api_token,
        }
        session = aiohttp.ClientSession(headers=headers)
        self.session = session

    def get_signature(self, path):
        sign = Util.get_signature(path, self.api_token)
        return sign

    async def get_api_url(self, *args, **kwargs):
        group_needed = kwargs.get('group_needed', False)
        no_method = kwargs.get('no_method', False)
        method = '' if no_method else 'https://'
        if group_needed:
            if not self.account_group:
                response = await self.get('/info')
                self.account_group = response['data']['accountGroup']
            return f'{method}{self.api_url}/{str(self.account_group)}{self.api_path}'
        else:
            return f'{method}{self.api_url}{self.api_path}'

    async def get_ws_url(self, *args, **kwargs):
        ws_url = await self.get_api_url(group_needed=True, no_method=True)
        ws_url = f'wss://{ws_url}'
        return ws_url

    async def connect_ws(self):
        url = await self.get_ws_url(group_needed=True) + '/stream'
        return BitmaxWebSocket(url, self)

    async def get_headers(self, path):
        return Util.make_headers(path, self.api_token)

        headers = {
            'x-auth-timestamp': str(timestamp),
            "x-auth-signature": self.get_signature(path),
        }
        return headers

Dispatcher = collections.namedtuple('Dispatcher', [
    'func', 'name'
])

class BitmaxWebSocket:
    class WSClosed(Exception):
        pass

    _dispatchers = None

    def __init__(self, url, api):
        self._url = url
        self._api = api
        self._dispatchers = []

    @property
    def _api_token(self):
        return self._api.api_token

    @property
    def _session(self):
        return self._api.session


    def add_dispatcher(self, name=None):
        def decorator(func):
            dispatcher = Dispatcher(
                func=func, name=name
            )
            self._dispatchers.append(dispatcher)
            return func
        return decorator

    async def __aenter__(self):
        headers = Util.make_headers('stream', self._api_token)
        self._ws_connection = await self._session.ws_connect(self._url, headers=headers)
        # self._ws = await self._ws_connection.__aenter__()

    async def __aexit__(self, *args, **kwargs):
        # await self._ws.__aexit__()
        await self._ws_connection.close()
        # pass

    async def send_json(self, op, data):
        data['op'] = op
        # pprint.pprint(data)
        await self._ws_connection.send_json(data)

    async def dispatch(self, message):
        if message.type != aiohttp.WSMsgType.TEXT:
            raise ValueError(f'Non-text message\n{message}')
        try:
            data = message.json()
            if data['m'] == 'ping':
                await self.send_json(op='pong', data={})
            else:
                for dispatcher in self._dispatchers:
                    result = dispatcher.func(data)
        except ValueError as exc:
            print(exc)

    async def handle_messages(self):
        while True:
            try:
                if self._ws_connection.closed:
                    raise self.WSClosed('WebSocket apparently closed')

                message = await self._ws_connection.receive()
                message = await self.dispatch(message)
            except Exception as exc:
                raise exc



if __name__ == '__main__':
    import pprint


    async def main():
        api = BitmaxREST_API(api_token=config['BITMAX']['KEY'])
        async with api:
            bitmax_ws = await api.connect_ws()


            @bitmax_ws.add_dispatcher(name='handler')
            def handler(msg):
                global count_num
                print(count_num)
                pprint.pprint(msg)
                count_num += 1

            async with bitmax_ws:
                # account = await api.get('/info')
                await bitmax_ws.send_json('sub', data={
                    'ch': 'depth:BTMX/USDT'
                })
                global previous_ts
                count_num = 0
                await bitmax_ws.handle_messages()


    asyncio.run(main())
