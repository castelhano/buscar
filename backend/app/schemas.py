import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.models import (
    DiaSemana,
    OperacaoExcecao,
    PapelConta,
    PeriodoCondutor,
    Sentido,
    StatusAtivoInativo,
    StatusAtendimentoDia,
    StatusCondutor,
    StatusFrequencia,
    StatusVeiculo,
    StatusViagemDia,
    TipoAtendimento,
    TipoLocal,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Regiao / Local / Empresa
# --------------------------------------------------------------------------

class RegiaoCreate(BaseModel):
    nome: str


class RegiaoRead(ORMModel):
    id: int
    nome: str


class LocalCreate(BaseModel):
    nome: str
    tipo: TipoLocal
    regiao_id: int
    observacao: str | None = None


class LocalRead(ORMModel):
    id: int
    nome: str
    tipo: TipoLocal
    regiao_id: int
    observacao: str | None


class LocalFixoUsuarioRead(BaseModel):
    usuario_id: int
    abbr: str
    dias: list[DiaSemana]


class LocalRecessoCreate(BaseModel):
    local_id: int
    data_inicio: dt.date
    data_fim: dt.date
    observacao: str | None = None


class LocalRecessoRead(ORMModel):
    id: int
    local_id: int
    data_inicio: dt.date
    data_fim: dt.date
    observacao: str | None


class EmpresaCreate(BaseModel):
    nome: str
    regiao_ids: list[int] = []


class EmpresaRead(ORMModel):
    id: int
    nome: str
    regioes: list[RegiaoRead] = []


# --------------------------------------------------------------------------
# Frota / Condutores
# --------------------------------------------------------------------------

class VeiculoCreate(BaseModel):
    empresa_id: int
    prefixo: str
    placa: str
    status: StatusVeiculo = StatusVeiculo.ATIVO
    capacidade: int = 4


class VeiculoRead(ORMModel):
    id: int
    empresa_id: int
    prefixo: str
    placa: str
    status: StatusVeiculo
    capacidade: int


class CondutorCreate(BaseModel):
    empresa_id: int
    matricula: str
    nome: str
    apelido: str | None = None
    status: StatusCondutor = StatusCondutor.ATIVO
    periodo: PeriodoCondutor = PeriodoCondutor.MANHA
    veiculo_preferencial_id: int | None = None


class CondutorRead(ORMModel):
    id: int
    empresa_id: int
    matricula: str
    nome: str
    apelido: str | None
    status: StatusCondutor
    periodo: PeriodoCondutor
    veiculo_preferencial_id: int | None


class CondutorFeriasCreate(BaseModel):
    condutor_id: int
    data_inicio: dt.date
    data_fim: dt.date
    observacao: str | None = None


class CondutorFeriasRead(ORMModel):
    id: int
    condutor_id: int
    data_inicio: dt.date
    data_fim: dt.date
    observacao: str | None


# --------------------------------------------------------------------------
# Usuario + agenda semanal + excecoes
# --------------------------------------------------------------------------

class UsuarioAgendaSemanalCreate(BaseModel):
    dia_semana: DiaSemana
    tipo: TipoAtendimento
    acompanhante: bool = False
    saida: dt.time | None = None
    retorno: dt.time | None = None
    origem: str | None = None
    regiao_origem_id: int | None = None
    destino_id: int | None = None
    ativo: bool = True
    detalhe: str | None = None


class UsuarioAgendaSemanalRead(ORMModel):
    id: int
    usuario_id: int
    dia_semana: DiaSemana
    tipo: TipoAtendimento
    acompanhante: bool
    saida: dt.time | None
    retorno: dt.time | None
    origem: str | None
    regiao_origem_id: int | None
    destino_id: int | None
    ativo: bool
    detalhe: str | None


class UsuarioExcecaoCreate(BaseModel):
    data_inicio: dt.date
    data_fim: dt.date
    operacao: OperacaoExcecao = OperacaoExcecao.MODIFICACAO
    tipo: TipoAtendimento | None = TipoAtendimento.EVENTUAL
    saida: dt.time | None = None
    retorno: dt.time | None = None
    origem: str | None = None
    regiao_origem_id: int | None = None
    destino_id: int | None = None
    acompanhante: bool | None = None
    motivo: str | None = None


class UsuarioExcecaoRead(ORMModel):
    id: int
    usuario_id: int
    data_inicio: dt.date
    data_fim: dt.date
    operacao: OperacaoExcecao
    tipo: TipoAtendimento | None
    saida: dt.time | None
    retorno: dt.time | None
    origem: str | None
    regiao_origem_id: int | None
    destino_id: int | None
    acompanhante: bool | None
    motivo: str | None


class UsuarioCreate(BaseModel):
    nome: str
    abbr: str
    status: StatusAtivoInativo = StatusAtivoInativo.ATIVO
    detalhe: str | None = None
    observacao: str | None = None


class UsuarioRead(ORMModel):
    id: int
    nome: str
    abbr: str
    data_cadastro: dt.date
    status: StatusAtivoInativo
    detalhe: str | None
    observacao: str | None


class UsuarioComAgendaRead(UsuarioRead):
    agenda_semanal: list[UsuarioAgendaSemanalRead] = []
    excecoes: list[UsuarioExcecaoRead] = []


# --------------------------------------------------------------------------
# Viagem do dia + passageiros
# --------------------------------------------------------------------------

class ViagemDiaPassageiroRead(ORMModel):
    id: int
    viagem_dia_id: int | None
    usuario_id: int
    usuario: UsuarioRead
    sentido: Sentido
    hora: dt.time
    origem: str | None
    regiao_origem_id: int | None
    destino_id: int | None
    regiao_destino_id: int | None
    acompanhante: bool
    ordem: int
    status: StatusAtendimentoDia
    observacoes: str | None
    fixo: bool
    irregular: bool = False
    motivo_irregular: str | None = None


class ViagemDiaRead(ORMModel):
    id: int
    data: dt.date
    regiao_id: int
    empresa_id: int | None
    condutor_id: int | None
    veiculo_id: int | None
    horario_saida: dt.time
    capacidade: int
    status: StatusViagemDia
    observacoes: str | None
    grupo_viagem_id: int | None
    ordem_exibicao: int | None
    passageiros: list[ViagemDiaPassageiroRead] = []
    condutor_em_ferias: bool = False
    conflito_horario: bool = False
    motivo_conflito_horario: str | None = None
    intervalo_inicio: dt.time | None = None
    intervalo_fim: dt.time | None = None


class ViagemDiaPassageiroCreate(BaseModel):
    usuario_id: int
    sentido: Sentido
    hora: dt.time
    origem: str | None = None
    regiao_origem_id: int | None = None
    destino_id: int | None = None
    regiao_destino_id: int | None = None
    acompanhante: bool = False
    observacoes: str | None = None


class ViagemDiaPassageiroAtualizar(BaseModel):
    sentido: Sentido | None = None
    hora: dt.time | None = None
    origem: str | None = None
    regiao_origem_id: int | None = None
    destino_id: int | None = None
    regiao_destino_id: int | None = None
    acompanhante: bool | None = None
    observacoes: str | None = None


class ViagemDiaPassageiroMover(BaseModel):
    viagem_dia_destino_id: int
    ordem: int | None = None


class ViagemDiaPassageiroMoverBloco(BaseModel):
    bloco_id: int


class ViagemDiaAtribuir(BaseModel):
    condutor_id: int | None = None
    veiculo_id: int | None = None
    limpar: bool = False


class ViagemDiaAtribuirBloco(BaseModel):
    viagem_ids: list[int]
    condutor_id: int | None = None
    veiculo_id: int | None = None


class ReordenarBlocosPayload(BaseModel):
    data: dt.date
    ancora_ids: list[int]


# --------------------------------------------------------------------------
# Modo Base (molde por dia da semana): grupos/viagens/membros curados
# manualmente -- a geracao real tenta materializar cada grupo como um carro
# real, sem dividir (ver app/services/base.py e app/services/geracao.py).
# --------------------------------------------------------------------------

class MembroBaseRead(BaseModel):
    id: int
    agenda_id: int
    ordem: int
    usuario_id: int
    usuario_nome: str
    usuario_abbr: str
    usuario_ativo: bool
    origem: str | None
    regiao_origem_id: int | None
    destino_id: int | None
    regiao_destino_id: int | None
    acompanhante: bool


class ViagemBaseRead(BaseModel):
    id: int
    grupo_base_id: int
    sentido: Sentido
    hora: dt.time
    membros: list[MembroBaseRead] = []


class GrupoBaseRead(BaseModel):
    id: int
    dia_semana: DiaSemana
    rotulo: str | None
    ordem_exibicao: int
    viagens: list[ViagemBaseRead] = []


class NaoClassificadoRead(BaseModel):
    agenda_id: int
    usuario_id: int
    usuario_nome: str
    usuario_abbr: str
    sentido: Sentido
    hora: dt.time
    origem: str | None
    regiao_origem_id: int | None
    destino_id: int | None
    regiao_destino_id: int | None
    acompanhante: bool


class EstruturaBaseRead(BaseModel):
    grupos: list[GrupoBaseRead]
    nao_classificados: list[NaoClassificadoRead]


class ViagemBaseCreate(BaseModel):
    sentido: Sentido
    hora: dt.time


class MembroBaseMover(BaseModel):
    sentido: Sentido
    grupo_base_id: int
    hora: dt.time
    ordem: int | None = None


class ViagemBaseAlterarHora(BaseModel):
    hora: dt.time


class ViagemDiaAbrir(BaseModel):
    data: dt.date
    regiao_id: int
    horario_saida: dt.time
    capacidade: int


# --------------------------------------------------------------------------
# Frequencia
# --------------------------------------------------------------------------

class FrequenciaCreate(BaseModel):
    condutor_id: int
    data: dt.date
    tipo: StatusFrequencia = StatusFrequencia.PENDENTE
    hora_entrada: dt.time | None = None
    intervalo_inicio: dt.time | None = None
    intervalo_fim: dt.time | None = None
    hora_saida: dt.time | None = None
    observacao: str | None = None


class FrequenciaRead(ORMModel):
    id: int
    condutor_id: int
    data: dt.date
    tipo: StatusFrequencia
    hora_entrada: dt.time | None
    intervalo_inicio: dt.time | None
    intervalo_fim: dt.time | None
    hora_saida: dt.time | None
    observacao: str | None


# --------------------------------------------------------------------------
# Sobras (carros/condutores nao escalados no dia)
# --------------------------------------------------------------------------

class CondutorSobraRead(CondutorRead):
    em_ferias: bool = False


class SobrasRead(BaseModel):
    condutores: list[CondutorSobraRead]
    veiculos: list[VeiculoRead]


# --------------------------------------------------------------------------
# Desconsiderados (usuarios Fixo previstos no dia que ficaram de fora)
# --------------------------------------------------------------------------

class UsuarioDesconsideradoRead(BaseModel):
    usuario_id: int
    usuario_nome: str
    motivo: str


# --------------------------------------------------------------------------
# Conta (login do sistema) + autenticacao
# --------------------------------------------------------------------------

class ContaCreate(BaseModel):
    nome: str
    login: str
    senha: str
    papel: PapelConta = PapelConta.OPERADOR
    status: StatusAtivoInativo = StatusAtivoInativo.ATIVO


class ContaAtualizar(BaseModel):
    nome: str
    login: str
    papel: PapelConta
    status: StatusAtivoInativo
    senha: str | None = None


class ContaRead(ORMModel):
    id: int
    nome: str
    login: str
    papel: PapelConta
    status: StatusAtivoInativo
    criado_em: dt.date


class LoginRequest(BaseModel):
    login: str
    senha: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    conta: ContaRead
