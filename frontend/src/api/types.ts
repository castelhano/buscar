export type StatusAtivoInativo = "Ativo" | "Inativo";
export type StatusVeiculo = "Ativo" | "Inativo" | "Manutencao";
export type StatusCondutor = "Ativo" | "Desligado" | "Afastado";
export type PeriodoCondutor = "Manha" | "Tarde";
export type TipoAtendimento = "Fixo" | "Eventual";
export type OperacaoExcecao = "Adicao" | "Modificacao" | "Suspensao";
export type DiaSemana = "SEG" | "TER" | "QUA" | "QUI" | "SEX" | "SAB" | "DOM";
export type TipoLocal = "Escola" | "Fisioterapia" | "Equoterapia" | "Trabalho" | "Hemodialise" | "Medico" | "Outros";
export type Sentido = "Ida" | "Retorno";
export type StatusViagemDia = "Planejada" | "Confirmada" | "Cancelada";
export type StatusAtendimentoDia = "Agendado" | "Cancelado" | "Em analise";
export type StatusFrequencia = "Trabalhado" | "Folga" | "Ferias" | "Falta" | "Pendente";
export type PapelConta = "Admin" | "Operador";

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
  capacidade: number;
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
  detalhe: string | null;
  observacao: string | null;
}

export interface UsuarioAgendaSemanal {
  id: number;
  usuario_id: number;
  dia_semana: DiaSemana;
  tipo: TipoAtendimento;
  acompanhante: boolean;
  saida: string | null;
  retorno: string | null;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
  ativo: boolean;
  detalhe: string | null;
}

export interface UsuarioExcecao {
  id: number;
  usuario_id: number;
  data_inicio: string;
  data_fim: string;
  operacao: OperacaoExcecao;
  tipo: TipoAtendimento | null;
  saida: string | null;
  retorno: string | null;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
  acompanhante: boolean | null;
  motivo: string | null;
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
  sentido: Sentido;
  hora: string;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
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
  capacidade: number;
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
  agenda_id: number;
  ordem: number;
  usuario_id: number;
  usuario_nome: string;
  usuario_abbr: string;
  usuario_ativo: boolean;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
  regiao_destino_id: number | null;
  acompanhante: boolean;
}

export interface ViagemBase {
  id: number;
  grupo_base_id: number;
  sentido: Sentido;
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
  agenda_id: number;
  usuario_id: number;
  usuario_nome: string;
  usuario_abbr: string;
  sentido: Sentido;
  hora: string;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
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
  veiculos: Veiculo[];
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
