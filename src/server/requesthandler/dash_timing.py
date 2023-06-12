from __future__ import division
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

from builtins import str
from builtins import object
from past.utils import old_div
import datetime
import logging

from utils.date_time import from_isodatetime
from utils.timezone import UTC

class DashTiming(object):
    DEFAULT_TIMESHIFT_BUFFER_DEPTH = 60  # in seconds

    def __init__(self, mode, now, representation, params):
        self.timeShiftBufferDepth = 0
        self.mode = mode
        self.now = now
        self.availabilityStartTime = None
        self.publishTime = now.replace(microsecond=0)
        # self.elapsedTime = datetime.timedelta(seconds=0)
        if mode == 'live':
            self.calculate_live_params(mode, now, representation, params)
        else:
            self.mediaDuration = datetime.timedelta(seconds=(
                old_div(representation.mediaDuration, representation.timescale)))

    def calculate_live_params(self, mode, now, representation, params):
        try:
            self.timeShiftBufferDepth = int(params.get(
                'depth', str(self.DEFAULT_TIMESHIFT_BUFFER_DEPTH)), 10)
        except ValueError:
            self.timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH
        startParam = params.get('start', 'today')
        if startParam == 'today':
            self.availabilityStartTime = now.replace(
                hour=0, minute=0, second=0, microsecond=0)
            if now.hour == 0 and now.minute == 0:
                self.availabilityStartTime -= datetime.timedelta(days=1)
        elif startParam == 'now':
            publishTime = now.replace(microsecond=0)
            self.availabilityStartTime = (
                publishTime -
                datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH))
        elif startParam == 'epoch':
            self.availabilityStartTime = datetime.datetime(
                1970, 1, 1, 0, 0, tzinfo=UTC())
        else:
            try:
                self.availabilityStartTime = from_isodatetime(startParam)
            except ValueError as err:
                logging.warning('Failed to parse availabilityStartTime: %s', err)
                self.availabilityStartTime = now.replace(
                    hour=0, minute=0, second=0, microsecond=0)
                if now.hour == 0 and now.minute == 0:
                    self.availabilityStartTime -= datetime.timedelta(days=1)
        self.elapsedTime = now - self.availabilityStartTime
        if self.elapsedTime.total_seconds() < self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = self.elapsedTime.total_seconds()
        minimumUpdatePeriod = 0
        default_mup = (old_div(2.0 * representation.segment_duration,
                       representation.timescale))
        try:
            minimumUpdatePeriod = float(params.get('mup', default_mup))
        except ValueError:
            pass
        if minimumUpdatePeriod > 0:
            self.minimumUpdatePeriod = minimumUpdatePeriod
        else:
            self.minimumUpdatePeriod = default_mup

    def generate_manifest_context(self):
        if self.mode == 'live':
            return {
                "availabilityStartTime": self.availabilityStartTime,
                "elapsedTime": self.elapsedTime,
                "now": self.now,
                "publishTime": self.publishTime,
                "minimumUpdatePeriod": self.minimumUpdatePeriod,
                "timeShiftBufferDepth": self.timeShiftBufferDepth,
            }
        return {
            "mediaDuration": self.mediaDuration,
            "now": self.now,
            "publishTime": self.publishTime,
        }
