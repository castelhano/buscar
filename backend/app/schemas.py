import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.models import (
    DiaSemana,
    OperacaoExcecao,
    PapelConta,
    PeriodoCondutor,
    StatusAtivoInativo,
    StatusAtendimentoDia,
    StatusCondutor,
    StatusFrequencia,
    StatusVeiculo,
    StatusViagemDia,
    TipoAtendimento,
    TipoLocal,
    TipoPonto,
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
    capacidade_usuarios: int = 4
    capacidade_acompanhantes: int = 2


class VeiculoRead(ORMModel):
    id: int
    empresa_id: int
    prefixo: str
    placa: str
    status: StatusVeiculo
    capacidade_usuarios: int
    capacidade_acompanhantes: int


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
# Trecho: uma perna do itinerario do dia (origem/destino/hora/acompanhante),
# na posicao `ordem` (0-based) -- reaproveitado em UsuarioAgendaSemanal e
# UsuarioExcecao. Ida-e-volta convencional e so uma lista de 2 trechos; um
# itinerario com paradas extras ou retorno pra local diferente da origem e
# so uma lista mais longa, sem tratamento especial.
#
# Origem e destino sao cada um um "ponto" com tipo (ver `TipoPonto`): Local
# cadastrado (`*_id`), endereco do proprio usuario (sem campo extra -- deriva
# de `Usuario.abbr`/`detalhe`/`regiao_id`) ou avulso (`*_texto` + `*_detalhe`
# opcional + `regiao_*_id` obrigatorio, unico caso sem de onde derivar a
# regiao sozinho). Validado/resolvido no servidor, nao como constraint de
# banco (`app.services.pontos.resolver_trecho`). `origem_tipo` nulo so vale
# em trechos que nao sao o primeiro do itinerario -- significa "herda o
# destino do trecho anterior".
# --------------------------------------------------------------------------

class TrechoCreate(BaseModel):
    hora: dt.time
    origem_tipo: TipoPonto | None = None
    origem_id: int | None = None
    origem_texto: str | None = None
    origem_detalhe: str | None = None
    regiao_origem_id: int | None = None
    destino_tipo: TipoPonto = TipoPonto.LOCAL
    destino_id: int | None = None
    destino_texto: str | None = None
    destino_detalhe: str | None = None
    regiao_destino_id: int | None = None
    acompanhante: bool = False


class TrechoRead(ORMModel):
    id: int
    ordem: int
    hora: dt.time
    origem_tipo: TipoPonto | None
    origem_id: int | None
    origem_texto: str | None
    origem_detalhe: str | None
    regiao_origem_id: int | None
    destino_tipo: TipoPonto
    destino_id: int | None
    destino_texto: str | None
    destino_detalhe: str | None
    regiao_destino_id: int | None
    acompanhante: bool


# --------------------------------------------------------------------------
# Usuario + agenda semanal + excecoes
# --------------------------------------------------------------------------

class UsuarioAgendaSemanalCreate(BaseModel):
    dia_semana: DiaSemana
    tipo: TipoAtendimento
    ativo: bool = True
    detalhe: str | None = None
    trechos: list[TrechoCreate] = []


class UsuarioAgendaSemanalRead(ORMModel):
    id: int
    usuario_id: int
    dia_semana: DiaSemana
    tipo: TipoAtendimento
    ativo: bool
    detalhe: str | None
    trechos: list[TrechoRead] = []


class UsuarioExcecaoCreate(BaseModel):
    data_inicio: dt.date
    data_fim: dt.date
    operacao: OperacaoExcecao = OperacaoExcecao.MODIFICACAO
    tipo: TipoAtendimento | None = TipoAtendimento.EVENTUAL
    motivo: str | None = None
    trechos: list[TrechoCreate] = []


class UsuarioExcecaoRead(ORMModel):
    id: int
    usuario_id: int
    data_inicio: dt.date
    data_fim: dt.date
    operacao: OperacaoExcecao
    tipo: TipoAtendimento | None
    motivo: str | None
    trechos: list[TrechoRead] = []


class GrupoFamiliarCreate(BaseModel):
    nome: str


class GrupoFamiliarRead(ORMModel):
    id: int
    nome: str


class UsuarioCreate(BaseModel):
    nome: str
    abbr: str
    status: StatusAtivoInativo = StatusAtivoInativo.ATIVO
    contato: str | None = None
    data_nascimento: dt.date | None = None
    detalhe: str | None = None
    observacao: str | None = None
    grupo_familiar_id: int | None = None
    regiao_id: int | None = None


class UsuarioRead(ORMModel):
    id: int
    nome: str
    abbr: str
    data_cadastro: dt.date
    status: StatusAtivoInativo
    contato: str | None
    data_nascimento: dt.date | None
    detalhe: str | None
    observacao: str | None
    grupo_familiar_id: int | None
    regiao_id: int | None


class UsuarioComAgendaRead(UsuarioRead):
    agenda_semanal: list[UsuarioAgendaSemanalRead] = []
    excecoes: list[UsuarioExcecaoRead] = []


class GrupoFamiliarComUsuariosRead(GrupoFamiliarRead):
    usuarios: list[UsuarioRead] = []


# --------------------------------------------------------------------------
# Viagem do dia + passageiros
# --------------------------------------------------------------------------

class ViagemDiaPassageiroRead(ORMModel):
    id: int
    viagem_dia_id: int | None
    usuario_id: int
    usuario: UsuarioRead
    ordem_trecho: int
    hora: dt.time
    origem_tipo: TipoPonto | None
    origem_id: int | None
    origem_texto: str | None
    origem_detalhe: str | None
    regiao_origem_id: int | None
    destino_tipo: TipoPonto
    destino_id: int | None
    destino_texto: str | None
    destino_detalhe: str | None
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
    capacidade_usuarios: int
    capacidade_acompanhantes: int
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
    ordem_trecho: int = 0
    hora: dt.time
    origem_tipo: TipoPonto | None = None
    origem_id: int | None = None
    origem_texto: str | None = None
    origem_detalhe: str | None = None
    regiao_origem_id: int | None = None
    destino_tipo: TipoPonto = TipoPonto.LOCAL
    destino_id: int | None = None
    destino_texto: str | None = None
    destino_detalhe: str | None = None
    regiao_destino_id: int | None = None
    acompanhante: bool = False
    observacoes: str | None = None


class ViagemDiaPassageiroAtualizar(BaseModel):
    ordem_trecho: int | None = None
    hora: dt.time | None = None
    origem_tipo: TipoPonto | None = None
    origem_id: int | None = None
    origem_texto: str | None = None
    origem_detalhe: str | None = None
    regiao_origem_id: int | None = None
    destino_tipo: TipoPonto | None = None
    destino_id: int | None = None
    destino_texto: str | None = None
    destino_detalhe: str | None = None
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


class ViagemDiaCopiar(BaseModel):
    data_origem: dt.date
    data_destino: dt.date
    ancora_ids: list[int]


class DiaTravadoRead(BaseModel):
    data: dt.date
    travado: bool
    travado_em: dt.datetime | None = None


# --------------------------------------------------------------------------
# Modo Base (molde por dia da semana): grupos/viagens/membros curados
# manualmente -- a geracao real tenta materializar cada grupo como um carro
# real, sem dividir (ver app/services/base.py e app/services/geracao.py).
# --------------------------------------------------------------------------

class MembroBaseRead(BaseModel):
    id: int
    agenda_trecho_id: int
    ordem_trecho: int
    ordem: int
    usuario_id: int
    usuario_nome: str
    usuario_abbr: str
    usuario_data_nascimento: dt.date | None
    usuario_ativo: bool
    atendimento_ativo: bool
    usuario_grupo_familiar_id: int | None
    usuario_grupo_familiar_nome: str | None
    origem_tipo: TipoPonto | None
    origem_id: int | None
    origem_texto: str | None
    origem_detalhe: str | None
    regiao_origem_id: int | None
    destino_tipo: TipoPonto
    destino_id: int | None
    destino_texto: str | None
    destino_detalhe: str | None
    regiao_destino_id: int | None
    acompanhante: bool
    hora_agenda: dt.time


class ViagemBaseRead(BaseModel):
    id: int
    grupo_base_id: int
    hora: dt.time
    membros: list[MembroBaseRead] = []


class GrupoBaseRead(BaseModel):
    id: int
    dia_semana: DiaSemana
    rotulo: str | None
    ordem_exibicao: int
    viagens: list[ViagemBaseRead] = []


class GrupoRevezamentoCarroRead(BaseModel):
    grupo_base_id: int
    ordem: int


class GrupoRevezamentoCondutorRead(BaseModel):
    condutor_id: int
    ordem: int
    nome: str
    apelido: str | None


class GrupoRevezamentoRead(BaseModel):
    id: int
    dia_semana: DiaSemana
    rotulo: str | None
    deslocamento: int
    carros: list[GrupoRevezamentoCarroRead] = []
    condutores: list[GrupoRevezamentoCondutorRead] = []


class NaoClassificadoRead(BaseModel):
    agenda_trecho_id: int
    ordem_trecho: int
    usuario_id: int
    usuario_nome: str
    usuario_abbr: str
    usuario_data_nascimento: dt.date | None
    hora: dt.time
    usuario_grupo_familiar_id: int | None
    usuario_grupo_familiar_nome: str | None
    origem_tipo: TipoPonto | None
    origem_id: int | None
    origem_texto: str | None
    origem_detalhe: str | None
    regiao_origem_id: int | None
    destino_tipo: TipoPonto
    destino_id: int | None
    destino_texto: str | None
    destino_detalhe: str | None
    regiao_destino_id: int | None
    acompanhante: bool


class EstruturaBaseRead(BaseModel):
    grupos: list[GrupoBaseRead]
    nao_classificados: list[NaoClassificadoRead]
    grupos_revezamento: list[GrupoRevezamentoRead] = []


class ViagemBaseCreate(BaseModel):
    hora: dt.time


class MembroBaseMover(BaseModel):
    grupo_base_id: int
    hora: dt.time
    ordem: int | None = None


class ViagemBaseAlterarHora(BaseModel):
    hora: dt.time


class GrupoRevezamentoCreate(BaseModel):
    rotulo: str | None = None


class CarrosRevezamentoSet(BaseModel):
    grupo_base_ids: list[int]


class CondutoresRevezamentoSet(BaseModel):
    condutor_ids: list[int]


class ViagemDiaAbrir(BaseModel):
    data: dt.date
    regiao_id: int
    horario_saida: dt.time
    capacidade_usuarios: int
    capacidade_acompanhantes: int


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

class SobrasRead(BaseModel):
    condutores: list[CondutorRead]
    veiculos_manha: list[VeiculoRead]
    veiculos_tarde: list[VeiculoRead]


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
