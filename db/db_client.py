import logging
import asyncio
import tortoise
import general

from .abstract_db_client import AbstractDBClient
from .models import Symbol, Order, ProcessingOrder, QuickButton

logger = logging.getLogger(f'{general.logger_name}.dbclient')


class DBClientWrapper:
    def __init__(self, dbconfig):
        self._dbconfig = dbconfig


    async def __aenter__(self):
        await tortoise.Tortoise.init(self._dbconfig)


    async def __aexit__(self, *args, **kwargs):
        await tortoise.Tortoise.close_connections()


class DBClient(AbstractDBClient):


    def __init__(self, using_db):
        self._using_db = using_db


    async def __aenter__(self):
        self._connection = tortoise.Tortoise.get_connection(self._using_db)


    async def __aexit__(self, *args, **kwargs):
        await tortoise.Tortoise.close_connections()


    def make_symbol(self, first, second, name=None, short_description=None):
        symbol = Symbol()
        symbol.first = first
        symbol.second = second
        return symbol


    async def list_buttons(self):
        buttons = QuickButton.all().using_db(self._connection)
        return buttons


    async def add_symbols(self, symbols):
        for symbol in symbols:
            existing = await Symbol.get_or_none(
                first=symbol.base,
                second=symbol.quote,
            ).using_db(self._connection)
            if not existing:
                new_symbol = Symbol()
                new_symbol.first = symbol.base
                new_symbol.second = symbol.quote
                new_symbol.ticker = symbol.name
                await new_symbol.save(
                    update_fields=tuple(),
                    using_db=self._connection
                )


    async def add_order(self, symbol, *args, **kwargs):
        return await symbol.add_order(*args, using_db=self._connection, **kwargs)


    async def add_button(self, order_type, volume):
        button = QuickButton()

        button.order_type = order_type
        button.volume = volume

        await button.save(using_db=self._connection)
        return button


    async def delete_symbol(self, pk):
        symbol = await Symbol.get_or_none(pk=pk).using_db(self._connection)
        if symbol:
            await symbol.delete(using_db=self._connection)
        else:
            raise self.NoSymbolExists(str(pk))
        return symbol


    async def get_order(self, pk):
        try:
            order = await Order.get(pk=pk).using_db(self._connection)
            await order.fetch_related('symbol', using_db=self._connection)
            return order
        except tortoise.exceptions.DoesNotExist:
            raise self.NoOrderExists(str(pk))


    async def delete_order(self, pk):
        order = await self.get_order(pk=pk)
        await order.delete(using_db=self._connection)
        return order


    async def delete_button(self, pk):
        button = await QuickButton.get_or_none(pk=pk).using_db(self._connection)
        if button:
            await button.delete()
        else:
            raise self.NoButtonExists(str(pk))
        return button


    async def list_symbols(self):
        symbols = Symbol.all().using_db(self._connection)
        if self._using_db == 'bitmax':
            symbols = symbols.filter(second='USDT')
        return symbols


    async def list_orders(self):
        orders = Order.all().prefetch_related(
            'symbol'
        ).using_db(self._connection)
        return orders


    async def list_processing_orders(self):
        orders = ProcessingOrder.all().prefetch_related(
            'symbol'
        ).using_db(self._connection)
        return orders


    async def get_symbol_by_pk(self, pk):
        symbol = await Symbol.get_or_none(
            pk=pk
        ).using_db(self._connection)
        if not symbol:
            raise self.NoSymbolExists(f'{pk}')
        return symbol


    async def get_symbol_by_ticker(self, ticker):
        symbol = await Symbol.get_or_none(
            ticker=ticker
        ).using_db(self._connection)
        if not symbol:
            raise self.NoSymbolExists(f'{ticker}')
        return symbol


    async def get_symbol(self, first, second):
        symbol = await Symbol.get_or_none(
            first=first,
            second=second,
        ).using_db(self._connection)
        if not symbol:
            exc = self.NoSymbolExists(f'{first}/{second}')
            raise exc
        return symbol


    async def get_orders_for_price_bid(self, price, symbol):
        return await symbol.get_orders_for_price_bid(
            price, self._connection
        )


    async def get_orders_for_price_ask(self, price, symbol):
        return await symbol.get_orders_for_price_ask(
            price, self._connection
        )


    async def make_processing(self, order, order_id):
        return await order.make_processing(
            order_id,
            using_db=self._connection,
            connection_name=self._using_db,
        )


class BitmaxDBClient(DBClient):


    def __init__(self):
        super().__init__(using_db='bitmax')


class BinanceDBClient(DBClient):


    def __init__(self):
        super().__init__(using_db='binance')


if __name__ == '__main__':
    async def main():
        client = BinanceDBClient(general.dbconfig)
        async with client:
            async for symbol in await client.list_symbols():
                print(symbol.pk)

    asyncio.run(main())
