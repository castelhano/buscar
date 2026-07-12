"""modo base: grupo_base / viagem_base / membro_viagem_base

Revision ID: d1a2b3c4e5f6
Revises: 895ce65ae638
Create Date: 2026-07-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = '895ce65ae638'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'grupo_base',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dia_semana', sa.String(length=20), nullable=False),
        sa.Column('rotulo', sa.String(length=100), nullable=True),
        sa.Column('ordem_exibicao', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_grupo_base_dia_semana'), 'grupo_base', ['dia_semana'], unique=False)

    op.create_table(
        'viagem_base',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grupo_base_id', sa.Integer(), nullable=False),
        sa.Column('sentido', sa.String(length=20), nullable=False),
        sa.Column('hora', sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(['grupo_base_id'], ['grupo_base.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('grupo_base_id', 'sentido', 'hora', name='uq_viagem_base_horario'),
    )

    op.create_table(
        'membro_viagem_base',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('viagem_base_id', sa.Integer(), nullable=False),
        sa.Column('agenda_id', sa.Integer(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['viagem_base_id'], ['viagem_base.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agenda_id'], ['usuario_agenda_semanal.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('viagem_base_id', 'agenda_id', name='uq_membro_viagem_base'),
    )

    # `ordem` original do schema inicial (prioridade global de preenchimento)
    # nunca fazia sentido pro modo Base de verdade -- o agrupamento agora e
    # explicito (grupo_base/viagem_base/membro_viagem_base), entao esse
    # campo nao tem mais uso nenhum.
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.drop_column('ordem')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordem', sa.Integer(), nullable=False, server_default='0'))

    op.drop_table('membro_viagem_base')
    op.drop_table('viagem_base')
    op.drop_index(op.f('ix_grupo_base_dia_semana'), table_name='grupo_base')
    op.drop_table('grupo_base')
