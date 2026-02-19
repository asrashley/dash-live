#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import AbstractSet

from dashlive.server.options.all_options import ALL_OPTIONS

from .container import OptionsContainer
from .dash_option import CgiOption, DashOption
from .types import OptionUsage

class OptionsRepository:
    @classmethod
    def get_dash_options(cls,
                         use: OptionUsage | None = None,
                         only: AbstractSet[str] | None = None,
                         exclude: AbstractSet[str] | None = None) -> list[DashOption]:
        """
        Returns a list of all the options applicable to "use", or all options
        if use is None.
        """
        result: list[DashOption] = []
        if use is None:
            use = 0xFF
        if exclude is None:
            exclude = set()
        for opt in ALL_OPTIONS:
            if (opt.usage & use) == 0:
                continue
            if only is not None and opt.full_name not in only:
                continue
            if opt.full_name in exclude:
                continue
            result.append(opt)
        return result

    @classmethod
    def get_cgi_options(cls, use: OptionUsage | None = None,
                        only: AbstractSet[str] | None = None,
                        exclude: AbstractSet[str] | None = None,
                        extras: list[DashOption] | None = None,
                        omit_empty: bool = False,
                        **filter) -> list[CgiOption]:
        """
        Get a list of all DASH options that match
        """
        def matches(item: DashOption) -> bool:
            if exclude is not None:
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
            for e in extras:
                assert isinstance(e, DashOption)
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
    def convert_cgi_options(cls, params: dict[str, str]) -> OptionsContainer:
        """
        Convert a dictionary of CGI parameters to an OptionsContainer object
        """
        result = OptionsContainer()
        result.apply_options(params, True)
        return result

    @classmethod
    def convert_short_name_options(cls, params: dict[str, str]) -> OptionsContainer:
        """
        Convert a dictionary of CGI parameters to an OptionsContainer object
        """
        result = OptionsContainer()
        result.apply_options(params, False)
        return result
