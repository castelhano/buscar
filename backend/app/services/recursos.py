import datetime as dt

from app.models import StatusAtendimentoDia, ViagemDia


def fim_viagem(viagem: ViagemDia) -> dt.time:
    """Horario do ultimo atendimento da viagem (ou o proprio horario de saida, se nao houver passageiros)."""
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    return max(horas) if horas else viagem.horario_saida


def janelas_sobrepoem(inicio_a: dt.time, fim_a: dt.time, inicio_b: dt.time, fim_b: dt.time) -> bool:
    return not (fim_a < inicio_b or fim_b < inicio_a)
