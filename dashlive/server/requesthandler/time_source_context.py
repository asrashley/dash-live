#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import datetime
from typing import ClassVar
import urllib.parse

import flask  # type: ignore

from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.utc_time_options import NTP_POOLS
from dashlive.utils.date_time import to_iso_datetime
from dashlive.utils.objects import dict_to_cgi_params

from .cgi_parameter_collection import CgiParameterCollection

class TimeSourceContext:
    DEFAULT_NTP_POOL: ClassVar[str] = 'google'

    method: str
    schemeIdUri: str
    value: str | None

    def __init__(self,
                 options: OptionsContainer,
                 cgi_params: CgiParameterCollection,
                 now: datetime.datetime) -> None:
        self.method = options.utcMethod
        self.value = None
        if self.method == 'direct':
            self.schemeIdUri = 'urn:mpeg:dash:utc:direct:2014'
            self.value = to_iso_datetime(now)
        elif self.method == 'head':
            self.schemeIdUri = 'urn:mpeg:dash:utc:http-head:2014'
        elif self.method == 'http-ntp':
            self.schemeIdUri = 'urn:mpeg:dash:utc:http-ntp:2014'
        elif self.method == 'iso':
            self.schemeIdUri = 'urn:mpeg:dash:utc:http-iso:2014'
        elif self.method in {'ntp', 'sntp'}:
            self.schemeIdUri = f'urn:mpeg:dash:utc:{self.method}:2014'
            servers: list[str] = [TimeSourceContext.DEFAULT_NTP_POOL]
            if options.ntpSources:
                servers = options.ntpSources
            if len(servers) == 1 and servers[0] in NTP_POOLS:
                servers = NTP_POOLS[servers[0]]
            self.value = ' '.join(servers)
        elif self.method == 'xsd':
            self.schemeIdUri = 'urn:mpeg:dash:utc:http-xsdate:2014'
        else:
            raise ValueError(fr'Unknown time method: "{self.method}"')

        if self.value is None:
            self.value = urllib.parse.urljoin(
                flask.request.host_url,
                flask.url_for('time', method=self.method))
            self.value += dict_to_cgi_params(cgi_params.time)
