"""split ordem em ordem_ida/ordem_retorno

Revision ID: b7f3a91c2d44
Revises: 895ce65ae638
Create Date: 2026-07-11 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f3a91c2d44'
down_revision: Union[str, Sequence[str], None] = '895ce65ae638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordem_ida', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ordem_retorno', sa.Integer(), nullable=True))

    # preserva o valor curado ate aqui pros dois sentidos -- quem quiser
    # diferenciar Ida de Volta ajusta dai em diante (via modo Base ou edicao manual)
    op.execute("UPDATE usuario_agenda_semanal SET ordem_ida = ordem, ordem_retorno = ordem")

    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.alter_column('ordem_ida', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('ordem_retorno', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('ordem')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordem', sa.Integer(), nullable=True))

    op.execute("UPDATE usuario_agenda_semanal SET ordem = ordem_ida")

    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.alter_column('ordem', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('ordem_ida')
        batch_op.drop_column('ordem_retorno')
