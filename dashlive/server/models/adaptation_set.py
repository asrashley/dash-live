#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TYPE_CHECKING, Iterable, Optional, cast

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashlive.mpeg.dash.content_role import ContentRole

from .db import db
from .mediafile import MediaFile
from .mixin import ModelMixin
from .type_decorators import IntEnumType

if TYPE_CHECKING:
    from .period import Period

class AdaptationSet(db.Model, ModelMixin):
    __plural__ = 'AdaptationSets'
    __tablename__ = "adaptation_set"

    pk: Mapped[int] = mapped_column(primary_key=True)
    period_pk: Mapped[int] = mapped_column(sa.ForeignKey("period.pk"))
    period: Mapped["Period"] = relationship(back_populates="adaptation_sets")
    track_id: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[ContentRole] = mapped_column(
        IntEnumType(ContentRole), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    __table_args__ = (sa.UniqueConstraint(
        "period_pk", "track_id", name="single_track_id_per_period"),)

    @classmethod
    def get(cls, **kwargs) -> Optional["AdaptationSet"]:
        return cast(AdaptationSet | None, cls.get_one(**kwargs))

    def media_files(self, encrypted: bool) -> Iterable[MediaFile]:
        stmt = db.select(MediaFile).filter_by(
            stream_pk=self.period.stream.pk, track_id=self.track_id,
            encrypted=encrypted)
        empty: bool = True
        for row in db.session.execute(stmt):
            empty = False
            yield cast(MediaFile, row[0])
        if empty and encrypted:
            stmt = db.select(MediaFile).filter_by(
                stream_pk=self.period.stream.pk, track_id=self.track_id,
                encrypted=False)
            for row in db.session.execute(stmt):
                yield cast(MediaFile, row[0])
