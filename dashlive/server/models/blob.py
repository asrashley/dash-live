from __future__ import print_function
import contextlib
from io import SEEK_SET
from typing import cast, List, Optional
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import relationship  # type: ignore

from dashlive.utils.date_time import toIsoDateTime
from .db import db
from .mixin import ModelMixin
from .session import DatabaseSession

class Blob(db.Model, ModelMixin):
    """
    Database model for a generic file store
    """
    __plural__ = 'Blobs'
    __tablename__ = 'Blob'

    pk = sa.Column('pk', sa.Integer, primary_key=True)
    filename = sa.Column(sa.String, unique=True, nullable=False)
    created = sa.Column(
        'created',
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())
    size = sa.Column(sa.Integer, nullable=False)
    sha1_hash = sa.Column(sa.String(42), nullable=False)
    content_type = sa.Column(sa.String(64), nullable=False)
    auto_delete = sa.Column(sa.Boolean, default=True, nullable=False)
    mediafile = relationship("MediaFile", back_populates="blob")

    @classmethod
    def all(cls, session: DatabaseSession) -> List["Blob"]:
        """
        Return all items from this table
        """
        return cast(List["Blob"], cls.get_all(session))

    def toJSON(self, pure=False):
        rv = self.to_dict()
        if pure:
            rv['created'] = toIsoDateTime(self.created)
        return rv

    def open_file(self, media_directory: Path,
                  start: Optional[int],
                  end: Optional[int],
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
