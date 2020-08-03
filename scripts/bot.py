from api.bitmax_api import BitmaxREST_API
from db.db_client import DBClient
from db.models import OrderType, Status
from rest.rest_server import RestServer

import general
import logging
import asyncio
import pprint
import sys


class MarketBot:

    class NoSuchOrderError(Exception):
        pass

    bid_floor = None
    ask_ceil = None

    def __init__(self, dbconfig, token, secret, server_pass):
        self._dbconfig = dbconfig
        self._token = token
        self._secret = secret
        self._server_pass = server_pass
        self._logger = logging.getLogger(f'{general.logger_name}.market_bot')
        # self._pending_tasks = asyncio.Queue()

    async def __aenter__(self):
        self._tasks = asyncio.Queue()
        self.bitmax_api = BitmaxREST_API(
            api_token=self._token,
            secret=self._secret,
            logger=self._logger
        )
        await self.bitmax_api.__aenter__()

        self.ws = await self.bitmax_api.connect_ws()
        await self.ws.__aenter__()

        self.dbclient = DBClient(self._dbconfig)
        await self.dbclient.__aenter__()


    async def __aexit__(self, *args, **kwargs):
        # print("aexit")
        await self.ws.__aexit__(*args, **kwargs)
        await self.bitmax_api.__aexit__(*args, **kwargs)
        await self.dbclient.__aexit__(*args, **kwargs)

    async def put_in_queue(self, item):
        await self._tasks.put(item)

    async def get_from_queue(self):
        return await self._tasks.get()

    async def add_order(self, *args, **kwargs):
        try:
            await self.db_client.add_order(*args, **kwargs)
            self.reset_limits()
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

    async def place_order(self, order_type, symbol, price, volume, ot='market'):
        symbol = str(symbol)
        order_side = 'buy' if order_type == OrderType.BUY else 'sell'
        result = await self.bitmax_api.place_order(
            symbol=symbol,
            price=price,
            size=volume,
            order_type=ot,
            order_side=order_side,
            post_only=False,
            resp_inst='ACK'
        )
        return result

    def reset_limits(self):
        self.bid_floor = self.ask_ceil = None

    async def add_symbols(self, *args, **kwargs):
        try:
            await self.dbclient.add_symbols(*args, **kwargs)
            self.reset_limits()
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

    async def update_symbols(self):
        result = await self.bitmax_api.get('/products')
        products = []
        for product in result['data']:
            product = tuple(product['symbol'].split('/'))
            if len(product) == 2:
                products.append(product)
        await self.add_symbols(products)
        return products


    async def get_orders_from_msg(self, msg):
        data = msg['data']
        symbol = msg['symbol']
        asks, bids = data['asks'], data['bids']
        min_bid_price, max_ask_price = float('inf'), 0

        for bid in bids:
            bid_price = float(bid[0])
            if min_bid_price > bid_price:
                min_bid_price = bid_price

        for ask in asks:
            ask_price = float(ask[0])
            if max_ask_price < ask_price:
                max_ask_price = ask_price

        if min_bid_price == float('inf'):
            min_bid_price = None

        if max_ask_price == 0:
            max_ask_price = None

        try:
            symbol = await self.dbclient.get_symbol(*symbol.split('/'))
        except self.dbclient.NoSymbolExists as exc:
            symbol = None
            return symbol
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

        if self.bid_floor and min_bid_price and min_bid_price >= self.bid_floor:
            min_bid_price = None

        if self.ask_ceil and max_ask_price and max_ask_price <= self.ask_ceil:
            max_ask_price = None

        if not min_bid_price and max_ask_price:
            bid_orders = None
            ask_orders = await symbol.get_orders_for_price_ask(max_ask_price)
        elif not max_ask_price and min_bid_price:
            ask_orders = None
            bid_orders = await symbol.get_orders_for_price_bid(min_bid_price)
        elif max_ask_price and min_bid_price:
            bid_orders, ask_orders = await asyncio.gather(
                symbol.get_orders_for_price_bid(min_bid_price),
                symbol.get_orders_for_price_ask(max_ask_price)
            )
        else:
            bid_orders = ask_orders = None

        if not self.bid_floor:
            self.bid_floor = min_bid_price

        if not self.ask_ceil:
            self.ask_ceil = max_ask_price

        return bid_orders, ask_orders, symbol

    async def handle_data(self):
        @self.ws.add_dispatcher(name='receiver')
        async def handler(msg):
            if msg['m'] == 'order':
                order_id = msg['data']['orderId']
                status = msg['data']['st']
                p_order = await ProcessingOrder.get_or_none(order_id)
                if not p_order:
                    raise self.NoSuchOrderError(order_id)

            elif msg['m'] == 'depth':
                symbol = msg.get('symbol')
                data = msg.get('data')
                if not (data and symbol):
                    raise ValueError(msg)
                orders = await self.get_orders_from_msg(msg)
                if not orders:
                    return None
                bid_orders, ask_orders, symbol = orders

                try:
                    if bid_orders:
                        async for order in bid_orders:
                            status = Status.PROCESSING
                            result = await self.place_order(
                                symbol=symbol,
                                ot='limit',
                                order_type=OrderType.BUY,
                                price=order.price,
                                volume=order.volume
                            )
                            self._logger.debug(result)
                            try:
                                order_id = result['data']['info']['orderId']
                                p_order = await order.make_processing(order_id)
                            except Exception as exc:
                                self._logger.exception(exc)
                                self._logger.debug(result)
                                raise exc
                    if ask_orders:
                        async for order in ask_orders:
                            status = Status.PROCESSING
                            result = await self.place_order(
                                symbol=symbol,
                                ot='limit',
                                order_type=OrderType.SELL,
                                price=order.price,
                                volume=order.volume
                            )
                            self._logger.debug(result)
                            try:
                                order_id = result['data']['info']['orderId']
                                p_order = await order.make_processing(order_id)
                            except Exception as exc:
                                self._logger.exception(exc)
                                self._logger.debug(result)
                                raise exc
                except Exception as exc:
                    self._logger.exception(exc)
                    raise exc

        result = await self.ws.handle_messages()
        # print('Result': result)
        return result


    async def send_from_queue(self):
        while True:
            op, data = await self.get_from_queue()
            await self.ws.send_json(op, data)

    async def subscribe_to_channel(self, channel, id=''):
        await self.ws.send_json('sub', data={
            'ch': channel,
            'id': id,
        })

    async def bot(self):
        await self.subscribe_to_channel(
            f'order:cash', id='abc')
        async for symbol in await self.dbclient.list_symbols():
            await self.subscribe_to_channel(
                f'depth:{str(symbol)}', id='abc')
        self.tasks = asyncio.gather(
            self.handle_data(),
            self.send_from_queue()
        )
        await self.tasks


    # def run_bot(self):
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(loop)
    #     loop.run_until_complete(self.bot())

    async def api_server(self):
        self._api_server = RestServer(password=self._server_pass, bot=self)
        await self._api_server.run()

    async def run(self):
        await asyncio.gather(
            self.api_server(),
            self.bot()
        )

if __name__ == '__main__':
    from general import dbconfig
    from config import config
    import pprint
    async def main():
        bot = MarketBot(
            dbconfig=dbconfig,
            token=config['BITMAX']['KEY'],
            secret=config['BITMAX']['SECRET'],
            server_pass=config['REST']['PASSWORD']
        )
        async with bot:
            # asyncio.create_task(bot.ws.handle_messages())
            await bot.run()
            # await bot.update_symbols()
    asyncio.run(main())

    # async def main():
    #     async with bot:
    #         await bot.run()
    # asyncio.run(main())
