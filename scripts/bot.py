from api.bitmax_api import BitmaxREST_API
from db.db_client import DBClient
from db.models import SymbolPair, OrderType, Status

import general
import logging
import asyncio
import pprint
import sys


class MarketBot:
    bid_floor = None
    ask_ceil = None

    def __init__(self, dbconfig, token, secret):
        self._dbconfig = dbconfig
        self._token = token
        self._secret = secret
        self._tasks = asyncio.Queue()
        self._logger = logging.getLogger(f'{general.logger_name}.market_bot')
        # self._pending_tasks = asyncio.Queue()

    async def __aenter__(self):
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
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

    async def place_order(self, order_type, pair, price, volume, ot='market'):
        symbol = pair.to_symbol()
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
            pair = await self.dbclient.get_symbol_pair(*symbol.split('/'))
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

        if self.bid_floor and min_bid_price and min_bid_price >= self.bid_floor:
            min_bid_price = None

        if self.ask_ceil and max_ask_price and max_ask_price <= self.ask_ceil:
            max_ask_price = None

        if not min_bid_price and max_ask_price:
            bid_orders = None
            ask_orders = await pair.get_orders_for_price_ask(max_ask_price)
        elif not max_ask_price and min_bid_price:
            ask_orders = None
            bid_orders = await pair.get_orders_for_price_bid(min_bid_price)
        elif max_ask_price and min_bid_price:
            bid_orders, ask_orders = await asyncio.gather(
                pair.get_orders_for_price_bid(min_bid_price),
                pair.get_orders_for_price_ask(max_ask_price)
            )
        else:
            bid_orders = ask_orders = None

        if not self.bid_floor:
            self.bid_floor = min_bid_price

        if not self.ask_ceil:
            self.ask_ceil = max_ask_price

        return bid_orders, ask_orders, pair

    async def handle_data(self):
        @self.ws.add_dispatcher(name='receiver')
        async def handler(msg):
            if msg['m'] == 'depth':
                # pprint.pprint(msg)
                symbol = msg.get('symbol')
                data = msg.get('data')

                if not (data and symbol):
                    raise ValueError(msg)

                orders = await self.get_orders_from_msg(msg)

                if not orders:
                    return None

                bid_orders, ask_orders, pair = orders

                try:
                    if bid_orders:
                        async for order in bid_orders:
                            status = Status.PROCESSING
                            result = await self.place_order(
                                pair=pair,
                                ot='market',
                                order_type=OrderType.BUY,
                                price=order.price,
                                volume=order.volume
                            )
                            order_id = result['data']['info']['orderId']
                            p_order = await order.make_processing(order_id)
                    if ask_orders:
                        async for order in ask_orders:
                            # print(await order.make_processing(order_id))
                            status = Status.PROCESSING
                            result = await self.place_order(
                                pair=pair,
                                ot='market',
                                order_type=OrderType.SELL,
                                price=order.price,
                                volume=order.volume
                            )
                            order_id = result['data']['info']['orderId']
                            p_order = await order.make_processing(order_id)
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

    async def run(self):
        # orders
        channel = 'depth:BTMX/USDT'
        await self.subscribe_to_channel(channel, id='abc')
        self.tasks = asyncio.gather(
            self.handle_data(),
            self.send_from_queue()
        )

        await self.tasks

if __name__ == '__main__':
    from general import dbconfig
    from config import config

    async def main():
        bot = MarketBot(dbconfig=dbconfig, token=config['BITMAX']['KEY'], secret=config['BITMAX']['SECRET'])
        async with bot:
            await bot.run()
    asyncio.run(main())
