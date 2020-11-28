from aiohttp import web, web_exceptions
from db.models import Symbol, Order

import asyncio
import general
import json
import logging
import math

logger = logging.getLogger(f'{general.logger_name}.web')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('logs/web.log', mode='a+')
handler.setFormatter(general.logger_formatter)
logger.addHandler(handler)

DB_PATH = 'db/db.sqlite3'


class RestServer:
    class NotUSDTError(Exception):
        pass


    def get_bot(self, stock_name):
        if stock_name == 'bitmax':
            return self.bot.bitmax_bot
        elif stock_name == 'binance':
            return self.bot.binance_bot
        else:
            raise ValueError()


    def __init__(self, config, bot):
        self._host = config['HOST']
        self._port = config['PORT']
        self._app = web.Application(middlewares=[
            self.choose_stock_middleware,
            self.cors_middleware,
        ], logger=logger)
        self._prefix = '/api'
        self.bot = bot
        self.set_views()


    @web.middleware
    async def choose_stock_middleware(self, request, handler):
        stock = request.query.get('stock')
        if not stock:
            raise ValueError()
        request.stock_name = stock
        request.bot = self.get_bot(stock)
        response = await handler(request)
        return response


    @web.middleware
    async def cors_middleware(self, request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response


    async def get_user_info(self, request):
        response = await request.bot.api.get('/info')
        return web.json_response(response)


    async def update_symbols_handler(self, request):
        await request.bot.update_symbols()
        data = {'data':[]}
        async for symbol in await request.bot.dbclient.list_symbols():
            data['data'].append(await symbol.to_dict())
        return web.json_response(data)


    async def update_symbol_handler(self, request):
        pk = request.match_info['pk']
        data = await request.json()
        symbol = await request.bot.dbclient.get_order_by_pk(int(pk))
        if symbol:
            await symbol.update_from_dict(data)
            await symbol.save()
        else:
            symbol = {}
        return web.json_response({
            'data': await symbol.to_dict(),
        })


    async def options_handler(self, request):
        response = web.Response()
        response.headers['Access-Control-Allow-Methods'] = 'DELETE'
        return response


    async def delete_handler(self, request):
        object = request.match_info['object']
        if object == 'order':
            order_pk = request.match_info['id']
            if order_pk == 'all':
                await request.bot.delete_all_orders()
            else:
                await request.bot.delete_order(int(order_pk))
            return web.json_response({})
        elif object == 'button':
            button_pk = request.match_info['id']
            button = await request.bot.dbclient.delete_button(int(button_pk))
            return web.json_response({})
        else:
            raise web_exceptions.HTTPNotFound(reason='Unknown object')


    async def list_handler(self, request):
        objects = request.match_info['objects']
        if objects == 'orders':
            orders = await request.bot.dbclient.list_orders()
            data = []
            async for order in orders:
                data.append(await order.to_dict())
            data = {
                'data': data
            }
        elif objects == 'symbols':
            symbols = await request.bot.dbclient.list_symbols()
            data = []
            async for symbol in symbols:
                data.append(await symbol.to_dict())
            data = {
                'data': data
            }
        elif objects == 'buttons':
            buttons = await request.bot.dbclient.list_buttons()
            data = []
            async for button in buttons:
                data.append(await button.to_dict())
            data = {
                'data': data
            }
        else:
            raise web_exceptions.HTTPNotFound(reason="Unknown object")

        return web.json_response(data)


    async def get_handler(self, request):
        object = request.match_info['object']
        data = None
        if object == 'rate':
            ticker = request.query.get('ticker')
            if not ticker:
                raise ValueError('No params provided')
            try:
                price = await request.bot.api.get_rate(ticker)
                data = {'price': price}
            except KeyError:
                data = {'error' : 'No such symbol'}
        return web.json_response(data)


    async def post_handler(self, request):
        object = request.match_info['object']
        if object == 'order':
            data = await request.json()
            first, second = data['symbol'].split('/')
            if request.stock_name == 'bitmax' and second != 'USDT':
                raise self.NotUSDTError(data['symbol'])

            trigger_price = float(data['trigger_price'])
            price = float(data['price'])
            order_type = data['order_type']
            symbol = await request.bot.dbclient.get_symbol(first, second)
            volume = float(data['volume'])
            rate = await request.bot.api.get_rate(symbol.ticker)
            volume *= float(rate)


            volume = math.ceil(volume)

            order = await request.bot.add_order(
                symbol=symbol,
                order_type=order_type,
                trigger_price=trigger_price,
                price=price,
                volume=volume
            )

            return web.json_response(await order.to_dict())

        elif object == 'button':
            button = await request.json()

            order_type = int(button['order_type'])
            volume = float(button['volume'])

            new_button = await request.bot.dbclient.add_button(
                order_type=order_type,
                volume=volume
            )

            return web.json_response({'ok': 1})

        else:
            raise web_exceptions.HTTPNotFound(reason="Unknown object")


    async def download_db(self, request):
        orders = await (await request.bot.dbclient.list_orders())
        data = {'orders':[]}

        for order in orders:
            order = await order.to_dict()
            data['orders'].append(order)

        data = json.dumps(data)

        response = web.Response(
            body=data,
            headers={
                'Content-Disposition': 'Attachment;filename=db.dump',
            },
        )

        return response


    async def upload_db(self, request):
        reader = await request.multipart()
        while True:
            part = await reader.next()
            if not part:
                break
            if part.name == 'file':
                if not part.filename:
                    raise web_exceptions.HTTPBadRequest()
                data = json.loads(await part.text())
                for order in data['orders']:
                    first, second = order['symbol'].split('/')
                    symbol = await request.bot.dbclient.get_symbol(first, second)

                    trigger_price = float(order['trigger_price'])
                    price = float(order['price'])
                    order_type = int(order['order_type'])
                    volume = float(order['volume'])

                    try:
                        order = await request.bot.dbclient.add_order(
                            symbol=symbol,
                            order_type=order_type,
                            trigger_price=trigger_price,
                            price=price,
                            volume=volume
                        )
                    except Exception as exc:
                        logger.exception(exc)
                        raise exc
        return web.Response(text='response')


    def set_views(self):
        views = [
            web.get(self._prefix + '/list/{objects}', self.list_handler),
            web.get(self._prefix + '/get/{object}', self.get_handler),
            web.get(self._prefix + '/user/info', self.get_user_info),
            web.get(self._prefix + '/download/db', self.download_db),
            web.post(self._prefix + '/post/{object}', self.post_handler),
            web.post(self._prefix + '/update/symbol/{pk}', self.update_symbol_handler),
            web.post(self._prefix + '/update/symbols', self.update_symbols_handler),
            web.post(self._prefix + '/upload/db', self.upload_db),
            web.delete(self._prefix + '/delete/{object}/{id}', self.delete_handler),
            web.route('OPTIONS', self._prefix + '/delete/{object}/{id}', self.options_handler),
        ]
        self._app.add_routes(views)


    async def run(self):
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            self._host,
            self._port,
        )
        await site.start()
        while True:
            await asyncio.sleep(60*60)
