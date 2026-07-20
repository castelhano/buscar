import datetime as dt
from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Condutor,
    CondutorFerias,
    DiaSemana,
    GrupoBase,
    GrupoRevezamento,
    GrupoRevezamentoCondutor,
    Local,
    LocalRecesso,
    OperacaoExcecao,
    PeriodoCondutor,
    RodizioCondutorFimDeSemana,
    Sentido,
    StatusAtendimentoDia,
    StatusAtivoInativo,
    StatusCondutor,
    StatusVeiculo,
    StatusViagemDia,
    TipoAtendimento,
    Usuario,
    UsuarioAgendaSemanal,
    UsuarioExcecao,
    Veiculo,
    ViagemBase,
    ViagemDia,
    ViagemDiaPassageiro,
    empresa_regiao,
)
from app.services.dia import dia_semana_from_date
from app.services.recursos import fim_viagem, inicio_viagem, janelas_sobrepoem

TEMPO_SAIDA_GARAGEM_MINUTOS = 60
CORTE_PERIODO_TARDE = dt.time(14, 0)


def _periodo_da_hora(hora: dt.time) -> PeriodoCondutor:
    """Ate 13:59 e Manha, a partir de 14:00 e Tarde."""
    return PeriodoCondutor.TARDE if hora >= CORTE_PERIODO_TARDE else PeriodoCondutor.MANHA


def _periodo_da_viagem(viagem: ViagemDia) -> PeriodoCondutor:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    hora_referencia = min(horas) if horas else viagem.horario_saida
    return _periodo_da_hora(hora_referencia)


def agendas_fixo_da_semana(db: Session, dia_semana: DiaSemana) -> list[UsuarioAgendaSemanal]:
    """Agendas Fixo/ativas de um dia da semana generico, sem excecao pontual
    nem recesso (so existem pra uma data especifica) -- base tanto do modo
    Base (`app.services.base`) quanto de `_agendas_do_dia` pra data real.
    """
    return (
        db.query(UsuarioAgendaSemanal)
        .join(Usuario, UsuarioAgendaSemanal.usuario_id == Usuario.id)
        .options(joinedload(UsuarioAgendaSemanal.usuario))
        .filter(
            UsuarioAgendaSemanal.dia_semana == dia_semana,
            UsuarioAgendaSemanal.tipo == TipoAtendimento.FIXO,
            UsuarioAgendaSemanal.ativo.is_(True),
            Usuario.status == StatusAtivoInativo.ATIVO,
        )
        .order_by(UsuarioAgendaSemanal.id)
        .all()
    )


def _agendas_do_dia(db: Session, data: dt.date):
    """Agendas Fixo/ativas do dia da semana de `data` mais TODAS as
    `UsuarioExcecao` cujo intervalo [data_inicio, data_fim] cobre essa data --
    inclusive de usuarios sem nenhuma linha de agenda nesse dia da semana
    (atendimento avulso, ver `montar_pernas`) -- com os locais em recesso
    vigentes nessa data. Base comum usada tanto pela geracao quanto pelo
    diagnostico de desconsiderados.

    Excecoes do mesmo usuario com intervalos sobrepostos nao sao validadas na
    escrita (ver `UsuarioExcecao`); quando isso acontece, a de maior id
    (mais recente) vence.
    """
    dia_semana = dia_semana_from_date(data)
    agendas = agendas_fixo_da_semana(db, dia_semana)
    excecoes: dict[int, UsuarioExcecao] = {}
    for e in (
        db.query(UsuarioExcecao)
        .join(Usuario, UsuarioExcecao.usuario_id == Usuario.id)
        .options(joinedload(UsuarioExcecao.usuario))
        .filter(
            UsuarioExcecao.data_inicio <= data,
            UsuarioExcecao.data_fim >= data,
            Usuario.status == StatusAtivoInativo.ATIVO,
        )
        .order_by(UsuarioExcecao.id.desc())
    ):
        excecoes.setdefault(e.usuario_id, e)
    locais_em_recesso = {
        row[0]
        for row in db.query(LocalRecesso.local_id).filter(
            LocalRecesso.data_inicio <= data, LocalRecesso.data_fim >= data
        )
    }
    return dia_semana, agendas, excecoes, locais_em_recesso


def _motivo_desconsideracao(
    agenda: UsuarioAgendaSemanal | None, excecao: UsuarioExcecao | None, locais_em_recesso: set[int]
) -> str | None:
    """Motivo pelo qual esse usuario nao entra na geracao do dia, ou None se
    elegivel (ainda pode ficar de fora depois por falta de veiculo/frota --
    isso e um problema de escala, tratado a parte no painel de Sobras, nao
    aqui). `agenda` pode ser None no atendimento avulso (so excecao, sem
    nenhuma linha de agenda pro dia da semana).
    """
    if excecao and excecao.operacao == OperacaoExcecao.SUSPENSAO:
        return f"Excecao de usuario: suspenso nesse dia ({excecao.motivo})" if excecao.motivo else "Excecao de usuario: suspenso nesse dia"

    destino_id = excecao.destino_id if excecao and excecao.destino_id else (agenda.destino_id if agenda else None)
    if destino_id is not None and destino_id in locais_em_recesso:
        return "Local de destino em recesso"

    regiao_origem_id = (
        excecao.regiao_origem_id
        if excecao and excecao.regiao_origem_id
        else (agenda.regiao_origem_id if agenda else None)
    )
    if regiao_origem_id is None:
        return "Sem regiao de origem cadastrada"

    return None


def listar_desconsiderados_dia(db: Session, data: dt.date) -> list[dict]:
    """Usuarios com atendimento previsto pra essa data (Fixo, ou avulso via
    excecao) que ficam de fora da geracao (suspenso, local em recesso, sem
    regiao de origem), com o motivo -- pra alertar na tela de agendamento do
    dia.
    """
    _, agendas, excecoes, locais_em_recesso = _agendas_do_dia(db, data)
    desconsiderados = []
    usuarios_com_agenda: set[int] = set()
    for agenda in agendas:
        usuarios_com_agenda.add(agenda.usuario_id)
        motivo = _motivo_desconsideracao(agenda, excecoes.get(agenda.usuario_id), locais_em_recesso)
        if motivo is not None:
            desconsiderados.append({"usuario_id": agenda.usuario_id, "usuario_nome": agenda.usuario.nome, "motivo": motivo})
    for usuario_id, excecao in excecoes.items():
        if usuario_id in usuarios_com_agenda:
            continue
        motivo = _motivo_desconsideracao(None, excecao, locais_em_recesso)
        if motivo is not None:
            desconsiderados.append({"usuario_id": usuario_id, "usuario_nome": excecao.usuario.nome, "motivo": motivo})
    return desconsiderados


def regiao_alocacao(sentido: Sentido, regiao_origem_id: int, regiao_destino_id: int | None) -> int:
    """No retorno o veiculo opera na regiao do destino (de onde o usuario esta
    saindo nessa perna, ex: escola) em vez da regiao de origem/casa; sem
    regiao de destino cadastrada, cai pra regiao de origem como na ida.
    """
    if sentido == Sentido.RETORNO and regiao_destino_id is not None:
        return regiao_destino_id
    return regiao_origem_id


def _adicionar_pernas(
    pernas_por_regiao: dict[int, list[dict]],
    agenda_id: int,
    usuario: Usuario,
    agenda: UsuarioAgendaSemanal | None,
    excecao: UsuarioExcecao | None,
    locais_regiao: dict[int, int],
) -> None:
    """Monta as pernas (Ida/Retorno) de um usuario nesse dia. Quando ha
    excecao ela e a fonte de verdade (substitui o Fixo campo a campo onde
    estiver preenchida) -- inclusive sozinha, sem nenhuma `agenda` (Fixo)
    por tras, no atendimento avulso.
    """
    origem = excecao.origem if excecao and excecao.origem else (agenda.origem if agenda else None)
    regiao_origem_id = (
        excecao.regiao_origem_id
        if excecao and excecao.regiao_origem_id
        else (agenda.regiao_origem_id if agenda else None)
    )
    destino_id = excecao.destino_id if excecao and excecao.destino_id else (agenda.destino_id if agenda else None)
    regiao_destino_id = locais_regiao.get(destino_id) if destino_id else None
    acompanhante = (
        excecao.acompanhante
        if excecao and excecao.acompanhante is not None
        else (agenda.acompanhante if agenda else False)
    )

    pernas = (
        (Sentido.IDA, agenda.saida if agenda else None, excecao.saida if excecao else None),
        (Sentido.RETORNO, agenda.retorno if agenda else None, excecao.retorno if excecao else None),
    )
    for sentido, hora_padrao, hora_excecao in pernas:
        hora = hora_excecao or hora_padrao
        if hora is None:
            continue
        regiao_alocacao_id = regiao_alocacao(sentido, regiao_origem_id, regiao_destino_id)
        pernas_por_regiao[regiao_alocacao_id].append(
            {
                "agenda_id": agenda_id,
                "usuario_id": usuario.id,
                "usuario": usuario,
                "sentido": sentido,
                "hora": hora,
                "origem": origem,
                "regiao_origem_id": regiao_origem_id,
                "destino_id": destino_id,
                "regiao_destino_id": regiao_destino_id,
                "acompanhante": acompanhante,
                "fixo": excecao is None,
            }
        )


def montar_pernas(
    agendas: list[UsuarioAgendaSemanal],
    excecoes: dict[int, UsuarioExcecao],
    locais_em_recesso: set[int],
    locais_regiao: dict[int, int],
) -> dict[int, list[dict]]:
    """Monta as pernas (Ida/Retorno) de cada usuario elegivel nesse dia,
    agrupadas por regiao de alocacao -- usado tanto pela geracao real (com
    excecao/recesso de uma data) quanto pela leitura do modo Base (sem
    excecao/recesso, que so existem pra uma data especifica).

    Usuario com excecao pra essa data e tratado por ela (ver
    `_adicionar_pernas`), mesmo sem ter nenhuma linha de `UsuarioAgendaSemanal`
    nesse dia da semana -- cobre o atendimento avulso (uma vez na vida) sem
    precisar cadastrar um padrao semanal so pra essa ocorrencia.

    Quando a excecao e do tipo ADICAO e o usuario tem agenda Fixo, as duas
    pernas coexistem (Fixo original + excecao), em vez da excecao substituir o
    Fixo campo a campo como no MODIFICACAO.
    """
    pernas_por_regiao: dict[int, list[dict]] = defaultdict(list)
    usuarios_com_agenda: set[int] = set()

    for agenda in agendas:
        usuarios_com_agenda.add(agenda.usuario_id)
        excecao = excecoes.get(agenda.usuario_id)
        if excecao is not None and excecao.operacao == OperacaoExcecao.ADICAO:
            motivo_fixo = _motivo_desconsideracao(agenda, None, locais_em_recesso)
            if motivo_fixo is None:
                _adicionar_pernas(pernas_por_regiao, agenda.id, agenda.usuario, agenda, None, locais_regiao)
            else:
                print(f"[geracao] usuario_id={agenda.usuario_id}: {motivo_fixo}, Fixo ficou de fora (excecao ADICAO mantida)")
            motivo_excecao = _motivo_desconsideracao(None, excecao, locais_em_recesso)
            if motivo_excecao is None:
                _adicionar_pernas(pernas_por_regiao, -excecao.id, agenda.usuario, None, excecao, locais_regiao)
            else:
                print(f"[geracao] usuario_id={agenda.usuario_id}: {motivo_excecao}, excecao ADICAO ficou de fora")
            continue
        motivo = _motivo_desconsideracao(agenda, excecao, locais_em_recesso)
        if motivo is not None:
            print(f"[geracao] usuario_id={agenda.usuario_id}: {motivo}, ficou de fora")
            continue
        _adicionar_pernas(pernas_por_regiao, agenda.id, agenda.usuario, agenda, excecao, locais_regiao)

    for usuario_id, excecao in excecoes.items():
        if usuario_id in usuarios_com_agenda:
            continue
        motivo = _motivo_desconsideracao(None, excecao, locais_em_recesso)
        if motivo is not None:
            print(f"[geracao] usuario_id={usuario_id}: {motivo}, ficou de fora (avulso)")
            continue
        _adicionar_pernas(pernas_por_regiao, -excecao.id, excecao.usuario, None, excecao, locais_regiao)

    print(f"[geracao] pernas por regiao: { {k: len(v) for k, v in pernas_por_regiao.items()} }")
    return pernas_por_regiao


def _mapa_empresas_por_regiao(db: Session) -> dict[int, list[int]]:
    """Empresas de cada regiao, pre-carregado uma unica vez por geracao --
    usado hoje so pra restringir candidatos de condutor no rodizio alfabetico
    de fim de semana (`_proximo_condutor_alfabetico`).
    """
    resultado: dict[int, list[int]] = defaultdict(list)
    for empresa_id, regiao_id in db.query(empresa_regiao.c.empresa_id, empresa_regiao.c.regiao_id).all():
        resultado[regiao_id].append(empresa_id)
    return resultado


def horario_garagem(hora: dt.time) -> dt.time:
    referencia = dt.datetime.combine(dt.date.today(), hora) - dt.timedelta(minutes=TEMPO_SAIDA_GARAGEM_MINUTOS)
    return referencia.time()


# --------------------------------------------------------------------------
# Geracao real do dia
# --------------------------------------------------------------------------

def gerar_agendamento_dia(db: Session, data: dt.date) -> list[ViagemDia]:
    """Gera as ViagemDia + ViagemDiaPassageiro de uma data a partir da agenda
    semanal, carregando primeiro os grupos do modo Base (`GrupoBase`) pra esse
    dia da semana e so depois preenchendo quem nao esta em nenhum grupo.

    Idempotente: se ja existir ViagemDia para a data, retorna o que ja foi
    gerado em vez de duplicar (a tela de agendamento so mostra "Gerar" quando
    ainda nao existe nada para a data).

    Cada `GrupoBase` (carro conceitual curado na tela Base) vira um unico
    carro real ao longo do dia -- a geracao nunca divide o que foi definido
    manualmente: sempre cria a `ViagemDia`, mesmo sem condutor/veiculo. O
    excedente de capacidade tambem so gera alerta visual (lugares ocupados
    acima da capacidade), nunca remove ninguem.

    Condutor e escolhido depois, em `_atribuir_condutores`, por uma de duas
    estrategias conforme o dia da semana: em dia util, se o `GrupoBase` for
    uma vaga de algum `GrupoRevezamento`, o condutor da vaga e determinado
    pela posicao (`ordem`) e pelo deslocamento atual do grupo de revezamento
    (`_condutor_do_slot`); em sabado/domingo, rodizio alfabetico continuo por
    periodo (`RodizioCondutorFimDeSemana`), independente de grupo. Em ambos os
    casos, o veiculo da viagem e o `Condutor.veiculo_preferencial_id` do
    condutor escalado, se disponivel -- senao a viagem fica so com condutor,
    sem veiculo (fica pra atribuicao manual so do veiculo).

    Quem nao esta em nenhum grupo (ou caiu fora por excecao pontual do dia,
    ex: horario mudou e nao bate mais com a viagem_base) nao entra em carro
    nenhum automaticamente -- vira "orfao" pra alocacao manual (painel "Sem
    vaga" na tela do dia), igual a quem ficou sem vaga por falta de frota.
    """
    existentes = db.query(ViagemDia).filter(ViagemDia.data == data).all()
    existe_orfao = (
        db.query(ViagemDiaPassageiro.id)
        .filter(ViagemDiaPassageiro.viagem_dia_id.is_(None), ViagemDiaPassageiro.data == data)
        .first()
        is not None
    )
    if existentes or existe_orfao:
        return existentes

    dia_semana, agendas, excecoes, locais_em_recesso = _agendas_do_dia(db, data)
    print(
        f"[geracao] {data} ({dia_semana.name}): {len(agendas)} agendas Fixo + {len(excecoes)} excecoes encontradas"
    )
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    empresas_por_regiao = _mapa_empresas_por_regiao(db)

    pernas_por_regiao = montar_pernas(agendas, excecoes, locais_em_recesso, locais_regiao)
    pernas_por_agenda_sentido = {
        (p["agenda_id"], p["sentido"]): p for pernas in pernas_por_regiao.values() for p in pernas
    }

    todas_viagens: list[ViagemDia] = []
    ocupacao: dict[tuple[int, Sentido, dt.time], int] = defaultdict(int)
    regioes_por_viagem: dict[int, set[int]] = defaultdict(set)
    proximo_ordem: dict[int, int] = {}
    consumidos: set[tuple[int, Sentido]] = set()
    grupo_por_viagem_id: dict[int, int] = {}

    grupos_base = (
        db.query(GrupoBase)
        .options(joinedload(GrupoBase.viagens).joinedload(ViagemBase.membros))
        .filter(GrupoBase.dia_semana == dia_semana)
        .order_by(GrupoBase.ordem_exibicao, GrupoBase.id)
        .all()
    )
    for grupo in grupos_base:
        _gerar_carro_do_grupo_base(
            grupo,
            pernas_por_agenda_sentido,
            data,
            db,
            todas_viagens,
            ocupacao,
            regioes_por_viagem,
            proximo_ordem,
            consumidos,
            grupo_por_viagem_id,
        )

    pernas_residuais = [perna for chave, perna in pernas_por_agenda_sentido.items() if chave not in consumidos]
    pernas_residuais.sort(key=lambda p: (p["sentido"].value, p["hora"]))
    _deixar_para_alocacao_manual(db, pernas_residuais, data)

    db.flush()
    _atribuir_condutores(db, todas_viagens, data, dia_semana, grupo_por_viagem_id, empresas_por_regiao)
    db.commit()
    for viagem in todas_viagens:
        db.refresh(viagem)
    print(f"[geracao] {len(todas_viagens)} viagens geradas")
    return todas_viagens


def _regioes_do_grupo_base(
    grupo: GrupoBase, pernas_por_agenda_sentido: dict[tuple[int, Sentido], dict]
) -> tuple[list[tuple[ViagemBase, list[dict]]], set[int]]:
    """Pra cada viagem_base do grupo, filtra so os membros elegiveis hoje
    (excecao/recesso podem ter tirado alguem), e devolve junto o conjunto de
    regioes tocadas pelo grupo inteiro no dia -- usado so como rotulo/regiao_id
    da `ViagemDia` gerada (condutor/veiculo sao resolvidos depois, em
    `_atribuir_condutores`, a partir do `GrupoRevezamento`).
    """
    viagens_membros: list[tuple[ViagemBase, list[dict]]] = []
    regioes: set[int] = set()
    for viagem in sorted(grupo.viagens, key=lambda v: (v.sentido.value, v.hora)):
        membros_hoje = []
        for membro in sorted(viagem.membros, key=lambda m: m.ordem):
            perna = pernas_por_agenda_sentido.get((membro.agenda_id, viagem.sentido))
            if perna is None:
                continue
            if perna["hora"] != viagem.hora:
                # defesa contra dado inconsistente (nao deveria acontecer --
                # `mover_membro` ja valida isso na escrita): se o horario real
                # da pessoa nao bate com o da viagem_base, ela nao materializa
                # aqui; vira "nao classificado" nessa geracao em vez de
                # corromper o carro com gente de dois horarios.
                print(
                    f"[geracao] membro_viagem_base agenda_id={membro.agenda_id}: horario real "
                    f"({perna['hora']}) nao bate com o da viagem_base ({viagem.hora}), ignorado"
                )
                continue
            membros_hoje.append(perna)
            regioes.add(regiao_alocacao(viagem.sentido, perna["regiao_origem_id"], perna["regiao_destino_id"]))
        if membros_hoje:
            viagens_membros.append((viagem, membros_hoje))
    return viagens_membros, regioes


def _gerar_carro_do_grupo_base(
    grupo: GrupoBase,
    pernas_por_agenda_sentido: dict[tuple[int, Sentido], dict],
    data: dt.date,
    db: Session,
    todas_viagens: list[ViagemDia],
    ocupacao: dict[tuple[int, Sentido, dt.time], int],
    regioes_por_viagem: dict[int, set[int]],
    proximo_ordem: dict[int, int],
    consumidos: set[tuple[int, Sentido]],
    grupo_por_viagem_id: dict[int, int],
) -> None:
    """Sempre cria a `ViagemDia` de cada perna do grupo, sem condutor/veiculo
    (essa atribuicao acontece depois, em `_atribuir_condutores`, a partir do
    `GrupoRevezamento` -- ver docstring de `gerar_agendamento_dia`).
    """
    viagens_membros, regioes = _regioes_do_grupo_base(grupo, pernas_por_agenda_sentido)
    if not viagens_membros:
        return  # ninguem do grupo esta elegivel hoje

    rotulo_regiao = min(regioes) if regioes else None
    ancora_id: int | None = None

    for viagem_base, membros in viagens_membros:
        lugares_totais = sum(2 if m["acompanhante"] else 1 for m in membros)
        regiao_da_viagem = rotulo_regiao
        if regiao_da_viagem is None:
            regiao_da_viagem = regiao_alocacao(
                viagem_base.sentido, membros[0]["regiao_origem_id"], membros[0]["regiao_destino_id"]
            )
        # So a primeira perna do carro sai da garagem (por isso o desconto de
        # TEMPO_SAIDA_GARAGEM_MINUTOS); as pernas seguintes do mesmo carro
        # (ex: segundo horario de retorno) partem de onde a anterior terminou,
        # com o carro ja em rota -- aplicar o desconto nelas tambem fazia a
        # janela da perna seguinte "comecar" antes do fim da anterior e
        # acusar conflito de condutor/veiculo com o proprio carro.
        eh_primeira_perna = ancora_id is None
        viagem = ViagemDia(
            data=data,
            regiao_id=regiao_da_viagem,
            horario_saida=horario_garagem(viagem_base.hora) if eh_primeira_perna else viagem_base.hora,
            capacidade=max(lugares_totais, 1),
            status=StatusViagemDia.PLANEJADA,
        )
        db.add(viagem)
        db.flush()
        todas_viagens.append(viagem)

        # A primeira perna aberta pro grupo vira a ancora do bloco; as
        # seguintes (ex: retorno da tarde) apontam pra ela via grupo_viagem_id,
        # independente de condutor/veiculo terem sido atribuidos.
        if ancora_id is None:
            ancora_id = viagem.id
            viagem.ordem_exibicao = grupo.ordem_exibicao
        elif viagem.grupo_viagem_id is None:
            viagem.grupo_viagem_id = ancora_id

        grupo_por_viagem_id[viagem.id] = grupo.id

        for indice, perna in enumerate(membros):
            db.add(
                ViagemDiaPassageiro(
                    viagem_dia_id=viagem.id,
                    usuario_id=perna["usuario_id"],
                    sentido=perna["sentido"],
                    hora=perna["hora"],
                    origem=perna["origem"],
                    regiao_origem_id=perna["regiao_origem_id"],
                    destino_id=perna["destino_id"],
                    regiao_destino_id=perna["regiao_destino_id"],
                    acompanhante=perna["acompanhante"],
                    fixo=perna["fixo"],
                    ordem=indice,
                )
            )
            lugares = 2 if perna["acompanhante"] else 1
            regiao_pessoa = regiao_alocacao(perna["sentido"], perna["regiao_origem_id"], perna["regiao_destino_id"])
            ocupacao[(viagem.id, perna["sentido"], perna["hora"])] += lugares
            regioes_por_viagem[viagem.id].add(regiao_pessoa)
            consumidos.add((perna["agenda_id"], perna["sentido"]))

        proximo_ordem[viagem.id] = len(membros)


def _deixar_para_alocacao_manual(db: Session, pernas: list[dict], data: dt.date) -> None:
    """Quem nao esta em nenhum grupo_base (ou caiu fora por excecao pontual do
    dia, ex: horario mudou e nao bate mais com a viagem_base) nao entra em
    nenhum carro automaticamente -- vira "orfao" (`viagem_dia_id=None`) direto,
    igual a quem ficou sem vaga por falta de frota, pra alocacao manual na
    tela do dia (painel "Sem vaga", arrastando pra um carro).
    """
    for perna in pernas:
        db.add(
            ViagemDiaPassageiro(
                viagem_dia_id=None,
                data=data,
                usuario_id=perna["usuario_id"],
                sentido=perna["sentido"],
                hora=perna["hora"],
                origem=perna["origem"],
                regiao_origem_id=perna["regiao_origem_id"],
                destino_id=perna["destino_id"],
                regiao_destino_id=perna["regiao_destino_id"],
                acompanhante=perna["acompanhante"],
                fixo=perna["fixo"],
            )
        )


_FIM_DE_SEMANA = (DiaSemana.SAB, DiaSemana.DOM)


def _veiculo_disponivel(db: Session, veiculo_id: int, pernas: list[ViagemDia], viagens: list[ViagemDia]) -> Veiculo | None:
    """O veiculo das `pernas` (todas as viagens de um mesmo carro/periodo, ver
    `_atribuir_condutores`) e sempre o `veiculo_preferencial_id` do condutor
    escalado: confirma que esse veiculo esta ATIVO e sem sobreposicao de
    horario de atendimento com outro carro que ja o esteja usando -- senao as
    pernas ficam so com condutor, sem veiculo (o rodizio de condutor nunca
    pula a vez por causa disso). A janela usada e o atendimento real
    (`inicio_viagem`/`fim_viagem`, primeiro ao ultimo passageiro), nunca
    `horario_saida` (saida de garagem e so estimativa de exportacao, nao
    ocupacao real). Pernas do mesmo grupo nunca conflitam entre si -- e o
    mesmo carro, nao dois usos concorrentes do veiculo.
    """
    veiculo = db.get(Veiculo, veiculo_id)
    if veiculo is None or veiculo.status != StatusVeiculo.ATIVO:
        return None
    ids_do_grupo = {p.id for p in pernas}
    inicio = min(inicio_viagem(p) for p in pernas)
    fim = max(fim_viagem(p) for p in pernas)
    for outra in viagens:
        if outra.id in ids_do_grupo or outra.veiculo_id != veiculo_id:
            continue
        if janelas_sobrepoem(inicio, fim, inicio_viagem(outra), fim_viagem(outra)):
            return None
    return veiculo


def _condutor_livre(condutor_id: int, viagem: ViagemDia, viagens: list[ViagemDia]) -> bool:
    """So usado no rodizio alfabetico de fim de semana (`_proximo_condutor_alfabetico`),
    onde ha de fato uma escolha entre varios condutores candidatos. Janela
    calculada pelo atendimento real (`inicio_viagem`/`fim_viagem`), nunca
    `horario_saida`.
    """
    inicio = inicio_viagem(viagem)
    fim = fim_viagem(viagem)
    for outra in viagens:
        if outra.id == viagem.id or outra.condutor_id != condutor_id:
            continue
        if janelas_sobrepoem(inicio, fim, inicio_viagem(outra), fim_viagem(outra)):
            return False
    return True


def _atribuir_condutores(
    db: Session,
    viagens: list[ViagemDia],
    data: dt.date,
    dia_semana: DiaSemana,
    grupo_por_viagem_id: dict[int, int],
    empresas_por_regiao: dict[int, list[int]],
) -> None:
    """Atribui condutor (e, a partir dele, veiculo) as viagens geradas, por
    uma de duas estrategias conforme o dia da semana (nunca mistura condutor
    de Manha com viagem de Tarde e vice-versa, corte as 14h00):

    - Dia util: as pernas sao agrupadas por (`GrupoBase`, periodo) -- todas as
      pernas de um mesmo carro num mesmo periodo sao **uma unica decisao**: se
      o `GrupoBase` for uma vaga de algum `GrupoRevezamento`, o condutor e o
      da posicao calculada por `_condutor_do_slot` (ordem da vaga +
      deslocamento atual do grupo) e e gravado em todas as pernas do grupo de
      uma vez. Fora de qualquer grupo de revezamento, fica sem condutor
      (manual). Pernas do mesmo carro nunca sao checadas por sobreposicao de
      horario entre si -- e o mesmo carro, nunca compete com ele mesmo pelo
      proprio condutor/veiculo (essa auto-colisao, calculada em cima de
      `horario_saida`, era o que deixava pernas como o retorno do meio-dia
      sem condutor mesmo o carro tendo condutor definido o dia todo).
    - Sabado/domingo: rodizio alfabetico continuo por periodo, independente de
      grupo (`RodizioCondutorFimDeSemana`) -- ver `_proximo_condutor_alfabetico`.
      Aqui sim ha escolha entre varios condutores candidatos, entao a
      checagem de sobreposicao (`_condutor_livre`) se aplica, calculada pelo
      atendimento real (`inicio_viagem`/`fim_viagem`), nunca por
      `horario_saida`.

    Em ambos os casos, uma vez definido o condutor, o veiculo e o
    `Condutor.veiculo_preferencial_id` dele, se disponivel (ver
    `_veiculo_disponivel`) -- se nao, as pernas ficam so com condutor, sem
    veiculo; o rodizio de condutor nunca pula a vez por causa do veiculo.

    O deslocamento de cada `GrupoRevezamento` do dia so e gravado apos o laco
    inteiro, e persistido no mesmo commit das viagens (`gerar_agendamento_dia`)
    -- se a geracao falhar no meio, o deslocamento nao avanca sem viagem de
    fato gerada. Avanca pra **todos** os grupos de revezamento desse dia da
    semana, mesmo que alguma vaga deles nao tenha gerado viagem hoje (giro por
    calendario, nao por quem efetivamente rodou).
    """
    em_ferias = {
        f.condutor_id
        for f in db.query(CondutorFerias).filter(
            CondutorFerias.data_inicio <= data, CondutorFerias.data_fim >= data
        )
    }
    eh_fim_de_semana = dia_semana in _FIM_DE_SEMANA
    pendentes_periodo: dict[PeriodoCondutor, int] = {}

    revezamentos: list[GrupoRevezamento] = []
    slot_por_grupo_base: dict[int, tuple[GrupoRevezamento, int]] = {}
    if not eh_fim_de_semana:
        revezamentos = (
            db.query(GrupoRevezamento)
            .options(
                joinedload(GrupoRevezamento.carros),
                joinedload(GrupoRevezamento.condutores).joinedload(GrupoRevezamentoCondutor.condutor),
            )
            .filter(GrupoRevezamento.dia_semana == dia_semana)
            .all()
        )
        slot_por_grupo_base = {
            carro.grupo_base_id: (revezamento, carro.ordem)
            for revezamento in revezamentos
            for carro in revezamento.carros
        }

    if eh_fim_de_semana:
        for viagem in viagens:
            empresa_ids = empresas_por_regiao.get(viagem.regiao_id, [])
            condutor = _proximo_condutor_alfabetico(db, viagem, viagens, em_ferias, empresa_ids, pendentes_periodo)
            if condutor is None:
                continue
            viagem.condutor_id = condutor.id
            if condutor.veiculo_preferencial_id is not None:
                veiculo = _veiculo_disponivel(db, condutor.veiculo_preferencial_id, [viagem], viagens)
                if veiculo is not None:
                    viagem.veiculo_id = veiculo.id
                    viagem.empresa_id = veiculo.empresa_id
                    viagem.capacidade = veiculo.capacidade
    else:
        pernas_por_grupo_periodo: dict[tuple[int, PeriodoCondutor], list[ViagemDia]] = defaultdict(list)
        for viagem in viagens:
            grupo_id = grupo_por_viagem_id.get(viagem.id)
            if grupo_id is None:
                continue  # nao veio de nenhum GrupoBase (nao deveria acontecer aqui)
            pernas_por_grupo_periodo[(grupo_id, _periodo_da_viagem(viagem))].append(viagem)

        for (grupo_id, periodo), pernas in pernas_por_grupo_periodo.items():
            slot = slot_por_grupo_base.get(grupo_id)
            if slot is None:
                continue  # carro fora de qualquer grupo de revezamento -- so manual
            revezamento, ordem = slot
            condutor = _condutor_do_slot(revezamento, ordem, periodo, em_ferias)
            if condutor is None:
                continue
            veiculo = (
                _veiculo_disponivel(db, condutor.veiculo_preferencial_id, pernas, viagens)
                if condutor.veiculo_preferencial_id is not None
                else None
            )
            for perna in pernas:
                perna.condutor_id = condutor.id
                if veiculo is not None:
                    perna.veiculo_id = veiculo.id
                    perna.empresa_id = veiculo.empresa_id
                    perna.capacidade = veiculo.capacidade

    for periodo, condutor_id in pendentes_periodo.items():
        registro = db.get(RodizioCondutorFimDeSemana, periodo)
        if registro is None:
            registro = RodizioCondutorFimDeSemana(periodo=periodo)
            db.add(registro)
        registro.ultimo_condutor_id = condutor_id

    for revezamento in revezamentos:
        if revezamento.condutores:
            revezamento.deslocamento = (revezamento.deslocamento + 1) % len(revezamento.condutores)


def reverter_giro_revezamento(db: Session, dia_semana: DiaSemana) -> None:
    """Desfaz o giro de `GrupoRevezamento.deslocamento` que `_atribuir_condutores`
    aplica a cada geracao completa de um dia util -- chamado por
    `routers.viagens.limpar_dia` quando a geracao apagada tinha de fato rodado
    (existia `ViagemDia`/orfao pra data), pra manter o rodizio consistente num
    ciclo gerar/limpar/gerar (sem isso, o giro avanca de novo na proxima
    geracao e fica duplicado pra sempre nas ocorrencias seguintes desse dia da
    semana). Fim de semana nao usa `deslocamento` (ve `_proximo_condutor_alfabetico`),
    entao nao ha o que reverter.
    """
    if dia_semana in _FIM_DE_SEMANA:
        return
    revezamentos = (
        db.query(GrupoRevezamento)
        .options(joinedload(GrupoRevezamento.condutores))
        .filter(GrupoRevezamento.dia_semana == dia_semana)
        .all()
    )
    for revezamento in revezamentos:
        n = len(revezamento.condutores)
        if n:
            revezamento.deslocamento = (revezamento.deslocamento - 1) % n


def _condutor_do_slot(
    revezamento: GrupoRevezamento,
    ordem: int,
    periodo: PeriodoCondutor,
    em_ferias: set[int],
) -> Condutor | None:
    """Escolhe o condutor da vaga `ordem` desse `GrupoRevezamento`: a fila de
    condutores (`condutores`, na ordem cadastrada na tela Base) e deslocada
    por `deslocamento` posicoes -- indice = (ordem - deslocamento) % N. Nao
    substitui por outro condutor da fila se o da vez estiver indisponivel
    (inativo/ferias/periodo errado): a vaga so fica sem condutor nesse
    periodo, sem pular a vez de ninguem.

    Uma unica chamada decide o condutor de **todas** as pernas do carro nesse
    periodo (ver `_atribuir_condutores`) -- por isso nao ha aqui checagem de
    sobreposicao de horario contra outras pernas: o carro nunca compete com
    ele mesmo pelo proprio condutor.
    """
    condutores = revezamento.condutores
    carros = revezamento.carros
    n = len(condutores)
    if n == 0 or n != len(carros):
        print(
            f"[geracao] grupo_revezamento_id={revezamento.id}: numero de condutores ({n}) "
            f"diferente do numero de carros ({len(carros)}), rodizio desativado"
        )
        return None

    indice = (ordem - revezamento.deslocamento) % n
    condutor = condutores[indice].condutor
    if condutor.status != StatusCondutor.ATIVO or condutor.periodo != periodo or condutor.id in em_ferias:
        print(
            f"[geracao] grupo_revezamento_id={revezamento.id} vaga={ordem} periodo={periodo.value}: "
            f"condutor {condutor.nome} indisponivel, vaga fica sem condutor nesse periodo"
        )
        return None
    return condutor


def _proximo_condutor_alfabetico(
    db: Session,
    viagem: ViagemDia,
    viagens: list[ViagemDia],
    em_ferias: set[int],
    empresa_ids: list[int],
    pendentes_periodo: dict[PeriodoCondutor, int],
) -> Condutor | None:
    """Escolhe o condutor da viagem no rodizio alfabetico de fim de semana:
    ordena por nome os condutores ATIVOS do periodo/empresas elegiveis, e
    continua a partir de `RodizioCondutorFimDeSemana.ultimo_condutor_id`
    daquele periodo (ou do que ja avancou nesse mesmo laco, via
    `pendentes_periodo`), ciclando -- pula quem estiver de ferias/indisponivel
    sem travar.
    """
    periodo = _periodo_da_viagem(viagem)
    if not empresa_ids:
        return None

    candidatos = (
        db.query(Condutor)
        .filter(
            Condutor.empresa_id.in_(empresa_ids),
            Condutor.status == StatusCondutor.ATIVO,
            Condutor.periodo == periodo,
        )
        .order_by(Condutor.nome)
        .all()
    )
    candidatos = [c for c in candidatos if c.id not in em_ferias]
    if not candidatos:
        print(f"[geracao] viagem_id={viagem.id} periodo={periodo.value}: sem condutor {periodo.value} disponivel")
        return None

    por_id = {c.id: c for c in candidatos}
    ordem_ids = [c.id for c in candidatos]
    elegiveis = {c.id for c in candidatos if _condutor_livre(c.id, viagem, viagens)}
    if not elegiveis:
        print(
            f"[geracao] viagem_id={viagem.id}: nenhum condutor livre nesse horario (rodizio fim de semana)"
        )
        return None

    ultimo_id = pendentes_periodo.get(periodo)
    if ultimo_id is None:
        registro = db.get(RodizioCondutorFimDeSemana, periodo)
        ultimo_id = registro.ultimo_condutor_id if registro else None
    inicio = (ordem_ids.index(ultimo_id) + 1) if ultimo_id in ordem_ids else 0
    for deslocamento in range(len(ordem_ids)):
        candidato_id = ordem_ids[(inicio + deslocamento) % len(ordem_ids)]
        if candidato_id in elegiveis:
            pendentes_periodo[periodo] = candidato_id
            return por_id[candidato_id]
    return None
