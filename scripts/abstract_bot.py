from abc import ABC, abstractmethod


class AbstractBot(ABC):


    @abstractmethod
    def __init__(self, dbconfig, stock_config, sms_config, logger_name):
        pass


    @abstractmethod
    async def __aenter__(self):
        pass


    @abstractmethod
    async def __aexit__(self, *args, **kwargs):
        pass


    @abstractmethod
    async def put_in_queue(self, item):
        pass

    @abstractmethod
    async def get_from_queue(self):
        pass


    @abstractmethod
    async def add_order(self, *args, **kwargs):
        pass


    @abstractmethod
    async def damp(self, order, p_order, damping_left):
        pass


    @abstractmethod
    async def place_order(self, order, p_order, ot='limit', damp_count=None):
        pass


    @abstractmethod
    async def update_symbols(self):
        pass


    @abstractmethod
    async def get_orders_for_rate(self, rate):
        pass


    @abstractmethod
    async def handle_data(self):
        pass


    @abstractmethod
    async def send_from_queue(self):
        pass


    @abstractmethod
    async def run(self):
        pass
