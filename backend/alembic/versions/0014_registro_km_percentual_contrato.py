"""registro_km_percentual_contrato: novo controle de odometro por veiculo
(RegistroKm) e campo percentual_contrato em Empresa, base pra tela Resumos.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, Sequence[str], None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('empresa', sa.Column('percentual_contrato', sa.Float(), nullable=False, server_default='0'))

    op.create_table(
        'registro_km',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), nullable=False),
        sa.Column('data_inicio', sa.Date(), nullable=False),
        sa.Column('data_fim', sa.Date(), nullable=False),
        sa.Column('km_inicial', sa.Integer(), nullable=False),
        sa.Column('km_final', sa.Integer(), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['veiculo_id'], ['veiculo.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('data_fim >= data_inicio', name='ck_registro_km_periodo'),
        sa.CheckConstraint('km_final IS NULL OR km_final >= km_inicial', name='ck_registro_km_valores'),
    )
    op.create_index('ix_registro_km_veiculo_periodo', 'registro_km', ['veiculo_id', 'data_inicio', 'data_fim'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_registro_km_veiculo_periodo', table_name='registro_km')
    op.drop_table('registro_km')
    op.drop_column('empresa', 'percentual_contrato')
