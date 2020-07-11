import tortoise
import general
import os
import asyncio
from .models import Symbol, Order, OrderType

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
    def __init__(self, dbconfig=None):
        self._dbconfig = dbconfig
    async def __aenter__(self):
        await tortoise.Tortoise.init(config=self._dbconfig)

    async def __aexit__(self, *args, **kwargs):
        await tortoise.Tortoise.close_connections()

    async def list_symbols(self):
        symbols = Symbol.all()
        return symbols

    async def list_orders(self):
        orders = Order.all().prefetch_related(
            'first_symbol', 'second_symbol'
        )
        return orders


# if __name__ == '__main__':
#     client = DBClient(dbconfig=dbconfig)
#     async def main():
#         async with client:
#             symb = await Symbol.all().get(pk=1)
#             print(symb.first_ticker_orders.all().count())
#
#     asyncio.run(main())
