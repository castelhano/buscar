from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/agendamento-base", tags=["agendamento-base"])


def _get_base_ou_404(db: Session, base_id: int) -> models.AgendamentoBase:
    base = db.get(models.AgendamentoBase, base_id)
    if base is None:
        raise HTTPException(status_code=404, detail=f"AgendamentoBase {base_id} nao encontrado")
    return base


@router.get("", response_model=list[schemas.AgendamentoBaseRead])
def listar_agendamento_base(
    dia_tipo: models.DiaTipo | None = None, regiao_id: int | None = None, db: Session = Depends(get_db)
):
    query = db.query(models.AgendamentoBase)
    if dia_tipo is not None:
        query = query.filter(models.AgendamentoBase.dia_tipo == dia_tipo)
    if regiao_id is not None:
        query = query.filter(models.AgendamentoBase.regiao_id == regiao_id)
    return query.order_by(models.AgendamentoBase.dia_tipo, models.AgendamentoBase.inicio).all()


@router.post("", response_model=schemas.AgendamentoBaseRead, status_code=201)
def criar_agendamento_base(payload: schemas.AgendamentoBaseCreate, db: Session = Depends(get_db)):
    if db.get(models.Regiao, payload.regiao_id) is None:
        raise HTTPException(status_code=404, detail=f"Regiao {payload.regiao_id} nao encontrada")
    base = models.AgendamentoBase(**payload.model_dump())
    db.add(base)
    db.commit()
    db.refresh(base)
    return base


@router.put("/{base_id}", response_model=schemas.AgendamentoBaseRead)
def atualizar_agendamento_base(base_id: int, payload: schemas.AgendamentoBaseCreate, db: Session = Depends(get_db)):
    base = _get_base_ou_404(db, base_id)
    if db.get(models.Regiao, payload.regiao_id) is None:
        raise HTTPException(status_code=404, detail=f"Regiao {payload.regiao_id} nao encontrada")
    for campo, valor in payload.model_dump().items():
        setattr(base, campo, valor)
    db.commit()
    db.refresh(base)
    return base


@router.delete("/{base_id}", status_code=204)
def remover_agendamento_base(base_id: int, db: Session = Depends(get_db)):
    base = _get_base_ou_404(db, base_id)
    db.delete(base)
    db.commit()


# --------------------------------------------------------------------------
# Vinculo de usuarios Fixo a uma viagem base
# --------------------------------------------------------------------------

@router.get("/{base_id}/usuarios", response_model=list[schemas.UsuarioAgendamentoBaseRead])
def listar_usuarios_do_base(base_id: int, db: Session = Depends(get_db)):
    _get_base_ou_404(db, base_id)
    return (
        db.query(models.UsuarioAgendamentoBase)
        .filter(models.UsuarioAgendamentoBase.agendamento_base_id == base_id)
        .all()
    )


@router.post("/{base_id}/usuarios", response_model=schemas.UsuarioAgendamentoBaseRead, status_code=201)
def vincular_usuario(base_id: int, payload: schemas.UsuarioAgendamentoBaseCreate, db: Session = Depends(get_db)):
    _get_base_ou_404(db, base_id)
    if db.get(models.Usuario, payload.usuario_id) is None:
        raise HTTPException(status_code=404, detail=f"Usuario {payload.usuario_id} nao encontrado")
    existente = (
        db.query(models.UsuarioAgendamentoBase)
        .filter(
            models.UsuarioAgendamentoBase.agendamento_base_id == base_id,
            models.UsuarioAgendamentoBase.usuario_id == payload.usuario_id,
            models.UsuarioAgendamentoBase.sentido == payload.sentido,
        )
        .first()
    )
    if existente is not None:
        raise HTTPException(status_code=409, detail="Usuario ja vinculado a esse agendamento base nesse sentido")
    vinculo = models.UsuarioAgendamentoBase(agendamento_base_id=base_id, **payload.model_dump(exclude={"agendamento_base_id"}))
    db.add(vinculo)
    db.commit()
    db.refresh(vinculo)
    return vinculo


@router.delete("/{base_id}/usuarios/{vinculo_id}", status_code=204)
def desvincular_usuario(base_id: int, vinculo_id: int, db: Session = Depends(get_db)):
    vinculo = db.get(models.UsuarioAgendamentoBase, vinculo_id)
    if vinculo is None or vinculo.agendamento_base_id != base_id:
        raise HTTPException(status_code=404, detail="Vinculo nao encontrado para esse agendamento base")
    db.delete(vinculo)
    db.commit()
