from __future__ import print_function
from typing import cast, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import relationship  # type: ignore

from .db import db
from .mixin import ModelMixin

class Stream(db.Model, ModelMixin):
    """
    Model for each media stream
    """
    __plural__ = 'Streams'
    __tablename__ = 'Stream'

    pk = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String(120))
    directory = sa.Column(sa.String(32), unique=True, index=True)
    marlin_la_url = sa.Column(sa.String(), nullable=True)
    playready_la_url = sa.Column(sa.String(), nullable=True)
    media_files = relationship('MediaFile', cascade="all, delete")

    @classmethod
    def get(cls, **kwargs) -> Optional["Stream"]:
        """
        Get one object from this model, or None if not found
        """
        return cls.get_one(**kwargs)

    @classmethod
    def all(cls) -> List["Stream"]:
        """
        Return all items from this table
        """
        return cast(List["Stream"], cls.get_all())

    def toJSON(self, pure=False):
        return {
            'title': self.title,
            'directory': self.directory,
            'marlin_la_url': self.marlin_la_url,
            'playready_la_url': self.playready_la_url,
        }
