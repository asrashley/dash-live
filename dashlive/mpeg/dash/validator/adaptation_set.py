#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from .exceptions import ValidationException
from .frame_rate_type import FrameRateType
from .representation_base_type import RepresentationBaseType
from .representation import Representation

class AdaptationSet(RepresentationBaseType):
    attributes = RepresentationBaseType.attributes + [
        ('group', int, None),
        ('lang', str, None),
        ('contentType', str, None),
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

    def validate(self, depth: int = -1) -> None:
        if len(self.contentProtection):
            self.checkIsNotNone(
                self.default_KID,
                f'default_KID cannot be missing for protected stream: {self.baseurl}')
        self.checkIn(
            self.contentType,
            {'video', 'audio', 'text', 'image', 'font', 'application', None})
        if self.options.strict:
            self.checkIsNotNone(self.mimeType, 'mimeType is a mandatory attribute')
        if self.mimeType is None:
            self.log.warning('mimeType is a mandatory attribute')
        if not self.options.encrypted:
            self.checkEqual(len(self.contentProtection), 0)
        if depth == 0:
            return
        for cp in self.contentProtection:
            cp.validate(depth - 1)
        for rep in self.representations:
            try:
                rep.validate(depth - 1)
            except (AssertionError, ValidationException) as err:
                if self.options.strict:
                    raise
                self.log.error(err, exc_info=err)
