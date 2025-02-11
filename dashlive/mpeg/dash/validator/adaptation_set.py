#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio
import datetime

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation
from dashlive.utils.date_time import timedelta_to_timecode

from .content_component import ContentComponent
from .dash_element import DashElement
from .frame_rate_type import FrameRateType
from .representation_base_type import RepresentationBaseType
from .representation import Representation
from .validation_flag import ValidationFlag

class AdaptationSet(RepresentationBaseType):
    attributes = RepresentationBaseType.attributes + [
        ('contentType', str, None),
        ('group', int, None),
        ('href', str, None),
        ('id', int, None),
        ('lang', str, None),
        ('minBandwidth', int, None),
        ('maxBandwidth', int, None),
        ('minWidth', int, None),
        ('maxWidth', int, None),
        ('minHeight', int, None),
        ('maxHeight', int, None),
        ('minFrameRate', FrameRateType, None),
        ('maxFrameRate', FrameRateType, None),
    ]

    contentComponents: list[ContentComponent]
    representations: list[Representation]

    def __init__(self, adap_set, parent) -> None:
        super().__init__(adap_set, parent)
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.default_KID = None
        for cp in self.contentProtection:
            if cp.default_KID:
                self.default_KID = cp.default_KID
                break
        self.representations = [Representation(r, self) for r in reps]
        components = adap_set.findall('./dash:ContentComponent', self.xmlNamespaces)
        self.contentComponents = [ContentComponent(c, self) for c in components]
        abs_start: datetime.timedelta = self.parent.start
        for rep in self.representations:
            rep.timeline_start = timedelta_to_timecode(abs_start, rep.dash_timescale())

    async def prefetch_media_info(self) -> bool:
        self.progress.add_todo(len(self.representations))
        futures = {
            rep.prefetch_media_info() for rep in self.representations}
        results = await asyncio.gather(*futures)
        self.progress.inc()
        return False not in results

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.ADAPTATION_SET in self.options.verify:
            count += 1 + len(self.contentProtection) + len(self.contentComponents)
        for rep in self.representations:
            count += rep.num_tests()
        return count

    def children(self) -> list[DashElement]:
        return super().children() + self.representations + self.contentComponents

    @property
    def target_duration(self) -> datetime.timedelta | None:
        return self.parent.target_duration

    async def merge_previous_element(self, prev: "AdaptationSet") -> bool:
        def make_rep_id(idx, r):
            if r.id is not None:
                return r.id
            if r.bandwidth:
                return f'bw={r.bandwidth}'
            return f'idx={idx}'

        self.log.debug(
            'Merging previous AdaptationSet element id=%s contentType=%s',
            str(self.id), self.contentType)
        rep_map = {}
        for idx, r in enumerate(self.representations):
            rid = make_rep_id(idx, r)
            rep_map[rid] = r
        futures = []
        results = []
        for idx, r in enumerate(prev.representations):
            rid = make_rep_id(idx, r)
            try:
                futures.append(rep_map[rid].merge_previous_element(r))
            except KeyError as err:
                self.elt.add_error(
                    'Representations have changed within a Period: %s', err)
                results.append(False)
        results += await asyncio.gather(*futures)
        return False not in results

    def finished(self) -> bool:
        if self.progress.aborted():
            return True
        if (
                self.target_duration is not None and
                self.target_duration.total_seconds() == 0):
            self.log.debug('AdaptationSet %d finished (total_seconds==0)',
                           self.id)
            return True
        for child in self.representations:
            if not child.finished():
                self.log.debug(
                    'Representation %s in AdaptationSet %d not finished',
                    child.id, self.id)
                return False
        self.log.debug('AdaptationSet %d finished', self.id)
        return True

    def set_representation_info(self, info: ServerRepresentation):
        for r in self.representations:
            if r.id == info.id:
                r.set_representation_info(info)

    def get_codecs(self) -> set[str]:
        codecs = set()
        for r in self.representations:
            cd = r.get_codec()
            if cd is not None:
                codecs.add(cd)
        return codecs

    async def validate(self) -> None:
        if ValidationFlag.ADAPTATION_SET in self.options.verify:
            await self.validate_self()
            self.progress.inc()
        tasks = {rep.validate() for rep in self.representations}
        tasks.update({cc.validate() for cc in self.contentComponents})
        await asyncio.gather(*tasks)

    async def validate_self(self, depth: int = -1) -> None:
        if len(self.contentProtection):
            self.elt.check_not_none(
                self.default_KID,
                msg=f'default_KID cannot be missing for protected stream: {self.baseurl}')
        if self.contentType is not None:
            self.attrs.check_includes(
                ContentComponent.CONTENT_TYPES,
                self.contentType,
                msg=f'Unexpected @contentType "{self.contentType}"',
                clause='5.3.3.1')
        self.attrs.check_not_none(
            self.mimeType, msg='AdaptationSet@mimeType is a mandatory attribute',
            clause='5.3.7.2')
        if not self.options.encrypted:
            self.elt.check_equal(
                len(self.contentProtection), 0,
                msg='At least one ContentProtection element is required for an encrypted stream')
        futures = {cp.validate() for cp in self.contentProtection}
        await asyncio.gather(*futures)
