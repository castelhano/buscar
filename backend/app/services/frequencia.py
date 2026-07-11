import datetime as dt

from sqlalchemy.orm import Session

from app.models import Condutor, Frequencia, PeriodoCondutor

INTERVALO_PADRAO_POR_PERIODO: dict[PeriodoCondutor, tuple[dt.time, dt.time]] = {
    PeriodoCondutor.MANHA: (dt.time(9, 0), dt.time(10, 0)),
    PeriodoCondutor.TARDE: (dt.time(20, 30), dt.time(21, 30)),
}


def intervalo_do_condutor(db: Session, condutor_id: int | None, data: dt.date) -> tuple[dt.time, dt.time] | None:
    """Intervalo planejado do condutor numa data.

    Usa o que estiver lancado em Frequencia pra essa data especifica (pode
    ter sido ajustado por causa da programacao de usuarios daquele dia); na
    falta de um registro (ou de horario preenchido nele), cai no padrao do
    periodo do condutor. Frequencia aqui e o planejado (auxiliar), nao o
    ponto batido de verdade -- isso fica no ERP externo.
    """
    if condutor_id is None:
        return None

    frequencia = db.query(Frequencia).filter(Frequencia.condutor_id == condutor_id, Frequencia.data == data).first()
    if frequencia is not None and frequencia.intervalo_inicio is not None and frequencia.intervalo_fim is not None:
        return frequencia.intervalo_inicio, frequencia.intervalo_fim

    condutor = db.get(Condutor, condutor_id)
    if condutor is None:
        return None
    return INTERVALO_PADRAO_POR_PERIODO.get(condutor.periodo)
