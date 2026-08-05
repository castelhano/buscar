"""rodizio_fim_de_semana_snapshot: guarda o ultimo_condutor_id anterior a uma
geracao de fim de semana, por (data, periodo)

Permite reverter o avanco do rodizio alfabetico de fim de semana quando a
data gerada e limpa (ate aqui so o rodizio de dia util, GrupoRevezamento.deslocamento,
tinha reversao -- ver services.geracao.reverter_rodizio_fim_de_semana).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, Sequence[str], None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rodizio_condutor_fim_de_semana_snapshot',
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('periodo', sa.Enum('MANHA', 'TARDE', name='periodocondutor', native_enum=False, length=20), nullable=False),
        sa.Column('condutor_id_anterior', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['condutor_id_anterior'], ['condutor.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('data', 'periodo'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('rodizio_condutor_fim_de_semana_snapshot')
