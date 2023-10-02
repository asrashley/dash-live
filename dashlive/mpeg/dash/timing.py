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

import datetime
import logging
from typing import ClassVar

from dashlive.utils.timezone import UTC
from dashlive.mpeg.dash.reference import StreamTimingReference
from dashlive.server.options.container import OptionsContainer

class DashTiming:
    DEFAULT_TIMESHIFT_BUFFER_DEPTH: ClassVar[int] = 60  # in seconds

    __slots__ = ('timeShiftBufferDepth', 'mode', 'now', 'availabilityStartTime',
                 'publishTime', 'stream_reference', 'elapsedTime',
                 'mediaDuration', 'minimumUpdatePeriod',
                 'firstAvailableTime')

    availabilityStartTime: datetime.datetime | None
    elapsedTime: datetime.timedelta
    firstAvailableTime: datetime.timedelta
    mediaDuration: datetime.timedelta
    minimumUpdatePeriod: int | None
    mode: str
    now: datetime.datetime
    publishTime: datetime.datetime
    stream_reference: StreamTimingReference
    timeshiftbufferdepth: int

    def __init__(self,
                 now: datetime.datetime,
                 stream_ref: StreamTimingReference,
                 options: OptionsContainer) -> None:
        self.mode = options.mode
        self.now = now
        self.publishTime = now.replace(microsecond=0)
        self.stream_reference = stream_ref
        if options.mode == 'live':
            self.calculate_live_params(now, options)
        else:
            self.calculate_vod_params(now, options)

    def calculate_vod_params(self,
                             now: datetime.datetime,
                             options: OptionsContainer) -> None:
        self.availabilityStartTime = None
        self.timeShiftBufferDepth = 0
        self.elapsedTime = self.firstAvailableTime = datetime.timedelta(seconds=0)
        self.mediaDuration = datetime.timedelta(seconds=(
            self.stream_reference.media_duration / float(self.stream_reference.timescale)))
        self.minimumUpdatePeriod = None

    def calculate_live_params(self,
                              now: datetime.datetime,
                              options: OptionsContainer) -> None:
        self.timeShiftBufferDepth = options.timeShiftBufferDepth
        if not self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH
        if options.availabilityStartTime == 'epoch':
            # TODO: add in leap seconds
            self.availabilityStartTime = datetime.datetime(1970, 1, 1, 0, 0, tzinfo=UTC())
        elif options.availabilityStartTime == 'today':
            self.availabilityStartTime = now.replace(
                hour=0, minute=0, second=0, microsecond=0)
            if self.publishTime.hour == 0 and self.publishTime.minute == 0:
                self.availabilityStartTime -= datetime.timedelta(days=1)
        elif options.availabilityStartTime == 'now':
            self.availabilityStartTime = (
                self.publishTime -
                datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH))
        else:
            self.availabilityStartTime = options.availabilityStartTime
        self.elapsedTime = now - self.availabilityStartTime
        logging.debug('calculate_live_params elapsed=%s (%f) now=%s availabilityStartTime=%s',
                      self.elapsedTime, self.elapsedTime.total_seconds(),
                      now, self.availabilityStartTime)
        if self.elapsedTime.total_seconds() == 0:
            logging.info('Elapsed time is zero, moving availabilityStartTime back one day')
            self.elapsedTime = datetime.timedelta(days=1)
            self.availabilityStartTime -= self.elapsedTime
        if self.elapsedTime.total_seconds() < self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = int(self.elapsedTime.total_seconds())
        default_mup = 2.0 * self.stream_reference.segment_duration / self.stream_reference.timescale
        self.minimumUpdatePeriod = options.minimumUpdatePeriod
        if self.minimumUpdatePeriod is None:
            self.minimumUpdatePeriod = default_mup
        elif self.minimumUpdatePeriod <= 0:
            self.minimumUpdatePeriod = None
        self.firstAvailableTime = self.elapsedTime - datetime.timedelta(
            seconds=self.timeShiftBufferDepth)

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
