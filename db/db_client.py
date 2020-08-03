import tortoise
import general
import os
import asyncio
import logging
import sys

from .models import Symbol, Order, OrderType, ProcessingOrder, QuickButton

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
    class NoOrderExists(Exception):
        pass
    class NoButtonExists(Exception):
        pass
    def __init__(self, dbconfig=None):
        self._dbconfig = dbconfig
    async def __aenter__(self):
        await tortoise.Tortoise.init(config=self._dbconfig)

    async def __aexit__(self, *args, **kwargs):
        await tortoise.Tortoise.close_connections()

    def make_symbol(self, first, second, name=None, short_description=None):
        symbol = Symbol()
        symbol.first = first
        symbol.second = second
        return symbol

    async def list_buttons(self):
        buttons = QuickButton.all()
        return buttons

    async def add_symbols(self, values):
        i = 0
        for value in values:
            existing = await Symbol.get_or_none(
                first=value[0],
                second=value[1]
            )
            i += 1
            if not existing:
                symbol = Symbol()
                symbol.first, symbol.second = value
                await symbol.save(update_fields=tuple())

    async def add_order(self, symbol, *args, **kwargs):
        return await symbol.add_order(*args, **kwargs)

    async def add_button(self, order_type, volume):
        try:
            button = QuickButton()

            button.order_type = order_type
            button.volume = volume

            await button.save()
            return button

        except Exception as exc:
            logger.exception(exc)
            raise exc

    async def delete_symbol(self, pk):
        symbol = await Symbol.get_or_none(pk=pk)
        if symbol:
            await symbol.delete()
        else:
            raise self.NoSymbolExists(str(pk))
        return symbol

    async def delete_order(self, pk):
        order = await Order.get_or_none(pk=pk)
        if order:
            await order.delete()
        else:
            raise self.NoOrderExists(str(pk))
        return order

    async def delete_button(self, pk):
        button = await QuickButton.get_or_none(pk=pk)
        if button:
            await button.delete()
        else:
            raise self.NoButtonExists(str(pk))
        return button

    async def list_symbols(self):
        symbols = Symbol.all().filter(second='USDT')
        return symbols

    async def list_orders(self):
        orders = Order.all().prefetch_related(
            'symbol'
        )
        return orders

    async def list_processing_orders(self):
        orders = ProcessingOrder.all().prefetch_related(
            'symbol'
        )
        return orders

    async def get_symbol(self, first, second):
        symbol = await Symbol.get_or_none(
            first=first,
            second=second,
        )
        if not symbol:
            exc = self.NoSymbolExists(f'{first}/{first}')
            # logger.exception(exc)
            raise exc
        return symbol


if __name__ == '__main__':
    client = DBClient(dbconfig=dbconfig)
    async def main():
        async with client:
            order = await Order.all().limit(1)
            await order[0].save()
            print(await order[0].to_str())
    asyncio.run(main())
