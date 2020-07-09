import asyncio
import aiohttp

class DefaultAPI:
    api_token = None
    api_url = None
    session = None

    def __init__(self, api_url, api_token):
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

    async def get_headers(self, path=None):
        return {}

    async def get_api_url(self, *args, **kwargs):
        return self.api_url

    async def process_method(self, api_url, method, path, params=None, data=None, headers=None, *args, **kwargs):
        url = api_url + path
        if not headers:
            headers = {}
        init_headers = await self.get_headers(path)
        init_headers.update(headers)
        headers = init_headers

        if method == 'get':
            response = await self.session.get(url, params=params, headers=headers)
        elif method == 'post':
            response = await self.session.post(url, data=data, params=params, headers=headers)
        elif method == 'delete':
            response = await self.session.delete(url, params=params, headers=headers)
        response = await response.json()
        return response

    async def process_api_method(self, *args, **kwargs):
        url = await self.get_api_url(*args, **kwargs)
        return await self.process_method(url, *args, **kwargs)

    async def get(self, path, params=None, headers=None, *args, **kwargs):
        response = await self.process_api_method('get', path, params=params, headers=headers, *args, **kwargs)
        return response

    async def post(self, path, data, headers=None):
        return await self.process_api_method('post', path, data=data, params=params, headers=headers, *args, **kwargs)

    async def delete(self, path, data, headers=None):
        return await self.process_api_method('delete', path, data=data, params=params, headers=headers, *args, **kwargs)

# class WebSocketAPI(self):
#     def __init__(self, )
