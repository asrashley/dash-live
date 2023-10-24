#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio

from dashlive.mpeg.dash.representation import Representation as ServerRepresentation

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

    def __init__(self, adap_set, parent):
        super().__init__(adap_set, parent)
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.default_KID = None
        for cp in self.contentProtection:
            if cp.default_KID:
                self.default_KID = cp.default_KID
                break
        self.representations = [Representation(r, self) for r in reps]

    async def prefetch_media_info(self) -> None:
        self.progress.add_todo(len(self.representations))
        async with asyncio.TaskGroup() as tg:
            for rep in self.representations:
                tg.create_task(rep.generate_segment_todo_list())

    def num_tests(self) -> int:
        count = 0
        if ValidationFlag.ADAPTATION_SET in self.options.verify:
            count += 1 + len(self.contentProtection)
        for rep in self.representations:
            count += rep.num_tests()
        return count

    def children(self) -> list[DashElement]:
        return super().children() + self.representations

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
        for child in self.representations:
            if not child.finished():
                self.log.debug(
                    'AdaptationSet %s not finished, as Representation %s not finished',
                    self.id, child.id)
                return False
        self.log.debug('AdaptationSet %s finished', self.id)
        return True

    def set_representation_info(self, info: ServerRepresentation):
        for r in self.representations:
            if r.id == info.id:
                r.set_representation_info(info)

    async def validate(self) -> None:
        if ValidationFlag.ADAPTATION_SET in self.options.verify:
            await self.validate_self()
            self.progress.inc()
        tasks = {rep.validate() for rep in self.representations}
        await asyncio.gather(*tasks)

    async def validate_self(self, depth: int = -1) -> None:
        if len(self.contentProtection):
            self.elt.check_not_none(
                self.default_KID,
                msg=f'default_KID cannot be missing for protected stream: {self.baseurl}')
        self.attrs.check_includes(
            container={'video', 'audio', 'text', 'image', 'font', 'application', None},
            item=self.contentType,
            template=r'Unexpected content type {1}, allowed values: {0}')
        self.attrs.check_not_none(
            self.mimeType, msg='AdaptationSet@mimeType is a mandatory attribute',
            clause='5.3.7.2')
        if not self.options.encrypted:
            self.elt.check_equal(
                len(self.contentProtection), 0,
                msg='At least one ContentProtection element is required for an encrypted stream')
        futures = []
        for cp in self.contentProtection:
            if self.progress.aborted():
                return
            futures.append(cp.validate())
            self.progress.inc()
        await asyncio.gather(*futures)
