import datetime as dt

from app.models import DiaSemana, DiaTipo

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


def dia_tipo_from_date(data: dt.date) -> DiaTipo:
    weekday = data.weekday()
    if weekday == 5:
        return DiaTipo.SABADO
    if weekday == 6:
        return DiaTipo.DOMINGO
    return DiaTipo.UTIL
