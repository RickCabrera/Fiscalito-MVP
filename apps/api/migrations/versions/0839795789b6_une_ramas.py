"""une ramas

Revision ID: 0839795789b6
Revises: 167b4a092fe7, 2b7e141b238e
Create Date: 2026-10-19 23:53:06.754932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '0839795789b6'
down_revision: Union[str, Sequence[str], None] = ('167b4a092fe7', '2b7e141b238e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
