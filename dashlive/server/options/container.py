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

from typing import AbstractSet, Any, Optional

from dashlive.utils.json_object import JsonObject
from dashlive.utils.object_with_fields import ObjectWithFields
from dashlive.utils.objects import dict_to_cgi_params

from .dash_option import DashOption
from .types import OptionUsage

class OptionsContainer(ObjectWithFields):
    OBJECT_FIELDS = {}

    def __init__(self,
                 parameter_map: dict[str, DashOption] = None,
                 defaults: Optional["OptionsContainer"] = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._parameter_map = parameter_map
        self._defaults = defaults

    @property
    def encrypted(self) -> bool:
        try:
            return len(self.drmSelection) > 0
        except AttributeError:
            return False

    def clone(self, **kwargs) -> "OptionsContainer":
        args = {
            'parameter_map': self._parameter_map,
        }
        for key in self._fields:
            if key[0] == '_':
                continue
            ours = getattr(self, key)
            value = kwargs.get(key, ours)
            if isinstance(value, OptionsContainer) or isinstance(ours, OptionsContainer):
                if ours is None:
                    ours = {}
                elif isinstance(ours, OptionsContainer):
                    ours = ours.toJSON()
                if value is None:
                    theirs = {}
                elif isinstance(value, OptionsContainer):
                    theirs = value.toJSON()
                else:
                    theirs = value
                value = {
                    **ours,
                    **theirs,
                }
                dflt = None
                if self._defaults is not None:
                    dflt = self._defaults[key]
                value = self.__class__(
                    parameter_map=self._parameter_map, defaults=dflt, **value)
            args[key] = value
        for key, value in kwargs.items():
            if key in self._fields or key[0] == '_':
                continue
            args[key] = value
        if 'defaults' not in args:
            args['defaults'] = self._defaults
        return OptionsContainer(**args)

    def convert_sub_options(self,
                            destination: dict[str, str],
                            prefix: str,
                            sub_opts: dict[str, Any],
                            use: OptionUsage | None,
                            exclude: AbstractSet | None) -> None:
        defaults = ObjectWithFields()
        if self._defaults is not None and prefix in self._defaults._fields:
            defaults = self._defaults[prefix]
        for key, value in sub_opts.items():
            name = f'{prefix}.{key}'
            opt = self._parameter_map[name]
            if use is not None and (opt.usage & use) == 0:
                continue
            if name in exclude:
                continue
            try:
                dft_val = defaults[key]
                if value == dft_val:
                    continue
            except KeyError:
                pass
            destination[opt.cgi_name] = opt.to_string(value)

    def generate_cgi_parameters(self,
                                destination: dict[str, str] | None = None,
                                use: OptionUsage | None = None,
                                exclude: AbstractSet | None = None) -> dict[str, str]:
        """
        Produces a dictionary of CGI parameters that represent these options.
        Any option that matches its default is excluded.
        """
        return self.generate_parameters_dict(
            'cgi_name', destination=destination, use=use, exclude=exclude)

    def generate_parameters_dict(self,
                                 attr_name: str,
                                 destination: dict[str, str] | None = None,
                                 use: OptionUsage | None = None,
                                 exclude: AbstractSet | None = None) -> dict[str, str]:
        """
        Produces a dictionary of parameters that represent these options.
        Any option that matches its default is excluded.
        """
        if exclude is None:
            exclude = {'encrypted', 'mode'}
        if destination is None:
            destination: dict[str, str] = {}
        for key, value in self.items():
            if isinstance(value, OptionsContainer):
                self.convert_sub_options(destination, key, value, use, exclude)
                continue
            if key in exclude:
                continue
            if self._defaults is not None:
                if key in self._defaults._fields:
                    dft_val = getattr(self._defaults, key)
                    if value == dft_val:
                        continue
            opt = self._parameter_map[key]
            if use is not None and (opt.usage & use) == 0:
                continue
            destination[getattr(opt, attr_name)] = opt.to_string(value)
        return destination

    def remove_default_values(self, defaults: Optional["OptionsContainer"] = None) -> JsonObject:
        if defaults is None:
            defaults = self._defaults
        if defaults is None:
            return self.toJSON()
        result: JsonObject = {}
        for key, value in self.items():
            try:
                dflt = defaults[key]
            except KeyError:
                continue
            if isinstance(value, OptionsContainer):
                sub_result = {}
                for k, v in value.items():
                    if k not in dflt:
                        continue
                    d = dflt[k]
                    if d != v:
                        sub_result[k] = v
                if sub_result:
                    result[key] = sub_result
                continue
            if value != dflt:
                result[key] = value
        return result

    def generate_cgi_parameters_string(self,
                                       use: OptionUsage | None = None,
                                       exclude: AbstractSet | None = None) -> str:
        return dict_to_cgi_params(self.generate_cgi_parameters(
            use=use, exclude=exclude))

    def remove_unused_parameters(self, mode: str, encrypted: bool | None = None,
                                 use: OptionUsage | None = None) -> None:
        if encrypted is None:
            encrypted = self.encrypted
        todo: list[str] = []
        if mode != 'live':
            todo += {'availabilityStartTime', 'minimumUpdatePeriod',
                     'timeShiftBufferDepth', 'utcMethod', 'utcValue'}
        if encrypted:
            drms = {item[0] for item in self.drmSelection}
            if 'playready' not in drms:
                todo += {'playreadyLicenseUrl', 'playreadyPiff', 'playreadyVersion'}
            if 'marlin' not in drms:
                todo.append('marlinLicenseUrl')
        else:
            todo += {'marlinLicenseUrl', 'playreadyLicenseUrl', 'playreadyPiff',
                     'playreadyVersion'}
        if use is not None:
            fields = set(self._fields)
            fields.discard(set(todo))
            for name in fields:
                try:
                    opt = self._parameter_map[name]
                except KeyError:
                    continue
                if (opt.usage & use) == 0:
                    todo.append(name)
        for name in todo:
            self.remove_field(name)

    def generate_input_fields(self, field_choices: dict,
                              exclude: AbstractSet | None = None) -> list[JsonObject]:
        fields = []
        if exclude is None:
            exclude = set()
        for key, value in self.items():
            if key in exclude:
                continue
            if isinstance(value, OptionsContainer):
                for ok, ov in value.items():
                    name = f'{key}.{ok}'
                    if name in exclude:
                        continue
                    op = self._parameter_map[name]
                    fields.append(
                        op.input_field(ov, field_choices))
                continue
            try:
                opt = self._parameter_map[key]
            except KeyError:
                continue
            input = opt.input_field(value, field_choices)
            fields.append(input)
        fields.sort(key=lambda item: item['title'])
        return fields


# manually adding the event types avoids a circular import loop
OptionsContainer.OBJECT_FIELDS['ping'] = OptionsContainer
OptionsContainer.OBJECT_FIELDS['scte35'] = OptionsContainer
