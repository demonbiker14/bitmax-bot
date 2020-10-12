from .default_api import DefaultAPI, WebSocketAPI, Dispatcher
from config import config

import datetime
import json
import pprint
import logging

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
    def make_headers(cls, path, api_token, secret):
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        headers = {
            'x-auth-timestamp': str(timestamp),
            "x-auth-signature": cls.get_signature(path, secret),
        }
        return headers


    @classmethod
    def gen_server_order_id(user_uid, cl_order_id, ts, order_src='s'):
        return (order_src + format(ts, 'x')[-11:] + user_uid[-11:] + cl_order_id[-9:])[:32]


class BitmaxREST_API(DefaultAPI):
    api_url = 'bitmax.io'
    api_path = '/api/pro/v1'
    ws_path = '/stream'
    account_group = None

    def __init__(self, api_token, secret, account_group=None, logger=None):
        self.api_token = api_token
        self._secret = secret
        self.account_group = None
        self.user_uid = None
        if not logger:
            self._logger = logging.getLogger('bitmax_api')
        else:
            self._logger = logger


    async def create_session(self):
        headers = {
            'x-auth-key': self.api_token,
        }
        session = aiohttp.ClientSession(headers=headers)
        self.session = session


    def get_signature(self, path):
        sign = Util.get_signature(path, self._secret)
        return sign


    async def get_uuid(self):
        if self.uuid:
            return self.uuid
        else:
            response = await self.get(path='/info')
            self.uuid = response['data']['userUID']


    async def get_api_url(self, *args, **kwargs):
        group_needed = kwargs.get('group_needed', False)
        no_method = kwargs.get('no_method', False)
        method = '' if no_method else 'https://'
        if group_needed:
            if not self.account_group:
                response = await self.get('/info')
                self.account_group = response['data']['accountGroup']
                self.uuid = response['data']['userUID']
            return f'{method}{self.api_url}/{str(self.account_group)}{self.api_path}'
        else:
            return f'{method}{self.api_url}{self.api_path}'


    async def get_ws_url(self, *args, **kwargs):
        ws_url = await self.get_api_url(group_needed=True, no_method=True)
        ws_url = f'wss://{ws_url}'
        return ws_url


    async def connect_ws(self):
        url = await self.get_ws_url(group_needed=True) + self.ws_path
        return BitmaxWebSocket(url, self)


    async def get_all_products(self):
        return await self.get('/products')


    async def get_headers(self, path, *args, **kwargs):
        return Util.make_headers(path, self.api_token, self._secret)

        headers = {
            'x-auth-timestamp': str(timestamp),
            "x-auth-signature": self.get_signature(path),
        }
        return headers


    async def place_order(self, symbol, size, order_type, order_side, price=None, post_only=False, resp_inst='ACK', time_in_force='GTC'):
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        data = {
            'time': timestamp,
            'symbol': symbol,
            'orderQty': str(size),
            'orderType': order_type,
            'side': order_side,
            "respInst": 'ACK',
        }
        if order_type == 'limit':
            data['orderPrice'] = str(price)
        resp = await self.post(path='/cash/order', data=data, group_needed=True)
        return resp
        # pprint.pprint(resp)


    async def get_rate(self, symbol):
        result = await self.get(path='/ticker', params={
            'symbol': symbol
        })
        return result


class BitmaxWebSocket(WebSocketAPI):

    async def __aenter__(self):
        headers = Util.make_headers('stream', self._api_token, self._secret)
        await self.connect_ws(headers)


    async def send_json_with_op(self, op, data):
        data['op'] = op
        await self.send_json(data)


    async def handle_firstly(self, message):
        if message['m'] == 'ping':
            if int(message['hp']) < 3:
                self._logger.warning(message)
            await self.send_json_with_op(op='pong', data={})


if __name__ == '__main__':
    import pprint
    async def main():
        api = BitmaxREST_API(
            api_token=config['BITMAX']['KEY'],
            secret=config['BITMAX']['SECRET']
        )

        async with api:
            bitmax_ws = await api.connect_ws()

            await bitmax_ws.__aenter__()
            print(bitmax_ws.is_closed())

            await bitmax_ws.__aexit__()
            print(bitmax_ws.is_closed())
            await bitmax_ws.__aexit__()
            print(bitmax_ws.is_closed())

            await bitmax_ws.__aenter__()
            print(bitmax_ws.is_closed())

            await bitmax_ws.__aenter__()
            print(bitmax_ws.is_closed())


            await bitmax_ws.__aexit__()
            print(bitmax_ws.is_closed())


            # async with bitmax_ws:
                # account = await api.get('/info')
                # await bitmax_ws.send_json_with_op('sub', data={
                #     'ch': 'depth:BTMX/USDT'
                # })
                # global previous_ts
                # previous_ts = 0
                # await bitmax_ws.handle_messages()
                # await bitmax_ws.handle_messages()
                # print(await bitmax_ws.receive_json())


    asyncio.run(main())
