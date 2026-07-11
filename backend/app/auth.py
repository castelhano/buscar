import datetime as dt
import os

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

JWT_SECRET = os.environ.get("BUSCAR_JWT_SECRET", "dev-secret-troque-em-producao")
JWT_ALGORITHM = "HS256"
JWT_EXPIRACAO_DIAS = 30


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


def criar_token(conta: models.Conta) -> str:
    payload = {
        "sub": str(conta.id),
        "papel": conta.papel.value,
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=JWT_EXPIRACAO_DIAS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def obter_conta_atual(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> models.Conta:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Nao autenticado")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")

    conta = db.get(models.Conta, int(payload["sub"]))
    # revalida no banco a cada chamada (nao so confia no payload do token) --
    # assim desativar uma conta (status=Inativo) barra o acesso na hora,
    # mesmo com um token ainda valido/nao expirado.
    if conta is None or conta.status != models.StatusAtivoInativo.ATIVO:
        raise HTTPException(status_code=401, detail="Conta invalida ou desativada")
    return conta


def exigir_admin(conta: models.Conta = Depends(obter_conta_atual)) -> models.Conta:
    if conta.papel != models.PapelConta.ADMIN:
        raise HTTPException(status_code=403, detail="Acao restrita a administradores")
    return conta
