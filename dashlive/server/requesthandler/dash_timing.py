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

from past.utils import old_div
import datetime
import logging

from dashlive.mpeg.dash.representation import Representation
from dashlive.server.options.container import OptionsContainer

class DashTiming:
    DEFAULT_TIMESHIFT_BUFFER_DEPTH = 60  # in seconds

    def __init__(self, now: datetime.datetime,
                 representation: Representation,
                 options: OptionsContainer) -> None:
        self.timeShiftBufferDepth = 0
        self.mode = options.mode
        self.now = now
        self.availabilityStartTime = None
        self.publishTime = now.replace(microsecond=0)
        # self.elapsedTime = datetime.timedelta(seconds=0)
        if options.mode == 'live':
            self.calculate_live_params(now, representation, options)
        else:
            self.mediaDuration = datetime.timedelta(seconds=(
                old_div(representation.mediaDuration, representation.timescale)))

    def calculate_live_params(self,
                              now: datetime.datetime,
                              representation: Representation,
                              options: OptionsContainer) -> None:
        publishTime = now.replace(microsecond=0)
        self.timeShiftBufferDepth = options.timeShiftBufferDepth
        if not self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH
        if options.availabilityStartTime == 'today':
            self.availabilityStartTime = publishTime.replace(
                hour=0, minute=0, second=0, microsecond=0)
            if publishTime.hour == 0 and publishTime.minute == 0:
                self.availabilityStartTime -= datetime.timedelta(days=1)
        elif options.availabilityStartTime == 'now':
            self.availabilityStartTime = (
                publishTime -
                datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH))
        else:
            self.availabilityStartTime = options.availabilityStartTime
        self.elapsedTime = now - self.availabilityStartTime
        logging.debug('calculate_live_params elapsed=%s now=%s availabilityStartTime=%s',
                      self.elapsedTime, now, self.availabilityStartTime)
        if self.elapsedTime.total_seconds() == 0:
            logging.info('Elapsed time is zero, moving availabilityStartTime back one day')
            self.elapsedTime = datetime.timedelta(days=1)
            self.availabilityStartTime -= self.elapsedTime
        if self.elapsedTime.total_seconds() < self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = int(self.elapsedTime.total_seconds())
        default_mup = (old_div(2.0 * representation.segment_duration,
                       representation.timescale))
        self.minimumUpdatePeriod = options.minimumUpdatePeriod
        if self.minimumUpdatePeriod is None:
            self.minimumUpdatePeriod = default_mup
        elif self.minimumUpdatePeriod <= 0:
            self.minimumUpdatePeriod = None

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
