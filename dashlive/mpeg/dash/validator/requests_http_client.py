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
from werkzeug.utils import cached_property

from .concurrent_pool import ConcurrentWorkerPool
from .options import ValidatorOptions
from .pool import WorkerPool

class HttpResponse:
    headers: dict[str, str]
    status: str
    status_int: int
    status_code: int
    response: requests.Response
    _pos: int
    _xml: ET.Element | None

    def __init__(self, response: requests.Response) -> None:
        self.response = response
        self.status_int = self.status_code = response.status_code
        self._xml = None
        self.headers = {}
        for key, value in response.headers.items():
            name: str = '-'.join([k.title() for k in key.split('-')])
            self.headers[name] = value
        if response.ok:
            self.status = 'OK'
        else:
            self.status = response.reason
        self._pos = 0

    @cached_property
    def xml(self) -> ET.Element:
        if self._xml is None:
            self._xml = ET.fromstring(self.response.text)
        return self._xml

    @property
    def json(self) -> dict:
        return self.response.json()

    @property
    def body(self) -> bytes:
        return self.response.content

    def get_data(self, as_text: bool) -> bytes | str:
        if as_text:
            return self.response.text
        self.response.raise_for_status()
        return self.response.content

    def tell(self) -> int:
        return self._pos

    def read(self, length: int) -> bytes:
        rv: bytes = self.response.raw.read(length)
        self._pos += len(rv)
        return rv


class RequestsHttpClient:
    """
    Implements HttpClient protocol using the requests library
    """

    log: logging.Logger
    pool: WorkerPool

    def __init__(self, options: ValidatorOptions) -> None:
        self.session = requests.Session()
        if options.log is None:
            self.log = logging.getLogger()
        else:
            self.log = options.log
        if options.pool is None:
            self.pool = ConcurrentWorkerPool(ThreadPoolExecutor())
        else:
            self.pool = options.pool

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
