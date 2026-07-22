"""split capacidade em usuarios/acompanhantes

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('veiculo', schema=None) as batch_op:
        batch_op.drop_constraint('ck_veiculo_capacidade', type_='check')
        batch_op.alter_column('capacidade', new_column_name='capacidade_usuarios')
        batch_op.add_column(sa.Column('capacidade_acompanhantes', sa.Integer(), nullable=False, server_default='2'))
        batch_op.create_check_constraint('ck_veiculo_capacidade_usuarios', 'capacidade_usuarios > 0')
        batch_op.create_check_constraint('ck_veiculo_capacidade_acompanhantes', 'capacidade_acompanhantes >= 0')

    with op.batch_alter_table('veiculo', schema=None) as batch_op:
        batch_op.alter_column('capacidade_acompanhantes', server_default=None)

    with op.batch_alter_table('viagem_dia', schema=None) as batch_op:
        batch_op.drop_constraint('ck_viagem_dia_capacidade', type_='check')
        batch_op.alter_column('capacidade', new_column_name='capacidade_usuarios')
        batch_op.add_column(sa.Column('capacidade_acompanhantes', sa.Integer(), nullable=False, server_default='2'))
        batch_op.create_check_constraint('ck_viagem_dia_capacidade_usuarios', 'capacidade_usuarios > 0')
        batch_op.create_check_constraint('ck_viagem_dia_capacidade_acompanhantes', 'capacidade_acompanhantes >= 0')

    with op.batch_alter_table('viagem_dia', schema=None) as batch_op:
        batch_op.alter_column('capacidade_acompanhantes', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagem_dia', schema=None) as batch_op:
        batch_op.drop_constraint('ck_viagem_dia_capacidade_acompanhantes', type_='check')
        batch_op.drop_constraint('ck_viagem_dia_capacidade_usuarios', type_='check')
        batch_op.drop_column('capacidade_acompanhantes')
        batch_op.alter_column('capacidade_usuarios', new_column_name='capacidade')
        batch_op.create_check_constraint('ck_viagem_dia_capacidade', 'capacidade > 0')

    with op.batch_alter_table('veiculo', schema=None) as batch_op:
        batch_op.drop_constraint('ck_veiculo_capacidade_acompanhantes', type_='check')
        batch_op.drop_constraint('ck_veiculo_capacidade_usuarios', type_='check')
        batch_op.drop_column('capacidade_acompanhantes')
        batch_op.alter_column('capacidade_usuarios', new_column_name='capacidade')
        batch_op.create_check_constraint('ck_veiculo_capacidade', 'capacidade > 0')
