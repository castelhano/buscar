"""trechos: generaliza Sentido (Ida/Retorno) para lista ordenada de trechos

Substitui o enum binario `Sentido` + par fixo origem/destino por uma lista
ordenada de trechos (`ordem` 0-based), tanto na configuracao recorrente
(`UsuarioAgendaSemanal`/`UsuarioExcecao`, que ganham tabelas filhas
`*_trecho`) quanto na execucao do dia (`ViagemDiaPassageiro`, que ja e um
trecho materializado -- so ganha `ordem_trecho`/`destino_texto`) e no modo
Base (`ViagemBase` perde `sentido`; `MembroViagemBase` passa a apontar direto
pro trecho via `agenda_trecho_id`).

A migracao de dados aplica, de forma permanente, a troca origem<->destino que
ate aqui só acontecia em tempo de leitura (`_dados_origem`/`_dados_destino` em
`app/services/exportacao.py`) para as linhas que eram "Retorno": o destino
antigo (Local) vira a nova origem "implicita" (deixada em branco, herdada do
trecho anterior) e a origem antiga (endereco/casa) vira `destino_texto` do
novo trecho.

Para `UsuarioExcecao` do tipo MODIFICACAO, a migracao replica fielmente a
logica de merge campo-a-campo com o Fixo que existia em
`geracao._adicionar_pernas` (usando o Fixo do dia da semana de `data_inicio`,
quando existir) -- preservando o resultado ja efetivo de cada excecao
historica. Daqui pra frente (fora desta migracao), MODIFICACAO passa a
substituir a lista de trechos inteira, sem merge automatico (ver plano).

Limitacao do downgrade: reconstroi so os 2 primeiros trechos (ordem 0 e 1) de
cada agenda/excecao/dia -- trechos extras (N>2) sao perdidos se o sistema
rodar em producao com itinerarios maiores antes de um rollback.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-23 00:00:00.000000

"""
import datetime as dt
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DIA_POR_WEEKDAY = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]


def _as_date(value) -> dt.date:
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1) tabelas novas de trecho (config recorrente)
    # ------------------------------------------------------------------
    op.create_table(
        'usuario_agenda_semanal_trecho',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agenda_id', sa.Integer(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('hora', sa.Time(), nullable=False),
        sa.Column('origem', sa.String(length=200), nullable=True),
        sa.Column('regiao_origem_id', sa.Integer(), nullable=True),
        sa.Column('destino_id', sa.Integer(), nullable=True),
        sa.Column('destino_texto', sa.String(length=200), nullable=True),
        sa.Column('regiao_destino_id', sa.Integer(), nullable=True),
        sa.Column('acompanhante', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['agenda_id'], ['usuario_agenda_semanal.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destino_id'], ['local.id']),
        sa.ForeignKeyConstraint(['regiao_origem_id'], ['regiao.id']),
        sa.ForeignKeyConstraint(['regiao_destino_id'], ['regiao.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agenda_id', 'ordem', name='uq_agenda_trecho_ordem'),
    )
    op.create_table(
        'usuario_excecao_trecho',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('excecao_id', sa.Integer(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('hora', sa.Time(), nullable=False),
        sa.Column('origem', sa.String(length=200), nullable=True),
        sa.Column('regiao_origem_id', sa.Integer(), nullable=True),
        sa.Column('destino_id', sa.Integer(), nullable=True),
        sa.Column('destino_texto', sa.String(length=200), nullable=True),
        sa.Column('regiao_destino_id', sa.Integer(), nullable=True),
        sa.Column('acompanhante', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['excecao_id'], ['usuario_excecao.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destino_id'], ['local.id']),
        sa.ForeignKeyConstraint(['regiao_origem_id'], ['regiao.id']),
        sa.ForeignKeyConstraint(['regiao_destino_id'], ['regiao.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('excecao_id', 'ordem', name='uq_excecao_trecho_ordem'),
    )

    locais_regiao = dict(conn.execute(sa.text("SELECT id, regiao_id FROM local")).all())

    # ------------------------------------------------------------------
    # 2) popular usuario_agenda_semanal_trecho (Fixo -- mecanico, sem merge)
    # ------------------------------------------------------------------
    agendas = conn.execute(sa.text(
        "SELECT id, usuario_id, dia_semana, saida, retorno, origem, regiao_origem_id, destino_id, acompanhante "
        "FROM usuario_agenda_semanal"
    )).mappings().all()

    agenda_trecho_rows = []
    for a in agendas:
        ordem = 0
        if a["saida"] is not None:
            agenda_trecho_rows.append(dict(
                agenda_id=a["id"], ordem=0, hora=a["saida"],
                origem=a["origem"], regiao_origem_id=a["regiao_origem_id"], destino_id=a["destino_id"],
                destino_texto=None, regiao_destino_id=locais_regiao.get(a["destino_id"]),
                acompanhante=bool(a["acompanhante"]),
            ))
            ordem = 1
        if a["retorno"] is not None:
            agenda_trecho_rows.append(dict(
                agenda_id=a["id"], ordem=ordem, hora=a["retorno"],
                origem=None, regiao_origem_id=None, destino_id=None,
                destino_texto=a["origem"], regiao_destino_id=a["regiao_origem_id"],
                acompanhante=bool(a["acompanhante"]),
            ))

    if agenda_trecho_rows:
        conn.execute(sa.text(
            "INSERT INTO usuario_agenda_semanal_trecho "
            "(agenda_id, ordem, hora, origem, regiao_origem_id, destino_id, destino_texto, regiao_destino_id, acompanhante) "
            "VALUES (:agenda_id, :ordem, :hora, :origem, :regiao_origem_id, :destino_id, :destino_texto, :regiao_destino_id, :acompanhante)"
        ), agenda_trecho_rows)

    # ------------------------------------------------------------------
    # 3) popular usuario_excecao_trecho, replicando o merge de
    #    `geracao._adicionar_pernas`: MODIFICACAO usa o Fixo do dia da
    #    semana de `data_inicio` quando existir; ADICAO/SUSPENSAO nunca
    #    fazem merge (SUSPENSAO nao gera nenhum trecho).
    # ------------------------------------------------------------------
    agenda_por_usuario_dia = {(a["usuario_id"], a["dia_semana"]): a for a in agendas}

    excecoes = conn.execute(sa.text(
        "SELECT id, usuario_id, data_inicio, operacao, saida, retorno, origem, regiao_origem_id, "
        "destino_id, acompanhante FROM usuario_excecao"
    )).mappings().all()

    excecao_trecho_rows = []
    for e in excecoes:
        if e["operacao"] == "SUSPENSAO":
            continue

        agenda = None
        if e["operacao"] == "MODIFICACAO":
            dia = DIA_POR_WEEKDAY[_as_date(e["data_inicio"]).weekday()]
            agenda = agenda_por_usuario_dia.get((e["usuario_id"], dia))

        origem = e["origem"] or (agenda["origem"] if agenda else None)
        regiao_origem_id = e["regiao_origem_id"] or (agenda["regiao_origem_id"] if agenda else None)
        destino_id = e["destino_id"] or (agenda["destino_id"] if agenda else None)
        acompanhante = e["acompanhante"] if e["acompanhante"] is not None else (agenda["acompanhante"] if agenda else False)
        regiao_destino_id_ida = locais_regiao.get(destino_id) if destino_id else None

        ordem = 0
        saida_hora = e["saida"] or (agenda["saida"] if agenda else None)
        if saida_hora is not None:
            excecao_trecho_rows.append(dict(
                excecao_id=e["id"], ordem=0, hora=saida_hora,
                origem=origem, regiao_origem_id=regiao_origem_id, destino_id=destino_id,
                destino_texto=None, regiao_destino_id=regiao_destino_id_ida,
                acompanhante=bool(acompanhante),
            ))
            ordem = 1
        retorno_hora = e["retorno"] or (agenda["retorno"] if agenda else None)
        if retorno_hora is not None:
            excecao_trecho_rows.append(dict(
                excecao_id=e["id"], ordem=ordem, hora=retorno_hora,
                origem=None, regiao_origem_id=None, destino_id=None,
                destino_texto=origem, regiao_destino_id=regiao_origem_id,
                acompanhante=bool(acompanhante),
            ))

    if excecao_trecho_rows:
        conn.execute(sa.text(
            "INSERT INTO usuario_excecao_trecho "
            "(excecao_id, ordem, hora, origem, regiao_origem_id, destino_id, destino_texto, regiao_destino_id, acompanhante) "
            "VALUES (:excecao_id, :ordem, :hora, :origem, :regiao_origem_id, :destino_id, :destino_texto, :regiao_destino_id, :acompanhante)"
        ), excecao_trecho_rows)

    # ------------------------------------------------------------------
    # 4) checagem defensiva antes de mexer em viagem_base: colisao de
    #    horario dentro do mesmo grupo_base (Ida e Retorno na mesma hora)
    #    impediria a nova unique (grupo_base_id, hora).
    # ------------------------------------------------------------------
    colisoes = conn.execute(sa.text(
        "SELECT grupo_base_id, hora, COUNT(*) c FROM viagem_base GROUP BY grupo_base_id, hora HAVING COUNT(*) > 1"
    )).all()
    if colisoes:
        raise RuntimeError(
            f"Migracao 0008 abortada: {len(colisoes)} colisao(oes) de (grupo_base_id, hora) em viagem_base "
            "impediriam a nova unique constraint. Resolva manualmente antes de reaplicar a migracao."
        )

    # ------------------------------------------------------------------
    # 5) migrar membro_viagem_base: agenda_id (+ sentido do pai viagem_base)
    #    -> agenda_trecho_id direto. Precisa rodar ANTES de dropar
    #    viagem_base.sentido e usuario_agenda_semanal.saida/retorno.
    # ------------------------------------------------------------------
    trecho_id_by_agenda_ordem = {
        (row["agenda_id"], row["ordem"]): row["id"]
        for row in conn.execute(sa.text("SELECT id, agenda_id, ordem FROM usuario_agenda_semanal_trecho")).mappings().all()
    }
    tem_saida_by_agenda = {a["id"]: a["saida"] is not None for a in agendas}

    membros = conn.execute(sa.text(
        "SELECT m.id, m.agenda_id, vb.sentido FROM membro_viagem_base m "
        "JOIN viagem_base vb ON vb.id = m.viagem_base_id"
    )).mappings().all()

    with op.batch_alter_table('membro_viagem_base', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agenda_trecho_id', sa.Integer(), nullable=True))

    membro_updates = []
    membros_orfaos = []
    for m in membros:
        ordem_trecho = 0 if m["sentido"] == "IDA" else (1 if tem_saida_by_agenda.get(m["agenda_id"]) else 0)
        trecho_id = trecho_id_by_agenda_ordem.get((m["agenda_id"], ordem_trecho))
        if trecho_id is None:
            # Membro Base apontando pra uma perna (agenda_id, sentido) que a
            # propria agenda nao tem mais horario configurado -- ja e dado
            # morto hoje (base.py:montar_estrutura_base pula silenciosamente
            # esses membros quando usuario/atendimento estao ativos, ver
            # `continue` logo apos o lookup em pernas_por_agenda_sentido).
            # Remove em vez de bloquear a migracao ou inventar um trecho.
            membros_orfaos.append(m["id"])
            continue
        membro_updates.append(dict(id=m["id"], agenda_trecho_id=trecho_id))
    if membros_orfaos:
        conn.execute(
            sa.text(f"DELETE FROM membro_viagem_base WHERE id IN ({','.join(str(i) for i in membros_orfaos)})")
        )
    if membro_updates:
        conn.execute(sa.text("UPDATE membro_viagem_base SET agenda_trecho_id = :agenda_trecho_id WHERE id = :id"), membro_updates)

    with op.batch_alter_table('membro_viagem_base', schema=None) as batch_op:
        batch_op.drop_constraint('uq_membro_viagem_base', type_='unique')
        batch_op.drop_column('agenda_id')
        batch_op.alter_column('agenda_trecho_id', nullable=False)
        batch_op.create_foreign_key(
            'fk_membro_viagem_base_agenda_trecho_id', 'usuario_agenda_semanal_trecho',
            ['agenda_trecho_id'], ['id'], ondelete='CASCADE',
        )
        batch_op.create_unique_constraint('uq_membro_viagem_base', ['viagem_base_id', 'agenda_trecho_id'])

    # ------------------------------------------------------------------
    # 6) viagem_base: remove sentido, unique vira (grupo_base_id, hora)
    # ------------------------------------------------------------------
    with op.batch_alter_table('viagem_base', schema=None) as batch_op:
        batch_op.drop_constraint('uq_viagem_base_horario', type_='unique')
        batch_op.drop_column('sentido')
        batch_op.create_unique_constraint('uq_viagem_base_horario', ['grupo_base_id', 'hora'])

    # ------------------------------------------------------------------
    # 7) viagem_dia_passageiro: sentido -> ordem_trecho + destino_texto,
    #    aplicando o mesmo swap origem/destino nas linhas de Retorno.
    # ------------------------------------------------------------------
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordem_trecho', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('destino_texto', sa.String(length=200), nullable=True))

    passageiros = conn.execute(sa.text(
        "SELECT id, sentido, origem, regiao_origem_id, destino_id FROM viagem_dia_passageiro"
    )).mappings().all()
    passageiro_updates = []
    for p in passageiros:
        if p["sentido"] == "IDA":
            passageiro_updates.append(dict(
                id=p["id"], ordem_trecho=0,
                origem=p["origem"], regiao_origem_id=p["regiao_origem_id"],
                destino_id=p["destino_id"], destino_texto=None,
            ))
        else:
            passageiro_updates.append(dict(
                id=p["id"], ordem_trecho=1,
                origem=None, regiao_origem_id=None,
                destino_id=None, destino_texto=p["origem"],
            ))
    if passageiro_updates:
        conn.execute(sa.text(
            "UPDATE viagem_dia_passageiro SET ordem_trecho = :ordem_trecho, origem = :origem, "
            "regiao_origem_id = :regiao_origem_id, destino_id = :destino_id, destino_texto = :destino_texto WHERE id = :id"
        ), passageiro_updates)

    # regiao_destino_id das linhas de Retorno = regiao_origem_id ANTIGO (antes do swap acima).
    # Precisa ser calculado a partir do snapshot original, entao usamos os valores ja lidos em `passageiros`.
    regiao_destino_retorno_updates = [
        dict(id=p["id"], regiao_destino_id=p["regiao_origem_id"])
        for p in passageiros if p["sentido"] == "RETORNO"
    ]
    if regiao_destino_retorno_updates:
        conn.execute(sa.text(
            "UPDATE viagem_dia_passageiro SET regiao_destino_id = :regiao_destino_id WHERE id = :id"
        ), regiao_destino_retorno_updates)

    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.drop_constraint('uq_viagem_dia_passageiro', type_='unique')
        batch_op.alter_column('ordem_trecho', nullable=False)
        batch_op.drop_column('sentido')
        batch_op.create_unique_constraint('uq_viagem_dia_passageiro', ['viagem_dia_id', 'usuario_id', 'ordem_trecho'])

    # ------------------------------------------------------------------
    # 8) dropar colunas antigas de usuario_agenda_semanal / usuario_excecao
    # ------------------------------------------------------------------
    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.drop_constraint('uq_usuario_dia_semana_horario_destino', type_='unique')
        batch_op.drop_column('saida')
        batch_op.drop_column('retorno')
        batch_op.drop_column('origem')
        batch_op.drop_column('regiao_origem_id')
        batch_op.drop_column('destino_id')
        batch_op.drop_column('acompanhante')

    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.drop_column('saida')
        batch_op.drop_column('retorno')
        batch_op.drop_column('origem')
        batch_op.drop_column('regiao_origem_id')
        batch_op.drop_column('destino_id')
        batch_op.drop_column('acompanhante')


def downgrade() -> None:
    """Downgrade schema.

    Lossy para itinerarios com mais de 2 trechos: so os trechos de `ordem`
    0 e 1 de cada agenda/excecao/dia sao reconstruidos; trechos extras (ex:
    Caso 1 com 3+ paradas) sao descartados.
    """
    conn = op.get_bind()

    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('acompanhante', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('saida', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('retorno', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('origem', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('regiao_origem_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('destino_id', sa.Integer(), nullable=True))

    trechos_agenda = conn.execute(sa.text(
        "SELECT agenda_id, ordem, hora, origem, regiao_origem_id, destino_id, acompanhante "
        "FROM usuario_agenda_semanal_trecho WHERE ordem IN (0, 1) ORDER BY agenda_id, ordem"
    )).mappings().all()
    by_agenda: dict[int, list] = {}
    for t in trechos_agenda:
        by_agenda.setdefault(t["agenda_id"], []).append(t)

    agenda_reverts = []
    for agenda_id, trechos in by_agenda.items():
        t0 = trechos[0]
        t1 = trechos[1] if len(trechos) > 1 else None
        agenda_reverts.append(dict(
            id=agenda_id,
            saida=t0["hora"] if t0["ordem"] == 0 else None,
            retorno=(t1["hora"] if t1 else (t0["hora"] if t0["ordem"] == 1 else None)),
            origem=t0["origem"] if t0["ordem"] == 0 else None,
            regiao_origem_id=t0["regiao_origem_id"] if t0["ordem"] == 0 else None,
            destino_id=t0["destino_id"] if t0["ordem"] == 0 else None,
            acompanhante=bool(t0["acompanhante"]),
        ))
    if agenda_reverts:
        conn.execute(sa.text(
            "UPDATE usuario_agenda_semanal SET saida=:saida, retorno=:retorno, origem=:origem, "
            "regiao_origem_id=:regiao_origem_id, destino_id=:destino_id, acompanhante=:acompanhante WHERE id=:id"
        ), agenda_reverts)

    with op.batch_alter_table('usuario_agenda_semanal', schema=None) as batch_op:
        batch_op.alter_column('acompanhante', nullable=False)
        batch_op.create_unique_constraint(
            'uq_usuario_dia_semana_horario_destino', ['usuario_id', 'dia_semana', 'saida', 'destino_id']
        )

    with op.batch_alter_table('usuario_excecao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('acompanhante', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('saida', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('retorno', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('origem', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('regiao_origem_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('destino_id', sa.Integer(), nullable=True))

    trechos_excecao = conn.execute(sa.text(
        "SELECT excecao_id, ordem, hora, origem, regiao_origem_id, destino_id, acompanhante "
        "FROM usuario_excecao_trecho WHERE ordem IN (0, 1) ORDER BY excecao_id, ordem"
    )).mappings().all()
    by_excecao: dict[int, list] = {}
    for t in trechos_excecao:
        by_excecao.setdefault(t["excecao_id"], []).append(t)

    excecao_reverts = []
    for excecao_id, trechos in by_excecao.items():
        t0 = trechos[0]
        t1 = trechos[1] if len(trechos) > 1 else None
        excecao_reverts.append(dict(
            id=excecao_id,
            saida=t0["hora"] if t0["ordem"] == 0 else None,
            retorno=(t1["hora"] if t1 else (t0["hora"] if t0["ordem"] == 1 else None)),
            origem=t0["origem"] if t0["ordem"] == 0 else None,
            regiao_origem_id=t0["regiao_origem_id"] if t0["ordem"] == 0 else None,
            destino_id=t0["destino_id"] if t0["ordem"] == 0 else None,
            acompanhante=bool(t0["acompanhante"]),
        ))
    if excecao_reverts:
        conn.execute(sa.text(
            "UPDATE usuario_excecao SET saida=:saida, retorno=:retorno, origem=:origem, "
            "regiao_origem_id=:regiao_origem_id, destino_id=:destino_id, acompanhante=:acompanhante WHERE id=:id"
        ), excecao_reverts)

    # viagem_dia_passageiro: ordem_trecho -> sentido
    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'sentido', sa.Enum('IDA', 'RETORNO', name='sentido', native_enum=False, length=20), nullable=True
        ))

    conn.execute(sa.text("UPDATE viagem_dia_passageiro SET sentido = CASE WHEN ordem_trecho = 0 THEN 'IDA' ELSE 'RETORNO' END"))

    # reverte o swap origem/destino aplicado no upgrade (seção 7) pras linhas
    # que nao sao a primeira perna (ordem_trecho != 0), antes de dropar
    # destino_texto -- sem isso a origem/destino_id dessas linhas ficaria
    # perdida (None) no downgrade, mesmo pra itinerarios N=2 comuns.
    retorno_rows = conn.execute(sa.text(
        "SELECT id, destino_texto, regiao_destino_id FROM viagem_dia_passageiro WHERE ordem_trecho != 0"
    )).mappings().all()
    if retorno_rows:
        conn.execute(sa.text(
            "UPDATE viagem_dia_passageiro SET origem = :destino_texto, regiao_origem_id = :regiao_destino_id, "
            "destino_id = NULL WHERE id = :id"
        ), [dict(id=r["id"], destino_texto=r["destino_texto"], regiao_destino_id=r["regiao_destino_id"]) for r in retorno_rows])

    with op.batch_alter_table('viagem_dia_passageiro', schema=None) as batch_op:
        batch_op.alter_column('sentido', nullable=False)
        batch_op.drop_constraint('uq_viagem_dia_passageiro', type_='unique')
        batch_op.drop_column('ordem_trecho')
        batch_op.drop_column('destino_texto')
        batch_op.create_unique_constraint('uq_viagem_dia_passageiro', ['viagem_dia_id', 'usuario_id', 'sentido'])

    # viagem_base: hora -> (sentido, hora), inferido do primeiro membro
    with op.batch_alter_table('viagem_base', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'sentido', sa.Enum('IDA', 'RETORNO', name='sentido', native_enum=False, length=20), nullable=True
        ))

    viagens = conn.execute(sa.text(
        "SELECT vb.id, MIN(t.ordem) AS min_ordem FROM viagem_base vb "
        "LEFT JOIN membro_viagem_base m ON m.viagem_base_id = vb.id "
        "LEFT JOIN usuario_agenda_semanal_trecho t ON t.id = m.agenda_trecho_id "
        "GROUP BY vb.id"
    )).mappings().all()
    viagem_sentido = [
        dict(id=v["id"], sentido=("IDA" if (v["min_ordem"] is None or v["min_ordem"] == 0) else "RETORNO"))
        for v in viagens
    ]
    if viagem_sentido:
        conn.execute(sa.text("UPDATE viagem_base SET sentido = :sentido WHERE id = :id"), viagem_sentido)

    with op.batch_alter_table('viagem_base', schema=None) as batch_op:
        batch_op.alter_column('sentido', nullable=False)
        batch_op.drop_constraint('uq_viagem_base_horario', type_='unique')
        batch_op.create_unique_constraint('uq_viagem_base_horario', ['grupo_base_id', 'sentido', 'hora'])

    # membro_viagem_base: agenda_trecho_id -> agenda_id
    with op.batch_alter_table('membro_viagem_base', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agenda_id', sa.Integer(), nullable=True))

    membros = conn.execute(sa.text(
        "SELECT m.id, t.agenda_id FROM membro_viagem_base m "
        "JOIN usuario_agenda_semanal_trecho t ON t.id = m.agenda_trecho_id"
    )).mappings().all()
    if membros:
        conn.execute(sa.text("UPDATE membro_viagem_base SET agenda_id = :agenda_id WHERE id = :id"), membros)

    with op.batch_alter_table('membro_viagem_base', schema=None) as batch_op:
        batch_op.alter_column('agenda_id', nullable=False)
        batch_op.drop_constraint('uq_membro_viagem_base', type_='unique')
        batch_op.drop_column('agenda_trecho_id')
        batch_op.create_foreign_key(
            'fk_membro_viagem_base_agenda_id', 'usuario_agenda_semanal', ['agenda_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_unique_constraint('uq_membro_viagem_base', ['viagem_base_id', 'agenda_id'])

    op.drop_table('usuario_excecao_trecho')
    op.drop_table('usuario_agenda_semanal_trecho')
