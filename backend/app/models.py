import enum
import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _enum(python_enum: type[enum.Enum]):
    return SAEnum(python_enum, native_enum=False, validate_strings=True, length=20)


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class StatusAtivoInativo(str, enum.Enum):
    ATIVO = "Ativo"
    INATIVO = "Inativo"


class StatusVeiculo(str, enum.Enum):
    ATIVO = "Ativo"
    INATIVO = "Inativo"
    MANUTENCAO = "Manutencao"


class StatusCondutor(str, enum.Enum):
    ATIVO = "Ativo"
    DESLIGADO = "Desligado"
    AFASTADO = "Afastado"


class TipoAtendimento(str, enum.Enum):
    FIXO = "Fixo"
    EVENTUAL = "Eventual"


class DiaSemana(str, enum.Enum):
    SEG = "SEG"
    TER = "TER"
    QUA = "QUA"
    QUI = "QUI"
    SEX = "SEX"
    SAB = "SAB"
    DOM = "DOM"


class TipoLocal(str, enum.Enum):
    ESCOLA = "Escola"
    FISIOTERAPIA = "Fisioterapia"
    TRABALHO = "Trabalho"
    HEMODIALISE = "Hemodialise"
    OUTROS = "Outros"


class DiaTipo(str, enum.Enum):
    UTIL = "U"
    SABADO = "S"
    DOMINGO = "D"


class Sentido(str, enum.Enum):
    IDA = "Ida"
    RETORNO = "Retorno"


class StatusViagemDia(str, enum.Enum):
    PLANEJADA = "Planejada"
    CONFIRMADA = "Confirmada"
    CANCELADA = "Cancelada"


class StatusAtendimentoDia(str, enum.Enum):
    AGENDADO = "Agendado"
    CANCELADO = "Cancelado"
    EM_ANALISE = "Em analise"


class StatusFrequencia(str, enum.Enum):
    TRABALHADO = "Trabalhado"
    FOLGA = "Folga"
    FERIAS = "Ferias"
    FALTA = "Falta"
    PENDENTE = "Pendente"


# --------------------------------------------------------------------------
# Regiao / Local / Empresa
# --------------------------------------------------------------------------

class Regiao(Base):
    __tablename__ = "regiao"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True)


class Local(Base):
    __tablename__ = "local"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[TipoLocal] = mapped_column(_enum(TipoLocal))
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regiao.id"))
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    regiao: Mapped["Regiao"] = relationship()


class Empresa(Base):
    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), unique=True)

    regioes: Mapped[list["Regiao"]] = relationship(secondary="empresa_regiao")
    veiculos: Mapped[list["Veiculo"]] = relationship(back_populates="empresa")
    condutores: Mapped[list["Condutor"]] = relationship(back_populates="empresa")


empresa_regiao = Table(
    "empresa_regiao",
    Base.metadata,
    Column("empresa_id", ForeignKey("empresa.id"), primary_key=True),
    Column("regiao_id", ForeignKey("regiao.id"), primary_key=True),
)


# --------------------------------------------------------------------------
# Frota / Condutores
# --------------------------------------------------------------------------

class Veiculo(Base):
    __tablename__ = "veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    prefixo: Mapped[str] = mapped_column(String(20))
    placa: Mapped[str] = mapped_column(String(10), unique=True)
    status: Mapped[StatusVeiculo] = mapped_column(_enum(StatusVeiculo), default=StatusVeiculo.ATIVO)

    empresa: Mapped["Empresa"] = relationship(back_populates="veiculos")


class Condutor(Base):
    __tablename__ = "condutor"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    matricula: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(150))
    apelido: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[StatusCondutor] = mapped_column(_enum(StatusCondutor), default=StatusCondutor.ATIVO)
    veiculo_preferencial_id: Mapped[int | None] = mapped_column(ForeignKey("veiculo.id"), nullable=True)

    empresa: Mapped["Empresa"] = relationship(back_populates="condutores")
    veiculo_preferencial: Mapped["Veiculo | None"] = relationship()
    ferias: Mapped[list["CondutorFerias"]] = relationship(back_populates="condutor")


class CondutorFerias(Base):
    __tablename__ = "condutor_ferias"

    id: Mapped[int] = mapped_column(primary_key=True)
    condutor_id: Mapped[int] = mapped_column(ForeignKey("condutor.id"))
    data_inicio: Mapped[dt.date] = mapped_column(Date)
    data_fim: Mapped[dt.date] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    condutor: Mapped["Condutor"] = relationship(back_populates="ferias")

    __table_args__ = (
        CheckConstraint("data_fim >= data_inicio", name="ck_condutor_ferias_periodo"),
    )


# --------------------------------------------------------------------------
# Usuario (passageiro) + padrão semanal + exceções pontuais
# --------------------------------------------------------------------------

class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    abbr: Mapped[str] = mapped_column(String(30))
    data_cadastro: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
    status: Mapped[StatusAtivoInativo] = mapped_column(_enum(StatusAtivoInativo), default=StatusAtivoInativo.ATIVO)
    detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)

    agenda_semanal: Mapped[list["UsuarioAgendaSemanal"]] = relationship(back_populates="usuario")
    excecoes: Mapped[list["UsuarioExcecao"]] = relationship(back_populates="usuario")


class UsuarioAgendaSemanal(Base):
    """Padrão semanal do usuário: uma linha por dia da semana em que há atendimento.

    Cobre nativamente o caso de um usuario ser Fixo de Seg-Qui e Eventual na Sex,
    com horarios/locais diferentes, sem precisar de um conceito separado de excecao.
    """

    __tablename__ = "usuario_agenda_semanal"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    dia_semana: Mapped[DiaSemana] = mapped_column(_enum(DiaSemana))
    tipo: Mapped[TipoAtendimento] = mapped_column(_enum(TipoAtendimento))
    saida: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    retorno: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    origem: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regiao_origem_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("local.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    detalhe: Mapped[str | None] = mapped_column(Text, nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="agenda_semanal")
    regiao_origem: Mapped["Regiao | None"] = relationship()
    destino: Mapped["Local | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("usuario_id", "dia_semana", name="uq_usuario_dia_semana"),
    )


class UsuarioExcecao(Base):
    """Excecao pontual (uma data especifica), nao recorrente.

    Ex: nesse dia o local de destino muda so daquela vez, ou o usuario nao tem
    atendimento (suspenso=True) por algum motivo isolado. Padroes recorrentes
    (ex: toda sexta e diferente) devem virar uma linha em UsuarioAgendaSemanal,
    nao uma excecao.
    """

    __tablename__ = "usuario_excecao"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    data: Mapped[dt.date] = mapped_column(Date)
    suspenso: Mapped[bool] = mapped_column(default=False)
    tipo: Mapped[TipoAtendimento | None] = mapped_column(_enum(TipoAtendimento), nullable=True)
    saida: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    retorno: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    origem: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regiao_origem_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("local.id"), nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="excecoes")
    regiao_origem: Mapped["Regiao | None"] = relationship()
    destino: Mapped["Local | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("usuario_id", "data", name="uq_usuario_excecao_data"),
    )


# --------------------------------------------------------------------------
# Agendamento base (template) + vinculo de usuarios fixos
# --------------------------------------------------------------------------

class AgendamentoBase(Base):
    """Template de viagem por tipo de dia (Util/Sabado/Domingo) + regiao.

    Representa um carro no agendamento base, sem amarracao com frota nem
    condutor (revesados na geracao do dia).
    """

    __tablename__ = "agendamento_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_tipo: Mapped[DiaTipo] = mapped_column(_enum(DiaTipo))
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regiao.id"))
    inicio: Mapped[dt.time] = mapped_column(Time)
    capacidade: Mapped[int] = mapped_column(Integer)

    regiao: Mapped["Regiao"] = relationship()
    usuarios: Mapped[list["UsuarioAgendamentoBase"]] = relationship(back_populates="agendamento_base")

    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_agendamento_base_capacidade"),
    )


class UsuarioAgendamentoBase(Base):
    """Vincula um usuario Fixo a uma viagem base (carro/horario padrao)."""

    __tablename__ = "usuario_agendamento_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    agendamento_base_id: Mapped[int] = mapped_column(ForeignKey("agendamento_base.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido))
    hora: Mapped[dt.time] = mapped_column(Time)

    agendamento_base: Mapped["AgendamentoBase"] = relationship(back_populates="usuarios")
    usuario: Mapped["Usuario"] = relationship()

    __table_args__ = (
        UniqueConstraint("agendamento_base_id", "usuario_id", "sentido", name="uq_usuario_agendamento_base"),
    )


# --------------------------------------------------------------------------
# Viagem do dia (instancia gerada) + passageiros do dia
# --------------------------------------------------------------------------

class ViagemDia(Base):
    """Um carro escalado para uma data especifica (gerado a partir do AgendamentoBase,
    ou aberto manualmente quando a capacidade dos carros base estoura).
    """

    __tablename__ = "viagem_dia"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dt.date] = mapped_column(Date)
    agendamento_base_id: Mapped[int | None] = mapped_column(ForeignKey("agendamento_base.id"), nullable=True)
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regiao.id"))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), nullable=True)
    condutor_id: Mapped[int | None] = mapped_column(ForeignKey("condutor.id"), nullable=True)
    veiculo_id: Mapped[int | None] = mapped_column(ForeignKey("veiculo.id"), nullable=True)
    horario_saida: Mapped[dt.time] = mapped_column(Time)
    capacidade: Mapped[int] = mapped_column(Integer)
    status: Mapped[StatusViagemDia] = mapped_column(_enum(StatusViagemDia), default=StatusViagemDia.PLANEJADA)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    agendamento_base: Mapped["AgendamentoBase | None"] = relationship()
    regiao: Mapped["Regiao"] = relationship()
    empresa: Mapped["Empresa | None"] = relationship()
    condutor: Mapped["Condutor | None"] = relationship()
    veiculo: Mapped["Veiculo | None"] = relationship()
    passageiros: Mapped[list["ViagemDiaPassageiro"]] = relationship(back_populates="viagem_dia")

    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_viagem_dia_capacidade"),
    )


class ViagemDiaPassageiro(Base):
    """Um usuario dentro de uma ViagemDia (o card de passageiro na tela de agendamento).

    Campos de origem/destino/regiao sao uma copia (snapshot) do cadastro do
    usuario no momento da geracao, editavel independentemente do cadastro base.
    """

    __tablename__ = "viagem_dia_passageiro"

    id: Mapped[int] = mapped_column(primary_key=True)
    viagem_dia_id: Mapped[int] = mapped_column(ForeignKey("viagem_dia.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido))
    hora: Mapped[dt.time] = mapped_column(Time)
    origem: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regiao_origem_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("local.id"), nullable=True)
    regiao_destino_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StatusAtendimentoDia] = mapped_column(_enum(StatusAtendimentoDia), default=StatusAtendimentoDia.AGENDADO)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    viagem_dia: Mapped["ViagemDia"] = relationship(back_populates="passageiros")
    usuario: Mapped["Usuario"] = relationship()
    regiao_origem: Mapped["Regiao | None"] = relationship(foreign_keys=[regiao_origem_id])
    destino: Mapped["Local | None"] = relationship()
    regiao_destino: Mapped["Regiao | None"] = relationship(foreign_keys=[regiao_destino_id])

    __table_args__ = (
        UniqueConstraint("viagem_dia_id", "usuario_id", "sentido", name="uq_viagem_dia_passageiro"),
    )


# --------------------------------------------------------------------------
# Frequencia (apontamento de horas dos condutores)
# --------------------------------------------------------------------------

class Frequencia(Base):
    __tablename__ = "frequencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    condutor_id: Mapped[int] = mapped_column(ForeignKey("condutor.id"))
    data: Mapped[dt.date] = mapped_column(Date)
    tipo: Mapped[StatusFrequencia] = mapped_column(_enum(StatusFrequencia), default=StatusFrequencia.PENDENTE)
    hora_entrada: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    intervalo_inicio: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    intervalo_fim: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    hora_saida: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    condutor: Mapped["Condutor"] = relationship()

    __table_args__ = (
        UniqueConstraint("condutor_id", "data", name="uq_frequencia_condutor_data"),
    )
