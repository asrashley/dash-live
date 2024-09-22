#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db
from .error_reason import ErrorReason
from .mixin import ModelMixin
from .type_decorators import IntEnumType

class MediaFileError(db.Model, ModelMixin):
    __plural__ = 'MediaFileErrors'

    pk: Mapped[int] = sa.Column('pk', sa.Integer, primary_key=True)
    reason: Mapped[ErrorReason] = mapped_column(IntEnumType(ErrorReason), nullable=False)
    details: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    media_pk: Mapped[int] = mapped_column(sa.ForeignKey('media_file.pk'))
    media_file: Mapped["MediaFile"] = relationship(back_populates='errors')  # noqa

    __table_args__ = (sa.UniqueConstraint(
        "reason", "media_pk", name="single_reason_per_file"),)

    def __str__(self) -> str:
        return f'{self.reason.name}: {self.media_file.name} - {self.details}'
