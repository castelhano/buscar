"""pontos: origem/destino de um trecho ganham tipo (Local/Usuario/Avulso)

Generaliza origem (que so podia ser texto livre) e destino (que ja podia ser
Local OU texto livre) pro mesmo modelo de "ponto" com tipo -- ver
`app.models.TipoPonto`:

- LOCAL: um `Local` cadastrado (rotulo/endereco/regiao vem de la) -- origem
  ganha essa opcao pela primeira vez (`origem_id`, nova FK pra `local.id`).
- USUARIO: o endereco principal do proprio usuario do atendimento
  (`Usuario.abbr`/`detalhe`/`regiao_id`, novo campo) -- sem precisar
  redigitar em cada trecho.
- AVULSO: endereco livre (rotulo em `*_texto` + endereco completo opcional em
  `*_detalhe`, novo campo -- antes so existia pro destino, e sem endereco
  detalhado proprio).

Migracao de dados (preserva o texto/endereco exibido hoje, sem tentar
adivinhar quais origens "sao" o endereco do usuario -- isso fica pra o
operador migrar manualmente, trecho a trecho, quando quiser o beneficio de
nao redigitar):
- destino com `destino_id` preenchido -> `destino_tipo=LOCAL`.
- destino em texto livre -> `destino_tipo=AVULSO` (detalhe fica em branco,
  igual a exibicao atual, que nunca teve endereco detalhado pro destino
  avulso).
- origem em texto livre -> `origem_tipo=AVULSO`, com `origem_detalhe`
  preenchido com o `Usuario.detalhe` atual (snapshot) -- reproduz
  exatamente o que `_dados_origem` exibia ate aqui (usava
  `usuario.detalhe` como subtexto de QUALQUER origem preenchida,
  independente do que ela representava -- o bug que motivou esta migracao).
- origem em branco (herda do trecho anterior) -> `origem_tipo=NULL`,
  comportamento inalterado.

Downgrade: descarta a distincao LOCAL/AVULSO da origem (achata pra texto
livre, perdendo o vinculo com o Local) e sintetiza texto a partir do usuario
pra qualquer ponto USUARIO (unico jeito de representar isso no modelo
antigo, que nao tinha esse conceito) -- lossy nesses dois casos se o sistema
ja tiver dados usando as funcionalidades novas antes de um rollback.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TIPO_PONTO = sa.Enum('LOCAL', 'USUARIO', 'AVULSO', name='tipoponto', native_enum=False, length=20)


def _adicionar_colunas_ponto(nome_tabela: str) -> None:
    with op.batch_alter_table(nome_tabela, schema=None) as batch_op:
        batch_op.alter_column('origem', new_column_name='origem_texto', existing_type=sa.String(length=200))
        batch_op.add_column(sa.Column('origem_tipo', _TIPO_PONTO, nullable=True))
        batch_op.add_column(sa.Column('origem_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('origem_detalhe', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('destino_tipo', _TIPO_PONTO, nullable=True))
        batch_op.add_column(sa.Column('destino_detalhe', sa.Text(), nullable=True))
        batch_op.create_foreign_key(f'fk_{nome_tabela}_origem_id', 'local', ['origem_id'], ['id'])


def _backfill_destino_tipo(conn, nome_tabela: str) -> None:
    sem_destino = conn.execute(sa.text(
        f"SELECT COUNT(*) FROM {nome_tabela} WHERE destino_id IS NULL AND (destino_texto IS NULL OR destino_texto = '')"
    )).scalar()
    if sem_destino:
        raise RuntimeError(
            f"Migracao 0009 abortada: {sem_destino} linha(s) de {nome_tabela} sem destino_id nem destino_texto "
            "(viola a invariante 'exatamente um dos dois' que ja era esperada antes desta migracao)."
        )
    conn.execute(sa.text(f"UPDATE {nome_tabela} SET destino_tipo = 'LOCAL' WHERE destino_id IS NOT NULL"))
    conn.execute(sa.text(f"UPDATE {nome_tabela} SET destino_tipo = 'AVULSO' WHERE destino_id IS NULL"))
    with op.batch_alter_table(nome_tabela, schema=None) as batch_op:
        batch_op.alter_column('destino_tipo', existing_type=_TIPO_PONTO, nullable=False)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('regiao_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_usuario_regiao_id', 'regiao', ['regiao_id'], ['id'])

    # ------------------------------------------------------------------
    # usuario_agenda_semanal_trecho
    # ------------------------------------------------------------------
    _adicionar_colunas_ponto('usuario_agenda_semanal_trecho')
    detalhe_por_agenda = dict(conn.execute(sa.text(
        "SELECT a.id, u.detalhe FROM usuario_agenda_semanal a JOIN usuario u ON u.id = a.usuario_id"
    )).all())
    origens = conn.execute(sa.text(
        "SELECT id, agenda_id FROM usuario_agenda_semanal_trecho WHERE origem_texto IS NOT NULL AND origem_texto != ''"
    )).mappings().all()
    if origens:
        conn.execute(sa.text(
            "UPDATE usuario_agenda_semanal_trecho SET origem_tipo = 'AVULSO', origem_detalhe = :detalhe WHERE id = :id"
        ), [dict(id=o["id"], detalhe=detalhe_por_agenda.get(o["agenda_id"])) for o in origens])
    _backfill_destino_tipo(conn, 'usuario_agenda_semanal_trecho')

    # ------------------------------------------------------------------
    # usuario_excecao_trecho
    # ------------------------------------------------------------------
    _adicionar_colunas_ponto('usuario_excecao_trecho')
    detalhe_por_excecao = dict(conn.execute(sa.text(
        "SELECT e.id, u.detalhe FROM usuario_excecao e JOIN usuario u ON u.id = e.usuario_id"
    )).all())
    origens = conn.execute(sa.text(
        "SELECT id, excecao_id FROM usuario_excecao_trecho WHERE origem_texto IS NOT NULL AND origem_texto != ''"
    )).mappings().all()
    if origens:
        conn.execute(sa.text(
            "UPDATE usuario_excecao_trecho SET origem_tipo = 'AVULSO', origem_detalhe = :detalhe WHERE id = :id"
        ), [dict(id=o["id"], detalhe=detalhe_por_excecao.get(o["excecao_id"])) for o in origens])
    _backfill_destino_tipo(conn, 'usuario_excecao_trecho')

    # ------------------------------------------------------------------
    # viagem_dia_passageiro (ja e um trecho materializado -- usuario_id direto)
    # ------------------------------------------------------------------
    _adicionar_colunas_ponto('viagem_dia_passageiro')
    detalhe_por_usuario = dict(conn.execute(sa.text("SELECT id, detalhe FROM usuario")).all())
    origens = conn.execute(sa.text(
        "SELECT id, usuario_id FROM viagem_dia_passageiro WHERE origem_texto IS NOT NULL AND origem_texto != ''"
    )).mappings().all()
    if origens:
        conn.execute(sa.text(
            "UPDATE viagem_dia_passageiro SET origem_tipo = 'AVULSO', origem_detalhe = :detalhe WHERE id = :id"
        ), [dict(id=o["id"], detalhe=detalhe_por_usuario.get(o["usuario_id"])) for o in origens])
    _backfill_destino_tipo(conn, 'viagem_dia_passageiro')


def downgrade() -> None:
    """Downgrade schema.

    Lossy quando ha pontos do tipo USUARIO (sintetizados como texto livre a
    partir do cadastro do usuario, unica forma de representa-los no modelo
    antigo) ou origem do tipo LOCAL (achatada pra texto livre, perdendo o
    vinculo com o Local -- a origem antiga nunca podia ser um Local).
    """
    conn = op.get_bind()

    # Resolve o "rotulo" de um ponto do tipo USUARIO/LOCAL de volta pra texto
    # livre, pra caber na coluna antiga (que so aceitava texto). Local usa o
    # nome cadastrado; Usuario usa abbr/nome (mais estavel que o endereco
    # completo pra exibir num card).
    locais_nome = dict(conn.execute(sa.text("SELECT id, nome FROM local")).all())
    usuarios = conn.execute(sa.text("SELECT id, abbr, nome FROM usuario")).mappings().all()
    usuarios_por_id = {u["id"]: u for u in usuarios}

    def _nome_usuario(usuario_id) -> str | None:
        u = usuarios_por_id.get(usuario_id)
        return (u["abbr"] or u["nome"]) if u else None

    def _achatar_origem(tipo, origem_id, texto, usuario_id) -> str | None:
        if tipo == 'LOCAL':
            return locais_nome.get(origem_id)
        if tipo == 'USUARIO':
            return _nome_usuario(usuario_id)
        return texto  # AVULSO ou None (herda) -- None vira NULL, igual antes

    for nome_tabela, usuario_ref in (
        ('usuario_agenda_semanal_trecho', ('usuario_agenda_semanal', 'agenda_id')),
        ('usuario_excecao_trecho', ('usuario_excecao', 'excecao_id')),
        ('viagem_dia_passageiro', None),
    ):
        if usuario_ref is not None:
            tabela_pai, campo_fk = usuario_ref
            usuario_por_pai_id = dict(conn.execute(sa.text(f"SELECT id, usuario_id FROM {tabela_pai}")).all())
            linhas = conn.execute(sa.text(
                f"SELECT id, {campo_fk} AS pai_id, origem_tipo, origem_id, origem_texto, destino_tipo FROM {nome_tabela}"
            )).mappings().all()
            usuario_id_de = lambda linha: usuario_por_pai_id.get(linha["pai_id"])
        else:
            linhas = conn.execute(sa.text(
                "SELECT id, usuario_id, origem_tipo, origem_id, origem_texto, destino_tipo FROM viagem_dia_passageiro"
            )).mappings().all()
            usuario_id_de = lambda linha: linha["usuario_id"]

        atualizacoes = [
            dict(id=l["id"], origem=_achatar_origem(l["origem_tipo"], l["origem_id"], l["origem_texto"], usuario_id_de(l)))
            for l in linhas
        ]
        if atualizacoes:
            conn.execute(sa.text(f"UPDATE {nome_tabela} SET origem_texto = :origem WHERE id = :id"), atualizacoes)

        # destino_texto: pontos USUARIO tambem precisam ser achatados (LOCAL ja usa destino_id, sem mudanca).
        atualizacoes_destino = [
            dict(id=l["id"], destino_texto=_nome_usuario(usuario_id_de(l)))
            for l in linhas
            if l["destino_tipo"] == 'USUARIO'
        ]
        if atualizacoes_destino:
            conn.execute(
                sa.text(f"UPDATE {nome_tabela} SET destino_id = NULL, destino_texto = :destino_texto WHERE id = :id"),
                atualizacoes_destino,
            )

        with op.batch_alter_table(nome_tabela, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{nome_tabela}_origem_id', type_='foreignkey')
            batch_op.drop_column('origem_tipo')
            batch_op.drop_column('origem_id')
            batch_op.drop_column('origem_detalhe')
            batch_op.drop_column('destino_tipo')
            batch_op.drop_column('destino_detalhe')
            batch_op.alter_column('origem_texto', new_column_name='origem', existing_type=sa.String(length=200))

    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_constraint('fk_usuario_regiao_id', type_='foreignkey')
        batch_op.drop_column('regiao_id')
