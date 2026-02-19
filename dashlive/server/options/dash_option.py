#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar, Union, cast

import urllib.parse

from dashlive.utils.date_time import from_isodatetime, to_iso_datetime, toIsoDuration

from .form_input_field import FieldOption, FormInputContext
from .types import CgiOption, CgiOptionChoice, OptionUsage

CgiChoiceType = Union[tuple[str, str], str, None]
T = TypeVar('T')

@dataclass(slots=True, frozen=True)
class DashOption(Generic[T]):
    usage: OptionUsage
    short_name: str
    full_name: str
    title: str
    description: str
    cgi_name: str
    cgi_choices: tuple[CgiChoiceType, ...] | None = field(default=None)
    cgi_type: str | None = None
    input_type: str = ''
    prefix: str = field(default='')
    featured: bool = False
    html: str | None = None

    @abstractmethod
    def from_string(self, value: str) -> T:
        raise NotImplementedError(f"{__class__}.from_string() not implemented")

    @abstractmethod
    def to_string(self, value: T) -> str:
        raise NotImplementedError(f"{__class__}.to_string() not implemented")

    def html_input_type(self) -> str:
        return self.input_type

    def python_type_hint(self) -> str | None:
        return None

    def default_value(self) -> T | None:
        if self.cgi_choices is None:
            return None
        if len(self.cgi_choices) == 0:
            return None
        first = self.cgi_choices[0]
        if isinstance(first, tuple):
            if first[1] is None:
                return None
            return self.from_string(first[1])
        if isinstance(first, str):
            return self.from_string(first)
        return cast(T, first)

    def get_cgi_option(self, omit_empty: bool = True) -> CgiOption | None:
        """
        Get a description of the CGI values that are allowed for this option
        """
        if self.cgi_choices is None:
            return None
        ocs: list[CgiOptionChoice] = []
        for choice in self.cgi_choices:
            if omit_empty and choice in {None, '', 'none'}:
                continue
            if isinstance(choice, tuple):
                description, value = choice
            else:
                description = str(choice)
                value = choice
            if omit_empty and value in {None, '', 'none'}:
                continue
            if value is None:
                value = 'none'
            ocs.append(CgiOptionChoice(
                description=description,
                value=f'{self.cgi_name}={value}'))
        if self.html:
            html = self.html
        else:
            html = f'<p>{self.description}</p>'
        if self.cgi_type:
            syntax = self.cgi_type
        else:
            cgi_choices = []
            for ch in self.cgi_choices:
                if ch is None:
                    continue
                if isinstance(ch, tuple):
                    if ch[1] is not None:
                        cgi_choices.append(f'{ch[1]}')
                else:
                    cgi_choices.append(f'{ch}')
            syntax = '|'.join(cgi_choices)
            syntax = f'({syntax})'
        return CgiOption(
            name=self.cgi_name,
            title=self.title,
            featured=self.featured,
            html=html,
            syntax=syntax,
            options=ocs,
            usage=OptionUsage.to_string_set(self.usage))

    def input_field(self, value: Any, field_choices: dict) -> FormInputContext:
        input: FormInputContext = {
            "name": self.cgi_name,
            "title": self.title,
            "value": value,
            "text": self.description,
            "type": self.html_input_type(),
            "prefix": self.prefix,
            "fullName": self.full_name,
            "shortName": self.short_name,
            "featured": self.featured,
        }
        if self.cgi_choices and len(self.cgi_choices) > 1 and self.input_type != 'checkbox':
            input['options'] = []
            for ch in self.cgi_choices:
                if isinstance(ch, tuple):
                    title, val = ch
                else:
                    val = title = ch
                if title is None:
                    title = '--'
                if val is None:
                    val = ''
                input['options'].append(FieldOption(
                    value=val,
                    title=title,
                    selected=(value == val)
                ))
        if input['type'] == '':
            if isinstance(value, bool):
                input['type'] = 'bool'
            elif isinstance(value, (int, float)):
                input['type'] = 'number'
            elif self.cgi_choices and len(self.cgi_choices) > 1:
                input['type'] = 'select'
        if input['type'] == 'multipleSelect':
            input['type'] = 'select'
            input['multiple'] = True
            options: list[FieldOption] = input.get('options', [])
            for val in cast(list, value):
                for idx, ch in enumerate(options):  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    if ch.value == val:
                        options[idx] = FieldOption(
                            value=ch.value, title=ch.title, selected=True)
            input['options'] = options
        elif input['type'] == 'bool':
            if value is None:
                input['type'] = 'select'
                input['options'] = [
                    FieldOption(value='', title='--', selected=(value is None)),
                    FieldOption(value='1', title='True', selected=(value is True)),
                    FieldOption(value='0', title='False', selected=(value is False)),
                ]
            else:
                input['type'] = 'checkbox'
                try:
                    del input['options']
                except KeyError:
                    pass
        elif input['type'] == 'numberList':
            input['datalist_type'] = 'number'
            input['type'] = 'datalist'
        elif input['type'] == 'textList':
            input['datalist_type'] = 'text'
            input['type'] = 'datalist'
        elif input['type'] in field_choices:
            input['options'] = field_choices[input['type']]
            input['type'] = 'select'
        return input

    def replace(self, **kwargs) -> "DashOption":
        new_kwargs = asdict(self)
        new_kwargs.update(kwargs)
        return DashOption(**new_kwargs)


class BoolDashOption(DashOption[bool]):
    def from_string(self, value: str) -> bool:
        return value.lower() in {'true', '1', 'on'}

    def to_string(self, value: bool) -> str:
        if value:
            return '1'
        return '0'

    def html_input_type(self) -> str:
        return 'bool'

    def python_type_hint(self) -> str | None:
        return 'bool'


class IntOrNoneDashOption(DashOption[int | None]):
    def from_string(self, value: str) -> int | None:
        if value == '' or value.lower() == 'none':
            return None
        return int(value, 10)

    def to_string(self, value: int | None) -> str:
        if value is None:
            return ''
        return f"{value:d}"

    def html_input_type(self) -> str:
        return 'number'

    def python_type_hint(self) -> str | None:
        if self.default_value() is not None:
            return 'int'
        return 'int | None'

class FloatOrNoneDashOption(DashOption[float | None]):
    def from_string(self, value: str) -> float | None:
        if value in {None, '', 'none'}:
            return None
        return float(value)

    def to_string(self, value: float | None) -> str:
        if value is None:
            return ''
        return f'{value:f}'

    def python_type_hint(self) -> str | None:
        return 'float | None'


class StringDashOption(DashOption[str]):
    def from_string(self, value: str) -> str:
        if value.lower() in ['', 'none']:
            return ''
        return value

    def to_string(self, value: str) -> str:
        return value

    def python_type_hint(self) -> str | None:
        return 'str'


class StringOrNoneDashOption(DashOption[str | None]):
    def from_string(self, value: str) -> str | None:
        if value.lower() in ['', 'none']:
            return None
        return value

    def to_string(self, value: str | None) -> str:
        if value is None:
            return ''
        return value

    def python_type_hint(self) -> str | None:
        return 'str | None'


class UrlOrNoneDashOption(DashOption[str | None]):
    def from_string(self, value: str) -> str | None:
        if value.lower() in ['', 'none']:
            return None
        return urllib.parse.unquote_plus(value)

    def to_string(self, value: str | None) -> str:
        if value is None:
            return ''
        return urllib.parse.quote_plus(value)

    def python_type_hint(self) -> str | None:
        return 'str | None'

class StringListDashOption(DashOption[list[str]]):
    def from_string(self, value: str) -> list[str]:
        if value.lower() in {'', 'none'}:
            return []
        rv = []
        for item in value.split(','):
            if item.lower() not in {'', 'none'}:
                rv.append(item)
        return rv

    def to_string(self, value: list[str]) -> str:
        return ','.join(value)

    def python_type_hint(self) -> str | None:
        return 'list[str]'

    def default_value(self) -> list[str] | None:
        if not self.cgi_choices:
            return []
        default: str | None = cast(str | None, self.cgi_choices[0])
        if default is None:
            return []
        return [default]

class DateTimeDashOption(DashOption[datetime | timedelta | None]):
    def from_string(self, value: str) -> datetime | timedelta | None:
        if value in {None, '', 'none'}:
            return None
        return from_isodatetime(value)

    def to_string(self, value: datetime | timedelta | None) -> str:
        if value is None:
            return ''
        if isinstance(value, timedelta):
            return toIsoDuration(value)
        return to_iso_datetime(value)

    def python_type_hint(self) -> str | None:
        return 'datetime.datetime | datetime.timedelta | None'
