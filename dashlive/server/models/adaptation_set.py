#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TYPE_CHECKING, AbstractSet, Iterable, Optional, TypedDict, cast

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dashlive.mpeg.dash.content_role import ContentRole

from .base import Base
from .content_type import ContentType
from .db import db
from .mixin import ModelMixin
from .mediafile import MediaFile
from .type_decorators import IntEnumType

if TYPE_CHECKING:
    from .period import Period

class AdaptationSetJson(TypedDict):
    pk: int
    period_pk: int
    track_id: int
    role: str
    codec_fourcc: str | None
    content_type: str
    encrypted: bool
    lang: str | None

class AdaptationSet(ModelMixin["AdaptationSet"], Base):
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

    def media_files(self, encrypted: bool | None = None) -> Iterable[MediaFile]:
        if self.period.stream is None:
            return []
        stmt = db.select(MediaFile).filter_by(
            stream_pk=self.period.stream.pk, track_id=self.track_id)
        if encrypted is not None:
            stmt = stmt.filter_by(encrypted=encrypted)
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

    def codec_fourcc(self) -> str | None:
        for mf in self.media_files():
            if mf.codec_fourcc:
                return mf.codec_fourcc
        return None

    def to_dict(self, exclude: AbstractSet[str] | None = None,
                only: AbstractSet[str] | None = None,
                with_collections: bool = False) -> AdaptationSetJson:
        rv: AdaptationSetJson = cast(AdaptationSetJson, super().to_dict(
            exclude=exclude, only=only, with_collections=with_collections))
        if 'role' in rv:
            rv['role'] = self.role.name.lower()
        return rv
