#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging

from lxml import etree as ET
import requests

from .options import ValidatorOptions

class HttpResponse:
    def __init__(self, response):
        self.response = response
        self.status_int = self.status_code = response.status_code
        self._xml = None
        self.headers = response.headers
        self.headerlist = list(response.headers.keys())
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

    def mustcontain(self, *strings):
        for text in strings:
            self.checkIn(text, self.response.text)

    def warning(self, fmt, *args):
        logging.getLogger(__name__).warning(fmt, *args)


class RequestsHttpClient:
    """
    Implements HttpClient protocol using the requests library
    """

    def __init__(self, options: ValidatorOptions) -> None:
        self.session = requests.Session()
        self.log = options.log

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
        rv = HttpResponse(
            self.session.get(
                url,
                data=params,
                headers=headers))
        return rv
