from sqlalchemy import Table, Column, ForeignKey

from .base import Base

mediafile_keys = Table(
    "mediafile_keys",
    Base.metadata,
    Column("media_pk", ForeignKey("media_file.pk"), primary_key=True),
    Column("key_pk", ForeignKey("key.pk"), primary_key=True),
)
