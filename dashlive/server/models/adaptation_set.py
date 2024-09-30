#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TYPE_CHECKING, AbstractSet, Iterable, Optional, cast

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashlive.mpeg.dash.content_role import ContentRole
from dashlive.utils.json_object import JsonObject

from .content_type import ContentType
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
    content_type_pk: Mapped[int] = mapped_column(sa.ForeignKey("content_type.pk"))
    content_type: Mapped[ContentType] = relationship(back_populates="adaptation_sets")
    encrypted: Mapped[bool] = mapped_column(default=False)
    lang: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)

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

    def to_dict(self, exclude: AbstractSet[str] | None = None,
                only: AbstractSet[str] | None = None,
                with_collections: bool = False) -> JsonObject:
        rv: JsonObject = super().to_dict(
            exclude=exclude, only=only, with_collections=with_collections)
        if 'role' in rv:
            rv['role'] = self.role.name.lower()
        return rv
