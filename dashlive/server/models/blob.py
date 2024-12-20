#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import contextlib
from datetime import datetime
from io import SEEK_SET
from pathlib import Path
from typing import cast, AbstractSet, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import relationship, Mapped, mapped_column

from dashlive.utils.date_time import to_iso_datetime
from dashlive.utils.json_object import JsonObject

from .base import Base
from .mixin import ModelMixin

if TYPE_CHECKING:
    from .mediafile import MediaFile

class Blob(ModelMixin["Blob"], Base):
    """
    Database model for a generic file store
    """
    __plural__ = 'Blobs'
    __tablename__ = 'Blob'

    pk: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(sa.String, unique=True, nullable=False)
    created: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())
    size: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sha1_hash: Mapped[str] = mapped_column(sa.String(42), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    auto_delete: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    mediafile: Mapped["MediaFile"] = relationship("MediaFile", back_populates="blob")

    @classmethod
    def all(cls) -> list["Blob"]:
        """
        Return all items from this table
        """
        return cast(list["Blob"], cls.get_all())

    def toJSON(self, pure: bool = False,
               exclude: AbstractSet | None = None) -> JsonObject:
        rv = self.to_dict()
        if pure:
            rv['created'] = to_iso_datetime(self.created)
        if exclude:
            for k in rv.keys():
                if k in exclude:
                    del rv[k]
        return rv

    def open_file(self, media_directory: Path,
                  start: int | None,
                  buffer_size: int) -> contextlib.AbstractContextManager:
        filename = media_directory / self.filename
        handle = open(filename, mode='rb', buffering=buffer_size)
        if start is not None:
            handle.seek(start, SEEK_SET)
        return contextlib.closing(handle)

    def delete_file(self, media_directory: Path) -> None:
        if self.auto_delete:
            file_path = media_directory / self.filename
            file_path.unlink(missing_ok=True)
