from .default_api import DefaultAPI, WebSocketAPI
from config import config
from urllib.parse import urlencode
from general import Product


from collections import namedtuple
import datetime
import json
import pprint
import logging

from urllib.parse import urlencode
import asyncio
import aiohttp


import hmac
import hashlib
import base64


class Util:
    @classmethod
    def get_signature(cls, query, key):
        msg = urlencode(query)
        key = key.encode('utf-8')
        signature = hmac.new(key, msg.encode("utf-8"), hashlib.sha256)
        return signature.hexdigest()


class BinanceREST_API(DefaultAPI):
    api_url = 'api.binance.com'
    ws_url = 'wss://stream.binance.com:9443/stream'
    account_group = None
    ws_path = '/stream'
    connection_num = 1

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
        return self.ws_url


    async def connect_ws(self, url=None, connection_num=None):
        if not url:
            url = await self.get_ws_url(
                group_needed=True
            )
        if not connection_num:
            connection_num = self.connection_num
        return BinanceWebSocket(url, self, connection_num=self.connection_num)


    async def connect_to_orders_ws(self):
        addr = '/userDataStream'
        result = await self.post(addr, data={}, api_type='api', time_needed=False, signature_needed=False)
        key = result['listenKey']
        ws_addr = f'{self.ws_url}?streams={key}'
        ws = await self.connect_ws(ws_addr)
        asyncio.create_task(self.keepalive(ws, key))
        return ws


    async def keepalive(self, ws, key):
        addr = '/userDataStream'
        timedelta = 30 * 60
        while True:
            await self.process_api_method(
                method='put',
                path=addr,
                api_type='api',
                params={
                    'listenKey': key,
                },
            )
            await asyncio.sleep(timedelta)


    async def get_all_products(self):
        result = await self.get(
            '/exchangeInfo',
            api_type='api',
            time_needed=False,
            signature_needed=False
        )
        for product in result['symbols']:
            product = Product(
                base=product['baseAsset'],
                quote=product['quoteAsset'],
                name=product['symbol']
            )
            yield product



    async def get_last_prices(self):
        raise NotImplementedError()
        # return await self.get('/ticker/price')


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
                key=self._secret
            )
            params.update({
                'signature': signature,
            })

        return params


    async def place_order(
            self,
            symbol,
            size,
            order_type,
            order_side,
            price=None,
            time_in_force='GTC'
    ):
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        data = {
            'symbol': symbol,
            'timestamp': timestamp,
            'quantity': size,
            'type': order_type,
            'side': order_side,
            'timeInForce': time_in_force,
        }
        if order_type == 'LIMIT':
            data['price'] = price
        test_path = '/order'
        resp = await self.post(path=test_path, params=data, api_type='api', signature_needed=True)
        return resp


    async def get_rate(self, symbol=None):
        params = {
            'symbol': symbol
        } if symbol else None
        result = await self.get(
            path='/ticker/price',
            api_type='api',
            time_needed=False,
            signature_needed=False,
            params=params
        )
        price = result['price']
        return price


class BinanceWebSocket(WebSocketAPI):


    async def subscribe_to_channels(self, channels, index=None, id=1):
        if not index:
            index = 0
        await self.send_json(index=index, data={
                "method": "SUBSCRIBE",
                "params": channels,
                "id": id
        })

    async def subscribe_to_channel(self, channel, index=None, id=1):
        await self.subscribe_to_channels([channel], index=index, id=id)

    async def unsubscribe_from_channels(self, channels, index=None, id=1):
        if not index:
            index = 0
        await self.send_json(index=index, data={
                "method": "UNSUBSCRIBE",
                "params": channels,
                "id": id
        })


if __name__ == '__main__':
    import pprint
    async def main():
        api = BinanceREST_API(
            api_token=config['BINANCE']['KEY'],
            secret=config['BINANCE']['SECRET']
        )
        async with api:
            # rates = await api.get_rate(symbol='BTCUSDT')
            ws = await api.connect_to_orders_ws()


    asyncio.run(main(), debug=True)
