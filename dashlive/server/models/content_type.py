#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Optional, cast, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .mixin import ModelMixin
from .session import DatabaseSession

if TYPE_CHECKING:
    from .adaptation_set import AdaptationSet

class ContentType(ModelMixin["ContentType"], Base):
    """
    Table for holding RFC 6838 content types
    """
    __plural__: str = 'ContentTypes'
    __tablename__: str = "content_type"

    pk: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    adaptation_sets: Mapped[list["AdaptationSet"]] = relationship(
        back_populates="content_type"
    )

    @classmethod
    def get(
        cls, session: DatabaseSession | None = None, **kwargs
    ) -> Optional["ContentType"]:
        return cast(Optional[ContentType], cls.get_one(session=session, **kwargs))

    @classmethod
    def populate_if_empty(cls, session: DatabaseSession) -> None:
        count: int = cls.count()
        if count > 0:
            return
        for name in ["application", "video", "audio", "text", "image"]:
            ct = ContentType(name=name)
            session.add(ct)
