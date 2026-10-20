"""une ramas

Revision ID: 090fdb7aff5c
Revises: 660f7c46ab37, d817ede1bbb3
Create Date: 2026-10-19 22:51:53.325064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '090fdb7aff5c'
down_revision: Union[str, Sequence[str], None] = ('660f7c46ab37', 'd817ede1bbb3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
