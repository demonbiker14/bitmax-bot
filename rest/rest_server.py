from aiohttp import web, web_exceptions
from config import config
from db.models import Symbol, OrderType

import asyncio
import aiohttp
import general
import logging
import os.path

logger = logging.getLogger(f'{general.logger_name}.web')
logger.addHandler(logging.FileHandler('logs/web.log', mode='a+'))
DB_PATH = 'db/db.sqlite3'

api_config = config['SERVER_API']

class RestServer:
    class NotUSDTError(Exception):
        pass

    def __init__(self, password, bot, host=api_config['HOST'], port=api_config['PORT']):
        self._host = host
        self._port = port
        self._password = password
        self._app = web.Application(middlewares=[self.cors_middleware])
        self._prefix = '/api'
        self.bot = bot
        self.set_views()

    @web.middleware
    async def cors_middleware(self, request, handler):
        try:
            response = await handler(request)
            # print(response)
        except Exception as exc:
            logger.debug(request)
            logger.exception(exc)
            raise exc
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    async def download_db(self, request):
        return web.FileResponse(os.path.join(general.BASE_DIR, DB_PATH))

    async def get_user_info(self, request):
        response = await self.bot.bitmax_api.get('/info')
        return web.json_response(response)

    async def update_symbols_handler(self, request):
        await self.bot.update_symbols()
        data = {'data':[]}
        async for symbol in await self.bot.dbclient.list_symbols():
            data['data'].append(await symbol.to_dict())
        return web.json_response(data)

    async def update_symbol(self, request):
        pk = request.match_info['pk']
        data = await request.json()
        symbol = await Symbol.get_or_none(pk=int(pk))
        if symbol:
            try:
                symbol.update_from_dict(data)
                await symbol.save()
            except Exception as exc:
                logger.exception(exc)
                raise exc
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
            order = await self.bot.dbclient.delete_order(int(order_pk))
            # print(order.to_str())
            return web.json_response({})
        elif object == 'button':
            button_pk = request.match_info['id']
            button = await self.bot.dbclient.delete_button(int(button_pk))
            return web.json_response({})
        else:
            raise web_exceptions.HTTPNotFound(reason='Unknown object')

    async def list_handler(self, request):
        objects = request.match_info['objects']
        if objects == 'orders':

            orders = await self.bot.dbclient.list_orders()
            data = []
            async for order in orders:
                data.append(await order.to_dict())
            data = {
                'data': data
            }

        elif objects == 'symbols':
            symbols = await self.bot.dbclient.list_symbols()
            data = []
            async for symbol in symbols:
                data.append(await symbol.to_dict())
            data = {
                'data': data
            }

        elif objects == 'buttons':
            buttons = await self.bot.dbclient.list_buttons()
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
        if object == 'rate':
            ticker = request.query.get('ticker')
            if not ticker:
                raise ValueError('No params provided')
            rate = await self.bot.bitmax_api.get_rate(ticker)
            data = {'data':rate}
        return web.json_response(data)

    async def post_handler(self, request):
        object = request.match_info['object']
        if object == 'order':
            data = await request.json()
            first, second = data['symbol'].split('/')
            if second != 'USDT':
                raise self.NotUSDTError(data['symbol'])
            rate = await self.bot.bitmax_api.get_rate(data['symbol'])

            symbol = await self.bot.dbclient.get_symbol(first, second)

            trigger_price = float(data['trigger_price'])
            price = float(data['price'])
            order_type = data['order_type']
            volume = float(data['price']) * float(rate['data']['open'])
            # correct_volume = floatvolume * rate

            try:
                order = await self.bot.dbclient.add_order(
                    symbol=symbol,
                    order_type=order_type,
                    trigger_price=trigger_price,
                    price=price,
                    volume=volume
                )
            except Exception as exc:
                logger.exception(exc)
                raise exc
            return web.json_response(await order.to_dict())

        elif object == 'button':
            button = await request.json()

            order_type = int(button['order_type'])
            volume = float(button['volume'])

            new_button = await self.bot.dbclient.add_button(
                order_type=order_type,
                volume=volume
            )

            return web.json_response({'ok': 1})

        else:
            raise web_exceptions.HTTPNotFound(reason="Unknown object")

    async def upload_db(self, request):
        reader = await request.multipart()
        # if fiekd
        while True:
            part = await reader.next()
            if not part:
                break
            if part.name == 'file':
                if not part.filename:
                    raise web_exceptions.HTTPBadRequest()
                file = open(os.path.join(general.BASE_DIR, DB_PATH), 'wb+')
                with file:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        file.write(chunk)

        async with asyncio.Lock():
            pass
        return web.Response(text='response')


    def set_views(self):
        views = [
            web.get(self._prefix + '/list/{objects}', self.list_handler),
            web.get(self._prefix + '/get/{object}', self.get_handler),
            # web.get(self._prefix + '/get/')
            web.get(self._prefix + '/user/info', self.get_user_info),
            web.get(self._prefix + '/download/db', self.download_db),
            web.post(self._prefix + '/post/{object}', self.post_handler),
            web.post(self._prefix + '/update/symbol/{pk}', self.update_symbol),
            web.post(self._prefix + '/update/symbols', self.update_symbols_handler),
            web.post(self._prefix + '/upload/db', self.upload_db),
            web.delete(self._prefix + '/delete/{object}/{id}', self.delete_handler),
            web.route('OPTIONS', self._prefix + '/delete/{object}/{id}', self.options_handler),
        ]
        self._app.add_routes(views)

    async def run(self):
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        while True:
            await asyncio.sleep(60*60)




if __name__ == '__main__':
    # async def main():
    server = RestServer(config['REST']['PASSWORD'])
    asyncio.run_forever(server.run())
    # server.run()
    # asyncio.run(main(), debug=True)
