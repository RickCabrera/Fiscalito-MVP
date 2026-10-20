"""une ramas

Revision ID: 02147ff52b0a
Revises: 090fdb7aff5c, b00ee509a2ec
Create Date: 2026-10-19 22:58:18.195528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '02147ff52b0a'
down_revision: Union[str, Sequence[str], None] = ('090fdb7aff5c', 'b00ee509a2ec')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
