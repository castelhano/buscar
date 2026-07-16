"""usuario_excecao: suspenso vira operacao (enum), data vira intervalo

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_inicio', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('data_fim', sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'operacao',
                sa.Enum('ADICAO', 'MODIFICACAO', 'SUSPENSAO', name='operacaoexcecao', native_enum=False, length=20),
                nullable=True,
            )
        )

    op.execute("UPDATE usuario_excecao SET data_inicio = data, data_fim = data")
    op.execute("UPDATE usuario_excecao SET operacao = CASE WHEN suspenso THEN 'SUSPENSAO' ELSE 'MODIFICACAO' END")

    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.alter_column('data_inicio', nullable=False)
        batch_op.alter_column('data_fim', nullable=False)
        batch_op.alter_column('operacao', nullable=False)
        batch_op.drop_constraint('uq_usuario_excecao_data', type_='unique')
        batch_op.drop_column('data')
        batch_op.drop_column('suspenso')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('suspenso', sa.Boolean(), nullable=True))

    op.execute("UPDATE usuario_excecao SET data = data_inicio")
    op.execute("UPDATE usuario_excecao SET suspenso = (operacao = 'SUSPENSAO')")

    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.alter_column('data', nullable=False)
        batch_op.alter_column('suspenso', nullable=False)
        batch_op.create_unique_constraint('uq_usuario_excecao_data', ['usuario_id', 'data'])
        batch_op.drop_column('data_inicio')
        batch_op.drop_column('data_fim')
        batch_op.drop_column('operacao')
