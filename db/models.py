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
    first = fields.CharField(max_length=10)
    second = fields.CharField(max_length=10)
    ticker = fields.CharField(max_length=21)
    orders: fields.ReverseRelation["db.Order"]
    processing_orders: fields.ReverseRelation["db.ProcessingOrder"]


    def __str__(self):
        return f'{self.first}/{self.second}'


    async def to_dict(self):
        return {
            'id': self.pk,
            'first': self.first,
            'second': self.second,
            'ticker': self.ticker,
        }


    async def add_order(self, order_type, trigger_price, price, volume, using_db):
        order = Order()

        order.order_type = order_type
        order.trigger_price = trigger_price
        order.price = price
        order.symbol = self
        order.volume = volume

        await order.save(using_db=using_db)
        return order


    async def get_orders(self, using_db):
        return self.orders.all().prefetch_related('symbol').using_db(using_db)


    async def get_orders_for_price_ask(self, price, using_db):
        orders = (await self.get_orders(using_db)).filter(
            trigger_price__lte=price,
            order_type=OrderType.SELL
        )
        return orders


    async def get_orders_for_price_bid(self, price, using_db):
        orders = (await self.get_orders(using_db)).filter(
            trigger_price__gte=price,
            order_type=OrderType.BUY
        ).using_db(using_db)
        return orders


    class Meta:
        table = 'symbol'
        ordering = [
            'first', 'second'
        ]


class Order(Model):
    id = fields.IntField(pk=True)
    symbol = fields.ForeignKeyField('db.Symbol', related_name='orders')
    trigger_price = fields.FloatField()
    order_type = fields.IntEnumField(enum_type=OrderType)
    price = fields.FloatField()
    volume = fields.FloatField()
    add_timestamp = fields.DatetimeField(auto_now_add=True, null=True)


    async def to_dict(self):
        return {
            'id': self.pk,
            'symbol': str(await self.symbol),
            'trigger_price': self.trigger_price,
            'order_type': self.order_type,
            'price': self.price,
            'volume': self.volume,
            'add_timestamp': self.add_timestamp.strftime('%H:%M:%S %d-%m-%Y'),
        }


    class Meta:
        table = 'order'


    async def make_processing(self, order_id, using_db, connection_name):
        if order_id:
            existing_order = ProcessingOrder.filter(order_id=order_id).using_db(using_db)
            if not await existing_order.exists():
                raise Exception(f'Already exists {order_id}')

        symbol = await self.symbol
        async with transactions.in_transaction(connection_name) as transaction:
            p_order = ProcessingOrder()
            p_order.order_id = order_id
            p_order.symbol = symbol
            p_order.price = self.price
            p_order.order_type = self.order_type
            p_order.volume = self.volume
            p_order.status = Status.PROCESSING
            await p_order.save(using_db=transaction)
            await self.delete(using_db=transaction)
        return p_order


    async def to_str(self):
        symbol = await self.symbol
        order_type = 'BUY' if self.order_type == OrderType.BUY else 'SELL'
        return (
            f'{str(symbol)} {order_type} Trigger: {self.trigger_price} Actual: {self.price} at {str(self.add_timestamp)} Volume: {self.volume}'
        )


class Status(enum.IntEnum):
    PROCESSING = 0
    DONE = 1
    ERROR = 2
    NOT_ENOUGH_ACCOUNT_BALANCE = 3


    def __str__(self):
        if self.value == Status.PROCESSING:
            return 'PROCESSING'
        elif self.value == Status.DONE:
            return 'DONE'
        elif self.value == Status.ERROR:
            return 'ERROR'


class ProcessingOrder(Model):
    id = fields.IntField(pk=True)
    order_id = fields.CharField(max_length=32, null=True)
    symbol = fields.ForeignKeyField('db.Symbol', related_name='processing_orders')
    order_type = fields.IntEnumField(enum_type=OrderType)
    status = fields.IntEnumField(enum_type=Status)
    price = fields.FloatField()
    volume = fields.FloatField()


    class Meta:
        table = 'processing_order'


    async def to_str(self):
        symbol = await self.symbol
        order_type = 'BUY' if self.order_type == OrderType.BUY else 'SELL'
        return (
            f'{str(symbol)} {order_type} Actual: {self.price} Status: {str(self.status)} Volume: {self.volume} ID: {self.order_id}'
        )


class QuickButton(Model):
    id = fields.IntField(pk=True)
    order_type = fields.IntEnumField(enum_type=OrderType)
    volume = fields.FloatField()


    class Meta:
        table = 'quick_button'


    async def to_dict(self):
        return {
            'id': self.id,
            'order_type': self.order_type,
            'volume': self.volume,
        }
