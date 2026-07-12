import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Condutor,
    CondutorFerias,
    DiaSemana,
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
    ViagemDia,
    ViagemDiaPassageiro,
    empresa_regiao,
)
from app.services.dia import dia_semana_from_date
from app.services.recursos import fim_viagem, janelas_sobrepoem

TEMPO_SAIDA_GARAGEM_MINUTOS = 60
CORTE_PERIODO_TARDE = dt.time(14, 0)
DATA_PREVIEW_PLACEHOLDER = dt.date(2000, 1, 1)


def _periodo_da_hora(hora: dt.time) -> PeriodoCondutor:
    """Ate 13:59 e Manha, a partir de 14:00 e Tarde."""
    return PeriodoCondutor.TARDE if hora >= CORTE_PERIODO_TARDE else PeriodoCondutor.MANHA


def _periodo_da_viagem(viagem: ViagemDia) -> PeriodoCondutor:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    hora_referencia = min(horas) if horas else viagem.horario_saida
    return _periodo_da_hora(hora_referencia)


def _agendas_fixo_da_semana(db: Session, dia_semana: DiaSemana) -> list[UsuarioAgendaSemanal]:
    """Agendas Fixo/ativas de um dia da semana generico, sem excecao pontual
    nem recesso (so existem pra uma data especifica) -- base pro preview do
    modo Base, e reaproveitada por `_agendas_fixo_do_dia` pra data real.
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
    agendas = _agendas_fixo_da_semana(db, dia_semana)
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


def _chave_ordenacao_perna(perna: dict) -> tuple:
    """Ordem de preenchimento dos carros dentro de uma regiao: por sentido
    (ida e retorno nunca dividem carro, mas idas sao sempre "Ida" < "Retorno"
    entao ficam naturalmente separadas), depois horario.

    `ordem` 0 significa "sem classificacao" (ninguem revisou no modo Base
    ainda) -- entra como criterio de desempate ANTES do valor de `ordem` em
    si, pra quem nunca foi classificado preencher só o que sobrar depois de
    quem já foi organizado (mas ainda pode abrir carro novo se tiver frota,
    já que o laço de preenchimento roda por cima da lista inteira já
    ordenada, sem precisar de duas fases separadas).

    Na ida o desempate seguinte e o `ordem` manual (curado pra manter juntos
    quem mora perto). No retorno o desempate prioriza o destino exato (Local,
    ex: mesma escola) antes do "sem classificacao"/`ordem` -- so mistura
    locais diferentes da mesma regiao quando o destino exato acabou.
    """
    nao_classificado = perna["ordem"] == 0
    if perna["sentido"] == Sentido.RETORNO:
        return (perna["sentido"].value, perna["hora"], perna["destino_id"] or 0, nao_classificado, perna["ordem"])
    return (perna["sentido"].value, perna["hora"], nao_classificado, perna["ordem"])


def _regiao_alocacao(sentido: Sentido, regiao_origem_id: int, regiao_destino_id: int | None) -> int:
    """No retorno o veiculo opera na regiao do destino (de onde o usuario esta
    saindo nessa perna, ex: escola) em vez da regiao de origem/casa; sem
    regiao de destino cadastrada, cai pra regiao de origem como na ida.
    """
    if sentido == Sentido.RETORNO and regiao_destino_id is not None:
        return regiao_destino_id
    return regiao_origem_id


def _montar_pernas(
    agendas: list[UsuarioAgendaSemanal],
    excecoes: dict[int, UsuarioExcecao],
    locais_em_recesso: set[int],
    locais_regiao: dict[int, int],
) -> dict[int, list[dict]]:
    """Monta as pernas (Ida/Retorno) de cada agenda elegivel, agrupadas por
    regiao de alocacao -- usado tanto pela geracao real (com excecao/recesso
    de uma data) quanto pelo preview do modo Base (sem excecao/recesso, que
    so existem pra uma data especifica).
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
            (Sentido.IDA, agenda.saida, excecao.saida if excecao else None, agenda.ordem_ida),
            (Sentido.RETORNO, agenda.retorno, excecao.retorno if excecao else None, agenda.ordem_retorno),
        )
        for sentido, hora_padrao, hora_excecao, ordem in pernas:
            hora = hora_excecao or hora_padrao
            if hora is None:
                continue
            regiao_alocacao_id = _regiao_alocacao(sentido, regiao_origem_id, regiao_destino_id)
            pernas_por_regiao[regiao_alocacao_id].append(
                {
                    "agenda_id": agenda.id,
                    "usuario_id": agenda.usuario_id,
                    "usuario": agenda.usuario,
                    "ordem": ordem,
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
    nao conta como opcao real pra viabilizar um pin cross-regiao.
    """
    return {row[0] for row in db.query(Veiculo.empresa_id).filter(Veiculo.status == StatusVeiculo.ATIVO).distinct()}


def _resolver_clusters_pin(
    pernas_por_regiao: dict[int, list[dict]],
    agendas_por_id: dict[int, UsuarioAgendaSemanal],
    sentido: Sentido,
    empresas_por_regiao: dict[int, list[int]],
    empresas_com_veiculo: set[int],
) -> tuple[list[tuple[int, list[int], list[dict]]], dict[int, list[dict]]]:
    """Resolve `pin_ida_agenda_id`/`pin_retorno_agenda_id` do sentido em
    clusters (uniao-find), so entre quem esta de fato elegivel nessa geracao
    -- um pin cujo alvo nao apareceu hoje (afastado, recesso, excecao pontual)
    e ignorado silenciosamente pra essa aresta, sem erro.

    Retorna (clusters, pernas_por_regiao_restante): cada cluster viavel (mais
    de uma regiao envolvida e existe empresa com veiculo ativo que atenda
    todas) vira uma tupla (regiao_rotulo, empresa_ids_da_intersecao,
    pernas_do_cluster); as pernas dos clusters viaveis saem do dict residual
    (processadas a parte, com a frota da intersecao). Cluster sem empresa
    com frota em comum e descartado -- suas pernas continuam no dict
    residual, como se nao tivessem pin nenhum.
    """
    campo_pin = "pin_ida_agenda_id" if sentido == Sentido.IDA else "pin_retorno_agenda_id"

    pernas_por_agenda: dict[int, dict] = {}
    regiao_por_agenda: dict[int, int] = {}
    for regiao_id, pernas in pernas_por_regiao.items():
        for perna in pernas:
            if perna["sentido"] != sentido:
                continue
            pernas_por_agenda[perna["agenda_id"]] = perna
            regiao_por_agenda[perna["agenda_id"]] = regiao_id

    pai: dict[int, int] = {aid: aid for aid in pernas_por_agenda}

    def encontrar(x: int) -> int:
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    def unir(a: int, b: int) -> None:
        ra, rb = encontrar(a), encontrar(b)
        if ra != rb:
            pai[ra] = rb

    for agenda_id in pernas_por_agenda:
        alvo_id = getattr(agendas_por_id[agenda_id], campo_pin)
        if alvo_id is not None and alvo_id in pernas_por_agenda:
            unir(agenda_id, alvo_id)

    grupos_por_raiz: dict[int, list[int]] = defaultdict(list)
    for agenda_id in pernas_por_agenda:
        grupos_por_raiz[encontrar(agenda_id)].append(agenda_id)

    clusters: list[tuple[int, list[int], list[dict]]] = []
    consumidos: set[int] = set()

    for membros_ids in grupos_por_raiz.values():
        if len(membros_ids) < 2:
            continue

        regioes_envolvidas = {regiao_por_agenda[aid] for aid in membros_ids}
        if len(regioes_envolvidas) < 2:
            continue  # todo mundo ja estava na mesma regiao, nao precisa de tratamento especial

        intersecao = set(empresas_por_regiao.get(next(iter(regioes_envolvidas)), []))
        for regiao_id in regioes_envolvidas:
            intersecao &= set(empresas_por_regiao.get(regiao_id, []))
        intersecao &= empresas_com_veiculo

        if not intersecao:
            print(
                f"[geracao] pin inviavel entre agendas {membros_ids} ({sentido.value}): "
                f"nenhuma empresa com frota atende as regioes {regioes_envolvidas}, pin ignorado"
            )
            continue

        membros = [pernas_por_agenda[aid] for aid in membros_ids]
        clusters.append((min(regioes_envolvidas), sorted(intersecao), membros))
        consumidos.update(membros_ids)

    pernas_por_regiao_restante = {
        regiao_id: [p for p in pernas if p["agenda_id"] not in consumidos]
        for regiao_id, pernas in pernas_por_regiao.items()
    }
    return clusters, pernas_por_regiao_restante


def gerar_agendamento_dia(db: Session, data: dt.date) -> list[ViagemDia]:
    """Gera as ViagemDia + ViagemDiaPassageiro de uma data a partir da agenda semanal.

    Idempotente: se ja existir ViagemDia para a data, retorna o que ja foi
    gerado em vez de duplicar (a tela de agendamento so mostra "Gerar" quando
    ainda nao existe nada para a data).

    Agrupa os usuarios Fixo por regiao de origem (ordenados por `ordem`, curado
    manualmente para manter juntos quem mora perto) e abre carros por
    regiao/sentido/horario ate a frota disponivel se esgotar; o que sobra fica
    de fora para alocacao manual na tela de escala do dia.

    No Retorno o carro opera na regiao do destino (ex: regiao da escola, de
    onde o usuario esta saindo nessa perna) em vez da regiao de origem/casa, e
    a ordem de preenchimento prioriza horario, depois o destino exato (mesmo
    local), so entao a regiao (local diferente, mesma regiao) -- ao contrario
    da Ida, que so usa horario + `ordem` manual.
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
    agendas_por_id = {a.id: a for a in agendas}

    pernas_por_regiao = _montar_pernas(agendas, excecoes, locais_em_recesso, locais_regiao)

    todas_viagens: list[ViagemDia] = []
    janelas: dict[int, tuple[dt.time, dt.time]] = {}
    avisos_emitidos: set[tuple] = set()

    for sentido in (Sentido.IDA, Sentido.RETORNO):
        clusters, pernas_por_regiao = _resolver_clusters_pin(
            pernas_por_regiao, agendas_por_id, sentido, empresas_por_regiao, empresas_com_veiculo
        )
        for regiao_rotulo, empresa_ids_cluster, membros in clusters:
            membros.sort(key=_chave_ordenacao_perna)
            _preencher_regiao(
                db, regiao_rotulo, membros, data, todas_viagens, janelas, avisos_emitidos, ultimos_usos_veiculo, empresa_ids_cluster
            )

    for regiao_id, pernas in pernas_por_regiao.items():
        pernas.sort(key=_chave_ordenacao_perna)
        _preencher_regiao(
            db,
            regiao_id,
            pernas,
            data,
            todas_viagens,
            janelas,
            avisos_emitidos,
            ultimos_usos_veiculo,
            empresas_por_regiao.get(regiao_id, []),
        )

    db.flush()
    _atribuir_condutores(db, todas_viagens, data, ultimos_usos_condutor, empresas_por_regiao)
    db.commit()
    for viagem in todas_viagens:
        db.refresh(viagem)
    print(f"[geracao] {len(todas_viagens)} viagens geradas")
    return todas_viagens


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
    """Preenche os carros de uma regiao (ou de um cluster pinado, rotulado
    com uma regiao so pra exibicao), na ordem de `ordem`, abrindo um novo
    carro (leg) sempre que o sentido/horario atual estoura a capacidade dos
    carros ja abertos para esse mesmo sentido/horario. `empresa_ids` ja vem
    resolvido pelo chamador -- da regiao (caminho normal) ou da intersecao de
    empresas de um cluster pinado cross-regiao.

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


def _horario_garagem(hora: dt.time) -> dt.time:
    referencia = dt.datetime.combine(dt.date.today(), hora) - dt.timedelta(minutes=TEMPO_SAIDA_GARAGEM_MINUTOS)
    return referencia.time()


def _mapa_empresas_por_regiao(db: Session) -> dict[int, list[int]]:
    """Empresas de cada regiao, pre-carregado uma unica vez por geracao --
    antes era consultado de novo a cada carro aberto e a cada viagem na
    atribuicao de condutor.
    """
    resultado: dict[int, list[int]] = defaultdict(list)
    for empresa_id, regiao_id in db.query(empresa_regiao.c.empresa_id, empresa_regiao.c.regiao_id).all():
        resultado[regiao_id].append(empresa_id)
    return resultado


# --------------------------------------------------------------------------
# Preview do modo Base (molde por dia da semana) -- somente leitura, nunca
# persiste ViagemDia/ViagemDiaPassageiro. Serve pro usuario visualizar como a
# geracao alocaria carros numa semana tipica e curar `ordem_ida`/
# `ordem_retorno` arrastando, sem misturar dados de template com dados
# operacionais reais.
# --------------------------------------------------------------------------

def _mapa_veiculos_por_empresa(db: Session, empresa_ids: set[int]) -> dict[int, list[Veiculo]]:
    """Veiculos ATIVOS de um conjunto de empresas, em ordem estavel por id --
    sem historico de "ultimo uso", que so existe pra uma data real. Base
    reaproveitada tanto pro mapa por regiao quanto pra intersecao de um
    cluster pinado cross-regiao.
    """
    resultado: dict[int, list[Veiculo]] = defaultdict(list)
    if not empresa_ids:
        return resultado
    for veiculo in (
        db.query(Veiculo)
        .filter(Veiculo.empresa_id.in_(empresa_ids), Veiculo.status == StatusVeiculo.ATIVO)
        .order_by(Veiculo.id)
        .all()
    ):
        resultado[veiculo.empresa_id].append(veiculo)
    return resultado


def _mapa_veiculos_por_regiao(
    empresas_por_regiao: dict[int, list[int]], veiculos_por_empresa: dict[int, list[Veiculo]]
) -> dict[int, list[Veiculo]]:
    """Veiculos ATIVOS de cada regiao (via empresas que a atendem), em ordem
    estavel por id.
    """
    return {
        regiao_id: [v for empresa_id in empresa_ids for v in veiculos_por_empresa.get(empresa_id, [])]
        for regiao_id, empresa_ids in empresas_por_regiao.items()
    }


def montar_preview_semana(db: Session, dia_semana: DiaSemana) -> list[dict]:
    """Preview de como a geracao alocaria carros pra um dia da semana
    generico, direto a partir da agenda semanal -- sem excecao pontual, sem
    recesso, sem rodizio historico de condutor/veiculo (nao fazem sentido
    fora de uma data real) e sem atribuicao de condutor. Nada e persistido.

    Devolve grupos no mesmo formato que a geracao real devolve pra tela (ids
    sinteticos, sem veiculo/condutor identificados pra nao sugerir uma escala
    que o rodizio diario pode nao repetir). Quem nao coube na frota
    disponivel da regiao/horario entra num grupo "overflow" (capacidade 0,
    sem veiculo) -- continua arrastavel/reordenavel como qualquer outro
    grupo, so que sempre com o aviso de lugares acima da capacidade.
    """
    agendas = _agendas_fixo_da_semana(db, dia_semana)
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    empresas_por_regiao = _mapa_empresas_por_regiao(db)
    todos_empresa_ids = {eid for ids in empresas_por_regiao.values() for eid in ids}
    veiculos_por_empresa = _mapa_veiculos_por_empresa(db, todos_empresa_ids)
    veiculos_por_regiao = _mapa_veiculos_por_regiao(empresas_por_regiao, veiculos_por_empresa)
    empresas_com_veiculo = {eid for eid, vs in veiculos_por_empresa.items() if vs}
    agendas_por_id = {a.id: a for a in agendas}

    pernas_por_regiao = _montar_pernas(agendas, {}, set(), locais_regiao)

    grupos: list[dict] = []
    janelas: dict[int, tuple[dt.time, dt.time]] = {}
    veiculo_por_grupo: dict[int, int] = {}
    contador_id = [0]

    for sentido in (Sentido.IDA, Sentido.RETORNO):
        clusters, pernas_por_regiao = _resolver_clusters_pin(
            pernas_por_regiao, agendas_por_id, sentido, empresas_por_regiao, empresas_com_veiculo
        )
        for regiao_rotulo, empresa_ids_cluster, membros in clusters:
            membros.sort(key=_chave_ordenacao_perna)
            veiculos_cluster = [v for empresa_id in empresa_ids_cluster for v in veiculos_por_empresa.get(empresa_id, [])]
            _preencher_regiao_preview(regiao_rotulo, membros, grupos, janelas, veiculo_por_grupo, veiculos_cluster, contador_id)

    for regiao_id, pernas in pernas_por_regiao.items():
        pernas.sort(key=_chave_ordenacao_perna)
        _preencher_regiao_preview(
            regiao_id, pernas, grupos, janelas, veiculo_por_grupo, veiculos_por_regiao.get(regiao_id, []), contador_id
        )
    return grupos


def _preencher_regiao_preview(
    regiao_id: int,
    pernas: list[dict],
    grupos: list[dict],
    janelas: dict[int, tuple[dt.time, dt.time]],
    veiculo_por_grupo: dict[int, int],
    veiculos: list[Veiculo],
    contador_id: list[int],
) -> None:
    """Espelha `_preencher_regiao`, mas monta dicts em memoria (nada de
    `db.add`) e sem rodizio/condutor. Um grupo com `capacidade` 0 e o
    "overflow" da regiao/sentido/horario (frota esgotada) -- sempre aceita
    mais gente (por isso o `or g["capacidade"] == 0` no filtro de vaga).
    `veiculos` ja vem resolvido pelo chamador -- da regiao (caminho normal)
    ou da intersecao de empresas de um cluster pinado cross-regiao.
    """
    ocupacao: dict[tuple[int, Sentido, dt.time], int] = defaultdict(int)
    abertos_por_perna: dict[tuple[Sentido, dt.time], list[dict]] = defaultdict(list)

    for perna in pernas:
        perna_chave = (perna["sentido"], perna["hora"])
        lugares = 2 if perna["acompanhante"] else 1
        grupo = next(
            (
                g
                for g in abertos_por_perna[perna_chave]
                if g["capacidade"] == 0 or ocupacao[(g["id"], *perna_chave)] + lugares <= g["capacidade"]
            ),
            None,
        )
        if grupo is None:
            grupo = _abrir_grupo_preview(
                regiao_id, perna["hora"], janelas, veiculo_por_grupo, veiculos, contador_id
            ) or _abrir_grupo_overflow_preview(regiao_id, perna["hora"], contador_id)
            abertos_por_perna[perna_chave].append(grupo)
            grupos.append(grupo)

        contador_id[0] += 1
        grupo["passageiros"].append(
            {
                "id": -contador_id[0],
                "viagem_dia_id": grupo["id"],
                "usuario_id": perna["usuario_id"],
                "usuario": perna["usuario"],
                "sentido": perna["sentido"],
                "hora": perna["hora"],
                "origem": perna["origem"],
                "regiao_origem_id": perna["regiao_origem_id"],
                "destino_id": perna["destino_id"],
                "regiao_destino_id": perna["regiao_destino_id"],
                "acompanhante": perna["acompanhante"],
                "ordem": perna["ordem"],
                "status": StatusAtendimentoDia.AGENDADO,
                "observacoes": None,
                "irregular": False,
                "motivo_irregular": None,
                "agenda_id": perna["agenda_id"],
            }
        )
        ocupacao[(grupo["id"], *perna_chave)] += lugares


def _abrir_grupo_overflow_preview(regiao_id: int, hora: dt.time, contador_id: list[int]) -> dict:
    """Grupo "sem vaga" da regiao/sentido/horario -- frota esgotada. Capacidade
    0 faz o LegBlock/CarroCard ja mostrarem o aviso de lugares acima da
    capacidade automaticamente, sem nenhuma logica extra no frontend.
    """
    contador_id[0] += 1
    return {
        "id": -contador_id[0],
        "data": DATA_PREVIEW_PLACEHOLDER,
        "regiao_id": regiao_id,
        "empresa_id": None,
        "condutor_id": None,
        "veiculo_id": None,
        "horario_saida": _horario_garagem(hora),
        "capacidade": 0,
        "status": StatusViagemDia.PLANEJADA,
        "observacoes": None,
        "passageiros": [],
        "condutor_em_ferias": False,
        "conflito_horario": False,
        "motivo_conflito_horario": None,
        "intervalo_inicio": None,
        "intervalo_fim": None,
    }


def _abrir_grupo_preview(
    regiao_id: int,
    hora: dt.time,
    janelas: dict[int, tuple[dt.time, dt.time]],
    veiculo_por_grupo: dict[int, int],
    veiculos: list[Veiculo],
    contador_id: list[int],
) -> dict | None:
    horario_saida = _horario_garagem(hora)
    veiculo = _proximo_veiculo_livre_preview(janelas, veiculo_por_grupo, horario_saida, hora, veiculos)
    if veiculo is None:
        return None  # sem veiculo disponivel na regiao/horario -- vira "sem vaga" no molde

    contador_id[0] += 1
    grupo_id = -contador_id[0]
    grupo = {
        "id": grupo_id,
        "data": DATA_PREVIEW_PLACEHOLDER,
        "regiao_id": regiao_id,
        "empresa_id": None,
        "condutor_id": None,
        "veiculo_id": None,
        "horario_saida": horario_saida,
        "capacidade": veiculo.capacidade,
        "status": StatusViagemDia.PLANEJADA,
        "observacoes": None,
        "passageiros": [],
        "condutor_em_ferias": False,
        "conflito_horario": False,
        "motivo_conflito_horario": None,
        "intervalo_inicio": None,
        "intervalo_fim": None,
    }
    janelas[grupo_id] = (horario_saida, hora)
    veiculo_por_grupo[grupo_id] = veiculo.id
    return grupo


def _proximo_veiculo_livre_preview(
    janelas: dict[int, tuple[dt.time, dt.time]],
    veiculo_por_grupo: dict[int, int],
    inicio: dt.time,
    fim: dt.time,
    candidatos: list[Veiculo],
) -> Veiculo | None:
    """Igual a `_proximo_veiculo_livre`, mas sem rodizio historico (nao existe
    "ultimo uso" pra um dia da semana generico) -- so evita reusar o mesmo
    veiculo em janelas que se sobrepoem dentro do proprio preview, sempre em
    ordem estavel por id. `candidatos` ja vem resolvido pelo chamador (regiao
    ou intersecao de um cluster pinado).
    """

    def livre(veiculo_id: int) -> bool:
        for grupo_id, outro_veiculo_id in veiculo_por_grupo.items():
            if outro_veiculo_id != veiculo_id:
                continue
            janela = janelas.get(grupo_id)
            if janela and janelas_sobrepoem(inicio, fim, janela[0], janela[1]):
                return False
        return True

    return next((v for v in candidatos if livre(v.id)), None)


def _reindexar_bucket(bucket: list[dict], campo: str, agendas_por_id: dict[int, UsuarioAgendaSemanal]) -> None:
    """Regrava `ordem_ida`/`ordem_retorno` (1..N) de todo mundo no bucket, na
    ordem em que aparecem na lista -- usado tanto ao persistir o molde
    inteiro quanto ao reordenar um unico arrastar. Comeca em 1 (nao 0) porque
    0 e reservado como sentinela de "sem classificacao"; depois de qualquer
    arrasto, todo mundo do bucket sai "classificado".
    """
    for indice, perna in enumerate(bucket, start=1):
        setattr(agendas_por_id[perna["agenda_id"]], campo, indice)


def persistir_ordem_semana(db: Session, dia_semana: DiaSemana) -> None:
    """Ao "gerar" o molde no modo Base, ja regrava `ordem_ida`/`ordem_retorno`
    sequencial (0..N-1) refletindo o agrupamento atual de cada bucket --
    sem isso, quem o usuario nao arrastou continuaria com ordem=0 (empate),
    sujeito a reordenar de forma imprevisivel se a agenda semanal mudar
    (usuario novo, remocao etc) antes do proximo arrasto.
    """
    agendas = _agendas_fixo_da_semana(db, dia_semana)
    agendas_por_id = {a.id: a for a in agendas}
    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    pernas_por_regiao = _montar_pernas(agendas, {}, set(), locais_regiao)

    for pernas in pernas_por_regiao.values():
        for sentido, campo in ((Sentido.IDA, "ordem_ida"), (Sentido.RETORNO, "ordem_retorno")):
            bucket = sorted((p for p in pernas if p["sentido"] == sentido), key=_chave_ordenacao_perna)
            _reindexar_bucket(bucket, campo, agendas_por_id)

    db.commit()


def reordenar_preview_semana(
    db: Session,
    dia_semana: DiaSemana,
    agenda_id: int,
    sentido: Sentido,
    ordem: int,
    pin_para_agenda_id: int | None = None,
) -> None:
    """Persiste um arrastar do modo Base: reindexa `ordem_ida`/`ordem_retorno`
    de TODO o bucket de quem foi movido -- um criterio global de prioridade
    (quem decide em qual carro cada um cai na geracao), nao uma ordem "dentro
    de um carro" como `ViagemDiaPassageiro.ordem` na tela do dia real.

    Se `pin_para_agenda_id` for de uma regiao diferente da natural do usuario
    movido, tenta um pin cross-regiao: so grava se existir empresa que atenda
    todas as regioes do cluster resultante (reaproveita `_resolver_clusters_pin`,
    a mesma logica usada na geracao) -- senao reverte e leva ValueError, sem
    persistir nada. Mesma regiao (ou `pin_para_agenda_id=None`) limpa
    qualquer pin existente daquele sentido e volta ao comportamento normal.
    """
    agendas = _agendas_fixo_da_semana(db, dia_semana)
    agendas_por_id = {a.id: a for a in agendas}
    agenda_movida = agendas_por_id.get(agenda_id)
    if agenda_movida is None:
        raise ValueError("Agenda nao encontrada para esse dia da semana")

    locais_regiao = dict(db.query(Local.id, Local.regiao_id).all())
    empresas_por_regiao = _mapa_empresas_por_regiao(db)
    empresas_com_veiculo = _empresas_com_veiculo_ativo(db)
    pernas_por_regiao = _montar_pernas(agendas, {}, set(), locais_regiao)

    def regiao_de(agenda: UsuarioAgendaSemanal) -> int:
        regiao_destino = locais_regiao.get(agenda.destino_id) if agenda.destino_id else None
        return _regiao_alocacao(sentido, agenda.regiao_origem_id, regiao_destino)

    campo_ordem = "ordem_ida" if sentido == Sentido.IDA else "ordem_retorno"
    campo_pin = "pin_ida_agenda_id" if sentido == Sentido.IDA else "pin_retorno_agenda_id"
    regiao_movida = regiao_de(agenda_movida)

    cross_regiao = False
    if pin_para_agenda_id is not None:
        alvo_agenda = agendas_por_id.get(pin_para_agenda_id)
        if alvo_agenda is None:
            raise ValueError("Agenda de destino nao encontrada")
        cross_regiao = regiao_de(alvo_agenda) != regiao_movida

    setattr(agenda_movida, campo_pin, pin_para_agenda_id if cross_regiao else None)

    clusters, pernas_por_regiao_restante = _resolver_clusters_pin(
        pernas_por_regiao, agendas_por_id, sentido, empresas_por_regiao, empresas_com_veiculo
    )
    bucket = next((membros for _, _, membros in clusters if any(p["agenda_id"] == agenda_id for p in membros)), None)

    if cross_regiao and bucket is None:
        setattr(agenda_movida, campo_pin, None)  # inviavel -- reverte, nada persiste
        raise ValueError("Nenhuma empresa atende as regioes envolvidas, nao e possivel juntar esses carros")

    if bucket is None:
        # sem cluster (nao pinado): o bucket real e por (regiao, sentido,
        # horario) -- so essa combinacao decide em qual carro cada um cai
        # (`_preencher_regiao`/`_preencher_regiao_preview` abrem um carro por
        # horario dentro da regiao). Faltar o filtro de horario aqui mistura
        # gente de horarios diferentes no reindex e escala quem nem foi
        # arrastado pra outro carro na proxima geracao.
        perna_movida_atual = next(
            (p for pernas in pernas_por_regiao.values() for p in pernas if p["agenda_id"] == agenda_id and p["sentido"] == sentido),
            None,
        )
        if perna_movida_atual is None:
            raise ValueError("Usuario nao tem esse sentido elegivel hoje")
        bucket = [
            p
            for p in pernas_por_regiao_restante.get(regiao_movida, [])
            if p["sentido"] == sentido and p["hora"] == perna_movida_atual["hora"]
        ]

    bucket = sorted(bucket, key=_chave_ordenacao_perna)
    indice_atual = next((i for i, p in enumerate(bucket) if p["agenda_id"] == agenda_id), None)
    if indice_atual is None:
        raise ValueError("Usuario nao pertence a esse bucket nesse sentido")

    perna_movida = bucket.pop(indice_atual)
    posicao = max(0, min(ordem, len(bucket)))
    bucket.insert(posicao, perna_movida)

    _reindexar_bucket(bucket, campo_ordem, agendas_por_id)
    db.commit()


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
) -> ViagemDia | None:
    if not empresa_ids:
        chave_aviso = ("sem_empresa", regiao_id)
        if chave_aviso not in avisos_emitidos:
            avisos_emitidos.add(chave_aviso)
            print(f"[geracao] regiao_id={regiao_id}: nenhuma empresa vinculada (empresa_regiao vazio pra essa regiao)")
        return None

    horario_saida = _horario_garagem(hora)
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
