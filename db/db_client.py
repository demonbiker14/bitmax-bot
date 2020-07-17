import tortoise
import general
import os
import asyncio
import logging
import sys

from .models import Symbol, Order, OrderType, SymbolPair

logger = logging.getLogger(f'{general.logger_name}.dbclient')

db_path = os.path.join(general.BASE_DIR, general.DB_NAME)

dbconfig = {
    'connections': {
        'default': f'sqlite://{db_path}'
    },
    'apps': {
        'db': {
            'models': ['db.models'],
            'default_connection': 'default',
        }
    }
}

class DBClient:
    class NoSymbolExists(Exception):
        pass
    def __init__(self, dbconfig=None):
        self._dbconfig = dbconfig
    async def __aenter__(self):
        await tortoise.Tortoise.init(config=self._dbconfig)

    async def __aexit__(self, *args, **kwargs):
        await tortoise.Tortoise.close_connections()

    async def add_order(self, pair, *args, **kwargs):
        await pair.add_order(*args, **kwargs)

    async def list_symbols(self):
        symbols = Symbol.all()
        return symbols

    async def list_orders(self):
        orders = Order.all().prefetch_related(
            'first_symbol', 'second_symbol'
        )
        return orders

    async def get_symbol_pair(self, first_ticker, second_ticker):
        first, second = await asyncio.gather(
            Symbol.get_or_none(ticker=first_ticker),
            Symbol.get_or_none(ticker=second_ticker)
        )
        if not (first and second):
            exc = self.NoSymbolExists(f'{first_ticker}/{second_ticker}')
            logger.exception(exc)
            raise exc
        pair = SymbolPair(first, second)
        return pair


if __name__ == '__main__':
    client = DBClient(dbconfig=dbconfig)
    async def main():
        async with client:
            symb = await Symbol.all().get(pk=1)
            print(symb.first_ticker_orders.all().count())

    asyncio.run(main())
