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

import logging
from typing import AbstractSet, ClassVar, Optional

from .audio_options import audio_options
from .container import OptionsContainer
from .dash_option import CgiOption, DashOption
from .drm_options import drm_options
from .event_options import event_options
from .manifest_options import manifest_options
from .player_options import player_options
from .text_options import text_options
from .types import OptionUsage
from .video_options import video_options
from .utc_time_options import time_options

class OptionsRepository:
    _cgi_map: ClassVar[Optional[dict[str, DashOption]]] = None
    _param_map: ClassVar[Optional[dict[str, DashOption]]] = None
    _global_default_options: ClassVar[Optional[OptionsContainer]] = None
    _all_options: ClassVar[list[DashOption]] = (
        audio_options +
        drm_options +
        event_options +
        manifest_options +
        player_options +
        video_options +
        text_options +
        time_options)

    @classmethod
    def get_dash_options(cls,
                         use: Optional[OptionUsage] = None,
                         only: Optional[AbstractSet[str]] = None,
                         exclude: Optional[AbstractSet[str]] = None) -> list[DashOption]:
        """
        Returns a list of all the options applicable to "use", or all options
        if use is None.
        """
        result = []
        if use is None:
            use = 0xFF
        if exclude is None:
            exclude = set()
        for opt in cls._all_options:
            if (opt.usage & use) == 0:
                continue
            if only is not None and opt.full_name not in only:
                continue
            if opt.full_name in exclude:
                continue
            result.append(opt)
        return result

    @classmethod
    def get_cgi_options(cls, use: Optional[OptionUsage] = None,
                        only: Optional[AbstractSet[str]] = None,
                        exclude: Optional[AbstractSet[str]] = None,
                        extras: Optional[DashOption] = None,
                        omit_empty: bool = False,
                        **filter) -> list[CgiOption]:
        """
        Get a list of all DASH options that match
        """
        def matches(item: DashOption) -> bool:
            if item.cgi_name in exclude:
                return False
            if only is not None and item.cgi_name not in only:
                return False
            for name, value in filter.items():
                if getattr(item, name) != value:
                    return False
            return True

        if exclude is None:
            exclude = set()
        result: list[CgiOption] = []
        todo = cls.get_dash_options(use=use)
        if extras:
            todo += extras
        for item in todo:
            if not matches(item):
                continue
            c_opt = item.get_cgi_option(omit_empty=omit_empty)
            if c_opt is not None:
                result.append(c_opt)
        result.sort(key=lambda item: item.name)
        return result

    @classmethod
    def get_cgi_map(cls) -> dict[str, str]:
        """
        Returns a dictionary that maps from the CGI parameter used in a
        URL to its DashOption entry
        """
        if cls._cgi_map is not None:
            return cls._cgi_map
        cls._cgi_map = {}
        for opt in cls.get_dash_options():
            cls._cgi_map[opt.cgi_name] = opt
        return cls._cgi_map

    @classmethod
    def get_parameter_map(cls) -> dict[str, str]:
        """
        Returns a dictionary that maps from the full parameter name
        to is DashOption entry
        """
        if cls._param_map is not None:
            return cls._param_map
        cls._param_map = {}
        for opt in cls.get_dash_options():
            if opt.prefix:
                name = f'{opt.prefix}.{opt.full_name}'
            else:
                name = opt.full_name
            cls._param_map[name] = opt
        return cls._param_map

    @classmethod
    def get_default_options(cls, use: Optional[OptionUsage] = None) -> OptionsContainer:
        """
        Returns a dictionary containing the global defaults for every option
        """
        if cls._global_default_options is not None:
            return cls._global_default_options
        result = OptionsContainer(cls.get_parameter_map(), None)
        cls._global_default_options = result
        for opt in cls.get_dash_options():
            if opt.cgi_choices:
                value = opt.cgi_choices[0]
                if isinstance(value, tuple):
                    value = value[1]
            else:
                value = ''
            if value is None:
                value = 'none'
            value = opt.from_string(value)
            if opt.prefix:
                try:
                    dest = result[opt.prefix]
                except KeyError:
                    dest = OptionsContainer(cls.get_parameter_map(), None)
                    result.add_field(opt.prefix, dest)
            else:
                dest = result
            dest.add_field(opt.full_name, value)
        return result

    @classmethod
    def convert_cgi_options(cls, params: dict[str, str],
                            defaults: Optional[OptionsContainer] = None) -> OptionsContainer:
        """
        Convert a dictionary of CGI parameters to an OptionsContainer object
        """
        if defaults is not None:
            result = defaults.clone(
                parameter_map=cls.get_parameter_map(),
                defaults=defaults)
        else:
            result = OptionsContainer(cls.get_parameter_map(), defaults)
        cgi_map = cls.get_cgi_map()
        for key, value in params.items():
            try:
                opt = cgi_map[key]
                value = opt.from_string(value)
                if opt.prefix:
                    name = key[len(opt.prefix) + 1:]
                    try:
                        dest = result[opt.prefix]
                    except KeyError:
                        dflt = None
                        if defaults is not None:
                            dflt = getattr(defaults, opt.prefix)
                        dest = OptionsContainer(
                            cls.get_parameter_map(), dflt)
                        result.add_field(opt.prefix, dest)
                    dest.add_field(name, value)
                else:
                    result.add_field(opt.full_name, value)
            except KeyError as err:
                logging.warning(f'Invalid CGI parameter {key}: {err}')
                continue
        result.add_field('encrypted', len(getattr(result, 'drmSelection', '')) > 0)
        return result
