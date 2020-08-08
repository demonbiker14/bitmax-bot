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
    def __init__(self, dbconfig, token, secret, server_pass):
        self._dbconfig = dbconfig
        self._token = token
        self._secret = secret
        self._server_pass = server_pass
        self._logger = logging.getLogger(f'{general.logger_name}.market_bot')
        self.stopped = False

        # self._pending_tasks = asyncio.Queue()

    async def __aenter__(self):
        try:
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

            self.stopped = False
        except Exception as exc:
            await self.__aexit__()
            raise exc

    async def __aexit__(self, *args, **kwargs):
        self.stopped = True

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

    async def damp(self, order, damping_left):
        self._logger.debug(f'damping {damping_left}')
        if damping_left == 0:
            return None
        await self.place_order(
            order=order,
            damping_left=(damping_left - 1)
        )

    async def place_order(self, order, ot='limit', damping_left=200):
        p_order = await order.make_processing(None)
        status = Status.PROCESSING
        symbol = str(await order.symbol)
        order_side = 'buy' if order.order_type == OrderType.BUY else 'sell'
        result = await self.bitmax_api.place_order(
            symbol=symbol,
            price=order.price,
            size=order.volume,
            order_type=ot,
            order_side=order_side,
            post_only=False,
            resp_inst='ACK'
        )
        if result['code'] in config['DAMPING_CODES']:
            if config['DAMPING']:
                self._logger.debug(result)
                await asyncio.sleep(0.5)
                asyncio.create_task(self.damp(order, damping_left))
        else:
            self._logger.debug(result)
            order_id = result['data']['info']['orderId']
            p_order.order_id = order_id
            await p_order.save()
        return result

    async def add_symbols(self, *args, **kwargs):
        try:
            await self.dbclient.add_symbols(*args, **kwargs)
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
        channel = ','.join(map(lambda x:str(x[0] + '/' + x[1]), products))
        await self.subscribe_to_channel(
            f'depth:{products}', id='abc')
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

        return bid_orders, ask_orders, symbol

    async def handle_data(self):
        @self.ws.add_dispatcher(name='receiver')
        async def handler(msg):
            if self.stopped:
                return None
            # elif msg['m'] == 'order':
            #     order_id = msg['data']['orderId']
            #     status = msg['data']['st']
            #     # p_order = await ProcessingOrder.get_or_none(order_id)
            #     if not p_order:
            #         raise self.NoSuchOrderError(order_id)

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
                            try:
                                result = await self.place_order(
                                    order=order,
                                    ot='limit',
                                )
                            except Exception as exc:
                                self._logger.exception(exc)
                                raise exc
                    if ask_orders:
                        async for order in ask_orders:
                            try:
                                result = await self.place_order(
                                    order=order,
                                    ot='limit',
                                )
                            except Exception as exc:
                                self._logger.exception(exc)
                                raise exc
                except Exception as exc:
                    self._logger.exception(exc)
                    raise exc

        await self.ws.handle_messages(close_exc=False)
        # print('Result': result)
        return result


    async def send_from_queue(self):
        while True:
            data = await self.get_from_queue()
            if not data:
                return None
            op, data = data
            await self.ws.send_json(op, data)

    async def subscribe_to_channel(self, channel, id=''):
        await self.ws.send_json('sub', data={
            'ch': channel,
            'id': id,
        })

    async def subscribe_to_all_channels(self):
        await self.subscribe_to_channel(
            f'order:cash', id='abc')
        async for symbol in await self.dbclient.list_symbols():
            await self.subscribe_to_channel(
                f'depth:{str(symbol)}', id='abc')

    async def bot(self):
        try:
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
        except asyncio.CancelledError:
            return None

    async def api_server(self):
        self._api_server = RestServer(password=self._server_pass, bot=self)
        await self._api_server.run()

    async def run(self):
        try:
            self.server = asyncio.create_task(self.api_server())
            self.bot_handler = asyncio.create_task(self.bot())
            await asyncio.gather(
                self.server,
                self.bot_handler,
            )
        except asyncio.CancelledError as exc:
            await self.__aexit__()
            raise exc

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
