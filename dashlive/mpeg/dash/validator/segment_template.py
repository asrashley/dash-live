from .multiple_segment_base_type import MultipleSegmentBaseType

class SegmentTemplate(MultipleSegmentBaseType):
    attributes = MultipleSegmentBaseType.attributes + [
        ('media', str, None),
        ('index', str, None),
        ('initialization', str, None),
        ('bitstreamSwitching', str, None),
    ]
    media: str | None
    index: str | None
    initialization: str | None
    startNumber: int

    def __init__(self, template, parent):
        super().__init__(template, parent)
        if self.startNumber is None:
            self.startNumber = 1
