from typing import cast, Optional

import sqlalchemy as sa
from sqlalchemy.orm import relationship  # type: ignore
import sqlalchemy_jsonfield  # type: ignore

from dashlive.utils.json_object import JsonObject
from dashlive.mpeg.dash.reference import StreamTimingReference
from .db import db
from .mediafile import MediaFile
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
    timing_ref = sa.Column(
        'timing_reference',
        sqlalchemy_jsonfield.JSONField(
            enforce_string=True,
            enforce_unicode=False
        ),
        nullable=True)

    @classmethod
    def get(cls, **kwargs) -> Optional["Stream"]:
        """
        Get one object from this model, or None if not found
        """
        return cls.get_one(**kwargs)

    @classmethod
    def all(cls) -> list["Stream"]:
        """
        Return all items from this table
        """
        return cast(list["Stream"], cls.get_all())

    def toJSON(self, pure=False):
        timing_ref: str | None = None
        if self.timing_ref is not None:
            timing_ref = self.timing_ref['media_name']
        return {
            'pk': self.pk,
            'title': self.title,
            'directory': self.directory,
            'marlin_la_url': self.marlin_la_url,
            'playready_la_url': self.playready_la_url,
            'timing_ref': timing_ref,
        }

    def get_fields(self, **kwargs) -> list[JsonObject]:
        def str_or_none(value):
            if value is None:
                return ''
            return value

        has_media_files = False
        if self.pk:
            has_media_files = MediaFile.count(stream=self) > 0
        return [{
            "name": "title",
            "title": "Title",
            "type": "text",
            "maxlength": 100,
            "value": kwargs.get("title", self.title),
        }, {
            "name": "directory",
            "title": "Directory",
            "type": "text",
            "pattern": "[A-Za-z0-9]+",
            "minlength": 3,
            "maxlength": 30,
            "disabled": has_media_files,
            "value": kwargs.get("directory", self.directory),
        }, {
            "name": "marlin_la_url",
            "title": "Marlin LA URL",
            "type": "url",
            "pattern": "((ms3[hsa]*)|(https?))://.*",
            "value": str_or_none(kwargs.get("marlin_la_url", self.marlin_la_url)),
        }, {
            "name": "playready_la_url",
            "title": "PlayReady LA URL",
            "type": "url",
            "pattern": "https?://.*",
            "value": str_or_none(kwargs.get("playready_la_url", self.playready_la_url)),
        }]

    def get_timing_reference(self) -> StreamTimingReference | None:
        if self.timing_ref is None:
            return None
        try:
            return StreamTimingReference(**self.timing_ref)
        except TypeError:
            return None

    def set_timing_reference(
            self, ref: StreamTimingReference | None) -> None:
        if ref is None:
            self.timing_ref = None
        else:
            self.timing_ref = ref.toJSON()

    timing_reference = property(get_timing_reference, set_timing_reference)
