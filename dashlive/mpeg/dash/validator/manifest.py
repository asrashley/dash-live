#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
import urllib.parse

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import from_isodatetime

from .dash_element import DashElement
from .period import Period

class Manifest(DashElement):
    attributes = [
        ('availabilityStartTime', from_isodatetime, None),
        ('minimumUpdatePeriod', from_isodatetime, None),
        ('timeShiftBufferDepth', from_isodatetime, None),
        ('mediaPresentationDuration', from_isodatetime, None),
        ('publishTime', from_isodatetime, None),
    ]

    def __init__(self, parent, url, mode, xml):
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
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in xml.get(
                    'profiles'):
                self.mode = 'odvod'
        if self.publishTime is None:
            self.publishTime = datetime.datetime.now()
        self.mpd_type = xml.get("type", "static")
        self.periods = [Period(p, self) for p in xml.findall('./dash:Period', self.xmlNamespaces)]
        self.dump_attributes()

    @property
    def mpd(self):
        return self

    def prefetch_media_info(self) -> None:
        self.progress.add_todo(len(self.periods))
        for p in self.periods:
            p.prefetch_media_info()

    def set_representation_info(self, info: ServerRepresentation):
        for p in self.periods:
            p.set_representation_info(info)

    def children(self) -> list[DashElement]:
        return self.periods

    def get_duration(self) -> datetime.timedelta:
        if self.mediaPresentationDuration:
            return self.mediaPresentationDuration
        return datetime.timedelta(seconds=0)

    def num_tests(self, depth: int = -1) -> int:
        if depth == 0:
            return 0
        count = len(self.periods)
        for period in self.periods:
            count += period.num_tests(depth - 1)
        return count

    def validate(self, depth=-1):
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
        if depth != 0:
            for period in self.periods:
                period.validate(depth - 1)
                self.progress.inc()
