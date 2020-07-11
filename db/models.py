from tortoise.models import Model
from tortoise import fields
from tortoise.query_utils import Q
from tortoise.functions import Max, Min
import enum

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

    def __str__(self):
        return self.ticker

    async def get_orders(self):
        orders = Order.filter(
            Q(first_symbol = self) | Q(second_symbol = self)
        )
        return orders

    async def get_first_orders(self):
        orders = Order.filter(
            Q(first_symbol = self)
        )
        return orders

    async def get_second_orders(self):
        orders = Order.filter(
            Q(second_symbol = self)
        )
        return orders

    class Meta:
        table = 'symbol'
        indexes = ('ticker',)

class Order(Model):
    id = fields.IntField(pk=True)
    first_symbol = fields.ForeignKeyField('db.Symbol', related_name='first_ticker_orders')
    second_symbol = fields.ForeignKeyField('db.Symbol', related_name='second_ticker_orders')
    trigger_price = fields.IntField()
    order_type = fields.IntEnumField(enum_type=OrderType)
    price = fields.IntField()
    class Meta:
        table = 'order'


class SymbolPair:
    first = None
    second = None

    def __init__(self, first_symbol, second_symbol):
        self.first = first_symbol
        self.second = second_symbol

    async def get_orders(self):
        orders = Order.filter(
            Q(first_symbol = self.first) | Q(second_symbol = self.second)
        )
        return orders

    async def get_max_order(self):
        orders = await self.get_orders()
        max_trigger_price = orders.annotate(
            max_trigger_price=Max('trigger_price')
        ).first()
        return (await max_trigger_price).max_trigger_price

    async def get_min_order(self):
        orders = await self.get_orders()
        min_trigger_price = orders.annotate(
            min_trigger_price=Min('trigger_price')
        ).first()
        return (await min_trigger_price).min_trigger_price

    async def get_orders_for_price_ask(self, price):
        orders = await self.get_orders()
        orders = orders.filter(trigger_price__lte=price)
        return orders

    async def get_orders_for_price_bid(self, price):
        orders = await self.get_orders()
        orders = orders.filter(trigger_price__gte=price)
        return orders

    def __eq__(self, pair2):
        return (self.first, self.second, ) == (pair2.first, pair2.second, )

    def __str__(self):
        return f'{self.first.ticker}/{self.second.ticker}'
