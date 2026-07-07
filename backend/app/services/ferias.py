import datetime as dt

from sqlalchemy.orm import Session

from app.models import Frequencia, StatusFrequencia


def materializar_frequencia_ferias(db: Session, condutor_id: int, data_inicio: dt.date, data_fim: dt.date) -> None:
    """Cria/atualiza uma linha de Frequencia (tipo Ferias) para cada dia do periodo.

    Se ja existir um registro de frequencia manual para o dia, ele e sobrescrito
    para Ferias -- o periodo de ferias e a fonte de verdade quando cadastrado.
    """
    d = data_inicio
    while d <= data_fim:
        frequencia = db.query(Frequencia).filter(Frequencia.condutor_id == condutor_id, Frequencia.data == d).first()
        if frequencia is not None:
            frequencia.tipo = StatusFrequencia.FERIAS
        else:
            db.add(Frequencia(condutor_id=condutor_id, data=d, tipo=StatusFrequencia.FERIAS))
        d += dt.timedelta(days=1)


def limpar_frequencia_ferias(db: Session, condutor_id: int, data_inicio: dt.date, data_fim: dt.date) -> None:
    """Remove as linhas de Frequencia com tipo Ferias criadas para esse periodo.

    Usado antes de editar/remover um periodo de ferias, para nao deixar linhas
    "Ferias" orfas quando o periodo muda ou e cancelado.
    """
    db.query(Frequencia).filter(
        Frequencia.condutor_id == condutor_id,
        Frequencia.data >= data_inicio,
        Frequencia.data <= data_fim,
        Frequencia.tipo == StatusFrequencia.FERIAS,
    ).delete()
