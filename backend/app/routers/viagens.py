import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.services.exportacao import gerar_zip_agendamentos
from app.services.geracao import gerar_agendamento_dia

router = APIRouter(prefix="/viagens", tags=["viagens"])


def _get_viagem_ou_404(db: Session, viagem_id: int) -> models.ViagemDia:
    viagem = db.get(models.ViagemDia, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"ViagemDia {viagem_id} nao encontrada")
    return viagem


def _get_passageiro_ou_404(db: Session, passageiro_id: int) -> models.ViagemDiaPassageiro:
    passageiro = db.get(models.ViagemDiaPassageiro, passageiro_id)
    if passageiro is None:
        raise HTTPException(status_code=404, detail=f"Passageiro {passageiro_id} nao encontrado")
    return passageiro


def _verificar_conflito(
    db: Session, viagem_dia_id: int, usuario_id: int, sentido: models.Sentido, excluir_passageiro_id: int | None = None
) -> None:
    query = db.query(models.ViagemDiaPassageiro).filter(
        models.ViagemDiaPassageiro.viagem_dia_id == viagem_dia_id,
        models.ViagemDiaPassageiro.usuario_id == usuario_id,
        models.ViagemDiaPassageiro.sentido == sentido,
    )
    if excluir_passageiro_id is not None:
        query = query.filter(models.ViagemDiaPassageiro.id != excluir_passageiro_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Usuario ja possui um atendimento de {sentido.value} nesse carro",
        )


def _calcular_irregularidade(db: Session, viagem: models.ViagemDia, regiao_origem_id: int | None):
    if viagem.empresa_id is None or regiao_origem_id is None:
        return False, None
    habilitada = (
        db.query(models.empresa_regiao)
        .filter(
            models.empresa_regiao.c.empresa_id == viagem.empresa_id,
            models.empresa_regiao.c.regiao_id == regiao_origem_id,
        )
        .first()
    )
    if habilitada is not None:
        return False, None
    regiao = db.get(models.Regiao, regiao_origem_id)
    nome_regiao = regiao.nome if regiao else str(regiao_origem_id)
    return True, f"Empresa da viagem nao esta habilitada para a regiao {nome_regiao} do usuario"


def _condutor_em_ferias(db: Session, condutor_id: int | None, data: dt.date) -> bool:
    if condutor_id is None:
        return False
    return (
        db.query(models.CondutorFerias)
        .filter(
            models.CondutorFerias.condutor_id == condutor_id,
            models.CondutorFerias.data_inicio <= data,
            models.CondutorFerias.data_fim >= data,
        )
        .first()
        is not None
    )


def _serializar_viagem(db: Session, viagem: models.ViagemDia) -> schemas.ViagemDiaRead:
    base = schemas.ViagemDiaRead.model_validate(viagem)
    passageiros = []
    for passageiro, passageiro_read in zip(viagem.passageiros, base.passageiros):
        irregular, motivo = _calcular_irregularidade(db, viagem, passageiro.regiao_origem_id)
        passageiros.append(passageiro_read.model_copy(update={"irregular": irregular, "motivo_irregular": motivo}))
    condutor_em_ferias = _condutor_em_ferias(db, viagem.condutor_id, viagem.data)
    return base.model_copy(update={"passageiros": passageiros, "condutor_em_ferias": condutor_em_ferias})


def _query_viagens(db: Session, data: dt.date):
    return (
        db.query(models.ViagemDia)
        .options(joinedload(models.ViagemDia.passageiros).joinedload(models.ViagemDiaPassageiro.usuario))
        .filter(models.ViagemDia.data == data)
        .order_by(models.ViagemDia.regiao_id, models.ViagemDia.horario_saida)
        .all()
    )


@router.get("", response_model=list[schemas.ViagemDiaRead])
def listar_viagens(data: dt.date, db: Session = Depends(get_db)):
    return [_serializar_viagem(db, v) for v in _query_viagens(db, data)]


@router.post("/gerar", response_model=list[schemas.ViagemDiaRead], status_code=201)
def gerar(data: dt.date, db: Session = Depends(get_db)):
    gerar_agendamento_dia(db, data)
    return [_serializar_viagem(db, v) for v in _query_viagens(db, data)]


@router.post("/abrir", response_model=schemas.ViagemDiaRead, status_code=201)
def abrir_viagem(payload: schemas.ViagemDiaAbrir, db: Session = Depends(get_db)):
    if db.get(models.Regiao, payload.regiao_id) is None:
        raise HTTPException(status_code=404, detail=f"Regiao {payload.regiao_id} nao encontrada")
    viagem = models.ViagemDia(
        data=payload.data,
        regiao_id=payload.regiao_id,
        horario_saida=payload.horario_saida,
        capacidade=payload.capacidade,
        agendamento_base_id=payload.agendamento_base_id,
        status=models.StatusViagemDia.PLANEJADA,
    )
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.patch("/{viagem_id}/atribuir", response_model=schemas.ViagemDiaRead)
def atribuir_condutor_veiculo(viagem_id: int, payload: schemas.ViagemDiaAtribuir, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    if payload.veiculo_id is not None:
        veiculo = db.get(models.Veiculo, payload.veiculo_id)
        if veiculo is None:
            raise HTTPException(status_code=404, detail=f"Veiculo {payload.veiculo_id} nao encontrado")
        viagem.veiculo_id = veiculo.id
        viagem.empresa_id = veiculo.empresa_id
    if payload.condutor_id is not None:
        if db.get(models.Condutor, payload.condutor_id) is None:
            raise HTTPException(status_code=404, detail=f"Condutor {payload.condutor_id} nao encontrado")
        viagem.condutor_id = payload.condutor_id
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.patch("/{viagem_id}/status", response_model=schemas.ViagemDiaRead)
def alterar_status_viagem(viagem_id: int, status: models.StatusViagemDia, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    viagem.status = status
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.delete("/{viagem_id}", status_code=204)
def remover_viagem(viagem_id: int, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    if viagem.passageiros:
        raise HTTPException(status_code=409, detail="Mova ou remova os passageiros antes de remover o carro")
    db.delete(viagem)
    db.commit()


# --------------------------------------------------------------------------
# Passageiros dentro de uma viagem do dia
# --------------------------------------------------------------------------

@router.post("/{viagem_id}/passageiros", response_model=schemas.ViagemDiaRead, status_code=201)
def adicionar_passageiro(viagem_id: int, payload: schemas.ViagemDiaPassageiroCreate, db: Session = Depends(get_db)):
    viagem = _get_viagem_ou_404(db, viagem_id)
    if db.get(models.Usuario, payload.usuario_id) is None:
        raise HTTPException(status_code=404, detail=f"Usuario {payload.usuario_id} nao encontrado")
    _verificar_conflito(db, viagem_id, payload.usuario_id, payload.sentido)
    maior_ordem = max((p.ordem for p in viagem.passageiros), default=-1)
    passageiro = models.ViagemDiaPassageiro(viagem_dia_id=viagem_id, ordem=maior_ordem + 1, **payload.model_dump())
    db.add(passageiro)
    db.commit()
    db.refresh(viagem)
    return _serializar_viagem(db, viagem)


@router.patch("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead)
def atualizar_passageiro(passageiro_id: int, payload: schemas.ViagemDiaPassageiroAtualizar, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    dados = payload.model_dump(exclude_unset=True)
    if "sentido" in dados:
        _verificar_conflito(db, passageiro.viagem_dia_id, passageiro.usuario_id, dados["sentido"], passageiro.id)
    for campo, valor in dados.items():
        setattr(passageiro, campo, valor)
    db.commit()
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(db, viagem)


@router.patch("/passageiros/{passageiro_id}/mover", response_model=schemas.ViagemDiaRead)
def mover_passageiro(passageiro_id: int, payload: schemas.ViagemDiaPassageiroMover, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    _get_viagem_ou_404(db, payload.viagem_dia_destino_id)
    _verificar_conflito(db, payload.viagem_dia_destino_id, passageiro.usuario_id, passageiro.sentido, passageiro.id)
    passageiro.viagem_dia_id = payload.viagem_dia_destino_id
    if payload.ordem is not None:
        passageiro.ordem = payload.ordem
    db.commit()
    viagem = _get_viagem_ou_404(db, payload.viagem_dia_destino_id)
    return _serializar_viagem(db, viagem)


@router.patch("/passageiros/{passageiro_id}/status", response_model=schemas.ViagemDiaRead)
def alterar_status_passageiro(
    passageiro_id: int, status: models.StatusAtendimentoDia, observacoes: str | None = None, db: Session = Depends(get_db)
):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    passageiro.status = status
    if observacoes is not None:
        passageiro.observacoes = observacoes
    db.commit()
    viagem = _get_viagem_ou_404(db, passageiro.viagem_dia_id)
    return _serializar_viagem(db, viagem)


@router.delete("/passageiros/{passageiro_id}", response_model=schemas.ViagemDiaRead)
def remover_passageiro(passageiro_id: int, db: Session = Depends(get_db)):
    passageiro = _get_passageiro_ou_404(db, passageiro_id)
    viagem_id = passageiro.viagem_dia_id
    db.delete(passageiro)
    db.commit()
    viagem = _get_viagem_ou_404(db, viagem_id)
    return _serializar_viagem(db, viagem)


# --------------------------------------------------------------------------
# Sobras (carros e condutores nao escalados no dia)
# --------------------------------------------------------------------------

@router.get("/sobras", response_model=schemas.SobrasRead)
def sobras(data: dt.date, db: Session = Depends(get_db)):
    viagens_do_dia = db.query(models.ViagemDia).filter(models.ViagemDia.data == data).all()
    usados_condutor = {v.condutor_id for v in viagens_do_dia if v.condutor_id is not None}
    usados_veiculo = {v.veiculo_id for v in viagens_do_dia if v.veiculo_id is not None}
    em_ferias = {
        f.condutor_id
        for f in db.query(models.CondutorFerias).filter(
            models.CondutorFerias.data_inicio <= data, models.CondutorFerias.data_fim >= data
        )
    }

    condutores = (
        db.query(models.Condutor)
        .filter(models.Condutor.status == models.StatusCondutor.ATIVO)
        .all()
    )
    condutores_sobrando = [
        schemas.CondutorSobraRead.model_validate(c).model_copy(update={"em_ferias": c.id in em_ferias})
        for c in condutores
        if c.id not in usados_condutor
    ]

    veiculos = db.query(models.Veiculo).filter(models.Veiculo.status == models.StatusVeiculo.ATIVO).all()
    veiculos_sobrando = [schemas.VeiculoRead.model_validate(v) for v in veiculos if v.id not in usados_veiculo]

    return schemas.SobrasRead(condutores=condutores_sobrando, veiculos=veiculos_sobrando)


@router.get("/agendamentos/zip")
def baixar_agendamentos(data: dt.date, db: Session = Depends(get_db)):
    conteudo = gerar_zip_agendamentos(db, data)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Nenhuma viagem com condutor atribuido para essa data")
    nome_arquivo = f"agendamentos_{data.isoformat()}.zip"
    return Response(
        content=conteudo,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.post("/sobras/condutor/{condutor_id}/folga", response_model=schemas.FrequenciaRead)
def marcar_folga(condutor_id: int, data: dt.date, db: Session = Depends(get_db)):
    if db.get(models.Condutor, condutor_id) is None:
        raise HTTPException(status_code=404, detail=f"Condutor {condutor_id} nao encontrado")
    frequencia = (
        db.query(models.Frequencia)
        .filter(models.Frequencia.condutor_id == condutor_id, models.Frequencia.data == data)
        .first()
    )
    if frequencia is None:
        frequencia = models.Frequencia(condutor_id=condutor_id, data=data, tipo=models.StatusFrequencia.FOLGA)
        db.add(frequencia)
    else:
        frequencia.tipo = models.StatusFrequencia.FOLGA
    db.commit()
    db.refresh(frequencia)
    return frequencia
