"""une ramas

Revision ID: 2b7e141b238e
Revises: 213e12e1792b, dc87d3feb8c3
Create Date: 2026-10-19 23:43:53.297435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '2b7e141b238e'
down_revision: Union[str, Sequence[str], None] = ('213e12e1792b', 'dc87d3feb8c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
