#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import ClassVar

from .all_options import ALL_OPTIONS
from .dash_option import DashOption

class DashOptionNameMaps:
    _cgi_map: ClassVar[dict[str, DashOption] | None] = None
    _short_name_map: ClassVar[dict[str, DashOption] | None] = None
    _param_map: ClassVar[dict[str, DashOption] | None] = None

    @classmethod
    def get_parameter_map(cls) -> dict[str, DashOption]:
        """
        Returns a dictionary that maps from the full parameter name
        to its DashOption entry
        """
        if cls._param_map is not None:
            return cls._param_map
        cls._param_map = {}
        for opt in ALL_OPTIONS:
            if opt.prefix:
                cls._param_map[f'{opt.prefix}.{opt.short_name}'] = opt
                name = f'{opt.prefix}.{opt.full_name}'
            else:
                name = opt.full_name
            cls._param_map[name] = opt
        return cls._param_map

    @classmethod
    def get_cgi_map(cls) -> dict[str, DashOption]:
        """
        Returns a dictionary that maps from the CGI parameter used in a
        URL to its DashOption entry
        """
        if cls._cgi_map is not None:
            return cls._cgi_map
        cls._cgi_map = {}
        for opt in ALL_OPTIONS:
            cls._cgi_map[opt.cgi_name] = opt
        return cls._cgi_map

    @classmethod
    def get_short_param_map(cls) -> dict[str, DashOption]:
        """
        Returns a dictionary that maps from the short parameter used in a
        stream defaults
        """
        if cls._short_name_map is not None:
            return cls._short_name_map
        cls._short_name_map = {}
        for opt in ALL_OPTIONS:
            cls._short_name_map[opt.short_name] = opt
        return cls._short_name_map
