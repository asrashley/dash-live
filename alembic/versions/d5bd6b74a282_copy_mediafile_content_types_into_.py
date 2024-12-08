"""copy MediaFile content types into ContentTypes

Revision ID: d5bd6b74a282
Revises: b49e3234ce8a
Create Date: 2024-10-21 12:36:49.106928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from dashlive.server.models.migrations.copy_content_types import CopyContentTypes

# revision identifiers, used by Alembic.
revision: str = 'd5bd6b74a282'
down_revision: Union[str, None] = 'b49e3234ce8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    migration = CopyContentTypes()
    migration.upgrade(session)
    session.commit()


def downgrade() -> None:
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    migration = CopyContentTypes()
    migration.downgrade(session)
    session.commit()
