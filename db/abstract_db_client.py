from abc import ABC, abstractmethod


# noinspection PyUnusedLocal
class AbstractDBClient(ABC):
    class NoSymbolExists(Exception):
        pass


    class NoOrderExists(Exception):
        pass


    class NoButtonExists(Exception):
        pass


    @abstractmethod
    def __init__(self, using_db=None):
        pass

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(self, *args, **kwargs):
        pass

    @abstractmethod
    def make_symbol(self, first, second, name=None, short_description=None):
        pass

    @abstractmethod
    async def list_buttons(self):
        pass

    @abstractmethod
    async def add_symbols(self, values):
        pass

    @abstractmethod
    async def add_order(self, symbol, *args, **kwargs):
        pass

    @abstractmethod
    async def add_button(self, order_type, volume):
        pass

    @abstractmethod
    async def delete_symbol(self, pk):
        pass

    @abstractmethod
    async def delete_order(self, pk):
        pass

    @abstractmethod
    async def delete_button(self, pk):
        pass

    @abstractmethod
    async def list_symbols(self):
        pass

    @abstractmethod
    async def list_orders(self):
        pass

    @abstractmethod
    async def list_processing_orders(self):
        pass

    @abstractmethod
    async def get_symbol(self, first, second):
        pass
