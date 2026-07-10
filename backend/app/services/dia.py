import datetime as dt

from app.models import DiaSemana

_DIA_SEMANA_POR_WEEKDAY = {
    0: DiaSemana.SEG,
    1: DiaSemana.TER,
    2: DiaSemana.QUA,
    3: DiaSemana.QUI,
    4: DiaSemana.SEX,
    5: DiaSemana.SAB,
    6: DiaSemana.DOM,
}


def dia_semana_from_date(data: dt.date) -> DiaSemana:
    return _DIA_SEMANA_POR_WEEKDAY[data.weekday()]
