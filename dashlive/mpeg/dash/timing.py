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
from dashlive.utils.date_time import timecode_to_timedelta
from dashlive.server.options.container import OptionsContainer

from .reference import StreamTimingReference

class DashTiming:
    DEFAULT_TIMESHIFT_BUFFER_DEPTH: ClassVar[int] = 60  # in seconds

    __slots__ = ('timeShiftBufferDepth', 'mode', 'now', 'availabilityStartTime',
                 'publishTime', 'stream_reference', 'elapsedTime', 'leeway',
                 'mediaDuration', 'minimumUpdatePeriod',
                 'firstAvailableTime')

    availabilityStartTime: datetime.datetime | None
    elapsedTime: datetime.timedelta
    firstAvailableTime: datetime.timedelta
    leeway: datetime.timedelta
    mediaDuration: datetime.timedelta
    minimumUpdatePeriod: int | None
    mode: str
    now: datetime.datetime
    publishTime: datetime.datetime
    stream_reference: StreamTimingReference
    timeShiftBufferDepth: int  # in seconds

    def __init__(self,
                 now: datetime.datetime,
                 stream_ref: StreamTimingReference,
                 options: OptionsContainer) -> None:
        self.mode = options.mode
        self.now = now
        self.publishTime = now.replace(microsecond=0)
        self.stream_reference = stream_ref
        self.leeway = datetime.timedelta(seconds=0)
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
        self.mediaDuration = timecode_to_timedelta(
            self.stream_reference.media_duration, self.stream_reference.timescale)
        self.minimumUpdatePeriod = None

    def calculate_live_params(self,
                              now: datetime.datetime,
                              options: OptionsContainer) -> None:
        self.timeShiftBufferDepth = options.timeShiftBufferDepth
        if not self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = self.DEFAULT_TIMESHIFT_BUFFER_DEPTH
        one_day = datetime.timedelta(days=1)
        if options.availabilityStartTime == 'epoch':
            # TODO: add in leap seconds
            self.availabilityStartTime = datetime.datetime(1970, 1, 1, 0, 0, tzinfo=UTC())
        elif options.availabilityStartTime == 'today':
            self.availabilityStartTime = now.replace(
                hour=0, minute=0, second=0, microsecond=0)
            if self.publishTime.hour == 0 and self.publishTime.minute == 0:
                self.availabilityStartTime -= datetime.timedelta(days=1)
        elif options.availabilityStartTime == 'month':
            self.availabilityStartTime = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0)
            if (self.publishTime - self.availabilityStartTime) < one_day:
                self.availabilityStartTime -= one_day
        elif options.availabilityStartTime == 'year':
            self.availabilityStartTime = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            if (self.publishTime - self.availabilityStartTime) < one_day:
                self.availabilityStartTime -= one_day
        elif options.availabilityStartTime == 'now':
            self.availabilityStartTime = (
                self.publishTime -
                datetime.timedelta(seconds=self.DEFAULT_TIMESHIFT_BUFFER_DEPTH))
        else:
            self.availabilityStartTime = options.availabilityStartTime
        self.elapsedTime = now - self.availabilityStartTime
        logging.debug(
            'calculate_live_params elapsed=%s (%f) now=%s availabilityStartTime=%s timescale=%d',
            self.elapsedTime, self.elapsedTime.total_seconds(),
            now, self.availabilityStartTime, self.stream_reference.timescale)
        logging.debug(
            'elapsed_fragments=%d',
            self.elapsedTime.total_seconds() * self.stream_reference.timescale //
            self.stream_reference.segment_duration)
        if self.elapsedTime.total_seconds() == 0:
            logging.info('Elapsed time is zero, moving availabilityStartTime back one day')
            self.elapsedTime = datetime.timedelta(days=1)
            self.availabilityStartTime -= self.elapsedTime
        if self.elapsedTime.total_seconds() < self.timeShiftBufferDepth:
            self.timeShiftBufferDepth = int(self.elapsedTime.total_seconds())
        logging.debug('timeShiftBufferDepth: %d seconds', self.timeShiftBufferDepth)
        default_mup = 2.0 * self.stream_reference.segment_duration / self.stream_reference.timescale
        self.minimumUpdatePeriod = options.minimumUpdatePeriod
        if self.minimumUpdatePeriod is None:
            self.minimumUpdatePeriod = default_mup
        elif self.minimumUpdatePeriod <= 0:
            self.minimumUpdatePeriod = None
        self.firstAvailableTime = self.elapsedTime - datetime.timedelta(
            seconds=self.timeShiftBufferDepth)
        if options.leeway is not None:
            self.leeway = datetime.timedelta(seconds=options.leeway)

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
