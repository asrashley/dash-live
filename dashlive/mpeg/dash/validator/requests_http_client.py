#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from concurrent.futures import ThreadPoolExecutor
import logging

from lxml import etree as ET
import requests

from .concurrent_pool import ConcurrentWorkerPool
from .options import ValidatorOptions

class HttpResponse:
    def __init__(self, response):
        self.response = response
        self.status_int = self.status_code = response.status_code
        self._xml = None
        self.headers = {}
        for key, value in response.headers.items():
            name = '-'.join([k.title() for k in key.split('-')])
            self.headers[name] = value
        if response.ok:
            self.status = 'OK'
        else:
            self.status = response.reason

    @property
    def xml(self):
        if self._xml is None:
            self._xml = ET.fromstring(self.response.text)
        return self._xml

    @property
    def forms(self, id):
        raise Exception("Not implemented")

    @property
    def json(self):
        return self.response.json

    @property
    def body(self):
        return self.response.content

    def get_data(self, as_text: bool) -> bytes | str:
        if as_text:
            return self.response.text
        return self.response.content


class RequestsHttpClient:
    """
    Implements HttpClient protocol using the requests library
    """

    def __init__(self, options: ValidatorOptions) -> None:
        self.session = requests.Session()
        self.log = options.log
        self.pool = options.pool
        if self.pool is None:
            self.pool = ConcurrentWorkerPool(ThreadPoolExecutor())

    async def get(self, url, headers=None, params=None, status=None, xhr=False) -> HttpResponse:
        try:
            self.log.debug('GET %s', url)
        except AttributeError:
            print('GET %s' % (url))
        if xhr:
            if headers is None:
                headers = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
            else:
                h = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
                h.update(headers)
                headers = h

        def do_get():
            return self.session.get(url, data=params, headers=headers)

        async with self.pool.group() as tg:
            resp = tg.submit(do_get)
        return HttpResponse(resp.result())
