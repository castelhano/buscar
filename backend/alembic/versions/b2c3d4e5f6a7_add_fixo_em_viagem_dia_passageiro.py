"""add fixo em viagem_dia_passageiro

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fixo', sa.Boolean(), nullable=False, server_default=sa.true()))

    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.alter_column('fixo', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.drop_column('fixo')
