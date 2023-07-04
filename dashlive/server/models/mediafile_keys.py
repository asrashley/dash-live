from .db import db

mediafile_keys = db.Table(
    "mediafile_keys",
    db.Column("media_pk", db.ForeignKey("media_file.pk"), primary_key=True),
    db.Column("key_pk", db.ForeignKey("key.pk"), primary_key=True),
)
