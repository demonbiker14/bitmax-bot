from .default_api import DefaultAPI, WebSocketAPI, Dispatcher
from config import config
from urllib.parse import urlencode

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
    def get_signature(cls, query, data, key):
        querystring = urlencode(query)
        body = urlencode(data)
        msg = querystring + body
        key = key.encode('utf-8')
        signature = hmac.new(key, msg.encode("utf-8"), hashlib.sha256)
        return signature.hexdigest()

class BinanceREST_API(DefaultAPI):
    api_url = 'api.binance.com'
    account_group = None
    ws_path = '/stream'

    def __init__(self, api_token, secret, account_group=None, logger=None):
        self.api_token = api_token
        self._secret = secret
        self.account_group = None
        self.user_uid = None
        if not logger:
            self._logger = logging.getLogger('binance_api')
        else:
            self._logger = logger


    async def create_session(self):
        headers = {
            'X-MBX-APIKEY': self.api_token,
        }
        session = aiohttp.ClientSession(headers=headers)
        self.session = session


    async def get_api_url(self, *args, **kwargs):
        no_method = kwargs.get('no_method', False)
        api_type = kwargs['api_type']
        if api_type == 'sapi':
            api_path = '/sapi/v1'
        elif api_type == 'wapi':
            api_path = '/wapi/v3'
        elif api_type == 'api':
            api_path = '/api/v3'
        else:
            raise ValueError(f'Unsupported api: {api_type}')
        method = '' if no_method else 'https://'
        return f'{method}{self.api_url}{api_path}'


    async def get_ws_url(self, *args, **kwargs):
        ws_url = await self.get_api_url(no_method=True)
        ws_url = f'wss://{ws_url}'
        return ws_url


    async def connect_ws(self):
        url = await self.get_ws_url(group_needed=True) + '/stream'
        return BitmaxWebSocket(url, self)


    async def get_all_products(self):
        return await self.get('/products')


    async def get_last_prices(self):
        return await self.get('/ticker/price')


    async def get_params(self, path, *args, **kwargs):
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        timestamp = str(timestamp)

        params = kwargs.get('params', {})
        time_needed = kwargs.get('time_needed', True)
        signature_needed = kwargs.get('signature_needed', True)
        if time_needed:
            params.update({
                'timestamp': timestamp,
            })

        if signature_needed:
            signature = Util.get_signature(
                query=params,
                data=kwargs.get('data', {}),
                key=self._secret
            )
            params.update({
                'signature': signature,
            })

        return params


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


    async def get_rate(self, symbol):
        result = await self.get(path='/ticker', params={
            'symbol': symbol
        })
        return result

class BinanceWebSocket(WebSocketAPI):

    async def __aenter__(self):
        # headers = Util.make_headers('stream', self._api_token, self._secret)
        await self.connect_ws(headers)


    async def send_json_with_op(self, data, op):
        data['op'] = op
        await self.send_json(data)


    async def handle_firstly(self, message):
        if message['m'] == 'ping':
            if int(message['hp']) < 3:
                self._logger.warning(message)
            await self.send_json(op='pong', data={})


if __name__ == '__main__':
    import pprint
    async def main():
        api = BinanceREST_API(
            api_token=config['BINANCE']['KEY'],
            secret=config['BINANCE']['SECRET']
        )
        async with api:
            # pprint.pprint(await api.get('/apiTradingStatus.html', params={'type':'SPOT'}, api_type='wapi'))
            result = await api.get(
                '/ticker/price',
                api_type='api',
                time_needed=False,
                signature_needed=False
            )
            pprint.pprint(result)


    asyncio.run(main())
