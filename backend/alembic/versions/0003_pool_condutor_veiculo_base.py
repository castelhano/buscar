"""grupo de revezamento carro condutor

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('grupo_revezamento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dia_semana', sa.Enum('SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB', 'DOM', name='diasemana', native_enum=False, length=20), nullable=False),
    sa.Column('rotulo', sa.String(length=100), nullable=True),
    sa.Column('deslocamento', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('grupo_revezamento', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_grupo_revezamento_dia_semana'), ['dia_semana'], unique=False)

    op.create_table('grupo_revezamento_carro',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grupo_revezamento_id', sa.Integer(), nullable=False),
    sa.Column('grupo_base_id', sa.Integer(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['grupo_revezamento_id'], ['grupo_revezamento.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['grupo_base_id'], ['grupo_base.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('grupo_revezamento_id', 'ordem', name='uq_grev_carro_ordem'),
    sa.UniqueConstraint('grupo_base_id', name='uq_grev_carro_grupo_base')
    )

    op.create_table('grupo_revezamento_condutor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grupo_revezamento_id', sa.Integer(), nullable=False),
    sa.Column('condutor_id', sa.Integer(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['grupo_revezamento_id'], ['grupo_revezamento.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['condutor_id'], ['condutor.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('grupo_revezamento_id', 'ordem', name='uq_grev_condutor_ordem'),
    sa.UniqueConstraint('grupo_revezamento_id', 'condutor_id', name='uq_grev_condutor_unico')
    )

    op.create_table('rodizio_condutor_fim_de_semana',
    sa.Column('periodo', sa.Enum('MANHA', 'TARDE', name='periodocondutor', native_enum=False, length=20), nullable=False),
    sa.Column('ultimo_condutor_id', sa.Integer(), nullable=True),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ultimo_condutor_id'], ['condutor.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('periodo')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('rodizio_condutor_fim_de_semana')
    op.drop_table('grupo_revezamento_condutor')
    op.drop_table('grupo_revezamento_carro')
    with op.batch_alter_table('grupo_revezamento', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_grupo_revezamento_dia_semana'))
    op.drop_table('grupo_revezamento')
