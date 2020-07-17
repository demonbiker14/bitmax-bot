from tortoise.models import Model
from tortoise import fields, transactions
from tortoise.query_utils import Q
from tortoise.functions import Max, Min

import general
import enum
import logging

logger = logging.getLogger(f'{general.logger_name}.dbclient')

class OrderType(enum.IntEnum):
    BUY = 0
    SELL = 1

class Symbol(Model):
    id = fields.IntField(pk=True)
    ticker = fields.CharField(max_length=10)
    name = fields.CharField(max_length=256, null=True)
    short_description = fields.TextField(null=True)

    first_ticker_orders: fields.ReverseRelation["Order"]
    second_ticker_orders: fields.ReverseRelation["Order"]
    first_ticker_processing_orders: fields.ReverseRelation["Order"]
    second_ticker_processing_orders: fields.ReverseRelation["Order"]

    def __str__(self):
        return self.ticker

    # async def get_orders(self):
    #     orders = Order.filter(
    #         Q(first_symbol = self) | Q(second_symbol = self)
    #     )
    #     return orders
    #
    # async def get_first_orders(self):
    #     orders = Order.filter(
    #         Q(first_symbol = self)
    #     )
    #     return orders
    #
    # async def get_second_orders(self):
    #     orders = Order.filter(
    #         Q(second_symbol = self)
    #     )
    #     return orders

    class Meta:
        table = 'symbol'
        indexes = ('ticker',)

class Order(Model):
    id = fields.IntField(pk=True)
    first_symbol = fields.ForeignKeyField('db.Symbol', related_name='first_ticker_orders')
    second_symbol = fields.ForeignKeyField('db.Symbol', related_name='second_ticker_orders')
    trigger_price = fields.FloatField()
    order_type = fields.IntEnumField(enum_type=OrderType)
    price = fields.FloatField()
    volume = fields.FloatField()
    class Meta:
        table = 'order'

    async def make_processing(self, order_id):
        async with transactions.in_transaction() as transaction:
            p_order = ProcessingOrder()
            p_order.order_id = order_id
            p_order.first_symbol = await self.first_symbol
            p_order.second_symbol = await self.second_symbol
            p_order.price = self.price
            p_order.order_type = self.order_type
            p_order.status = Status.PROCESSING
            await p_order.save()
            await self.delete()
            return p_order

    async def to_str(self):
        first = await self.first_symbol
        second = await self.second_symbol
        order_type = 'BUY' if self.order_type == OrderType.BUY else 'SELL'
        return (
            f'{first}/{second} {order_type} Trigger: {self.trigger_price} Actual: {self.price}'
        )

class Status(enum.IntEnum):
    PROCESSING = 0
    DONE = 1
    ERROR = 2

    def __str__(self):
        if self.value == Status.PROCESSING:
            return 'PROCESSING'
        elif self.value == Status.DONE:
            return 'DONE'
        elif self.value == Status.ERROR:
            return 'ERROR'

class ProcessingOrder(Model):
    id = fields.IntField(pk=True)
    order_id = fields.CharField(max_length=32)
    first_symbol = fields.ForeignKeyField('db.Symbol', related_name='first_ticker_processing_orders')
    second_symbol = fields.ForeignKeyField('db.Symbol', related_name='second_ticker_processing_orders')
    order_type = fields.IntEnumField(enum_type=OrderType)
    status = fields.IntEnumField(enum_type=Status)
    price = fields.FloatField()
    volume = fields.FloatField()
    class Meta:
        table = 'processing_order'

    async def to_str(self):
        first = await self.first_symbol
        second = await self.second_symbol
        order_type = 'BUY' if self.order_type == OrderType.BUY else 'SELL'
        return (
            f'{first}/{second} {order_type} Actual: {self.price} Status: {str(self.status)}'
        )


class SymbolPair:
    first = None
    second = None

    @classmethod
    async def get_by_tickers(cls, first_ticker, second_ticker):
        first = await Symbol.get(ticker=first_ticker)
        second = await Symbol.get(ticker=second_ticker)
        return cls(first, second)

    def __init__(self, first_symbol, second_symbol):
        self.first = first_symbol
        self.second = second_symbol

    def to_symbol(self):
        return f'{self.first.ticker}/{self.second.ticker}'

    async def get_orders(self):
        orders = Order.filter(
            Q(first_symbol = await self.first) | Q(second_symbol = await self.second )
        )
        return orders

    async def add_order(self, order_type, trigger_price, price, volume):
        order = Order()

        order.order_type = order_type
        order.trigger_price = trigger_price
        order.price = price
        order.first_symbol = self.first
        order.second_symbol = self.second
        order.volume = volume

        await order.save()

    async def get_max_ask_order(self):
        orders = await self.get_orders()
        max_trigger_price = orders.annotate(
            max_trigger_price=Max('trigger_price'),
            order_type=OrderType.SELL
        ).first()
        return (await max_trigger_price).max_trigger_price

    async def get_min_bid_order(self):
        orders = await self.get_orders()
        min_trigger_price = orders.annotate(
            min_trigger_price=Min('trigger_price'),
            order_type=OrderType.BUY
        ).first()
        return (await min_trigger_price).min_trigger_price

    async def get_orders_for_price_ask(self, price):
        orders = await self.get_orders()
        orders = orders.filter(
            trigger_price__lte=price,
            order_type=OrderType.SELL
        )
        return orders

    async def get_orders_for_price_bid(self, price):
        orders = await self.get_orders()
        orders = orders.filter(
            trigger_price__gte=price,
            order_type=OrderType.BUY
        )
        return orders

    def __eq__(self, pair2):
        return (self.first, self.second, ) == (pair2.first, pair2.second, )

    def __str__(self):
        return f'{self.first.ticker}/{self.second.ticker}'

    async def to_str(self):
        first = (await self.first.first()).ticker
        second = (await self.second.first()).ticker
        return f'{first}/{second}'

    # def __str__(self):
    #     print(dir(self.first))
