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


class PeriodoCondutor(str, enum.Enum):
    MANHA = "Manha"
    TARDE = "Tarde"


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
    EQUOTERAPIA = "Equoterapia"
    TRABALHO = "Trabalho"
    HEMODIALISE = "Hemodialise"
    OUTROS = "Outros"


class Sentido(str, enum.Enum):
    IDA = "Ida"
    RETORNO = "Retorno"


class Modalidade(str, enum.Enum):
    SOMENTE_IDA = "Somente Ida"
    IDA_E_VOLTA = "Ida e Volta"


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


class LocalRecesso(Base):
    """Periodo em que um Local fica fechado (ex: recesso escolar): usuarios
    com destino nesse local nesse intervalo ficam de fora da geracao do dia,
    sem precisar de uma UsuarioExcecao por usuario.
    """

    __tablename__ = "local_recesso"

    id: Mapped[int] = mapped_column(primary_key=True)
    local_id: Mapped[int] = mapped_column(ForeignKey("local.id"))
    data_inicio: Mapped[dt.date] = mapped_column(Date)
    data_fim: Mapped[dt.date] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    local: Mapped["Local"] = relationship()

    __table_args__ = (
        CheckConstraint("data_fim >= data_inicio", name="ck_local_recesso_periodo"),
    )


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
    capacidade: Mapped[int] = mapped_column(Integer, default=4)

    empresa: Mapped["Empresa"] = relationship(back_populates="veiculos")

    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_veiculo_capacidade"),
    )


class Condutor(Base):
    __tablename__ = "condutor"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    matricula: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(150))
    apelido: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[StatusCondutor] = mapped_column(_enum(StatusCondutor), default=StatusCondutor.ATIVO)
    periodo: Mapped[PeriodoCondutor] = mapped_column(_enum(PeriodoCondutor), default=PeriodoCondutor.MANHA)
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

    `ordem` e curado manualmente (agrupar quem mora perto) e usado pela geracao
    do dia para decidir a sequencia de preenchimento dos carros por regiao.
    """

    __tablename__ = "usuario_agenda_semanal"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    dia_semana: Mapped[DiaSemana] = mapped_column(_enum(DiaSemana))
    tipo: Mapped[TipoAtendimento] = mapped_column(_enum(TipoAtendimento))
    modalidade: Mapped[Modalidade] = mapped_column(_enum(Modalidade), default=Modalidade.IDA_E_VOLTA)
    acompanhante: Mapped[bool] = mapped_column(default=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
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
        UniqueConstraint(
            "usuario_id", "dia_semana", "saida", "destino_id", name="uq_usuario_dia_semana_horario_destino"
        ),
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
# Viagem do dia (instancia gerada) + passageiros do dia
# --------------------------------------------------------------------------

class ViagemDia(Base):
    """Um carro escalado para uma data especifica: gerado automaticamente pela
    geracao do dia (a partir da UsuarioAgendaSemanal), ou aberto manualmente
    na tela de escala quando sobra usuario sem carro.
    """

    __tablename__ = "viagem_dia"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dt.date] = mapped_column(Date)
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regiao.id"))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), nullable=True)
    condutor_id: Mapped[int | None] = mapped_column(ForeignKey("condutor.id"), nullable=True)
    veiculo_id: Mapped[int | None] = mapped_column(ForeignKey("veiculo.id"), nullable=True)
    horario_saida: Mapped[dt.time] = mapped_column(Time)
    capacidade: Mapped[int] = mapped_column(Integer)
    status: Mapped[StatusViagemDia] = mapped_column(_enum(StatusViagemDia), default=StatusViagemDia.PLANEJADA)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    regiao: Mapped["Regiao"] = relationship()
    empresa: Mapped["Empresa | None"] = relationship()
    condutor: Mapped["Condutor | None"] = relationship()
    veiculo: Mapped["Veiculo | None"] = relationship()
    passageiros: Mapped[list["ViagemDiaPassageiro"]] = relationship(
        back_populates="viagem_dia",
        order_by="ViagemDiaPassageiro.hora, ViagemDiaPassageiro.ordem",
    )

    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_viagem_dia_capacidade"),
    )


class ViagemDiaPassageiro(Base):
    """Um usuario dentro de uma ViagemDia (o card de passageiro na tela de agendamento).

    Campos de origem/destino/regiao sao uma copia (snapshot) do cadastro do
    usuario no momento da geracao, editavel independentemente do cadastro base.

    `viagem_dia_id` pode ser nulo: e o caso de quem ficou sem vaga na geracao
    (frota esgotada) -- fica "orfao" (sem carro), com `data` preenchida pra
    aparecer no container "Sem vaga" da tela do dia e poder ser arrastado
    manualmente pra um carro depois.
    """

    __tablename__ = "viagem_dia_passageiro"

    id: Mapped[int] = mapped_column(primary_key=True)
    viagem_dia_id: Mapped[int | None] = mapped_column(ForeignKey("viagem_dia.id"), nullable=True)
    data: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido))
    hora: Mapped[dt.time] = mapped_column(Time)
    origem: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regiao_origem_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("local.id"), nullable=True)
    regiao_destino_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    acompanhante: Mapped[bool] = mapped_column(default=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StatusAtendimentoDia] = mapped_column(_enum(StatusAtendimentoDia), default=StatusAtendimentoDia.AGENDADO)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    viagem_dia: Mapped["ViagemDia | None"] = relationship(back_populates="passageiros")
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
