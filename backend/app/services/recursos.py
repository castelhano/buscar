import datetime as dt

from app.models import StatusAtendimentoDia, ViagemDia

TEMPO_ENCERRAMENTO_CONDUTOR_MINUTOS = 90
"""Tempo apos o ultimo atendimento do dia ate o condutor encerrar o turno
(retorno a garagem etc). Usado tanto no calculo do horario final exibido no
PDF de agendamento quanto no horario de saida lancado na escala/frequencia."""


def fim_viagem(viagem: ViagemDia) -> dt.time:
    """Horario do ultimo atendimento da viagem (ou o proprio horario de saida, se nao houver passageiros)."""
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    return max(horas) if horas else viagem.horario_saida


def fim_turno_condutor(viagem: ViagemDia) -> dt.time:
    """Horario de encerramento do turno do condutor: ultimo atendimento + TEMPO_ENCERRAMENTO_CONDUTOR_MINUTOS."""
    referencia = dt.datetime.combine(dt.date.today(), fim_viagem(viagem)) + dt.timedelta(
        minutes=TEMPO_ENCERRAMENTO_CONDUTOR_MINUTOS
    )
    return referencia.time()


def janelas_sobrepoem(inicio_a: dt.time, fim_a: dt.time, inicio_b: dt.time, fim_b: dt.time) -> bool:
    return not (fim_a < inicio_b or fim_b < inicio_a)
