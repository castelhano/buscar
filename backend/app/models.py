import enum
import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
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


class OperacaoExcecao(str, enum.Enum):
    ADICAO = "Adicao"
    MODIFICACAO = "Modificacao"
    SUSPENSAO = "Suspensao"


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
    MEDICO = "Medico"
    OUTROS = "Outros"


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


class PapelConta(str, enum.Enum):
    ADMIN = "Admin"
    OPERADOR = "Operador"


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
        Index("ix_condutor_ferias_periodo", "data_inicio", "data_fim"),
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
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    agenda_semanal: Mapped[list["UsuarioAgendaSemanal"]] = relationship(back_populates="usuario")
    excecoes: Mapped[list["UsuarioExcecao"]] = relationship(back_populates="usuario")


class UsuarioAgendaSemanal(Base):
    """Padrão semanal do usuário: uma linha por dia da semana em que há atendimento.

    Cobre nativamente o caso de um usuario ser Fixo de Seg-Qui e Eventual na Sex,
    com horarios/locais diferentes, sem precisar de um conceito separado de excecao.

    O agrupamento em carros pro modo Base (`GrupoBase`/`ViagemBase`/
    `MembroViagemBase`) e curado a parte, sem nenhum campo aqui -- essa agenda
    so descreve o atendimento em si (horario/local/regiao).
    """

    __tablename__ = "usuario_agenda_semanal"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    dia_semana: Mapped[DiaSemana] = mapped_column(_enum(DiaSemana), index=True)
    tipo: Mapped[TipoAtendimento] = mapped_column(_enum(TipoAtendimento))
    acompanhante: Mapped[bool] = mapped_column(default=False)
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
    """Excecao pontual (um intervalo de datas), nao recorrente.

    `operacao` define o que a excecao faz nesse intervalo:
    - SUSPENSAO: usuario nao tem atendimento (equivalente ao antigo
      suspenso=True); os demais campos de override sao ignorados.
    - MODIFICACAO: substitui o atendimento Fixo campo a campo onde a excecao
      tiver valor preenchido (comportamento historico da excecao).
    - ADICAO: inclui um atendimento extra, mantendo o Fixo original (quando
      existir) intacto -- os dois coexistem no dia (ver `montar_pernas`).

    Padroes recorrentes (ex: toda sexta e diferente) devem virar uma linha em
    UsuarioAgendaSemanal, nao uma excecao.

    Tambem cobre o atendimento avulso (sem nenhuma linha em
    UsuarioAgendaSemanal pro dia da semana): nesse caso a excecao sozinha
    descreve o(s) dia(s) (ver `app.services.geracao._agendas_do_dia`), sem
    precisar cadastrar um padrao semanal so pra essa ocorrencia.

    Intervalos de excecoes do mesmo usuario podem se sobrepor sem validacao
    (igual ao resto do sistema); quando sobrepoem, `_agendas_do_dia` resolve
    pegando a excecao de maior id (mais recente) pra cada dia.
    """

    __tablename__ = "usuario_excecao"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    data_inicio: Mapped[dt.date] = mapped_column(Date)
    data_fim: Mapped[dt.date] = mapped_column(Date)
    operacao: Mapped[OperacaoExcecao] = mapped_column(_enum(OperacaoExcecao), default=OperacaoExcecao.MODIFICACAO)
    tipo: Mapped[TipoAtendimento | None] = mapped_column(_enum(TipoAtendimento), nullable=True)
    saida: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    retorno: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    origem: Mapped[str | None] = mapped_column(String(200), nullable=True)
    regiao_origem_id: Mapped[int | None] = mapped_column(ForeignKey("regiao.id"), nullable=True)
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("local.id"), nullable=True)
    acompanhante: Mapped[bool | None] = mapped_column(nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    usuario: Mapped["Usuario"] = relationship(back_populates="excecoes")
    regiao_origem: Mapped["Regiao | None"] = relationship()
    destino: Mapped["Local | None"] = relationship()


# --------------------------------------------------------------------------
# Modo Base (molde por dia da semana): carros conceituais curados manualmente,
# sem restricao de regiao nem limite rigido de gente por horario -- so uma
# entidade explicita que a geracao real replica, sem tentar reotimizar.
# --------------------------------------------------------------------------

class GrupoBase(Base):
    """Um "carro conceitual" da Base: sem prefixo/empresa/condutor, so um
    agrupamento manual que a geracao do dia tenta materializar como um unico
    carro real (mesmo condutor/veiculo ao longo do dia), sem dividir.
    """

    __tablename__ = "grupo_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_semana: Mapped[DiaSemana] = mapped_column(_enum(DiaSemana), index=True)
    rotulo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ordem_exibicao: Mapped[int] = mapped_column(Integer, default=0)

    viagens: Mapped[list["ViagemBase"]] = relationship(
        back_populates="grupo", cascade="all, delete-orphan"
    )


class GrupoRevezamento(Base):
    """Amarra N carros conceituais (`GrupoBase`) a N condutores, em vagas
    fixas -- a cada geracao de dia util desse `dia_semana`, `deslocamento`
    avanca uma posicao (ciclando), fazendo cada condutor migrar pra proxima
    vaga (ver `services.geracao._condutor_do_slot`). Fim de semana nao usa
    isso (rodizio alfabetico por periodo, ver `RodizioCondutorFimDeSemana`).
    """

    __tablename__ = "grupo_revezamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_semana: Mapped[DiaSemana] = mapped_column(_enum(DiaSemana), index=True)
    rotulo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deslocamento: Mapped[int] = mapped_column(Integer, default=0)

    carros: Mapped[list["GrupoRevezamentoCarro"]] = relationship(
        back_populates="grupo_revezamento", cascade="all, delete-orphan",
        order_by="GrupoRevezamentoCarro.ordem",
    )
    condutores: Mapped[list["GrupoRevezamentoCondutor"]] = relationship(
        back_populates="grupo_revezamento", cascade="all, delete-orphan",
        order_by="GrupoRevezamentoCondutor.ordem",
    )


class GrupoRevezamentoCarro(Base):
    """Uma vaga (posicao `ordem`) do grupo de revezamento, ocupada por um
    `GrupoBase` -- um carro so pode pertencer a um grupo de revezamento.
    """

    __tablename__ = "grupo_revezamento_carro"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_revezamento_id: Mapped[int] = mapped_column(ForeignKey("grupo_revezamento.id", ondelete="CASCADE"))
    grupo_base_id: Mapped[int] = mapped_column(ForeignKey("grupo_base.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column(Integer)

    grupo_revezamento: Mapped["GrupoRevezamento"] = relationship(back_populates="carros")
    grupo_base: Mapped["GrupoBase"] = relationship()

    __table_args__ = (
        UniqueConstraint("grupo_revezamento_id", "ordem", name="uq_grev_carro_ordem"),
        UniqueConstraint("grupo_base_id", name="uq_grev_carro_grupo_base"),
    )


class GrupoRevezamentoCondutor(Base):
    """Um condutor na fila do grupo de revezamento, na posicao `ordem` --
    determina em qual vaga ele entra a cada geracao (junto com `deslocamento`).
    """

    __tablename__ = "grupo_revezamento_condutor"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_revezamento_id: Mapped[int] = mapped_column(ForeignKey("grupo_revezamento.id", ondelete="CASCADE"))
    condutor_id: Mapped[int] = mapped_column(ForeignKey("condutor.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column(Integer)

    grupo_revezamento: Mapped["GrupoRevezamento"] = relationship(back_populates="condutores")
    condutor: Mapped["Condutor"] = relationship()

    __table_args__ = (
        UniqueConstraint("grupo_revezamento_id", "ordem", name="uq_grev_condutor_ordem"),
        UniqueConstraint("grupo_revezamento_id", "condutor_id", name="uq_grev_condutor_unico"),
    )


class RodizioCondutorFimDeSemana(Base):
    """Ponteiro do rodizio alfabetico de condutor no sabado/domingo, um por
    periodo (Manha/Tarde) -- independente de `GrupoBase`, que so existe pro
    rodizio de dia util. Atualizado ao final de cada geracao de fim de
    semana (ver `services.geracao._proximo_condutor_alfabetico`).
    """

    __tablename__ = "rodizio_condutor_fim_de_semana"

    periodo: Mapped[PeriodoCondutor] = mapped_column(_enum(PeriodoCondutor), primary_key=True)
    ultimo_condutor_id: Mapped[int | None] = mapped_column(
        ForeignKey("condutor.id", ondelete="SET NULL"), nullable=True
    )
    atualizado_em: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    ultimo_condutor: Mapped["Condutor | None"] = relationship()


class ViagemBase(Base):
    """Um horario (Ida ou Retorno) dentro de um `GrupoBase` -- vira uma
    `ViagemDia` na geracao real, tentando reaproveitar o mesmo veiculo das
    outras viagens do mesmo grupo.
    """

    __tablename__ = "viagem_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_base_id: Mapped[int] = mapped_column(ForeignKey("grupo_base.id", ondelete="CASCADE"))
    sentido: Mapped[Sentido] = mapped_column(_enum(Sentido))
    hora: Mapped[dt.time] = mapped_column(Time)

    grupo: Mapped["GrupoBase"] = relationship(back_populates="viagens")
    membros: Mapped[list["MembroViagemBase"]] = relationship(
        back_populates="viagem", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("grupo_base_id", "sentido", "hora", name="uq_viagem_base_horario"),
    )


class MembroViagemBase(Base):
    """Um usuario (via sua `UsuarioAgendaSemanal`) dentro de uma `ViagemBase`,
    com sua posicao entre os demais dessa viagem -- sem limite rigido, so um
    alerta visual na tela quando passa de 4.
    """

    __tablename__ = "membro_viagem_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    viagem_base_id: Mapped[int] = mapped_column(ForeignKey("viagem_base.id", ondelete="CASCADE"))
    agenda_id: Mapped[int] = mapped_column(ForeignKey("usuario_agenda_semanal.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    viagem: Mapped["ViagemBase"] = relationship(back_populates="membros")
    agenda: Mapped["UsuarioAgendaSemanal"] = relationship()

    __table_args__ = (
        UniqueConstraint("viagem_base_id", "agenda_id", name="uq_membro_viagem_base"),
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
    data: Mapped[dt.date] = mapped_column(Date, index=True)
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regiao.id"))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), nullable=True)
    condutor_id: Mapped[int | None] = mapped_column(ForeignKey("condutor.id"), nullable=True)
    veiculo_id: Mapped[int | None] = mapped_column(ForeignKey("veiculo.id"), nullable=True)
    horario_saida: Mapped[dt.time] = mapped_column(Time)
    capacidade: Mapped[int] = mapped_column(Integer)
    status: Mapped[StatusViagemDia] = mapped_column(_enum(StatusViagemDia), default=StatusViagemDia.PLANEJADA)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Amarra pernas (ida/volta/varios horarios) que formam um unico carro real ao
    # longo do dia, apontando pro id da primeira perna aberta (a "ancora", que
    # fica com grupo_viagem_id nulo) -- assim o bloco na tela do dia nao depende
    # de condutor_id/veiculo_id, que podem ficar nulos ou ser reatribuidos.
    grupo_viagem_id: Mapped[int | None] = mapped_column(ForeignKey("viagem_dia.id"), nullable=True)
    # Copia do GrupoBase.ordem_exibicao no momento da geracao, gravada so na
    # ancora do bloco -- deixa a tela do dia reproduzir a ordem definida na
    # Base em vez de reordenar por horario. Nulo pra carros abertos manualmente
    # (esses ficam no fim, ordenados por horario).
    ordem_exibicao: Mapped[int | None] = mapped_column(Integer, nullable=True)

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


class DiaTravado(Base):
    """Marca uma data como travada: bloqueia edicao do agendamento gerado pra
    esse dia (evita alteracao nao intencional apos o dia estar fechado).
    """

    __tablename__ = "dia_travado"

    data: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    travado_em: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)


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
    fixo: Mapped[bool] = mapped_column(default=True)

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
    data: Mapped[dt.date] = mapped_column(Date, index=True)
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


# --------------------------------------------------------------------------
# Conta (login do sistema -- nao confundir com Usuario, que e o passageiro)
# --------------------------------------------------------------------------

class Conta(Base):
    __tablename__ = "conta"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    login: Mapped[str] = mapped_column(String(50), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    papel: Mapped[PapelConta] = mapped_column(_enum(PapelConta), default=PapelConta.OPERADOR)
    status: Mapped[StatusAtivoInativo] = mapped_column(_enum(StatusAtivoInativo), default=StatusAtivoInativo.ATIVO)
    criado_em: Mapped[dt.date] = mapped_column(Date, default=dt.date.today)
