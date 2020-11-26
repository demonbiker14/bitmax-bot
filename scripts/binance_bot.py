from .abstract_bot import AbstractBot
from api.sms_api import SMSApi
from api.binance_api import BinanceREST_API
from db.db_client import BinanceDBClient
from db.models import OrderType, Status, ProcessingOrder

import asyncio
import logging
import pprint


class BinanceBot(AbstractBot):

    def __init__(self, dbconfig, stock_config, sms_config, logger_name):
        self._dbconfig = dbconfig
        self._stock_config = stock_config
        self._logger = logging.getLogger(f'{logger_name}.binance_bot')
        self._sms_config = sms_config
        self._subscribed_channels = {}

    async def __aenter__(self):
        self._tasks = asyncio.Queue()
        self.api = BinanceREST_API(
            api_token=self._stock_config['KEY'],
            secret=self._stock_config['SECRET'],
            logger=self._logger
        )
        self.sms = SMSApi(
            self._sms_config['LOGIN'],
            self._sms_config['PASSWORD']
        )
        self.dbclient = BinanceDBClient()

        await self.api.__aenter__()

        self.ws = await self.api.connect_ws()
        # self.order_ws = await self.api.connect_to_orders_ws()
        await self.ws.__aenter__()
        # await self.order_ws.__aenter__()

        await self.sms.__aenter__()
        await self.dbclient.__aenter__()

    async def __aexit__(self, *args, **kwargs):
        await self.sms.__aexit__(*args, **kwargs)
        await self.ws.__aexit__(*args, **kwargs)
        # await self.order_ws.__aexit__(*args, **kwargs)
        await self.api.__aexit__(*args, **kwargs)
        await self.dbclient.__aexit__(*args, **kwargs)

    async def put_in_queue(self, item):
        await self._tasks.put(item)

    async def get_from_queue(self):
        return await self._tasks.get()


    async def add_order(self, symbol, *args, **kwargs):
        channel = f'{symbol.ticker.lower()}@ticker'
        await self.ws.subscribe_to_channel(channel)
        channel_num = self._subscribed_channels.get(channel, 0) + 1
        self._subscribed_channels[channel] = channel_num
        # print(self._subscribed_channels)
        order = await self.dbclient.add_order(symbol, *args, **kwargs)
        return order


    async def delete_all_orders(self):
        channels = list(map(str.lower, self._subscribed_channels.keys()))
        await self.ws.unsubscribe_from_channels(list(channels))
        self._subscribed_channels.clear()
        await (await self.dbclient.list_orders()).delete()


    async def delete_order(self, order_pk):
        order = await self.dbclient.delete_order(order_pk)
        ticker = (await order.symbol).ticker
        channel = f'{ticker.lower()}@ticker'
        if channel in self._subscribed_channels:
            if self._subscribed_channels[channel] == 1:
                del self._subscribed_channels[channel]
                await self.ws.unsubscribe_from_channels([channel])
            else:
                self._subscribed_channels[channel] -= 1


    async def damp(self, order, p_order, damping_left):
        self._logger.debug(f'damping {damping_left}')
        if damping_left == 0:
            return None
        await self.place_order(
            order=order,
            p_order=p_order,
            damp_count=(damping_left - 1)
        )

    async def place_order(self, order, p_order, ot='LIMIT', damp_count=None):
        if not damp_count:
            damp_count = self._stock_config['DAMP_COUNT']
        status = Status.PROCESSING
        symbol = order.symbol
        order_side = 'BUY' if order.order_type == OrderType.BUY else 'SELL'
        result = await self.api.place_order(
            symbol=symbol.ticker,
            price=str(order.price),
            size=str(order.volume),
            order_type=ot,
            order_side=order_side,
        )
        self._logger.info('Placed order')
        self._logger.info(result)
        self._logger.info(await p_order.to_str())
        if result['code'] in self._stock_config['DAMPING_CODES']:
            if self._stock_config['DAMPING']:
                await asyncio.sleep(0.5)
                asyncio.create_task(self.damp(
                    order=order,
                    p_order=p_order,
                    damping_left=damp_count,
                ))
        elif result['code'] == 0:
            order_id = result['data']['info']['orderId']
            p_order.order_id = order_id
            await p_order.save()
            return result
        else:
            await p_order.delete()

    async def update_symbols(self):
        products = self.api.get_all_products()
        products = [product async for product in products]
        await self.dbclient.add_symbols(products)
        return products

    async def get_orders_for_rate(self, price, symbol):
        try:
            symbol = await self.dbclient.get_symbol_by_ticker(symbol)
        except self.dbclient.NoSymbolExists as exc:
            return None

        bid_orders, ask_orders = await asyncio.gather(
            self.dbclient.get_orders_for_price_bid(price, symbol),
            self.dbclient.get_orders_for_price_ask(price, symbol)
        )

        return bid_orders, ask_orders, symbol

    async def handle_data(self):
        @self.ws.add_dispatcher(name='rate_handler')
        async def handle_rate(msg):
            if 'stream' in msg:
                price = float(msg['data']['c'])
                symbol = msg['stream'].split('@')[0].upper()
                orders = await self.get_orders_for_rate(price, symbol)

                if not orders:
                    return None

                bid_orders, ask_orders, symbol = orders

                if bid_orders:
                    async for order in bid_orders:
                        p_order = await self.dbclient.make_processing(order, None)
                        result = await self.place_order(
                            order=order,
                            p_order=p_order,
                        )
                if ask_orders:
                    async for order in ask_orders:
                        p_order = await self.dbclient.make_processing(order, None)
                        result = await self.place_order(
                            order=order,
                            p_order=p_order,
                        )
        while True:
            try:
                await self.ws.handle_messages()
            except self.ws.WSClosed as exc:
                self._logger.warning(f'WS closed in handle_data')
                await self.ws.__aenter__()
                await self.subscribe_to_existing_orders()


    async def handle_order_updates(self):
        @self.order_ws.add_dispatcher('orders_handler')
        async def handler(msg):
            self._logger.info(msg)
        while True:
            try:
                await self.order_ws.handle_messages()
            except self.order_ws.WSClosed as exc:
                self._logger.warning(f'Order WS closed in handle_order_updates')
                await self.order_ws.__aenter__()

    async def send_from_queue(self):
        while True:
            data = await self.get_from_queue()
            if not data:
                return None
            await self.ws.send_json(data=data)


    async def subscribe_to_existing_orders(self):
        channels = list(self._subscribed_channels.keys())
        # print(channels)
        if channels:
            await self.ws.subscribe_to_channels(channels)


    async def setup(self):
        existing_orders = await self.dbclient.list_orders()
        async for order in existing_orders:
            ticker = order.symbol.ticker.lower()
            channel = f'{ticker}@ticker'
            num = self._subscribed_channels.get(channel, 0) + 1
            self._subscribed_channels[channel] = num
        await self.subscribe_to_existing_orders()


    async def run(self):
        self._logger.debug('Started')
        await self.setup()
        try:
            tasks = asyncio.gather(*[
                self.handle_data(),
                # self.handle_order_updates(),
            ])
            await tasks
        except Exception as exc:
            tasks.cancel()
            raise exc