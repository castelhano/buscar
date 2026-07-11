from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import exigir_admin, hash_senha
from app.database import get_db

router = APIRouter(prefix="/contas", tags=["contas"], dependencies=[Depends(exigir_admin)])


def _get_conta_ou_404(db: Session, conta_id: int) -> models.Conta:
    conta = db.get(models.Conta, conta_id)
    if conta is None:
        raise HTTPException(status_code=404, detail=f"Conta {conta_id} nao encontrada")
    return conta


@router.get("", response_model=list[schemas.ContaRead])
def listar_contas(db: Session = Depends(get_db)):
    return db.query(models.Conta).order_by(models.Conta.nome).all()


@router.post("", response_model=schemas.ContaRead, status_code=201)
def criar_conta(payload: schemas.ContaCreate, db: Session = Depends(get_db)):
    conta = models.Conta(
        nome=payload.nome,
        login=payload.login,
        senha_hash=hash_senha(payload.senha),
        papel=payload.papel,
        status=payload.status,
    )
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.put("/{conta_id}", response_model=schemas.ContaRead)
def atualizar_conta(
    conta_id: int,
    payload: schemas.ContaAtualizar,
    db: Session = Depends(get_db),
    conta_atual: models.Conta = Depends(exigir_admin),
):
    conta = _get_conta_ou_404(db, conta_id)
    if conta_id == conta_atual.id and payload.papel != models.PapelConta.ADMIN:
        raise HTTPException(status_code=409, detail="Nao e possivel remover o proprio papel de administrador")
    conta.nome = payload.nome
    conta.login = payload.login
    conta.papel = payload.papel
    conta.status = payload.status
    if payload.senha:
        conta.senha_hash = hash_senha(payload.senha)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete("/{conta_id}", status_code=204)
def remover_conta(
    conta_id: int, db: Session = Depends(get_db), conta_atual: models.Conta = Depends(exigir_admin)
):
    if conta_id == conta_atual.id:
        raise HTTPException(status_code=409, detail="Nao e possivel remover a propria conta")
    conta = _get_conta_ou_404(db, conta_id)
    db.delete(conta)
    db.commit()
