import asyncio
import aiohttp
import random


import collections

Dispatcher = collections.namedtuple('Dispatcher', [
    'func', 'name'
])

class DefaultAPI:
    api_token = None
    api_url = None
    session = None


    def __init__(self, api_url, api_token=None):
        self.api_url = api_url
        self.api_token = api_token


    async def __aenter__(self):
        await self.create_session()


    async def __aexit__(self, *args, **kwargs):
        await self.session.close()


    async def create_session(self):
        headers = {}
        session = aiohttp.ClientSession(headers=headers)
        self.session = session


    async def get_headers(self, path=None, *args, **kwargs):
        return {}


    async def get_api_url(self, *args, **kwargs):
        return self.api_url


    async def get_params(self, path=None, *args, **kwargs):
        return {}


    async def process_method(
        self,
        api_url,
        method,
        path,
        params={},
        data={},
        headers={},
        json=True,
        *args, **kwargs
    ):
        headers = headers if headers else {}
        url = api_url + path
        init_headers = await self.get_headers(
            path, *args, params=params, data=data, **kwargs
        )
        init_headers.update(headers)
        headers = init_headers

        params = params if params else {}
        init_params = await self.get_params(
            path, *args, data=data, headers=headers, params=params, **kwargs
        )
        init_params.update(params)
        params = init_params

        if method == 'get':
            response = await self.session.get(url, params=params, headers=headers)
        elif method == 'post':
            if isinstance(data, dict):
                response = await self.session.post(url, json=data, params=params, headers=headers)
            else:
                response = await self.session.post(url, data=data, params=params, headers=headers)
        elif method == 'delete':
            response = await self.session.delete(url, params=params, headers=headers)
        elif method == 'put':
            response = await self.session.put(url, params=params, headers=headers)
        if json:
            response = await response.json()
        return response


    async def process_api_method(self, *args, **kwargs):
        url = await self.get_api_url(*args, **kwargs)
        return await self.process_method(url, *args, **kwargs)


    async def get(self, path, params=None, headers=None, *args, **kwargs):
        response = await self.process_api_method('get', path, params=params, headers=headers, *args, **kwargs)
        return response


    async def post(self, path, data={}, headers=None, params=None, *args, **kwargs):
        return await self.process_api_method('post', path, data=data, params=params, headers=headers, *args, **kwargs)


    async def delete(self, path, data, headers=None, params=None, *args, **kwargs):
        return await self.process_api_method('delete', path, data=data, params=params, headers=headers, *args, **kwargs)


    async def connect_ws(self):
        raise NotImplementedError()

class WebSocketAPI:
    class WSClosed(Exception):
        pass

    _dispatchers = None

    def __init__(self, url, api, connection_num=1):
        self._url = url
        self._api = api
        self._dispatchers = []
        self._logger = api._logger
        self._connection_num = connection_num
        self._headers = {}


    async def __aenter__(self):
        self.ws_pool = []
        async def add_ws(self):
            self.ws_pool.append(await self.connect_ws(self._headers))
        add_tasks = [add_ws(self) for i in range(self._connection_num)]
        await asyncio.gather(*add_tasks)


    async def __aexit__(self, *args, **kwargs):
        for ws in self.ws_pool:
            await ws.close()


    async def connect_ws(self, headers):
        return await self._session.ws_connect(self._url, headers=headers)


    @property
    def _api_token(self):
        return self._api.api_token


    @property
    def _secret(self):
        return self._api._secret


    @property
    def _session(self):
        return self._api.session


    def is_closed(self, index):
        return self.ws_pool[index].closed


    def add_dispatcher(self, name=None):
        def decorator(func):
            dispatcher = Dispatcher(
                func=func, name=name
            )
            self._dispatchers.append(dispatcher)
            return func
        return decorator


    def get_random_ws_index(self):
        return random.choice(list(range(len(self.ws_pool))))


    async def send_json(self, index, data):
        await self.ws_pool[index].send_json(data)


    async def receive_json(self, index):
        response = await self.ws_pool[index].receive_json()
        return response


    async def handle_firstly(self, message, index):
        pass


    async def dispatch(self, message, index):
        data = message.json()
        asyncio.create_task(self.handle_firstly(data, index))
        for dispatcher in self._dispatchers:
            asyncio.create_task(dispatcher.func(data))


    async def handle_one_ws(self, index):
        while True:
            message = await self.ws_pool[index].receive()
            if message.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR
            ):
                exc = self.WSClosed(f'Dispatch: WebSocket apparently closed\n{message}')
                raise exc
            elif message.type != aiohttp.WSMsgType.TEXT:
                exc = ValueError(f'Non-text message\n{message}')
                raise exc
            await self.dispatch(message, index)


    async def handle_messages(self):
        handlers = [self.handle_one_ws(i) for i in range(self._connection_num)]
        handling_tasks = asyncio.gather(*handlers)

        try:
            await handling_tasks
        except Exception as exc:
            handling_tasks.cancel()
            raise exc
