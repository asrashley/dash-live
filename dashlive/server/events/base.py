#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
import datetime
from typing import Any

from dashlive.mpeg.mp4 import EventMessageBox
from dashlive.server.options.dash_option import DashOption
from dashlive.server.options.types import OptionUsage
from dashlive.utils.object_with_fields import ObjectWithFields

class EventBase(ObjectWithFields):
    DEFAULT_VALUES = {
        'count': 0,
        'duration': 200,
        'inband': True,
        'interval': 1000,
        'start': 0,
        'timescale': 100,
        'value': '0',
        'version': 0,
    }

    @abstractmethod
    def create_manifest_context(self, context: dict) -> dict:
        ...

    @abstractmethod
    def create_emsg_boxes(self, **kwargs) -> list[EventMessageBox]:
        ...

    @classmethod
    def get_dash_options(cls) -> list[DashOption]:
        """
        Get a list of all DASH options for this event
        """
        def default_to_string(val: Any) -> str:
            return str(val)

        result: list[DashOption] = []
        for key, dflt in cls.DEFAULT_VALUES.items():
            name = f'{cls.PREFIX}_{key}'
            short_name = cls.PREFIX[:3] + key.title()[:4]
            cgi_choices = None
            to_string = default_to_string
            if isinstance(dflt, bool):
                from_string = DashOption.bool_from_string
                to_string = DashOption.bool_to_string
                cgi_type = '(0|1)'
                cgi_choices = (str(dflt), str(not dflt))
            elif isinstance(dflt, int):
                from_string = DashOption.int_or_none_from_string
                cgi_type = '<int>'
                cgi_choices = tuple([str(dflt)])
            elif isinstance(dflt, (
                    datetime.date, datetime.datetime, datetime.time,
                    datetime.timedelta)):
                from_string = DashOption.datetime_or_none_from_string
                to_string = DashOption.datetime_or_none_to_string
                cgi_type = '<iso-datetime>'
                cgi_choices = tuple([str(dflt)])
            else:
                from_string = default_to_string
                cgi_type = None
                if dflt is not None:
                    cgi_choices = tuple(str(dflt))
            opt = DashOption(
                usage=(OptionUsage.MANIFEST + OptionUsage.AUDIO + OptionUsage.VIDEO),
                short_name=short_name,
                full_name=key,
                title=f'{cls.PREFIX.title()} {key}',
                description='',
                prefix=cls.PREFIX,
                cgi_name=name,
                cgi_type=cgi_type,
                cgi_choices=cgi_choices,
                from_string=from_string,
                to_string=to_string)
            result.append(opt)
        return result
