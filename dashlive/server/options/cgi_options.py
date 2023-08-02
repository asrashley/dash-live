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

from typing import AbstractSet, Literal, Optional

from .audio_options import audio_options
from .dash_option import CgiOption, DashOption
from .drm_options import drm_options
from .manifest_options import manifest_options
from .video_options import video_options
from .utc_time_options import time_options

OPTION_USAGE = Literal['manifest', 'video', 'audio', 'time']

def get_dash_options(use: Optional[OPTION_USAGE] = None) -> list[DashOption]:
    result = []
    if use is None or use == 'manifest':
        result += manifest_options
    if use is None or use == 'video':
        result += video_options
    if use is None or use == 'audio':
        result += audio_options
    if use in {None, 'manifest', 'time'}:
        result += time_options
    if use is None or use != 'time':
        result += drm_options
    return result


def get_cgi_options(use: Optional[OPTION_USAGE] = None,
                    only: Optional[AbstractSet[str]] = None,
                    exclude: Optional[AbstractSet[str]] = None,
                    omit_empty: bool = False,
                    **filter) -> list[CgiOption]:
    def matches(item: DashOption) -> bool:
        if isinstance(item.cgi_name, list):
            names = set(item.cgi_name)
        else:
            names = {item.cgi_name}
        if exclude.intersection(names):
            return False
        if only is not None:
            if not only.intersection(names):
                return False
        for name, value in filter.items():
            if getattr(item, name) != value:
                return False
        return True

    if exclude is None:
        exclude = set()
    result: list[CgiOption] = []
    todo = get_dash_options(use=use)
    for item in todo:
        if matches(item):
            result += item.get_cgi_options(omit_empty=omit_empty)
    result.sort(key=lambda item: item.name)
    return result
