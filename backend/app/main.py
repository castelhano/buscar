from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import agendamento_base, frequencia, usuarios, viagens
from app.routers.cadastros import (
    router_condutores,
    router_empresas,
    router_ferias,
    router_locais,
    router_regioes,
    router_veiculos,
)

app = FastAPI(title="Buscar - Agendamento de Transporte")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_regioes)
app.include_router(router_locais)
app.include_router(router_empresas)
app.include_router(router_veiculos)
app.include_router(router_condutores)
app.include_router(router_ferias)
app.include_router(usuarios.router)
app.include_router(agendamento_base.router)
app.include_router(viagens.router)
app.include_router(frequencia.router)


@app.get("/health")
def health():
    return {"status": "ok"}
