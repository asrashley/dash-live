#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
import urllib.parse

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

    def num_tests(self, depth: int = -1) -> int:
        if depth == 0:
            return 0
        count = len(self.periods)
        for period in self.periods:
            count += period.num_tests(depth - 1)
        return count

    def validate(self, depth=-1):
        self.checkGreaterThan(len(self.periods), 0,
                              "Manifest does not have a Period element: %s" % self.url)
        if self.mode == "live":
            self.checkEqual(
                self.mpd_type, "dynamic",
                "MPD@type must be dynamic for live manifest: %s" % self.url)
            self.checkIsNotNone(
                self.availabilityStartTime,
                "MPD@availabilityStartTime must be present for live manifest: %s" % self.url)
            self.checkIsNotNone(
                self.timeShiftBufferDepth,
                "MPD@timeShiftBufferDepth must be present for live manifest: %s" % self.url)
            self.checkIsNone(
                self.mediaPresentationDuration,
                "MPD@mediaPresentationDuration must not be present for live manifest: %s" % self.url)
        else:
            msg = r'MPD@type must be static for VOD manifest, got "{}": {}'.format(
                self.mpd_type, self.url)
            self.checkEqual(self.mpd_type, "static", msg=msg)
            if self.mediaPresentationDuration is not None:
                self.checkGreaterThan(
                    self.mediaPresentationDuration,
                    datetime.timedelta(seconds=0),
                    'Invalid MPD@mediaPresentationDuration "{}": {}'.format(
                        self.mediaPresentationDuration, self.url))
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, ' +\
                      'Period@duration must be present: ' + self.url
                for p in self.periods:
                    self.checkIsNotNone(p.duration, msg)
            self.checkIsNone(
                self.minimumUpdatePeriod,
                "MPD@minimumUpdatePeriod must not be present for VOD manifest: %s" % self.url)
            self.checkIsNone(
                self.availabilityStartTime,
                "MPD@availabilityStartTime must not be present for VOD manifest: %s" % self.url)
        if depth != 0:
            for period in self.periods:
                period.validate(depth - 1)
                self.progress.inc()
