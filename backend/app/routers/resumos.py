import calendar
import datetime as dt

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import obter_conta_atual
from app.database import get_db
from app.services.km import km_do_registro, registros_km_periodo

router = APIRouter(prefix="/resumos", tags=["resumos"], dependencies=[Depends(obter_conta_atual)])

_DIAS_SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]


def _range_mes(ano: int, mes: int) -> tuple[dt.date, dt.date]:
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return dt.date(ano, mes, 1), dt.date(ano, mes, ultimo_dia)


def _seis_meses(ano: int, mes: int) -> list[tuple[int, int]]:
    """Mes selecionado + 5 meses anteriores, do mais antigo pro mais recente."""
    meses = []
    for i in range(5, -1, -1):
        m = mes - i
        a = ano
        while m <= 0:
            m += 12
            a -= 1
        meses.append((a, m))
    return meses


def _empresas_filtradas(db: Session, empresa_id: int | None) -> list[models.Empresa]:
    query = db.query(models.Empresa)
    if empresa_id is not None:
        query = query.filter(models.Empresa.id == empresa_id)
    return query.order_by(models.Empresa.nome).all()


# --------------------------------------------------------------------------
# Rodagem
# --------------------------------------------------------------------------

def _uso_frota_diario(db: Session, inicio: dt.date, fim: dt.date, empresa_id: int | None) -> list[schemas.UsoFrotaDia]:
    query = db.query(models.ViagemDia).filter(
        models.ViagemDia.data >= inicio,
        models.ViagemDia.data <= fim,
        models.ViagemDia.veiculo_id.isnot(None),
        models.ViagemDia.empresa_id.isnot(None),
    )
    if empresa_id is not None:
        query = query.filter(models.ViagemDia.empresa_id == empresa_id)

    por_dia: dict[dt.date, dict[int, set[int]]] = {}
    for v in query.all():
        por_dia.setdefault(v.data, {}).setdefault(v.empresa_id, set()).add(v.veiculo_id)

    return [
        schemas.UsoFrotaDia(
            data=data,
            dia_semana=_DIAS_SEMANA[data.weekday()],
            por_empresa={str(emp_id): len(veiculos) for emp_id, veiculos in por_empresa.items()},
        )
        for data, por_empresa in sorted(por_dia.items())
    ]


@router.get("/rodagem", response_model=schemas.ResumoRodagem)
def resumo_rodagem(ano: int, mes: int, empresa_id: int | None = None, db: Session = Depends(get_db)):
    inicio, fim = _range_mes(ano, mes)
    empresas = _empresas_filtradas(db, empresa_id)

    registros = registros_km_periodo(db, inicio, fim, empresa_id)
    por_veiculo: dict[int, schemas.KmPorVeiculo] = {}
    km_por_empresa_id: dict[int, int] = {}
    for r in registros:
        km = km_do_registro(r)
        v = r.veiculo
        if v.id not in por_veiculo:
            por_veiculo[v.id] = schemas.KmPorVeiculo(
                veiculo_id=v.id, placa=v.placa, prefixo=v.prefixo,
                empresa_id=v.empresa_id, empresa_nome=v.empresa.nome, km_total=0,
            )
        por_veiculo[v.id].km_total += km
        km_por_empresa_id[v.empresa_id] = km_por_empresa_id.get(v.empresa_id, 0) + km

    km_total_periodo = sum(km_por_empresa_id.values())
    km_por_empresa = [
        schemas.KmPorEmpresa(
            empresa_id=empresa.id,
            empresa_nome=empresa.nome,
            km_total=km_por_empresa_id.get(empresa.id, 0),
            percentual_contrato=empresa.percentual_contrato,
            percentual_km_periodo=round(km_por_empresa_id.get(empresa.id, 0) / km_total_periodo * 100, 2) if km_total_periodo else 0.0,
        )
        for empresa in empresas
    ]

    evolucao: list[schemas.EvolucaoKmMes] = []
    for a, m in _seis_meses(ano, mes):
        ini_m, fim_m = _range_mes(a, m)
        km_mes: dict[int, int] = {}
        for r in registros_km_periodo(db, ini_m, fim_m, empresa_id):
            km_mes[r.veiculo.empresa_id] = km_mes.get(r.veiculo.empresa_id, 0) + km_do_registro(r)
        for empresa in empresas:
            evolucao.append(
                schemas.EvolucaoKmMes(ano=a, mes=m, empresa_id=empresa.id, empresa_nome=empresa.nome, km_total=km_mes.get(empresa.id, 0))
            )

    return schemas.ResumoRodagem(
        km_por_veiculo=sorted(por_veiculo.values(), key=lambda k: k.placa),
        km_por_empresa=km_por_empresa,
        evolucao_km_empresa=evolucao,
        uso_frota_diario=_uso_frota_diario(db, inicio, fim, empresa_id),
    )


# --------------------------------------------------------------------------
# Atendimentos
# --------------------------------------------------------------------------

def _passageiros_periodo(db: Session, inicio: dt.date, fim: dt.date, empresa_id: int | None) -> list[models.ViagemDiaPassageiro]:
    """Todo atendimento planejado no periodo, incluindo quem ficou sem vaga
    (viagem_dia_id nulo, data direto no passageiro) -- so exceções antecipadas
    ficam de fora, pois essas nunca chegam a gerar o registro.
    """
    query = (
        db.query(models.ViagemDiaPassageiro)
        .outerjoin(models.ViagemDia, models.ViagemDiaPassageiro.viagem_dia_id == models.ViagemDia.id)
        .options(
            joinedload(models.ViagemDiaPassageiro.viagem_dia),
            joinedload(models.ViagemDiaPassageiro.usuario),
            joinedload(models.ViagemDiaPassageiro.regiao_origem),
            joinedload(models.ViagemDiaPassageiro.origem_local),
            joinedload(models.ViagemDiaPassageiro.destino),
        )
        .filter(
            sa.or_(
                models.ViagemDia.data.between(inicio, fim),
                sa.and_(models.ViagemDiaPassageiro.viagem_dia_id.is_(None), models.ViagemDiaPassageiro.data.between(inicio, fim)),
            )
        )
    )
    if empresa_id is not None:
        query = query.filter(models.ViagemDia.empresa_id == empresa_id)
    return query.all()


def _data_efetiva(p: models.ViagemDiaPassageiro) -> dt.date:
    return p.viagem_dia.data if p.viagem_dia is not None else p.data


@router.get("/atendimentos", response_model=schemas.ResumoAtendimentos)
def resumo_atendimentos(ano: int, mes: int, empresa_id: int | None = None, db: Session = Depends(get_db)):
    inicio, fim = _range_mes(ano, mes)
    passageiros = _passageiros_periodo(db, inicio, fim, empresa_id)

    grade_contagem: dict[tuple[dt.date, dt.time], int] = {}
    planejados_por_usuario: dict[int, int] = {}
    cancelamento_por_usuario: dict[int, dict] = {}
    for p in passageiros:
        chave = (_data_efetiva(p), p.hora)
        grade_contagem[chave] = grade_contagem.get(chave, 0) + 1
        planejados_por_usuario[p.usuario_id] = planejados_por_usuario.get(p.usuario_id, 0) + 1

        if p.status == models.StatusAtendimentoDia.CANCELADO or p.viagem_perdida:
            entrada = cancelamento_por_usuario.setdefault(
                p.usuario_id, {"nome": p.usuario.nome, "cancelamentos": 0, "viagens_perdidas": 0}
            )
            if p.status == models.StatusAtendimentoDia.CANCELADO:
                entrada["cancelamentos"] += 1
            if p.viagem_perdida:
                entrada["viagens_perdidas"] += 1

    grade = [
        schemas.CelulaAtendimento(data=data, hora=hora, quantidade=quantidade)
        for (data, hora), quantidade in sorted(grade_contagem.items())
    ]
    cancelamentos = sorted(
        (
            schemas.CancelamentoUsuario(
                usuario_id=uid,
                usuario_nome=v["nome"],
                planejados=planejados_por_usuario.get(uid, 0),
                cancelamentos=v["cancelamentos"],
                percentual_cancelamento=round(v["cancelamentos"] / planejados_por_usuario[uid] * 100, 2) if planejados_por_usuario.get(uid) else 0.0,
                viagens_perdidas=v["viagens_perdidas"],
            )
            for uid, v in cancelamento_por_usuario.items()
        ),
        key=lambda c: (-c.cancelamentos, c.usuario_nome),
    )

    return schemas.ResumoAtendimentos(grade=grade, cancelamento_por_usuario=cancelamentos)


# --------------------------------------------------------------------------
# Outros
# --------------------------------------------------------------------------

@router.get("/outros", response_model=schemas.ResumoOutros)
def resumo_outros(ano: int, mes: int, empresa_id: int | None = None, db: Session = Depends(get_db)):
    inicio, fim = _range_mes(ano, mes)

    veiculos_ativos_query = db.query(models.Veiculo).filter(models.Veiculo.status == models.StatusVeiculo.ATIVO)
    if empresa_id is not None:
        veiculos_ativos_query = veiculos_ativos_query.filter(models.Veiculo.empresa_id == empresa_id)
    veiculos_ativos = veiculos_ativos_query.count()

    viagens_query = db.query(models.ViagemDia).options(joinedload(models.ViagemDia.passageiros)).filter(
        models.ViagemDia.data >= inicio,
        models.ViagemDia.data <= fim,
        models.ViagemDia.veiculo_id.isnot(None),
    )
    if empresa_id is not None:
        viagens_query = viagens_query.filter(models.ViagemDia.empresa_id == empresa_id)
    viagens = viagens_query.all()

    veiculos_utilizados = len({v.veiculo_id for v in viagens})
    percentual_ocioso = round((1 - veiculos_utilizados / veiculos_ativos) * 100, 2) if veiculos_ativos else 0.0

    passageiros_embarcados = 0
    capacidade_total = 0
    for v in viagens:
        capacidade_total += v.capacidade_usuarios + v.capacidade_acompanhantes
        passageiros_embarcados += len([p for p in v.passageiros if p.status != models.StatusAtendimentoDia.CANCELADO])
    percentual_ocupacao = round(passageiros_embarcados / capacidade_total * 100, 2) if capacidade_total else 0.0

    registros_km = registros_km_periodo(db, inicio, fim, empresa_id)
    km_total = sum(km_do_registro(r) for r in registros_km)
    total_atendimentos_realizados = passageiros_embarcados
    km_por_atendimento = round(km_total / total_atendimentos_realizados, 2) if total_atendimentos_realizados else None

    passageiros = _passageiros_periodo(db, inicio, fim, empresa_id)
    ranking: dict[int, dict] = {}
    for p in passageiros:
        if p.status == models.StatusAtendimentoDia.CANCELADO and p.regiao_origem_id is not None:
            entrada = ranking.setdefault(p.regiao_origem_id, {"nome": p.regiao_origem.nome if p.regiao_origem else "-", "cancelamentos": 0})
            entrada["cancelamentos"] += 1
    ranking_lista = sorted(
        (schemas.RankingCancelamentoRegiao(regiao_id=rid, regiao_nome=v["nome"], cancelamentos=v["cancelamentos"]) for rid, v in ranking.items()),
        key=lambda r: -r.cancelamentos,
    )

    # Cada trecho (perna) do dia referencia um Local na origem e/ou no destino;
    # uma ida-e-volta convencional e 2 trechos apontando pro mesmo Local (uma
    # vez como destino, outra como origem). Pra nao contar isso como 2
    # atendimentos, agrupamos por (usuario, data) dentro de cada Local antes
    # de contar -- ida+volta no mesmo dia vira 1 unico atendimento naquele Local.
    visitas_por_local: dict[int, set[tuple[int, dt.date]]] = {}
    nome_do_local: dict[int, str] = {}
    for p in passageiros:
        data_ref = _data_efetiva(p)
        if p.origem_tipo == models.TipoPonto.LOCAL and p.origem_id is not None:
            visitas_por_local.setdefault(p.origem_id, set()).add((p.usuario_id, data_ref))
            if p.origem_local is not None:
                nome_do_local[p.origem_id] = p.origem_local.nome
        if p.destino_tipo == models.TipoPonto.LOCAL and p.destino_id is not None:
            visitas_por_local.setdefault(p.destino_id, set()).add((p.usuario_id, data_ref))
            if p.destino is not None:
                nome_do_local[p.destino_id] = p.destino.nome

    total_atendimentos_local = sum(len(visitas) for visitas in visitas_por_local.values())
    atendimentos_por_local = sorted(
        (
            schemas.AtendimentosPorLocal(
                local_id=lid,
                local_nome=nome_do_local.get(lid, "-"),
                atendimentos=len(visitas),
                percentual=round(len(visitas) / total_atendimentos_local * 100, 2) if total_atendimentos_local else 0.0,
            )
            for lid, visitas in visitas_por_local.items()
        ),
        key=lambda a: -a.atendimentos,
    )

    return schemas.ResumoOutros(
        ociosidade_frota=schemas.OciosidadeFrota(
            veiculos_ativos=veiculos_ativos, veiculos_utilizados=veiculos_utilizados, percentual_ocioso=percentual_ocioso
        ),
        taxa_ocupacao=schemas.TaxaOcupacao(
            passageiros=passageiros_embarcados, capacidade_total=capacidade_total, percentual=percentual_ocupacao
        ),
        km_por_atendimento=km_por_atendimento,
        ranking_cancelamento_regiao=ranking_lista,
        atendimentos_por_local=atendimentos_por_local,
    )


# --------------------------------------------------------------------------
# Relatorio PDF (capa + todas as secoes acima, reestruturado como documento)
# --------------------------------------------------------------------------

@router.get("/relatorio")
def relatorio_pdf(ano: int, mes: int, empresa_id: int | None = None, db: Session = Depends(get_db)):
    # import local pra evitar ciclo: services.relatorio importa as funcoes
    # deste modulo (resumo_rodagem/resumo_atendimentos/resumo_outros) pra
    # reaproveitar a mesma agregacao do JSON, entao nao pode ser importado
    # no topo do arquivo.
    from app.services.relatorio import gerar_pdf_relatorio_resumos

    conteudo = gerar_pdf_relatorio_resumos(db, ano, mes, empresa_id)
    nome_arquivo = f"relatorio-resumos-{ano}-{mes:02d}.pdf"
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
