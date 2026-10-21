"""une p2 reportes y conciliacion

Revision ID: 5ee8544ed166
Revises: 885d10b0a6f5, f9fe7d2ec2b7
Create Date: 2026-10-19 15:21:07.820901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado


# revision identifiers, used by Alembic.
revision: str = '5ee8544ed166'
down_revision: Union[str, Sequence[str], None] = ('885d10b0a6f5', 'f9fe7d2ec2b7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
