from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import obter_conta_atual
from app.database import get_db

router = APIRouter(prefix="/registros-km", tags=["registros-km"], dependencies=[Depends(obter_conta_atual)])


def _validar_sem_sobreposicao(db: Session, veiculo_id: int, data_inicio, data_fim, excluir_id: int | None = None):
    query = db.query(models.RegistroKm).filter(
        models.RegistroKm.veiculo_id == veiculo_id,
        models.RegistroKm.data_inicio <= data_fim,
        models.RegistroKm.data_fim >= data_inicio,
    )
    if excluir_id is not None:
        query = query.filter(models.RegistroKm.id != excluir_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="Ja existe um periodo de km cadastrado para esse veiculo nesse intervalo")


@router.get("", response_model=list[schemas.RegistroKmRead])
def listar_registros_km(veiculo_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.RegistroKm)
    if veiculo_id is not None:
        query = query.filter(models.RegistroKm.veiculo_id == veiculo_id)
    return query.order_by(models.RegistroKm.data_inicio.desc()).all()


@router.post("", response_model=schemas.RegistroKmRead, status_code=201)
def criar_registro_km(payload: schemas.RegistroKmCreate, db: Session = Depends(get_db)):
    if db.get(models.Veiculo, payload.veiculo_id) is None:
        raise HTTPException(status_code=404, detail=f"Veiculo {payload.veiculo_id} nao encontrado")
    _validar_sem_sobreposicao(db, payload.veiculo_id, payload.data_inicio, payload.data_fim)
    registro = models.RegistroKm(**payload.model_dump())
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.put("/{registro_id}", response_model=schemas.RegistroKmRead)
def atualizar_registro_km(registro_id: int, payload: schemas.RegistroKmCreate, db: Session = Depends(get_db)):
    registro = db.get(models.RegistroKm, registro_id)
    if registro is None:
        raise HTTPException(status_code=404, detail=f"Registro de km {registro_id} nao encontrado")
    if db.get(models.Veiculo, payload.veiculo_id) is None:
        raise HTTPException(status_code=404, detail=f"Veiculo {payload.veiculo_id} nao encontrado")
    _validar_sem_sobreposicao(db, payload.veiculo_id, payload.data_inicio, payload.data_fim, excluir_id=registro_id)
    for campo, valor in payload.model_dump().items():
        setattr(registro, campo, valor)
    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{registro_id}", status_code=204)
def remover_registro_km(registro_id: int, db: Session = Depends(get_db)):
    registro = db.get(models.RegistroKm, registro_id)
    if registro is None:
        raise HTTPException(status_code=404, detail=f"Registro de km {registro_id} nao encontrado")
    db.delete(registro)
    db.commit()
