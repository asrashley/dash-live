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
from typing import Optional, Union, NamedTuple

class OptionChoice(NamedTuple):
    description: str
    value: Union[str, bool, int]


@dataclass(frozen=True, slots=True)
class CgiOption:
    """
    Container class for one CGI option
    """
    name: str
    title: str
    options: list[OptionChoice]
    html: str
    syntax: str
    usage: set[str]
    hidden: bool = False

    def toJSON(self):
        return {
            'name': self.name,
            'title': self.title,
            'options': self.options,
            'hidden': self.hidden,
        }

@dataclass(slots=True, frozen=True)
class DashOption:
    name: str
    title: str
    description: str
    cgi_name: Union[str, list[str]]
    cgi_choices: list[Union[str, bool, int, tuple[str, str]]] = field(default_factory=list)
    cgi_type: Optional[str] = None
    hidden: bool = True
    html: Optional[str] = None
    usage: set[str] = field(default_factory=lambda: {'manifest', 'video', 'audio'})

    def get_cgi_options(self) -> list[CgiOption]:
        """
        Convert this option into a list of CGI options
        """
        result: list[CgiOption] = []
        if isinstance(self.cgi_name, list):
            names = self.cgi_name
        else:
            names = [self.cgi_name]
        for name in names:
            ocs = []
            for choice in self.cgi_choices:
                if choice is None or choice == '':
                    continue
                if isinstance(choice, tuple):
                    description, value = choice
                    if value is None or value == '':
                        continue
                    ocs.append(OptionChoice(
                        description=description,
                        value=f'{name}={value}'))
                else:
                    ocs.append(OptionChoice(
                        description=str(choice),
                        value=f'{name}={choice}'))
            if not ocs:
                continue
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
            result.append(CgiOption(
                name=name,
                title=self.title,
                hidden=self.hidden,
                html=html,
                syntax=syntax,
                options=ocs,
                usage=self.usage))
        return result
