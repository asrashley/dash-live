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

from past.builtins import basestring
from builtins import object
from future.utils import with_metaclass
from abc import ABCMeta, abstractmethod
import copy
import datetime
from typing import Dict, Optional

from flask import Request

from dashlive.utils.date_time import from_isodatetime

class EventBase(with_metaclass(ABCMeta, object)):
    PARAMS = {
        'count': 0,
        'duration': 200,
        'inband': True,
        'interval': 1000,
        'start': 0,
        'timescale': 100,
        'value': '0',
        'version': 0,
    }

    def __init__(self, prefix: str, request: Request,
                 extra_params: Optional[Dict] = None) -> None:
        all_params = copy.deepcopy(self.PARAMS)
        if extra_params is not None:
            all_params.update(extra_params)
        self.prefix = prefix
        self.params = set()
        for key, dflt in all_params.items():
            value = request.args.get(prefix + key, dflt)
            if isinstance(dflt, bool):
                if isinstance(value, basestring):
                    value = value.lower() in {'true', 'yes', '1'}
                elif isinstance(value, (int, int)):
                    value = (value == 1)
            elif isinstance(dflt, int):
                value = int(value)
            elif isinstance(dflt, int):
                value = int(value)
            elif isinstance(dflt, (
                    datetime.date, datetime.datetime, datetime.time,
                    datetime.timedelta)):
                value = from_isodatetime(value)
            setattr(self, key, value)
            self.params.add(key)

    def cgi_parameters(self) -> Dict:
        """
        Get all parameters for this event generator as a dictionary
        """
        retval = {}
        for key in self.params:
            value = getattr(self, key)
            retval['{0:s}{1:s}'.format(self.prefix, key)] = value
        return retval

    @abstractmethod
    def create_manifest_context(self, context: Dict) -> Dict:
        return {}

    @abstractmethod
    def create_emsg_boxes(self, **kwargs):
        return None
