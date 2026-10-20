"""une ramas

Revision ID: e5edf6d55a23
Revises: 54b9eb753d72, 7d3c6b0aac7b
Create Date: 2026-10-19 16:47:36.095371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = 'e5edf6d55a23'
down_revision: Union[str, Sequence[str], None] = ('54b9eb753d72', '7d3c6b0aac7b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
