from db.models import OrderType, Status, ProcessingOrder
from db.db_client import DBClientWrapper
from rest.rest_server import RestServer

from .bitmax_bot import BitmaxBot
from .binance_bot import BinanceBot

import general
import logging
import asyncio
import pprint

class MarketBot:
    class NoSuchOrderError(Exception):
        pass


    def __init__(
        self, dbconfig, bitmax_config, binance_config, sms_config, server_config
    ):
        self._dbconfig = dbconfig
        self._bitmax_config = bitmax_config
        self._binance_config = binance_config
        self._server_config = server_config
        self._sms_config = sms_config
        self._logger_name = f'{general.logger_name}'
        self._logger = logging.getLogger(self._logger_name)


    async def __aenter__(self):
        self._tasks = asyncio.Queue()
        self.dbclient_wrapper = DBClientWrapper(self._dbconfig)

        self.bitmax_bot = BitmaxBot(
            dbconfig=self._dbconfig,
            stock_config=self._bitmax_config,
            sms_config=self._sms_config,
            logger_name=self._logger_name,
        )
        self.binance_bot = BinanceBot(
            dbconfig=self._dbconfig,
            stock_config=self._binance_config,
            sms_config=self._sms_config,
            logger_name=self._logger_name,
        )
        await self.dbclient_wrapper.__aenter__()
        await self.bitmax_bot.__aenter__()
        await self.binance_bot.__aenter__()


    async def __aexit__(self, *args, **kwargs):
        await self.bitmax_bot.__aexit__(*args, **kwargs)
        await self.binance_bot.__aexit__(*args, **kwargs)
        await self.dbclient_wrapper.__aexit__(*args, **kwargs)



    async def api_server(self):
        self.api_server = RestServer(config=self._server_config, bot=self)
        await self.api_server.run()


    async def run(self):
        self.server_task = self.api_server()
        self.bitmax_bot_task = self.bitmax_bot.run()
        self.binance_bot_task = self.binance_bot.run()
        self.running = asyncio.gather(
            self.server_task,
            self.bitmax_bot_task,
            self.binance_bot_task,
        )
        await self.running


if __name__ == '__main__':
    from general import dbconfig
    from config import config
    import pprint
    async def main():
        bot = MarketBot(
            dbconfig=dbconfig,
            bitmax_config=config['BITMAX'],
            binance_config=config['BINANCE'],
            sms_config=config['SMS'],
            server_config=config['SERVER_API'],
        )
        while True:
            async with bot:
                await bot.run()
    asyncio.run(main())
