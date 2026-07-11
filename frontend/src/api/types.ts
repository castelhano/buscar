export type StatusAtivoInativo = "Ativo" | "Inativo";
export type StatusVeiculo = "Ativo" | "Inativo" | "Manutencao";
export type StatusCondutor = "Ativo" | "Desligado" | "Afastado";
export type PeriodoCondutor = "Manha" | "Tarde";
export type TipoAtendimento = "Fixo" | "Eventual";
export type Modalidade = "Somente Ida" | "Ida e Volta";
export type DiaSemana = "SEG" | "TER" | "QUA" | "QUI" | "SEX" | "SAB" | "DOM";
export type TipoLocal = "Escola" | "Fisioterapia" | "Equoterapia" | "Trabalho" | "Hemodialise" | "Outros";
export type Sentido = "Ida" | "Retorno";
export type StatusViagemDia = "Planejada" | "Confirmada" | "Cancelada";
export type StatusAtendimentoDia = "Agendado" | "Cancelado" | "Em analise";
export type StatusFrequencia = "Trabalhado" | "Folga" | "Ferias" | "Falta" | "Pendente";

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
  detalhe: string | null;
}

export interface UsuarioAgendaSemanal {
  id: number;
  usuario_id: number;
  dia_semana: DiaSemana;
  tipo: TipoAtendimento;
  modalidade: Modalidade;
  acompanhante: boolean;
  ordem: number;
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
  data: string;
  suspenso: boolean;
  tipo: TipoAtendimento | null;
  saida: string | null;
  retorno: string | null;
  origem: string | null;
  regiao_origem_id: number | null;
  destino_id: number | null;
  motivo: string | null;
}

export interface UsuarioComAgenda extends Usuario {
  agenda_semanal: UsuarioAgendaSemanal[];
  excecoes: UsuarioExcecao[];
}

export interface ViagemDiaPassageiro {
  id: number;
  viagem_dia_id: number;
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
  passageiros: ViagemDiaPassageiro[];
  condutor_em_ferias: boolean;
  conflito_horario: boolean;
  motivo_conflito_horario: string | null;
  intervalo_inicio: string | null;
  intervalo_fim: string | null;
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

export interface CondutorSobra extends Condutor {
  em_ferias: boolean;
}

export interface Sobras {
  condutores: CondutorSobra[];
  veiculos: Veiculo[];
}
