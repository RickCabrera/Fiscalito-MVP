"""une ramas

Revision ID: 54b9eb753d72
Revises: a7c1e2d3f4b5, e5e9e5a58627
Create Date: 2026-10-19 16:28:26.368192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '54b9eb753d72'
down_revision: Union[str, Sequence[str], None] = ('a7c1e2d3f4b5', 'e5e9e5a58627')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
