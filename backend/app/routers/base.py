from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import obter_conta_atual
from app.database import get_db
from app.services.base import (
    alterar_hora_viagem,
    criar_grupo,
    criar_viagem,
    mover_membro,
    montar_estrutura_base,
    remover_grupo,
    remover_membro,
    remover_viagem,
)

router = APIRouter(prefix="/base", tags=["base"], dependencies=[Depends(obter_conta_atual)])


@router.get("/{dia_semana}", response_model=schemas.EstruturaBaseRead)
def obter_estrutura(dia_semana: models.DiaSemana, db: Session = Depends(get_db)):
    return montar_estrutura_base(db, dia_semana)


@router.post("/{dia_semana}/grupos", response_model=schemas.EstruturaBaseRead, status_code=201)
def criar_grupo_base(dia_semana: models.DiaSemana, db: Session = Depends(get_db)):
    criar_grupo(db, dia_semana)
    return montar_estrutura_base(db, dia_semana)


@router.delete("/grupos/{grupo_id}", response_model=schemas.EstruturaBaseRead)
def remover_grupo_base(grupo_id: int, db: Session = Depends(get_db)):
    grupo = db.get(models.GrupoBase, grupo_id)
    if grupo is None:
        raise HTTPException(status_code=404, detail=f"Grupo {grupo_id} nao encontrado")
    dia_semana = grupo.dia_semana
    remover_grupo(db, grupo_id)
    return montar_estrutura_base(db, dia_semana)


@router.post("/grupos/{grupo_id}/viagens", response_model=schemas.EstruturaBaseRead, status_code=201)
def criar_viagem_base(grupo_id: int, payload: schemas.ViagemBaseCreate, db: Session = Depends(get_db)):
    grupo = db.get(models.GrupoBase, grupo_id)
    if grupo is None:
        raise HTTPException(status_code=404, detail=f"Grupo {grupo_id} nao encontrado")
    try:
        criar_viagem(db, grupo_id, payload.sentido, payload.hora)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, grupo.dia_semana)


@router.delete("/viagens/{viagem_id}", response_model=schemas.EstruturaBaseRead)
def remover_viagem_base(viagem_id: int, db: Session = Depends(get_db)):
    viagem = db.get(models.ViagemBase, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"Viagem {viagem_id} nao encontrada")
    dia_semana = viagem.grupo.dia_semana
    remover_viagem(db, viagem_id)
    return montar_estrutura_base(db, dia_semana)


@router.patch("/viagens/{viagem_id}/hora", response_model=schemas.EstruturaBaseRead)
def alterar_hora_viagem_base(viagem_id: int, payload: schemas.ViagemBaseAlterarHora, db: Session = Depends(get_db)):
    viagem = db.get(models.ViagemBase, viagem_id)
    if viagem is None:
        raise HTTPException(status_code=404, detail=f"Viagem {viagem_id} nao encontrada")
    dia_semana = viagem.grupo.dia_semana
    try:
        alterar_hora_viagem(db, viagem_id, payload.hora)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.patch("/membros/{agenda_id}/mover", response_model=schemas.EstruturaBaseRead)
def mover_membro_base(agenda_id: int, payload: schemas.MembroBaseMover, db: Session = Depends(get_db)):
    try:
        dia_semana = mover_membro(
            db, agenda_id, payload.sentido, payload.grupo_base_id, payload.hora, payload.ordem
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return montar_estrutura_base(db, dia_semana)


@router.delete("/membros/{membro_id}", response_model=schemas.EstruturaBaseRead)
def remover_membro_base(membro_id: int, db: Session = Depends(get_db)):
    membro = db.get(models.MembroViagemBase, membro_id)
    if membro is None:
        raise HTTPException(status_code=404, detail=f"Membro {membro_id} nao encontrado")
    dia_semana = membro.viagem.grupo.dia_semana
    remover_membro(db, membro_id)
    return montar_estrutura_base(db, dia_semana)
