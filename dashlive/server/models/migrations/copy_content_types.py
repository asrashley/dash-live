#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from .data_migration import DataMigration

from sqlalchemy import distinct

from ..content_type import ContentType
from ..db import db
from ..mediafile import MediaFile
from ..session import DatabaseSession

class CopyContentTypes(DataMigration):
    """
    Add entries into the ContentType table for all MediaFile content types.
    """

    def upgrade(self, session: DatabaseSession) -> None:
        stmt = db.select(distinct(MediaFile.content_type))
        for row in session.execute(stmt):
            name: str | None = row[0]
            if name is None:
                continue
            ct = ContentType.get(name=name, session=session)
            if ct is not None:
                continue
            ct = ContentType(name=name)
            session.add(ct)

    def downgrade(self, session: DatabaseSession) -> None:
        pass
