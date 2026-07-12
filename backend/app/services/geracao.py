import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Condutor,
    CondutorFerias,
    DiaSemana,
    GrupoBase,
    Local,
    LocalRecesso,
    PeriodoCondutor,
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
from app.services.recursos import fim_viagem, janelas_sobrepoem

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
    Base (`app.services.base`) quanto de `_agendas_fixo_do_dia` pra data real.
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


def _agendas_fixo_do_dia(db: Session, data: dt.date):
    """Agendas Fixo/ativas do dia da semana de `data`, com as excecoes pontuais
    (por usuario) e os locais em recesso vigentes nessa data -- base comum
    usada tanto pela geracao quanto pelo diagnostico de desconsiderados.
    """
    dia_semana = dia_semana_from_date(data)
    agendas = agendas_fixo_da_semana(db, dia_semana)
    usuario_ids = [a.usuario_id for a in agendas]
    excecoes = {
        e.usuario_id: e
        for e in db.query(UsuarioExcecao).filter(
            UsuarioExcecao.data == data, UsuarioExcecao.usuario_id.in_(usuario_ids)
        )
    }
    locais_em_recesso = {
        row[0]
        for row in db.query(LocalRecesso.local_id).filter(
            LocalRecesso.data_inicio <= data, LocalRecesso.data_fim >= data
        )
    }
    return dia_semana, agendas, excecoes, locais_em_recesso


def _motivo_desconsideracao(
    agenda: UsuarioAgendaSemanal, excecao: UsuarioExcecao | None, locais_em_recesso: set[int]
) -> str | None:
    """Motivo pelo qual esse usuario nao entra na geracao do dia, ou None se
    elegivel (ainda pode ficar de fora depois por falta de veiculo/frota --
    isso e um problema de escala, tratado a parte no painel de Sobras, nao
    aqui).
    """
    if excecao and excecao.suspenso:
        return f"Excecao de usuario: suspenso nesse dia ({excecao.motivo})" if excecao.motivo else "Excecao de usuario: suspenso nesse dia"

    destino_id = excecao.destino_id if excecao and excecao.destino_id else agenda.destino_id
    if destino_id is not None and destino_id in locais_em_recesso:
        return "Local de destino em recesso"

    regiao_origem_id = (
        excecao.regiao_origem_id if excecao and excecao.regiao_origem_id else agenda.regiao_origem_id
    )
    if regiao_origem_id is None:
        return "Sem regiao de origem cadastrada"

    return None


def listar_desconsiderados_dia(db: Session, data: dt.date) -> list[dict]:
    """Usuarios com atendimento Fixo previsto pra essa data que ficam de fora
    da geracao (suspenso, local em recesso, sem regiao de origem), com o
    motivo -- pra alertar na tela de agendamento do dia.
    """
    _, agendas, excecoes, locais_em_recesso = _agendas_fixo_do_dia(db, data)
    desconsiderados = []
    for agenda in agendas:
        motivo = _motivo_desconsideracao(agenda, excecoes.get(agenda.usuario_id), locais_em_recesso)
        if motivo is not None:
            desconsiderados.append({"usuario_id": agenda.usuario_id, "usuario_nome": agenda.usuario.nome, "motivo": motivo})
    return desconsiderados


def regiao_alocacao(sentido: Sentido, regiao_origem_id: int, regiao_destino_id: int | None) -> int:
    """No retorno o veiculo opera na regiao do destino (de onde o usuario esta
    saindo nessa perna, ex: escola) em vez da regiao de origem/casa; sem
    regiao de destino cadastrada, cai pra regiao de origem como na ida.
    """
    if sentido == Sentido.RETORNO and regiao_destino_id is not None:
        return regiao_destino_id
    return regiao_origem_id


def montar_pernas(
    agendas: list[UsuarioAgendaSemanal],
    excecoes: dict[int, UsuarioExcecao],
    locais_em_recesso: set[int],
    locais_regiao: dict[int, int],
) -> dict[int, list[dict]]:
    """Monta as pernas (Ida/Retorno) de cada agenda elegivel, agrupadas por
    regiao de alocacao -- usado tanto pela geracao real (com excecao/recesso
    de uma data) quanto pela leitura do modo Base (sem excecao/recesso, que so
    existem pra uma data especifica).
    """
    pernas_por_regiao: dict[int, list[dict]] = defaultdict(list)
    for agenda in agendas:
        excecao = excecoes.get(agenda.usuario_id)
        motivo = _motivo_desconsideracao(agenda, excecao, locais_em_recesso)
        if motivo is not None:
            print(f"[geracao] usuario_id={agenda.usuario_id}: {motivo}, ficou de fora")
            continue

        origem = excecao.origem if excecao and excecao.origem else agenda.origem
        regiao_origem_id = (
            excecao.regiao_origem_id if excecao and excecao.regiao_origem_id else agenda.regiao_origem_id
        )
        destino_id = excecao.destino_id if excecao and excecao.destino_id else agenda.destino_id
        regiao_destino_id = locais_regiao.get(destino_id) if destino_id else None

        pernas = (
            (Sentido.IDA, agenda.saida, excecao.saida if excecao else None),
            (Sentido.RETORNO, agenda.retorno, excecao.retorno if excecao else None),
        )
        for sentido, hora_padrao, hora_excecao in pernas:
            hora = hora_excecao or hora_padrao
            if hora is None:
                continue
            regiao_alocacao_id = regiao_alocacao(sentido, regiao_origem_id, regiao_destino_id)
            pernas_por_regiao[regiao_alocacao_id].append(
                {
                    "agenda_id": agenda.id,
                    "usuario_id": agenda.usuario_id,
                    "usuario": agenda.usuario,
                    "sentido": sentido,
                    "hora": hora,
                    "origem": origem,
                    "regiao_origem_id": regiao_origem_id,
                    "destino_id": destino_id,
                    "regiao_destino_id": regiao_destino_id,
                    "acompanhante": agenda.acompanhante,
                }
            )

    print(f"[geracao] pernas por regiao: { {k: len(v) for k, v in pernas_por_regiao.items()} }")
    return pernas_por_regiao


def _empresas_com_veiculo_ativo(db: Session) -> set[int]:
    """Empresas que tem pelo menos um veiculo ATIVO -- uma empresa pode
    atender uma regiao (`empresa_regiao`) sem ter frota nenhuma hoje, o que
    nao conta como opcao real pra viabilizar um grupo_base cross-regiao.
    """
    return {row[0] for row in db.query(Veiculo.empresa_id).filter(Veiculo.status == StatusVeiculo.ATIVO).distinct()}


def _mapa_empresas_por_regiao(db: Session) -> dict[int, list[int]]:
    """Empresas de cada regiao, pre-carregado uma unica vez por geracao --
    antes era consultado de novo a cada carro aberto e a cada viagem na
    atribuicao de condutor.
    """
    resultado: dict[int, list[int]] = defaultdict(list)
    for empresa_id, regiao_id in db.query(empresa_regiao.c.empresa_id, empresa_regiao.c.regiao_id).all():
        resultado[regiao_id].append(empresa_id)
    return resultado


def _horario_garagem(hora: dt.time) -> dt.time:
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
    manualmente: se existir empresa (com veiculo ativo) que atenda todas as
    regioes tocadas pelo grupo no dia, aloca condutor/veiculo normalmente
    (reaproveitando o mesmo veiculo entre as viagens do grupo quando possivel);
    senao, gera do jeito que esta definido mesmo assim, so sem condutor/
    veiculo (fica pra atribuicao manual). O excedente de capacidade tambem so
    gera alerta visual (lugares ocupados acima da capacidade), nunca remove
    ninguem.

    Quem nao esta em nenhum grupo (ou caiu fora por excecao pontual do dia)
    tenta uma vaga num carro que veio da Base pro mesmo sentido/horario antes
    de abrir carro novo -- sempre de uma unica regiao por horario, do jeito
    que a geracao ja funcionava antes do modo Base existir.
    """
    existentes = db.query(ViagemDia).filter(ViagemDia.data == data).all()
    if existentes:
        return existentes

    dia_semana, agendas, excecoes, locais_em_recesso = _agendas_fixo_do_dia(db, data)
    print(f"[geracao] {data} ({dia_semana.name}): {len(agendas)} agendas FIXO/ativas encontradas")
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    ultimos_usos_veiculo = _ultimos_usos(db, ViagemDia.veiculo_id, data)
    ultimos_usos_condutor = _ultimos_usos(db, ViagemDia.condutor_id, data)
    empresas_por_regiao = _mapa_empresas_por_regiao(db)
    empresas_com_veiculo = _empresas_com_veiculo_ativo(db)

    pernas_por_regiao = montar_pernas(agendas, excecoes, locais_em_recesso, locais_regiao)
    pernas_por_agenda_sentido = {
        (p["agenda_id"], p["sentido"]): p for pernas in pernas_por_regiao.values() for p in pernas
    }

    todas_viagens: list[ViagemDia] = []
    janelas: dict[int, tuple[dt.time, dt.time]] = {}
    ocupacao: dict[tuple[int, Sentido, dt.time], int] = defaultdict(int)
    regioes_por_viagem: dict[int, set[int]] = defaultdict(set)
    proximo_ordem: dict[int, int] = {}
    avisos_emitidos: set[tuple] = set()
    consumidos: set[tuple[int, Sentido]] = set()

    grupos_base = (
        db.query(GrupoBase)
        .options(joinedload(GrupoBase.viagens).joinedload(ViagemBase.membros))
        .filter(GrupoBase.dia_semana == dia_semana)
        .order_by(GrupoBase.ordem_exibicao, GrupoBase.id)
        .all()
    )
    for grupo in grupos_base:
        _gerar_carro_do_grupo_base(
            db,
            grupo,
            pernas_por_agenda_sentido,
            data,
            todas_viagens,
            janelas,
            ocupacao,
            regioes_por_viagem,
            proximo_ordem,
            avisos_emitidos,
            ultimos_usos_veiculo,
            empresas_por_regiao,
            empresas_com_veiculo,
            consumidos,
        )

    pernas_residuais = [perna for chave, perna in pernas_por_agenda_sentido.items() if chave not in consumidos]
    pernas_residuais.sort(key=lambda p: (p["sentido"].value, p["hora"]))
    _preencher_residual(
        db,
        pernas_residuais,
        data,
        todas_viagens,
        janelas,
        ocupacao,
        regioes_por_viagem,
        proximo_ordem,
        avisos_emitidos,
        ultimos_usos_veiculo,
        empresas_por_regiao,
    )

    db.flush()
    _atribuir_condutores(db, todas_viagens, data, ultimos_usos_condutor, empresas_por_regiao)
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
    regioes tocadas pelo grupo inteiro no dia -- e essa uniao que decide se
    existe empresa capaz de atender o grupo como um carro so.
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
    db: Session,
    grupo: GrupoBase,
    pernas_por_agenda_sentido: dict[tuple[int, Sentido], dict],
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    ocupacao: dict[tuple[int, Sentido, dt.time], int],
    regioes_por_viagem: dict[int, set[int]],
    proximo_ordem: dict[int, int],
    avisos_emitidos: set[tuple],
    ultimos_usos_veiculo: dict[int, dt.date],
    empresas_por_regiao: dict[int, list[int]],
    empresas_com_veiculo: set[int],
    consumidos: set[tuple[int, Sentido]],
) -> None:
    viagens_membros, regioes = _regioes_do_grupo_base(grupo, pernas_por_agenda_sentido)
    if not viagens_membros:
        return  # ninguem do grupo esta elegivel hoje

    empresa_ids: list[int] = []
    if regioes:
        intersecao = set(empresas_por_regiao.get(next(iter(regioes)), []))
        for regiao_id in regioes:
            intersecao &= set(empresas_por_regiao.get(regiao_id, []))
        intersecao &= empresas_com_veiculo
        empresa_ids = sorted(intersecao)
        if not empresa_ids:
            print(
                f"[geracao] grupo_base_id={grupo.id}: nenhuma empresa com frota atende as regioes "
                f"{sorted(regioes)}, gerado sem condutor/veiculo pra atribuicao manual"
            )

    rotulo_regiao = min(regioes) if regioes else None
    veiculo_do_grupo: int | None = None

    for viagem_base, membros in viagens_membros:
        viagem = None
        if empresa_ids:
            viagem = _abrir_carro(
                db,
                rotulo_regiao,
                viagem_base.hora,
                data,
                todas_viagens,
                janelas,
                avisos_emitidos,
                ultimos_usos_veiculo,
                empresa_ids,
                veiculo_preferido_id=veiculo_do_grupo,
            )
            if viagem is not None:
                veiculo_do_grupo = viagem.veiculo_id
                todas_viagens.append(viagem)

        if viagem is None:
            lugares_totais = sum(2 if m["acompanhante"] else 1 for m in membros)
            regiao_da_viagem = rotulo_regiao
            if regiao_da_viagem is None:
                regiao_da_viagem = regiao_alocacao(
                    viagem_base.sentido, membros[0]["regiao_origem_id"], membros[0]["regiao_destino_id"]
                )
            viagem = ViagemDia(
                data=data,
                regiao_id=regiao_da_viagem,
                horario_saida=_horario_garagem(viagem_base.hora),
                capacidade=max(lugares_totais, 1),
                status=StatusViagemDia.PLANEJADA,
            )
            db.add(viagem)
            db.flush()
            todas_viagens.append(viagem)

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
                    ordem=indice,
                )
            )
            lugares = 2 if perna["acompanhante"] else 1
            regiao_pessoa = regiao_alocacao(perna["sentido"], perna["regiao_origem_id"], perna["regiao_destino_id"])
            ocupacao[(viagem.id, perna["sentido"], perna["hora"])] += lugares
            regioes_por_viagem[viagem.id].add(regiao_pessoa)
            consumidos.add((perna["agenda_id"], perna["sentido"]))

        proximo_ordem[viagem.id] = len(membros)


def _preencher_residual(
    db: Session,
    pernas: list[dict],
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    ocupacao: dict[tuple[int, Sentido, dt.time], int],
    regioes_por_viagem: dict[int, set[int]],
    proximo_ordem: dict[int, int],
    avisos_emitidos: set[tuple],
    ultimos_usos_veiculo: dict[int, dt.date],
    empresas_por_regiao: dict[int, list[int]],
) -> None:
    """Encaixa quem nao esta em nenhum grupo_base (ou caiu fora por excecao
    pontual do dia): primeiro tenta vaga num carro que ja veio da Base pro
    mesmo sentido/horario -- respeitando a empresa dele se resolvida (precisa
    atender a regiao da pessoa e ter lugar), ou so aceitando quem ja tem a
    mesma regiao presente ali se o carro ficou sem empresa (inviavel). O que
    sobra abre carro novo, sempre de uma unica regiao por horario, igual a
    geracao ja fazia antes do modo Base existir. Prioridade entre os
    residuais e irrelevante (nao ha ordem curada pra eles) -- so processa na
    ordem em que chegam.
    """
    viagens_por_id = {v.id: v for v in todas_viagens}
    viagens_por_sentido_hora: dict[tuple[Sentido, dt.time], list[ViagemDia]] = defaultdict(list)
    for viagem_id, sentido, hora in ocupacao:
        viagem = viagens_por_id.get(viagem_id)
        if viagem is not None and viagem not in viagens_por_sentido_hora[(sentido, hora)]:
            viagens_por_sentido_hora[(sentido, hora)].append(viagem)

    residuais_por_regiao: dict[int, list[dict]] = defaultdict(list)

    for perna in pernas:
        chave = (perna["sentido"], perna["hora"])
        lugares = 2 if perna["acompanhante"] else 1
        regiao_pessoa = regiao_alocacao(perna["sentido"], perna["regiao_origem_id"], perna["regiao_destino_id"])

        viagem_encontrada = None
        for viagem in viagens_por_sentido_hora.get(chave, []):
            if viagem.empresa_id is not None:
                cabe = ocupacao[(viagem.id, *chave)] + lugares <= viagem.capacidade
                empresa_atende = viagem.empresa_id in empresas_por_regiao.get(regiao_pessoa, [])
                if cabe and empresa_atende:
                    viagem_encontrada = viagem
                    break
            elif regiao_pessoa in regioes_por_viagem.get(viagem.id, set()):
                viagem_encontrada = viagem
                break

        if viagem_encontrada is not None:
            ordem = proximo_ordem.get(viagem_encontrada.id, 0)
            db.add(
                ViagemDiaPassageiro(
                    viagem_dia_id=viagem_encontrada.id,
                    usuario_id=perna["usuario_id"],
                    sentido=perna["sentido"],
                    hora=perna["hora"],
                    origem=perna["origem"],
                    regiao_origem_id=perna["regiao_origem_id"],
                    destino_id=perna["destino_id"],
                    regiao_destino_id=perna["regiao_destino_id"],
                    acompanhante=perna["acompanhante"],
                    ordem=ordem,
                )
            )
            proximo_ordem[viagem_encontrada.id] = ordem + 1
            ocupacao[(viagem_encontrada.id, *chave)] += lugares
            regioes_por_viagem[viagem_encontrada.id].add(regiao_pessoa)
            continue

        residuais_por_regiao[regiao_pessoa].append(perna)

    for regiao_id, pernas_regiao in residuais_por_regiao.items():
        pernas_regiao.sort(key=lambda p: (p["sentido"].value, p["hora"]))
        _preencher_regiao(
            db,
            regiao_id,
            pernas_regiao,
            data,
            todas_viagens,
            janelas,
            avisos_emitidos,
            ultimos_usos_veiculo,
            empresas_por_regiao.get(regiao_id, []),
        )


def _preencher_regiao(
    db: Session,
    regiao_id: int,
    pernas: list[dict],
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    avisos_emitidos: set[tuple],
    ultimos_usos_veiculo: dict[int, dt.date],
    empresa_ids: list[int],
) -> None:
    """Preenche os carros de uma regiao na ordem em que as pernas chegam,
    abrindo um novo carro (leg) sempre que o sentido/horario atual estoura a
    capacidade dos carros ja abertos para esse mesmo sentido/horario. Usado
    so pro residual (quem nao esta em nenhum grupo_base) -- essas pernas ja
    sao de uma unica regiao (`_preencher_residual` separa por
    `regiao_alocacao` antes de chamar).

    Um usuario com acompanhante ocupa 2 lugares no veiculo em vez de 1.
    """
    ocupacao: dict[tuple[int, Sentido, dt.time], int] = defaultdict(int)
    abertos_por_perna: dict[tuple[Sentido, dt.time], list[ViagemDia]] = defaultdict(list)

    for perna in pernas:
        perna_chave = (perna["sentido"], perna["hora"])
        lugares = 2 if perna["acompanhante"] else 1
        viagem = next(
            (
                v
                for v in abertos_por_perna[perna_chave]
                if ocupacao[(v.id, *perna_chave)] + lugares <= v.capacidade
            ),
            None,
        )
        if viagem is None:
            viagem = _abrir_carro(
                db,
                regiao_id,
                perna["hora"],
                data,
                todas_viagens,
                janelas,
                avisos_emitidos,
                ultimos_usos_veiculo,
                empresa_ids,
            )
            if viagem is None:
                # sem veiculo disponivel na regiao/horario -- fica "orfao" (sem
                # carro) no container "Sem vaga" da tela do dia, pra alocacao manual
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
                    )
                )
                continue
            abertos_por_perna[perna_chave].append(viagem)
            todas_viagens.append(viagem)

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
            )
        )
        ocupacao[(viagem.id, *perna_chave)] += lugares


def _veiculo_se_livre(
    db: Session,
    veiculo_id: int,
    empresa_ids: list[int],
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    inicio: dt.time,
    fim: dt.time,
) -> Veiculo | None:
    """Confirma se um veiculo especifico (o "veiculo do grupo", pra manter o
    mesmo carro ao longo do dia) ainda serve: pertence a uma empresa elegivel,
    esta ATIVO, e nao tem janela sobreposta com outro carro do dia."""
    veiculo = db.get(Veiculo, veiculo_id)
    if veiculo is None or veiculo.status != StatusVeiculo.ATIVO or veiculo.empresa_id not in empresa_ids:
        return None
    for outra in todas_viagens:
        if outra.veiculo_id != veiculo_id:
            continue
        janela = janelas.get(outra.id)
        if janela and janelas_sobrepoem(inicio, fim, janela[0], janela[1]):
            return None
    return veiculo


def _abrir_carro(
    db: Session,
    regiao_id: int,
    hora: dt.time,
    data: dt.date,
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    avisos_emitidos: set[tuple],
    ultimos_usos_veiculo: dict[int, dt.date],
    empresa_ids: list[int],
    veiculo_preferido_id: int | None = None,
) -> ViagemDia | None:
    """Abre um carro pra uma regiao/horario. `veiculo_preferido_id` (opcional)
    tenta reaproveitar o mesmo veiculo de uma viagem irma do mesmo
    `grupo_base` ao longo do dia antes de cair no rodizio normal -- e isso que
    faz um grupo virar um unico carro real, mesmo com viagens em horarios
    bem separados.
    """
    if not empresa_ids:
        chave_aviso = ("sem_empresa", regiao_id)
        if chave_aviso not in avisos_emitidos:
            avisos_emitidos.add(chave_aviso)
            print(f"[geracao] regiao_id={regiao_id}: nenhuma empresa vinculada (empresa_regiao vazio pra essa regiao)")
        return None

    horario_saida = _horario_garagem(hora)

    veiculo = None
    if veiculo_preferido_id is not None:
        veiculo = _veiculo_se_livre(db, veiculo_preferido_id, empresa_ids, todas_viagens, janelas, horario_saida, hora)
    if veiculo is None:
        veiculo = _proximo_veiculo_livre(db, empresa_ids, todas_viagens, janelas, horario_saida, hora, ultimos_usos_veiculo)
    if veiculo is None:
        chave_aviso = ("sem_veiculo", regiao_id, hora)
        if chave_aviso not in avisos_emitidos:
            avisos_emitidos.add(chave_aviso)
            print(
                f"[geracao] regiao_id={regiao_id} hora={hora}: empresas {empresa_ids} sem veiculo ativo/livre nesse horario"
            )
        return None  # sem veiculo disponivel na regiao/horario para abrir novo carro

    viagem = ViagemDia(
        data=data,
        regiao_id=regiao_id,
        empresa_id=veiculo.empresa_id,
        veiculo_id=veiculo.id,
        horario_saida=horario_saida,
        capacidade=veiculo.capacidade,
        status=StatusViagemDia.PLANEJADA,
    )
    db.add(viagem)
    db.flush()
    janelas[viagem.id] = (horario_saida, hora)
    return viagem


def _proximo_veiculo_livre(
    db: Session,
    empresa_ids: list[int],
    todas_viagens: list[ViagemDia],
    janelas: dict[int, tuple[dt.time, dt.time]],
    inicio: dt.time,
    fim: dt.time,
    ultimos_usos_veiculo: dict[int, dt.date],
) -> Veiculo | None:
    """Escolhe o proximo veiculo (rodizio) livre para o intervalo [inicio, fim].

    Um veiculo ja usado hoje em outro carro continua elegivel desde que os
    intervalos nao se sobreponham -- e assim que o mesmo carro/condutor acaba
    fazendo mais de uma viagem no dia (ex: 06h00 e depois 07h00).
    """
    candidatos = (
        db.query(Veiculo)
        .filter(Veiculo.empresa_id.in_(empresa_ids), Veiculo.status == StatusVeiculo.ATIVO)
        .all()
    )

    def livre(veiculo_id: int) -> bool:
        for outra in todas_viagens:
            if outra.veiculo_id != veiculo_id:
                continue
            janela = janelas.get(outra.id)
            if janela and janelas_sobrepoem(inicio, fim, janela[0], janela[1]):
                return False
        return True

    disponiveis = [v for v in candidatos if livre(v.id)]
    if not disponiveis:
        return None
    disponiveis.sort(key=lambda v: ultimos_usos_veiculo.get(v.id, dt.date.min))
    return disponiveis[0]


def _atribuir_condutores(
    db: Session,
    viagens: list[ViagemDia],
    data: dt.date,
    ultimos_usos_condutor: dict[int, dt.date],
    empresas_por_regiao: dict[int, list[int]],
) -> None:
    """Atribui condutor a cada viagem, priorizando quem foi usado ha mais tempo
    (rodizio entre dias), mas permitindo reaproveitar o mesmo condutor em
    carros do mesmo dia que nao se sobrepoem (ex: o mesmo condutor faz a
    viagem das 06h00 e depois a das 07h00). So considera condutores do mesmo
    periodo da viagem (`Condutor.periodo`, corte as 14h00) -- um condutor de
    Manha nunca e escalado numa viagem de Tarde e vice-versa.
    """
    em_ferias = {
        f.condutor_id
        for f in db.query(CondutorFerias).filter(
            CondutorFerias.data_inicio <= data, CondutorFerias.data_fim >= data
        )
    }

    for viagem in viagens:
        if viagem.veiculo_id is None:
            continue  # sem veiculo (grupo_base inviavel/sem frota) -- espera atribuicao manual
        empresa_ids = empresas_por_regiao.get(viagem.regiao_id, [])
        if not empresa_ids:
            continue

        condutor = _proximo_condutor_livre(db, empresa_ids, em_ferias, viagens, viagem, ultimos_usos_condutor)
        if condutor is not None:
            viagem.condutor_id = condutor.id


def _proximo_condutor_livre(
    db: Session,
    empresa_ids: list[int],
    em_ferias: set[int],
    viagens: list[ViagemDia],
    viagem: ViagemDia,
    ultimos_usos_condutor: dict[int, dt.date],
) -> Condutor | None:
    periodo = _periodo_da_viagem(viagem)
    candidatos = (
        db.query(Condutor)
        .filter(
            Condutor.empresa_id.in_(empresa_ids),
            Condutor.status == StatusCondutor.ATIVO,
            Condutor.periodo == periodo,
        )
        .all()
    )
    candidatos = [c for c in candidatos if c.id not in em_ferias]
    if not candidatos:
        print(f"[geracao] viagem_id={viagem.id} regiao_id={viagem.regiao_id} periodo={periodo.value}: sem condutor {periodo.value} disponivel")
        return None

    inicio = viagem.horario_saida
    fim = fim_viagem(viagem)

    def livre(condutor_id: int) -> bool:
        for outra in viagens:
            if outra.id == viagem.id or outra.condutor_id != condutor_id:
                continue
            if janelas_sobrepoem(inicio, fim, outra.horario_saida, fim_viagem(outra)):
                return False
        return True

    def mesmo_veiculo_do_dia(condutor_id: int) -> bool:
        """Um condutor so opera um unico veiculo por dia: se ja foi escalado
        noutra viagem hoje, essa viagem precisa ser do mesmo veiculo."""
        for outra in viagens:
            if outra.id == viagem.id or outra.condutor_id != condutor_id:
                continue
            if outra.veiculo_id != viagem.veiculo_id:
                return False
        return True

    disponiveis = [c for c in candidatos if livre(c.id) and mesmo_veiculo_do_dia(c.id)]
    if not disponiveis:
        print(
            f"[geracao] viagem_id={viagem.id} regiao_id={viagem.regiao_id} veiculo_id={viagem.veiculo_id}: "
            "nenhum condutor livre com o mesmo veiculo do dia"
        )
        return None

    if viagem.veiculo_id is not None:
        preferenciais = [c for c in disponiveis if c.veiculo_preferencial_id == viagem.veiculo_id]
        if preferenciais:
            return preferenciais[0]

    disponiveis.sort(key=lambda c: ultimos_usos_condutor.get(c.id, dt.date.min))
    return disponiveis[0]


def _ultimos_usos(db: Session, coluna, antes_de: dt.date) -> dict[int, dt.date]:
    """Ultima data de uso (antes de `antes_de`) de cada valor de `coluna`
    (condutor_id ou veiculo_id) em ViagemDia -- uma unica query agregada em
    vez de uma query por candidato dentro do sort() de rodizio.
    """
    linhas = (
        db.query(coluna, func.max(ViagemDia.data))
        .filter(coluna.isnot(None), ViagemDia.data < antes_de)
        .group_by(coluna)
        .all()
    )
    return dict(linhas)
