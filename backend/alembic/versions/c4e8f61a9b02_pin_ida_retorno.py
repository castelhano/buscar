"""pin_ida_agenda_id / pin_retorno_agenda_id

Revision ID: c4e8f61a9b02
Revises: b7f3a91c2d44
Create Date: 2026-07-11 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8f61a9b02'
down_revision: Union[str, Sequence[str], None] = 'b7f3a91c2d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pin_ida_agenda_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pin_retorno_agenda_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_usuario_agenda_semanal_pin_ida', 'usuario_agenda_semanal', ['pin_ida_agenda_id'], ['id'], ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'fk_usuario_agenda_semanal_pin_retorno', 'usuario_agenda_semanal', ['pin_retorno_agenda_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.drop_constraint('fk_usuario_agenda_semanal_pin_retorno', type_='foreignkey')
        batch_op.drop_constraint('fk_usuario_agenda_semanal_pin_ida', type_='foreignkey')
        batch_op.drop_column('pin_retorno_agenda_id')
        batch_op.drop_column('pin_ida_agenda_id')
