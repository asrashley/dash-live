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

from dataclasses import dataclass, field
import datetime
from typing import Any, Union

from collections.abc import Callable
import urllib.parse

from dashlive.utils.date_time import from_isodatetime, to_iso_datetime
from dashlive.utils.objects import flatten

from .form_input_field import FormInputContext
from .types import CgiOption, CgiOptionChoice, OptionUsage

CgiChoiceType = Union[tuple[str, str], str, None]

@dataclass(slots=True, frozen=True)
class DashOption:
    usage: OptionUsage
    short_name: str
    full_name: str
    title: str
    description: str
    cgi_name: str | list[str]
    cgi_choices: tuple[CgiChoiceType, ...] | None = field(default=None)
    cgi_type: str | None = None
    input_type: str = ''
    from_string: Callable[[str], Any] = field(default_factory=lambda: DashOption.string_or_none)
    to_string: Callable[[str], Any] = field(default_factory=lambda: flatten)
    prefix: str = field(default='')
    featured: bool = False
    html: str | None = None

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
            "type": self.input_type,
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
                input['options'].append({
                    "value": val,
                    "title": title,
                    "selected": value == val
                })
        if input['type'] == '':
            if isinstance(value, bool) or self.to_string == DashOption.bool_to_string:
                input['type'] = 'bool'
            elif isinstance(value, int) or self.to_string == DashOption.int_or_none_from_string:
                input['type'] = 'number'
            elif self.cgi_choices and len(self.cgi_choices) > 1:
                input['type'] = 'select'
        if input['type'] == 'multipleSelect':
            input['type'] = 'select'
            input['multiple'] = True
            for val in value:
                for ch in input['options']:
                    if ch['value'] == val:
                        ch['selected'] = True
        elif input['type'] == 'bool':
            if value is None:
                input['type'] = 'select'
                input['options'] = [{
                    "value": '',
                    "title": '--',
                    "selected": value is None,
                }, {
                    "value": '1',
                    "title": 'True',
                    "selected": value is True,
                }, {
                    "value": '0',
                    "title": 'False',
                    "selected": value is False,
                }]
            else:
                input['type'] = 'checkbox'
                del input['options']
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

    @staticmethod
    def bool_from_string(value: str) -> bool:
        return value.lower() in {'true', '1', 'on'}

    @staticmethod
    def bool_to_string(value: bool) -> str:
        if value:
            return '1'
        return '0'

    @staticmethod
    def int_or_none_from_string(value: str) -> int | None:
        if value in {None, '', 'none'}:
            return None
        return int(value, 10)

    @staticmethod
    def float_or_none_from_string(value: str) -> float | None:
        if value in {None, '', 'none'}:
            return None
        return float(value)

    @staticmethod
    def datetime_or_none_from_string(value: str) -> float | None:
        if value in {None, '', 'none'}:
            return None
        return from_isodatetime(value)

    @staticmethod
    def datetime_or_none_to_string(value: datetime.datetime | None) -> str | None:
        if value is None:
            return None
        return to_iso_datetime(value)

    @staticmethod
    def list_without_none_from_string(value: str | None) -> list[str]:
        if value.lower() in {'', 'none'}:
            return []
        rv = []
        for item in value.split(','):
            if item.lower() not in {'', 'none'}:
                rv.append(item)
        return rv

    @staticmethod
    def string_or_none(value: str) -> str | None:
        if value.lower() in ['', 'none']:
            return None
        return value

    @staticmethod
    def unquoted_url_or_none_from_string(value: str):
        if value.lower() in ['', 'none']:
            return None
        return urllib.parse.unquote_plus(value)

    @staticmethod
    def quoted_url_or_none_to_string(value: str | None):
        if value is None:
            return None
        return urllib.parse.quote_plus(value)
