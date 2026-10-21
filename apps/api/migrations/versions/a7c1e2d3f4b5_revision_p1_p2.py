"""revision p1 p2: retenciones al pago

Revision ID: a7c1e2d3f4b5
Revises: 5ee8544ed166
Create Date: 2026-10-19 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.tipos  # noqa: F401 — tipos propios (FechaUTC) que usa el autogenerado

# revision identifiers, used by Alembic.
revision: str = 'a7c1e2d3f4b5'
down_revision: Union[str, Sequence[str], None] = '5ee8544ed166'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('config_contable', schema=None) as batch_op:
        batch_op.add_column(sa.Column('retenciones_al_pago', sa.Boolean(),
                                      server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('config_contable', schema=None) as batch_op:
        batch_op.drop_column('retenciones_al_pago')
