from api.bitmax_api import BitmaxREST_API
from db.db_client import DBClient
from db.models import OrderType, Status, ProcessingOrder
from rest.rest_server import RestServer
from api.sms_api import SMSApi

import general
import logging
import asyncio
import pprint
import sys


class MarketBot:
    class NoSuchOrderError(Exception):
        pass
    def __init__(self, dbconfig, token, secret, server_pass, sms_on, sms_login, sms_pass, sms_phone, damping, damp_count):
        self._dbconfig = dbconfig
        self._token = token
        self.damping = damping
        self.damp_count = damp_count
        self._secret = secret
        self._server_pass = server_pass
        self._logger = logging.getLogger(f'{general.logger_name}.market_bot')
        self.sms_on = sms_on
        self.sms_login = sms_login
        self.sms_pass = sms_pass
        self.sms_phone = sms_phone

    async def __aenter__(self):
        try:
            self._tasks = asyncio.Queue()
            self.bitmax_api = BitmaxREST_API(
                api_token=self._token,
                secret=self._secret,
                logger=self._logger
            )
            await self.bitmax_api.__aenter__()

            self.sms = SMSApi(self.sms_login, self.sms_pass)
            self.ws = await self.bitmax_api.connect_ws()
            self.dbclient = DBClient(self._dbconfig)

            await self.ws.__aenter__()
            await self.sms.__aenter__()
            await self.dbclient.__aenter__()


        except Exception as exc:
            self._logger.exception(exc)
            raise exc

    async def __aexit__(self, *args, **kwargs):
        try:
            await self.sms.__aexit__(*args, **kwargs)
            await self.ws.__aexit__(*args, **kwargs)
            await self.bitmax_api.__aexit__(*args, **kwargs)
            await self.dbclient.__aexit__(*args, **kwargs)
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

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
        if not damp_count:
            damp_count = self.damp_count
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
        self._logger.warning(result)
        try:
            if result['code'] in config['DAMPING_CODES']:
                if config['DAMPING']:
                    await asyncio.sleep(0.5)
                    asyncio.create_task(self.damp(
                        order=order,
                        p_order=p_order,
                        damping_left=damp_count,
                    ))
            elif result['code'] == 0:
                order_id = result['data']['info']['orderId']
                # print(order_id)
                p_order.order_id = order_id
                await p_order.save()
                return result
            else:
                await p_order.delete()
                self._logger.error(result)
        except Exception as exc:
            self._logger.error(result)
            self._logger.exception(exc)
            raise exc
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


    async def get_orders_for_rate(self, rate):
        symbol = rate['symbol']
        price = float(rate['close'])

        try:
            if '/' not in symbol:
                self._logger.debug(f'Improper symbol: {symbol}')
                return None
            symbol = await self.dbclient.get_symbol(*symbol.split('/'))
        except self.dbclient.NoSymbolExists as exc:
            self._logger.warning(f'No symbol: {symbol}')
            return None
        except Exception as exc:
            self._logger.exception(exc)
            raise exc

        bid_orders, ask_orders = await asyncio.gather(
            symbol.get_orders_for_price_bid(price),
            symbol.get_orders_for_price_ask(price)
        )

        return bid_orders, ask_orders, symbol

    async def handle_data(self):
        @self.ws.add_dispatcher(name='receiver')
        async def handler(msg):
            if msg['m'] == 'order':
                try:
                    order_id = msg['data']['orderId']
                    status = msg['data']['st']
                    # p_order = await ProcessingOrder.get_or_none(order_id=order_id)
                    if status in ('Filled', 'PartiallyFilled'):
                        raw = f'Ордер на бирже Bitmax сработал'
                        if self.sms_on:
                            await self.sms.send_sms([self.sms_phone], raw)
                    elif status != 'New':
                        self._logger.info(status)
                    # if not p_order:
                    #     raise self.NoSuchOrderError(order_id)
                except Exception as exc:
                    self._logger.exception(exc)
                    raise exc

        await self.ws.handle_messages(close_exc=False)
        return result

    async def handle_rate(self):
        while True:
            result = await self.bitmax_api.get('/ticker')
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
                            try:
                                p_order = await order.make_processing(None)
                                result = await self.place_order(
                                    order=order,
                                    p_order=p_order,
                                    ot='limit',
                                )
                            except Exception as exc:
                                self._logger.exception(exc)
                                raise exc
                    if ask_orders:
                        async for order in ask_orders:
                            try:
                                p_order = await order.make_processing(None)
                                result = await self.place_order(
                                    order=order,
                                    p_order=p_order,
                                    ot='limit',
                                )
                            except Exception as exc:
                                self._logger.exception(exc)
                                raise exc
                except Exception as exc:
                    self._logger.exception(exc)
                    continue
            await asyncio.sleep(0.5)

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

    # async def subscribe_to_all_channels(self):
    #     await self.subscribe_to_channel(
    #         f'order:cash', id='abc')

    async def bot(self):
        try:
            await self.subscribe_to_channel(
                f'order:cash', id='abc')

            self.tasks = asyncio.gather(
                self.handle_data(),
                self.handle_rate(),
                self.send_from_queue(),
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
            self.running = asyncio.gather(
                self.server,
                self.bot_handler,
            )
            await self.running
        except asyncio.CancelledError as exc:
            self._logger.exception(exc)
            await self.__aexit__()
            raise exc

if __name__ == '__main__':
    from general import dbconfig
    from config import config
    import pprint
    async def main():
        bot = MarketBot(
            dbconfig=dbconfig,
            damping=config.get('DAMPING', False),
            damp_count=config.get('DAMP_COUNT', 200),
            token=config['BITMAX']['KEY'],
            secret=config['BITMAX']['SECRET'],
            server_pass=config['REST']['PASSWORD'],
            sms_on=config['SMS'].get('ON', False),
            sms_login=config['SMS']['LOGIN'],
            sms_pass=config['SMS']['PASSWORD'],
            sms_phone=config['SMS']['PHONE'],

        )
        async with bot:
            await bot.run()
    asyncio.run(main())
