#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import json
import re

from lxml import etree as ET

from geventhttpclient.client import HTTPClient, URL

from .options import ValidatorOptions

class HttpResponse:
    CONTENT_TYPE_RE = re.compile(r'^(?P<mimetype>[\w/]+);\s*charset=(?P<charset>[\w-]+)$')

    def __init__(self, response):
        self.status_int = self.status_code = response.status_code
        self._xml = None
        self.headers = {}
        for key, value in response.headers:
            name = '-'.join([k.title() for k in key.split('-')])
            self.headers[name] = value
        self.status = response.status_message
        self._body = response.read()
        response.release()

    @property
    def xml(self):
        if self._xml is None:
            self._xml = ET.parse(self._body)
        return self._xml

    @property
    def forms(self, id):
        raise Exception("Not implemented")

    @property
    def json(self):
        js = json.load(self._body)
        return js

    def get_data(self, as_text: bool) -> bytes | str:
        if as_text:
            try:
                content_type = self.headers['content-type']
            except KeyError:
                content_type = 'text/plain; charset=utf-8'
            match = self.CONTENT_TYPE_RE.match(content_type)
            if match:
                return str(self._body, encoding=match.group('charset'))
            return str(self._body, 'utf-8')
        return self._body


class GeventHttpClient:
    """
    Implements HttpClient protocol using the geventhttpclient library
    """

    def __init__(self, options: ValidatorOptions) -> None:
        self.log = options.log

    def close(self) -> None:
        self.pool.close()

    async def get(self, url: str, headers=None, status=None, xhr=False) -> HttpResponse:
        self.log.debug('GET %s', url)
        client = HTTPClient.from_url(URL(url))
        if xhr:
            if headers is None:
                headers = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
            else:
                headers = {
                    'X-REQUESTED-WITH': 'XMLHttpRequest',
                    **headers
                }
        rv = HttpResponse(client.get(url, headers=headers))
        return rv
