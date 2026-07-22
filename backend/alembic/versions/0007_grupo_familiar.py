"""grupo familiar

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'grupo_familiar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grupo_familiar_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_usuario_grupo_familiar_id', 'grupo_familiar', ['grupo_familiar_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_constraint('fk_usuario_grupo_familiar_id', type_='foreignkey')
        batch_op.drop_column('grupo_familiar_id')
    op.drop_table('grupo_familiar')
