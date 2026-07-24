export type StatusAtivoInativo = "Ativo" | "Inativo";
export type StatusVeiculo = "Ativo" | "Inativo" | "Manutencao";
export type StatusCondutor = "Ativo" | "Desligado" | "Afastado";
export type PeriodoCondutor = "Manha" | "Tarde";
export type TipoAtendimento = "Fixo" | "Eventual";
export type OperacaoExcecao = "Adicao" | "Modificacao" | "Suspensao";
export type DiaSemana = "SEG" | "TER" | "QUA" | "QUI" | "SEX" | "SAB" | "DOM";
export type TipoLocal = "Escola" | "Fisioterapia" | "Equoterapia" | "Trabalho" | "Hemodialise" | "Medico" | "Outros";
export type StatusViagemDia = "Planejada" | "Confirmada" | "Cancelada";
export type StatusAtendimentoDia = "Agendado" | "Cancelado" | "Em analise";
export type StatusFrequencia = "Trabalhado" | "Folga" | "Ferias" | "Falta" | "Pendente";
export type PapelConta = "Admin" | "Operador";
/** O que a origem ou o destino de um trecho representa: um Local cadastrado
 * (nome/endereco/regiao vem de la), o endereco principal do proprio usuario
 * do atendimento (sem precisar redigitar -- deriva de Usuario.abbr/detalhe/
 * regiao_id), ou um endereco avulso (rotulo + endereco completo digitados na
 * hora, regiao informada manualmente -- unico caso sem de onde derivar). */
export type TipoPonto = "Local" | "Usuario" | "Avulso";

export const DIAS_SEMANA: DiaSemana[] = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"];
export const DIAS_SEMANA_LABEL: Record<DiaSemana, string> = {
  SEG: "Segunda",
  TER: "Terca",
  QUA: "Quarta",
  QUI: "Quinta",
  SEX: "Sexta",
  SAB: "Sabado",
  DOM: "Domingo",
};

export const DIAS_SEMANA_ABREV: Record<DiaSemana, string> = {
  SEG: "Seg",
  TER: "Ter",
  QUA: "Qua",
  QUI: "Qui",
  SEX: "Sex",
  SAB: "Sab",
  DOM: "Dom",
};

const DIA_SEMANA_POR_WEEKDAY_JS: DiaSemana[] = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SAB"];

/** `data` no formato YYYY-MM-DD, interpretada como data local (nao UTC) pra
 * bater com `dia_semana_from_date` do backend. */
export function diaSemanaFromData(data: string): DiaSemana {
  const [ano, mes, dia] = data.split("-").map(Number);
  return DIA_SEMANA_POR_WEEKDAY_JS[new Date(ano, mes - 1, dia).getDay()];
}

/** Rotulo puramente posicional -- sem tentar adivinhar Ida/Retorno (isso
 * gera confusao em itinerarios com mais de 2 trechos ou retorno pra um
 * local diferente da origem, ver Trecho). */
export function rotuloTrecho(ordemTrecho: number): string {
  return `Trecho ${ordemTrecho + 1}`;
}

/** Rotulo de exibicao (card/celula) de um ponto (origem OU destino) ja
 * resolvido, a partir do tipo escolhido (ver TipoPonto): Local usa o nome
 * cadastrado (resolvido pelo chamador, que ja tem a lista de locais em mao);
 * Usuario usa o abbr/nome do proprio usuario do atendimento; Avulso usa o
 * rotulo digitado. `null` (so valido pra origem) significa "herda do trecho
 * anterior". */
export function rotuloPonto(
  tipo: TipoPonto | null,
  localNome: string | undefined,
  texto: string | null | undefined,
  usuarioAbbr: string | undefined,
  usuarioNome: string | undefined,
): string {
  if (tipo === "Local") return localNome ?? "local cadastrado";
  if (tipo === "Usuario") return usuarioAbbr || usuarioNome || "-";
  if (tipo === "Avulso") return texto || "-";
  return "(herda)";
}

export interface Regiao {
  id: number;
  nome: string;
}

export interface Local {
  id: number;
  nome: string;
  tipo: TipoLocal;
  regiao_id: number;
  observacao: string | null;
}

export interface LocalFixoUsuario {
  usuario_id: number;
  abbr: string;
  dias: DiaSemana[];
}

export interface LocalRecesso {
  id: number;
  local_id: number;
  data_inicio: string;
  data_fim: string;
  observacao: string | null;
}

export interface Empresa {
  id: number;
  nome: string;
  regioes: Regiao[];
}

export interface Veiculo {
  id: number;
  empresa_id: number;
  prefixo: string;
  placa: string;
  status: StatusVeiculo;
  capacidade_usuarios: number;
  capacidade_acompanhantes: number;
}

export interface Condutor {
  id: number;
  empresa_id: number;
  matricula: string;
  nome: string;
  apelido: string | null;
  status: StatusCondutor;
  periodo: PeriodoCondutor;
  veiculo_preferencial_id: number | null;
}

export interface CondutorFerias {
  id: number;
  condutor_id: number;
  data_inicio: string;
  data_fim: string;
  observacao: string | null;
}

export interface Usuario {
  id: number;
  nome: string;
  abbr: string;
  data_cadastro: string;
  status: StatusAtivoInativo;
  contato: string | null;
  data_nascimento: string | null;
  detalhe: string | null;
  observacao: string | null;
  grupo_familiar_id: number | null;
  regiao_id: number | null;
}

export interface GrupoFamiliar {
  id: number;
  nome: string;
}

export interface GrupoFamiliarComUsuarios extends GrupoFamiliar {
  usuarios: Usuario[];
}

/** Uma perna do itinerario do dia (origem/destino/hora/acompanhante), na
 * posicao `ordem` (0-based). Ida-e-volta convencional e so uma lista de 2
 * trechos -- nao ha caso especial pra isso.
 *
 * Origem e destino sao cada um um "ponto" com tipo (ver TipoPonto): Local
 * cadastrado (`*_id`), endereco do proprio usuario (sem campo extra) ou
 * avulso (`*_texto` + `*_detalhe` opcional + `regiao_*_id` obrigatorio,
 * unico caso sem de onde derivar a regiao sozinho). `origem_tipo` nulo so
 * vale em trechos que nao sao o primeiro do itinerario -- significa "herda
 * o destino do trecho anterior". */
export interface Trecho {
  id: number;
  ordem: number;
  hora: string;
  origem_tipo: TipoPonto | null;
  origem_id: number | null;
  origem_texto: string | null;
  origem_detalhe: string | null;
  regiao_origem_id: number | null;
  destino_tipo: TipoPonto;
  destino_id: number | null;
  destino_texto: string | null;
  destino_detalhe: string | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
}

export interface TrechoInput {
  hora: string;
  origem_tipo: TipoPonto | null;
  origem_id: number | null;
  origem_texto: string | null;
  origem_detalhe: string | null;
  regiao_origem_id: number | null;
  destino_tipo: TipoPonto;
  destino_id: number | null;
  destino_texto: string | null;
  destino_detalhe: string | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
}

export interface UsuarioAgendaSemanal {
  id: number;
  usuario_id: number;
  dia_semana: DiaSemana;
  tipo: TipoAtendimento;
  ativo: boolean;
  detalhe: string | null;
  trechos: Trecho[];
}

export interface UsuarioExcecao {
  id: number;
  usuario_id: number;
  data_inicio: string;
  data_fim: string;
  operacao: OperacaoExcecao;
  tipo: TipoAtendimento | null;
  motivo: string | null;
  trechos: Trecho[];
}

export interface UsuarioComAgenda extends Usuario {
  agenda_semanal: UsuarioAgendaSemanal[];
  excecoes: UsuarioExcecao[];
}

export interface ViagemDiaPassageiro {
  id: number;
  viagem_dia_id: number | null;
  usuario_id: number;
  usuario: Usuario;
  ordem_trecho: number;
  hora: string;
  origem_tipo: TipoPonto | null;
  origem_id: number | null;
  origem_texto: string | null;
  origem_detalhe: string | null;
  regiao_origem_id: number | null;
  destino_tipo: TipoPonto;
  destino_id: number | null;
  destino_texto: string | null;
  destino_detalhe: string | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
  ordem: number;
  status: StatusAtendimentoDia;
  observacoes: string | null;
  fixo: boolean;
  irregular: boolean;
  motivo_irregular: string | null;
}

export interface ViagemDia {
  id: number;
  data: string;
  regiao_id: number;
  empresa_id: number | null;
  condutor_id: number | null;
  veiculo_id: number | null;
  horario_saida: string;
  capacidade_usuarios: number;
  capacidade_acompanhantes: number;
  status: StatusViagemDia;
  observacoes: string | null;
  grupo_viagem_id: number | null;
  ordem_exibicao: number | null;
  passageiros: ViagemDiaPassageiro[];
  condutor_em_ferias: boolean;
  conflito_horario: boolean;
  motivo_conflito_horario: string | null;
  intervalo_inicio: string | null;
  intervalo_fim: string | null;
}

// --------------------------------------------------------------------------
// Modo Base (molde por dia da semana)
// --------------------------------------------------------------------------

export interface MembroBase {
  id: number;
  agenda_trecho_id: number;
  ordem_trecho: number;
  ordem: number;
  usuario_id: number;
  usuario_nome: string;
  usuario_abbr: string;
  usuario_data_nascimento: string | null;
  usuario_ativo: boolean;
  atendimento_ativo: boolean;
  usuario_grupo_familiar_id: number | null;
  usuario_grupo_familiar_nome: string | null;
  origem_tipo: TipoPonto | null;
  origem_id: number | null;
  origem_texto: string | null;
  origem_detalhe: string | null;
  regiao_origem_id: number | null;
  destino_tipo: TipoPonto;
  destino_id: number | null;
  destino_texto: string | null;
  destino_detalhe: string | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
  hora_agenda: string;
}

export interface ViagemBase {
  id: number;
  grupo_base_id: number;
  hora: string;
  membros: MembroBase[];
}

export interface GrupoBase {
  id: number;
  dia_semana: DiaSemana;
  rotulo: string | null;
  ordem_exibicao: number;
  viagens: ViagemBase[];
}

export interface GrupoRevezamentoCarro {
  grupo_base_id: number;
  ordem: number;
}

export interface GrupoRevezamentoCondutor {
  condutor_id: number;
  ordem: number;
  nome: string;
  apelido: string | null;
}

export interface GrupoRevezamento {
  id: number;
  dia_semana: DiaSemana;
  rotulo: string | null;
  deslocamento: number;
  carros: GrupoRevezamentoCarro[];
  condutores: GrupoRevezamentoCondutor[];
}

export interface NaoClassificadoBase {
  agenda_trecho_id: number;
  ordem_trecho: number;
  usuario_id: number;
  usuario_nome: string;
  usuario_abbr: string;
  usuario_data_nascimento: string | null;
  hora: string;
  usuario_grupo_familiar_id: number | null;
  usuario_grupo_familiar_nome: string | null;
  origem_tipo: TipoPonto | null;
  origem_id: number | null;
  origem_texto: string | null;
  origem_detalhe: string | null;
  regiao_origem_id: number | null;
  destino_tipo: TipoPonto;
  destino_id: number | null;
  destino_texto: string | null;
  destino_detalhe: string | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
}

export interface EstruturaBase {
  grupos: GrupoBase[];
  nao_classificados: NaoClassificadoBase[];
  grupos_revezamento: GrupoRevezamento[];
}

export interface Frequencia {
  id: number;
  condutor_id: number;
  data: string;
  tipo: StatusFrequencia;
  hora_entrada: string | null;
  intervalo_inicio: string | null;
  intervalo_fim: string | null;
  hora_saida: string | null;
  observacao: string | null;
}

export interface Sobras {
  condutores: Condutor[];
  veiculos_manha: Veiculo[];
  veiculos_tarde: Veiculo[];
}

export interface UsuarioDesconsiderado {
  usuario_id: number;
  usuario_nome: string;
  motivo: string;
}

export interface Conta {
  id: number;
  nome: string;
  login: string;
  papel: PapelConta;
  status: StatusAtivoInativo;
  criado_em: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  conta: Conta;
}
