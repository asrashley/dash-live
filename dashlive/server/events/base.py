#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
import datetime

from dashlive.mpeg.mp4 import EventMessageBox
from dashlive.server.options.dash_option import (
    BoolDashOption,
    CgiChoiceType,
    DashOption,
    DateTimeDashOption,
    IntOrNoneDashOption,
    StringDashOption,
    StringOrNoneDashOption,
)
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
    count: int
    duration: int
    inband: bool
    interval: int
    start: int
    timescale: int
    value: str
    version: int

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

        result: list[DashOption] = []
        for key, dflt in cls.DEFAULT_VALUES.items():
            name: str = f"{cls.PREFIX}__{key}"
            short_name: str = f"{cls.PREFIX[:3]}{key.title()[:4]}"
            cgi_choices: tuple[CgiChoiceType, ...] | None = None
            cgi_type: str | None = None
            input_type: str = 'text'
            OptionType: type[DashOption] = StringDashOption
            if dflt is None or dflt == "":
                OptionType = StringOrNoneDashOption
            elif isinstance(dflt, bool):
                OptionType = BoolDashOption
                cgi_type = '(0|1)'
                input_type = 'checkbox'
                cgi_choices = (str(dflt), str(not dflt))
            elif isinstance(dflt, int):
                OptionType = IntOrNoneDashOption
                input_type = 'number'
                cgi_type = '<int>'
                cgi_choices = tuple([str(dflt)])
            elif isinstance(dflt, (
                    datetime.date, datetime.datetime, datetime.time,
                    datetime.timedelta)):
                OptionType = DateTimeDashOption
                cgi_type = '<iso-datetime>'
                cgi_choices = tuple([str(dflt)])
            else:
                cgi_choices = tuple(str(dflt))
            opt = OptionType(
                usage=(OptionUsage.MANIFEST + OptionUsage.AUDIO + OptionUsage.VIDEO),
                short_name=short_name,
                full_name=key,
                title=f'{cls.PREFIX.title()} {key}',
                description='',
                prefix=cls.PREFIX,
                input_type=input_type,
                cgi_name=name,
                cgi_type=cgi_type,
                cgi_choices=cgi_choices)
            result.append(opt)
        return result
