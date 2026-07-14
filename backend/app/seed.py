"""Cria a conta admin inicial.

Uso:
    python -m app.seed
"""

import os

from app.auth import hash_senha
from app.database import Base, SessionLocal, engine
from app.models import Conta, PapelConta


def seed_conta_admin() -> int:
    """Cria a primeira conta (admin) se a tabela `conta` estiver vazia --
    sem isso ninguem consegue logar pra criar as demais contas pela tela.
    """
    db = SessionLocal()
    try:
        if db.query(Conta).count() > 0:
            print("Tabela conta ja possui dados, seed nao executado.")
            return 0

        login = os.environ.get("BUSCAR_ADMIN_LOGIN", "admin")
        senha = os.environ.get("BUSCAR_ADMIN_SENHA", "admin123")
        db.add(
            Conta(
                nome="Administrador",
                login=login,
                senha_hash=hash_senha(senha),
                papel=PapelConta.ADMIN,
            )
        )
        db.commit()
        print(f"Conta admin criada (login={login!r}, senha={senha!r}) -- troque a senha depois do primeiro login.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_conta_admin()
