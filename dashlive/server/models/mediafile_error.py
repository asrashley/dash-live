#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import ClassVar, TYPE_CHECKING
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .error_reason import ErrorReason
from .mixin import ModelMixin
from .type_decorators import IntEnumType

if TYPE_CHECKING:
    from .mediafile import MediaFile

class MediaFileError(ModelMixin["MediaFileError"], Base):
    __plural__: ClassVar[str] = 'MediaFileErrors'
    __tablename__: ClassVar[str] = 'media_file_error'

    pk: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    reason: Mapped[ErrorReason] = mapped_column(IntEnumType(ErrorReason), nullable=False)
    details: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    media_pk: Mapped[int] = mapped_column(sa.ForeignKey('media_file.pk'))
    media_file: Mapped["MediaFile"] = relationship(back_populates='errors')  # noqa

    __table_args__ = (sa.UniqueConstraint(
        "reason", "media_pk", name="single_reason_per_file"),)

    def __str__(self) -> str:
        return f'{self.reason.name}: {self.media_file.name} - {self.details}'
