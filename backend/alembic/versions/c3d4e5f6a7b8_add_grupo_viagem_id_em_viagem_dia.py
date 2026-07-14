"""add grupo_viagem_id em viagem_dia

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-14 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('viagem_dia', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grupo_viagem_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_viagem_dia_grupo_viagem_id', 'viagem_dia', ['grupo_viagem_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagem_dia', schema=None) as batch_op:
        batch_op.drop_constraint('fk_viagem_dia_grupo_viagem_id', type_='foreignkey')
        batch_op.drop_column('grupo_viagem_id')
