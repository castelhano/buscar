import type { DiaSemana, GrupoBase, MembroBase, Sentido, ViagemBase } from "../api/types";
import { CORTE_TARDE_MINUTOS, minutosDaHora } from "../api/periodo";

/** Assuncao fixa (sem campo de capacidade no modo Base -- ver GrupoBase): todo
 * carro tem 4 lugares por viagem. */
export const CAPACIDADE_VIAGEM_BASE = 4;

export type PeriodoOcupacao = "Manha" | "Tarde";

export function periodoDaHora(hora: string): PeriodoOcupacao {
  return minutosDaHora(hora) >= CORTE_TARDE_MINUTOS ? "Tarde" : "Manha";
}

export type StatusOcupacao = "livre" | "lotado" | "acima";

export interface ViagemResumo {
  viagemId: number;
  sentido: Sentido;
  membros: MembroBase[];
}

export function statusOcupacao(ocupados: number, capacidade: number): StatusOcupacao {
  if (ocupados > capacidade) return "acima";
  if (ocupados === capacidade) return "lotado";
  return "livre";
}

export function ocupadosDaViagem(viagem: ViagemBase): number {
  return viagem.membros
    .filter((m) => m.usuario_ativo && m.atendimento_ativo)
    .reduce((soma, m) => soma + (m.acompanhante ? 2 : 1), 0);
}

function horasDosGrupos(grupos: GrupoBase[]): string[] {
  const horas = new Set<string>();
  for (const grupo of grupos) for (const viagem of grupo.viagens) horas.add(viagem.hora);
  return [...horas].sort();
}

// --------------------------------------------------------------------------
// Visao de dia simples: linhas = horario, colunas = carro
// --------------------------------------------------------------------------

export interface CelulaHoraCarro {
  ocupados: number;
  status: StatusOcupacao;
  viagens: ViagemResumo[];
}

export interface LinhaHoraDia {
  hora: string;
  porCarro: (CelulaHoraCarro | null)[];
  totalOcupados: number;
}

export interface MatrizDiaSimples {
  totalCarros: number;
  linhas: LinhaHoraDia[];
  totalPorCarro: number[];
  totalGeral: number;
}

/** Filtra grupos/viagens para um periodo especifico antes de montar a matriz --
 * carros sem nenhuma viagem no periodo nao entram como coluna, e as horas
 * consideradas ficam restritas ao periodo, evitando colunas/linhas em branco
 * quando um mesmo dia tem carros de manha e de tarde. */
export function montarMatrizDiaSimples(grupos: GrupoBase[], periodo?: PeriodoOcupacao): MatrizDiaSimples {
  const gruposDoPeriodo = periodo === undefined ? grupos : grupos.filter((g) => g.viagens.some((v) => periodoDaHora(v.hora) === periodo));
  const totalCarros = gruposDoPeriodo.length;
  const horas = horasDosGrupos(gruposDoPeriodo).filter((hora) => periodo === undefined || periodoDaHora(hora) === periodo);

  const linhas: LinhaHoraDia[] = horas.map((hora) => {
    const porCarro: (CelulaHoraCarro | null)[] = [];
    let totalOcupados = 0;
    for (const grupo of gruposDoPeriodo) {
      const viagensNaHora = grupo.viagens.filter((v) => v.hora === hora);
      if (viagensNaHora.length === 0) {
        porCarro.push(null);
        continue;
      }
      const ocupados = viagensNaHora.reduce((soma, v) => soma + ocupadosDaViagem(v), 0);
      totalOcupados += ocupados;
      porCarro.push({
        ocupados,
        status: statusOcupacao(ocupados, CAPACIDADE_VIAGEM_BASE),
        viagens: viagensNaHora.map((v) => ({ viagemId: v.id, sentido: v.sentido, membros: v.membros })),
      });
    }
    return { hora, porCarro, totalOcupados };
  });

  const totalPorCarro = gruposDoPeriodo.map((_, indice) => linhas.reduce((soma, l) => soma + (l.porCarro[indice]?.ocupados ?? 0), 0));
  const totalGeral = totalPorCarro.reduce((a, b) => a + b, 0);

  return { totalCarros, linhas, totalPorCarro, totalGeral };
}

// --------------------------------------------------------------------------
// Visao de semana toda: linhas = horario, colunas = dia (agregando os carros)
// --------------------------------------------------------------------------

export interface CarroNaCelula {
  grupoId: number;
  viagens: ViagemResumo[];
}

export interface CelulaHoraDiaSemana {
  ocupados: number;
  capacidade: number;
  status: StatusOcupacao;
  porCarro: CarroNaCelula[];
}

export interface LinhaHoraSemana {
  hora: string;
  porDia: (CelulaHoraDiaSemana | null)[];
  totalOcupados: number;
  totalCapacidade: number;
}

export interface DiaComGrupos {
  dia: DiaSemana;
  grupos: GrupoBase[];
}

export interface MatrizSemana {
  dias: DiaSemana[];
  linhas: LinhaHoraSemana[];
  totalPorDia: { ocupados: number; capacidade: number }[];
  totalGeral: { ocupados: number; capacidade: number };
}

export function montarMatrizSemana(diasComGrupos: DiaComGrupos[]): MatrizSemana {
  const horas = horasDosGrupos(diasComGrupos.flatMap((d) => d.grupos));

  const linhas: LinhaHoraSemana[] = horas.map((hora) => {
    let totalOcupados = 0;
    let totalCapacidade = 0;
    const porDia: (CelulaHoraDiaSemana | null)[] = diasComGrupos.map(({ grupos }) => {
      const porCarro: CarroNaCelula[] = [];
      let ocupados = 0;
      for (const grupo of grupos) {
        const viagensNaHora = grupo.viagens.filter((v) => v.hora === hora);
        if (viagensNaHora.length === 0) continue;
        porCarro.push({ grupoId: grupo.id, viagens: viagensNaHora.map((v) => ({ viagemId: v.id, sentido: v.sentido, membros: v.membros })) });
        ocupados += viagensNaHora.reduce((soma, v) => soma + ocupadosDaViagem(v), 0);
      }
      if (porCarro.length === 0) return null;
      const capacidade = porCarro.length * CAPACIDADE_VIAGEM_BASE;
      totalOcupados += ocupados;
      totalCapacidade += capacidade;
      return { ocupados, capacidade, status: statusOcupacao(ocupados, capacidade), porCarro };
    });
    return { hora, porDia, totalOcupados, totalCapacidade };
  });

  const totalPorDia = diasComGrupos.map((_, indice) => {
    const ocupados = linhas.reduce((soma, l) => soma + (l.porDia[indice]?.ocupados ?? 0), 0);
    const capacidade = linhas.reduce((soma, l) => soma + (l.porDia[indice]?.capacidade ?? 0), 0);
    return { ocupados, capacidade };
  });
  const totalGeral = totalPorDia.reduce(
    (acc, t) => ({ ocupados: acc.ocupados + t.ocupados, capacidade: acc.capacidade + t.capacidade }),
    { ocupados: 0, capacidade: 0 },
  );

  return { dias: diasComGrupos.map((d) => d.dia), linhas, totalPorDia, totalGeral };
}
