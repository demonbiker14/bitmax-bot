import logging

import asyncio

from api.bitmax_api import BitmaxREST_API
from api.sms_api import SMSApi
from db.db_client import BitmaxDBClient
from db.models import OrderType
from .abstract_bot import AbstractBot


class BitmaxBot(AbstractBot):


    def __init__(self, dbconfig, stock_config, sms_config, logger_name):
        super().__init__(dbconfig, stock_config, sms_config, logger_name)
        self._dbconfig = dbconfig
        self._stock_config = stock_config
        self._logger = logging.getLogger(f'{logger_name}.bitmax_bot')
        self._sms_config = sms_config


    async def __aenter__(self):
        self._tasks = asyncio.Queue()
        self.api = BitmaxREST_API(
            api_token=self._stock_config['KEY'],
            secret=self._stock_config['SECRET'],
            logger=self._logger
        )
        self.dbclient = BitmaxDBClient()
        self.sms = SMSApi(
            self._sms_config['LOGIN'],
            self._sms_config['PASSWORD']
        )

        await self.api.__aenter__()

        self.ws = await self.api.connect_ws()
        await self.ws.__aenter__()

        await self.sms.__aenter__()
        await self.dbclient.__aenter__()


    async def __aexit__(self, *args, **kwargs):
        await self.sms.__aexit__(*args, **kwargs)
        await self.ws.__aexit__(*args, **kwargs)
        await self.api.__aexit__(*args, **kwargs)
        await self.dbclient.__aexit__(*args, **kwargs)


    async def put_in_queue(self, item):
        await self._tasks.put(item)


    async def get_from_queue(self):
        return await self._tasks.get()


    async def add_order(self, symbol, *args, **kwargs):
        return await self.dbclient.add_order(symbol, *args, **kwargs)


    async def delete_all_orders(self):
        await (await self.dbclient.list_orders()).delete()


    async def delete_order(self, order_pk):
        await self.dbclient.delete_order(order_pk)


    async def damp(self, order, p_order, damping_left):
        self._logger.debug(f'damping {damping_left}')
        if damping_left == 0:
            return None
        await self.place_order(
            order=order,
            p_order=p_order,
            damp_count=(damping_left - 1)
        )


    async def place_order(self, order, p_order, ot='limit', damp_count=None):
        symbol = str(await order.symbol)
        order_side = 'buy' if order.order_type == OrderType.BUY else 'sell'
        result = await self.api.place_order(
            symbol=symbol,
            price=order.price,
            size=order.volume,
            order_type=ot,
            order_side=order_side,
            post_only=False,
            resp_inst='ACK'
        )
        self._logger.info(f'Placed order\n{result}\n')
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


    async def get_orders_for_rate(self, rate):
        symbol = rate['symbol']
        price = float(rate['close'])

        try:
            if '/' not in symbol:
                # self._logger.debug(f'Improper symbol: {symbol}')
                return None
            symbol = await self.dbclient.get_symbol(*symbol.split('/'))
        except self.dbclient.NoSymbolExists:
            return None

        bid_orders, ask_orders = await asyncio.gather(
            self.dbclient.get_orders_for_price_bid(price, symbol),
            self.dbclient.get_orders_for_price_ask(price, symbol)
        )

        return bid_orders, ask_orders, symbol


    async def handle_rate(self):
        while True:
            result = await self.api.get('/ticker')
            data = result.get('data')
            if not data:
                self._logger.error(result)
                continue
            for symbol in data:
                try:
                    orders = await self.get_orders_for_rate(symbol)
                    if not orders:
                        continue
                    bid_orders, ask_orders, symbol = orders

                    if bid_orders:
                        async for order in bid_orders:
                            p_order = await self.dbclient.make_processing(order, None)
                            result = await self.place_order(
                                order=order,
                                p_order=p_order,
                                ot='limit',
                            )
                    if ask_orders:
                        async for order in ask_orders:
                            p_order = await self.dbclient.make_processing(order, None)
                            result = await self.place_order(
                                order=order,
                                p_order=p_order,
                                ot='limit',
                            )
                except Exception as exc:
                    self._logger.exception(exc)
                    continue
            await asyncio.sleep(0.5)


    async def handle_data(self):
        @self.ws.add_dispatcher(name='receiver')
        async def handler(msg):
            if msg['m'] == 'order':
                try:
                    status = msg['data']['st']
                    if status in ('Filled', 'PartiallyFilled'):
                        raw = f'Ордер на бирже Bitmax сработал'
                        if self._sms_config['ON']:
                            await self.sms.send_sms([self._sms_config['PHONE']], raw)
                    elif status != 'New':
                        self._logger.info(status)
                except Exception as exc:
                    self._logger.exception(exc)
                    raise exc

        while True:
            try:
                await self.ws.handle_messages()
            except self.ws.WSClosed as exc:
                await self.ws.__aenter__()
                continue


    async def send_from_queue(self):
        while True:
            data = await self.get_from_queue()
            if not data:
                return None
            op, data = data
            await self.ws.send_json_with_op(op=op, data=data)


    async def run(self):
        self._logger.debug('Started')
        await self.ws.subscribe_to_channel(
            f'order:cash', id='abc')
        self.tasks = asyncio.gather(*[
            self.handle_data(),
            self.handle_rate(),
            self.send_from_queue(),
        ])
        result = await self.tasks
        self._logger.error(result)
        self.tasks.cancel()
