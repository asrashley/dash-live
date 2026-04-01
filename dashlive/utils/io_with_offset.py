#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from io import BytesIO
from os import SEEK_SET

class BytesIoWithOffset(BytesIO):
    def __init__(self, data: bytes, offset: int) -> None:
        super().__init__(data)
        self.offset = offset

    def tell(self) -> int:
        return self.offset + super().tell()

    def seek(self, pos: int, whence: int = SEEK_SET) -> int:
        if whence == SEEK_SET:
            assert pos >= self.offset, "Cannot seek to position before offset"
            return super().seek(pos - self.offset, whence)
        return super().seek(pos, whence)
