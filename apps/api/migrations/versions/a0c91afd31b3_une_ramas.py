"""une ramas

Revision ID: a0c91afd31b3
Revises: 5ee8544ed166, 88851b633136
Create Date: 2026-10-19 15:25:04.689044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = 'a0c91afd31b3'
down_revision: Union[str, Sequence[str], None] = ('5ee8544ed166', '88851b633136')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
