#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import asyncio
import datetime
from typing import Any, ClassVar
import urllib.parse

from lxml import etree as ET

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import from_isodatetime, UTC, toIsoDuration
from dashlive.utils.string import set_from_comma_string

from .dash_element import DashElement
from .patch_location import PatchLocation
from .period import Period
from .validation_flag import ValidationFlag

class Manifest(DashElement):
    attributes: ClassVar[list[tuple[str, Any, Any]]] = [
        ('availabilityStartTime', from_isodatetime, None),
        ('id', str, None),
        ('minimumUpdatePeriod', from_isodatetime, None),
        ('timeShiftBufferDepth', from_isodatetime, None),
        ('mediaPresentationDuration', from_isodatetime, None),
        ('profiles', set_from_comma_string, None),
        ('publishTime', from_isodatetime, None),
    ]

    baseurl: str
    url: str
    mode: str
    mpd_type: str  # "static" or "dynamic"
    periods: list[Period]
    params: dict[str, Any]
    patches: list[PatchLocation]
    profiles: set[str]
    publishTime: datetime.datetime

    def __init__(self,
                 parent: DashElement | None,
                 url: str,
                 mode: str,
                 xml: ET.ElementBase) -> None:
        super().__init__(xml, parent)
        self.url = url
        parsed = urllib.parse.urlparse(url)
        self.params = {}
        for key, value in urllib.parse.parse_qs(parsed.query).items():
            self.params[key] = value[0]
        self.mode = mode
        if self.baseurl is None:
            self.baseurl = url
            assert isinstance(url, str)
        if mode != 'live':
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in self.profiles:
                self.mode = 'odvod'
        if self.publishTime is None:
            self.publishTime = datetime.datetime.now(tz=UTC())
        self.mpd_type = xml.get("type", "static")
        self.periods = []
        self.patches = []
        for idx, prd in enumerate(xml.findall('./dash:Period', self.xmlNamespaces), start=1):
            period: Period = Period(prd, self)
            if period.id is None:
                # Period@id is a string. Setting it to a number is therefore safely unique
                period.id = idx
            self.periods.append(period)
        self.patches = [PatchLocation(loc, self) for loc in xml.findall(
            './dash:PatchLocation', self.xmlNamespaces)]
        self.set_target_durations()

    def set_target_durations(self) -> None:
        if self.options.duration is None:
            return
        todo = datetime.timedelta(seconds=self.options.duration)
        for period in self.periods:
            if period.duration is None:
                self.log.debug(
                    'Using target duration %s for last period %s', todo, period.id)
                period.target_duration = todo
                break
            if todo < period.duration:
                period.target_duration = todo
            else:
                period.target_duration = period.duration
            self.log.debug(
                'Using target duration %s for period %s',
                period.target_duration, period.id)
            todo -= period.target_duration
            if todo.total_seconds() < 0:
                todo = datetime.timedelta(seconds=0)

    @property
    def mpd(self):
        return self

    def now(self) -> datetime.datetime:
        # TODO: implement clock drift compensation
        return datetime.datetime.now(tz=UTC())

    async def prefetch_media_info(self) -> bool:
        self.progress.add_todo(len(self.periods))
        futures = [
            p.prefetch_media_info() for p in self.periods]
        results = await asyncio.gather(*futures)
        return False not in results

    def set_representation_info(self, info: ServerRepresentation):
        for p in self.periods:
            p.set_representation_info(info)

    def children(self) -> list[DashElement]:
        return self.periods + self.patches

    def get_duration(self) -> datetime.timedelta:
        if self.mediaPresentationDuration:
            return self.mediaPresentationDuration
        return datetime.timedelta(seconds=0)

    def get_codecs(self) -> set[str]:
        codecs = set()
        for period in self.periods:
            codecs.update(period.get_codecs())
        return codecs

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.MANIFEST in self.options.verify:
            count += 1
        for period in self.periods:
            count += period.num_tests()
        return count

    def finished(self) -> bool:
        for period in self.periods:
            if (
                    (period.target_duration is None or
                     period.target_duration.total_seconds() > 0) and
                    not period.finished()):
                return False
        return True

    async def merge_previous_element(self, prev: "Manifest") -> bool:
        period_map = {}
        for idx, period in enumerate(self.periods):
            period_map[period.id] = period
        self.set_target_durations()
        futures = []
        for idx, period in enumerate(prev.periods):
            try:
                futures.append(period_map[period.id].merge_previous_element(period))
            except KeyError:
                self.log.debug('New period %s', period.id)
        result = await asyncio.gather(*futures)
        return False not in result

    async def validate(self):
        if ValidationFlag.MANIFEST in self.options.verify:
            self.validate_self()
        futures = [p.validate() for p in self.periods]
        futures += [p.validate() for p in self.patches]
        await asyncio.gather(*futures)

    def validate_self(self):
        self.elt.check_greater_than(
            len(self.periods), 0,
            msg=f'Manifest does not have a Period element: {self.url}')
        if self.mode == "live":
            self.attrs.check_equal(
                self.mpd_type, "dynamic",
                msg=f'MPD@type must be dynamic for live manifest: {self.url}')
            self.attrs.check_not_none(
                self.availabilityStartTime,
                msg=f"MPD@availabilityStartTime must be present for live manifest: {self.url}")
            self.attrs.check_not_none(
                self.timeShiftBufferDepth,
                msg=f"MPD@timeShiftBufferDepth must be present for live manifest: {self.url}")
            self.attrs.check_none(
                self.mediaPresentationDuration,
                msg=f"MPD@mediaPresentationDuration must not be present for live manifest: {self.url}")
        else:
            msg = f'MPD@type must be static for VOD manifest, got "{self.mpd_type}": {self.url}'
            self.attrs.check_equal(self.mpd_type, "static", msg=msg)
            if self.mediaPresentationDuration is not None:
                msg = ('Invalid MPD@mediaPresentationDuration ' +
                       f'"{self.mediaPresentationDuration}": {self.url}')
                self.attrs.check_greater_than(
                    self.mediaPresentationDuration,
                    datetime.timedelta(seconds=0),
                    msg=msg)
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, ' +\
                      'Period@duration must be present: ' + self.url
                for p in self.periods:
                    self.elt.check_not_none(p.duration, msg)
            self.attrs.check_none(
                self.minimumUpdatePeriod,
                msg=f"MPD@minimumUpdatePeriod must not be present for VOD manifest: {self.url}")
            self.attrs.check_none(
                self.availabilityStartTime,
                msg=f"MPD@availabilityStartTime must not be present for VOD manifest: {self.url}")
            self.elt.check_equal(
                self.patches, [],
                msg='PatchLocation elements should only be used in live streams')
        start: datetime.timedelta | None = datetime.timedelta()
        if self.periods:
            start = self.periods[0].start
        for period in self.periods:
            if not period.attrs.check_not_none(
                    start, 'Previous Period@duration was absent'):
                continue
            period.attrs.check_almost_equal(
                period.start.total_seconds(),
                start.total_seconds(),
                delta=0.2,
                msg=(f"Expected Period@start {toIsoDuration(start)} " +
                     f"but found {toIsoDuration(period.start)}"))
            if period.duration is None:
                start = None
            else:
                start = period.start + period.duration
        self.progress.inc()
