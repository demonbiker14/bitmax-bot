from .default_api import DefaultAPI
from config import config

import asyncio
import aiohttp

class SMSApi(DefaultAPI):
    api_url = 'https://smsc.ru/sys/send.php'
    def __init__(self, login, password):
        self._login = login
        self._password = password

    async def send_sms(self, phones, message):
        response = await self.get('', params={
            'phones': ','.join(phones),
            'mes': message,
            'cost': '0'
        })
        response = response
        return response

    async def process_api_method(self, *args, **kwargs):
        params = kwargs.get('params', {})
        kwargs['params'].update({
            'login': self._login,
            'psw': self._password,
            'fmt': 3,
        })
        url = await self.get_api_url(*args, **kwargs)
        return await self.process_method(url, *args, **kwargs)

    async def get_sms_cost(self, phones, message):
        response = await self.get('', params={
            'phones': ','.join(phones),
            'mes': message,
            'cost': '1'
        })
        response = response
        return response

if __name__ == '__main__':
    async def main():
        api = SMSApi(config['SMS']['LOGIN'], config['SMS']['PASSWORD'])
        async with api:
            print(await api.send_sms([config['SMS']['PHONE']], 'Your code 1234'))
    asyncio.run(main())
