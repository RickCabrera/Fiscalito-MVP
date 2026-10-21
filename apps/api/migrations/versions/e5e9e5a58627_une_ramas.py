"""une ramas

Revision ID: e5e9e5a58627
Revises: 809c4f3a2d85, 8ddb1c856ab7
Create Date: 2026-10-19 16:28:16.100297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = 'e5e9e5a58627'
down_revision: Union[str, Sequence[str], None] = ('809c4f3a2d85', '8ddb1c856ab7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
