"""viagem_perdida: adiciona ViagemDiaPassageiro.viagem_perdida

Flag marcada no modal de cancelamento de atendimento para indicar que a
viagem foi perdida (ex: nao ha como reagendar/repor), usada pro painel de
cancelamentos do dia destacar esses casos separadamente dos demais.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.add_column(sa.Column('viagem_perdida', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.alter_column('viagem_perdida', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.drop_column('viagem_perdida')
