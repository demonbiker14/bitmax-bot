import asyncio
import aiohttp

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
            # print(url, data, params, headers, sep='\n')
            response = await self.session.post(url, json=data, params=params, headers=headers)
        elif method == 'delete':
            response = await self.session.delete(url, params=params, headers=headers)
        if json:
            response = await response.json()
        return response


    async def process_api_method(self, *args, **kwargs):
        url = await self.get_api_url(*args, **kwargs)
        return await self.process_method(url, *args, **kwargs)


    async def get(self, path, params=None, headers=None, *args, **kwargs):
        response = await self.process_api_method('get', path, params=params, headers=headers, *args, **kwargs)
        return response


    async def post(self, path, data, headers=None, params=None, *args, **kwargs):
        return await self.process_api_method('post', path, data=data, params=params, headers=headers, *args, **kwargs)


    async def delete(self, path, data, headers=None, *args, **kwargs):
        return await self.process_api_method('delete', path, data=data, params=params, headers=headers, *args, **kwargs)

class WebSocketAPI:
    class WSClosed(Exception):
        pass

    _dispatchers = None

    def __init__(self, url, api):
        self._url = url
        self._api = api
        self._dispatchers = []
        self._logger = api._logger


    @property
    def _api_token(self):
        return self._api.api_token


    @property
    def _secret(self):
        return self._api._secret


    @property
    def _session(self):
        return self._api.session


    def is_closed(self):
        return self._ws_connection.closed


    def add_dispatcher(self, name=None):
        def decorator(func):
            dispatcher = Dispatcher(
                func=func, name=name
            )
            self._dispatchers.append(dispatcher)
            return func
        return decorator


    async def connect_ws(self, headers):
        self._ws_connection = await self._session.ws_connect(self._url, headers=headers)


    async def __aenter__(self):
        await self.connect_ws(headers)


    async def __aexit__(self, *args, **kwargs):
        await self._ws_connection.close()


    async def send_json(self, data):
        await self._ws_connection.send_json(data)


    async def receive_json(self):
        response = await self._ws_connection.receive_json()
        return response


    async def handle_firstly(self, message):
        pass

    async def dispatch(self, message):
        try:
            data = message.json()
            asyncio.create_task(self.handle_firstly(data))
            for dispatcher in self._dispatchers:
                asyncio.create_task(dispatcher.func(data))
        except ValueError as exc:
            self._logger.exception(exc)
            raise exc

    async def handle_messages(self, close_exc=True):
        while True:
            try:
                if self.is_closed():
                    raise self.WSClosed('Handling: WebSocket apparently closed')
                message = await self._ws_connection.receive()
                if message.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    exc = self.WSClosed(f'Dispatch: WebSocket apparently closed\n{message}')
                    self._logger.error(message)
                    raise exc
                elif message.type != aiohttp.WSMsgType.TEXT:
                    exc = ValueError(f'Non-text message\n{message}')
                    self._logger.exception(exc)
                    raise exc
                await self.dispatch(message)
            except self.WSClosed as exc:
                self._logger.exception(exc)
                if close_exc:
                    raise exc
                await self.__aenter__()
                continue
            except Exception as exc:
                self._logger.exception(exc)
                raise exc
