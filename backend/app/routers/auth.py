from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import criar_token, obter_conta_atual, verificar_senha
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    conta = db.query(models.Conta).filter(models.Conta.login == payload.login).first()
    if (
        conta is None
        or conta.status != models.StatusAtivoInativo.ATIVO
        or not verificar_senha(payload.senha, conta.senha_hash)
    ):
        raise HTTPException(status_code=401, detail="Login ou senha invalidos")
    return schemas.LoginResponse(access_token=criar_token(conta), conta=conta)


@router.get("/me", response_model=schemas.ContaRead)
def me(conta: models.Conta = Depends(obter_conta_atual)):
    return conta
