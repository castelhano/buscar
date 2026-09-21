"""cancelado_pela_empresa: adiciona ViagemDiaPassageiro.cancelado_pela_empresa

Flag marcada no modal de cancelamento de atendimento para indicar que o
cancelamento foi motivado pela empresa (nao pelo usuario/passageiro), usada
pro painel de cancelamentos do dia destacar esses casos e pra excluir essas
ocorrencias do historico de cancelamento do usuario nos resumos/relatorios.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, Sequence[str], None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancelado_pela_empresa', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.alter_column('cancelado_pela_empresa', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.drop_column('cancelado_pela_empresa')
