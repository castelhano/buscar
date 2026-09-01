import datetime as dt

from sqlalchemy.orm import Session, joinedload

from app.models import RegistroKm


def registros_km_periodo(db: Session, inicio: dt.date, fim: dt.date, empresa_id: int | None = None) -> list[RegistroKm]:
    """Registros de km cujo periodo esta totalmente contido em [inicio, fim].

    Hoje os lancamentos sao sempre mensais e alinhados ao mes (dia 1 ao
    ultimo dia), entao "contido" cobre o caso real sem precisar de logica de
    clipping de periodo parcial atravessando a borda do intervalo buscado.
    """
    query = (
        db.query(RegistroKm)
        .options(joinedload(RegistroKm.veiculo))
        .filter(RegistroKm.data_inicio >= inicio, RegistroKm.data_fim <= fim)
    )
    if empresa_id is not None:
        query = query.join(RegistroKm.veiculo).filter_by(empresa_id=empresa_id)
    return query.all()


def km_do_registro(registro: RegistroKm) -> int:
    return (registro.km_final - registro.km_inicial) if registro.km_final is not None else 0
