#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from concurrent.futures import ThreadPoolExecutor

from lxml import etree as ET
import requests

from .concurrent_pool import ConcurrentWorkerPool
from .options import ValidatorOptions

class HttpResponse:
    headers: dict
    status_int: int
    _pos: int

    def __init__(self, response) -> None:
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
        self._pos = 0

    @property
    def xml(self):
        if self._xml is None:
            self._xml = ET.fromstring(self.response.text)
        return self._xml

    @property
    def forms(self, id) -> dict:
        raise Exception("Not implemented")

    @property
    def json(self) -> dict:
        return self.response.json

    @property
    def body(self) -> bytes:
        return self.response.content

    def get_data(self, as_text: bool) -> bytes | str:
        if as_text:
            return self.response.text
        return self.response.content

    def tell(self) -> int:
        return self._pos

    def read(self, length: int) -> bytes:
        rv = self.response.raw.read(length)
        self._pos += len(rv)
        return rv


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

    async def head(self, url, headers=None, params=None, status=None, xhr=False) -> HttpResponse:
        def do_head():
            return self.session.head(url, data=params, headers=headers)

        if xhr:
            headers = self.add_xhr_headers(headers)

        async with self.pool.group() as tg:
            resp = tg.submit(do_head)
        return HttpResponse(resp.result())

    async def get(self,
                  url: str,
                  headers: dict | None = None,
                  params: dict | None = None,
                  status: int | None = None,
                  xhr: bool = False,
                  stream: bool = False) -> HttpResponse:
        def do_get():
            return self.session.get(url, data=params, headers=headers, stream=stream)

        try:
            self.log.debug('GET %s', url)
        except AttributeError as err:
            self.log.error('GET %s: attribute error:', url, err)
        if xhr:
            headers = self.add_xhr_headers(headers)
        async with self.pool.group() as tg:
            resp = tg.submit(do_get)
        return HttpResponse(resp.result())

    def add_xhr_headers(self, headers: dict | None = None) -> dict:
        if headers is None:
            return {'X-REQUESTED-WITH': 'XMLHttpRequest'}
        return {
            'X-REQUESTED-WITH': 'XMLHttpRequest',
            **headers
        }
