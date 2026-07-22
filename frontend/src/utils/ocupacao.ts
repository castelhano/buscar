import type { DiaSemana, GrupoBase, MembroBase, Sentido, ViagemBase } from "../api/types";
import { CORTE_TARDE_MINUTOS, minutosDaHora } from "../api/periodo";

/** Assuncao fixa (sem campo de capacidade no modo Base -- ver GrupoBase): todo
 * carro tem 4 usuarios + 2 acompanhantes por viagem, como dois pools
 * independentes (nao somados num unico numero de "lugares"). */
export const CAPACIDADE_USUARIOS_BASE = 4;
export const CAPACIDADE_ACOMPANHANTES_BASE = 2;

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

/** Usuarios e acompanhantes sao dois pools independentes (ver
 * `CAPACIDADE_USUARIOS_BASE`/`CAPACIDADE_ACOMPANHANTES_BASE`), nunca somados
 * num unico numero de ocupacao. */
export interface OcupacaoPar {
  usuarios: number;
  acompanhantes: number;
}

function somaPar(a: OcupacaoPar, b: OcupacaoPar): OcupacaoPar {
  return { usuarios: a.usuarios + b.usuarios, acompanhantes: a.acompanhantes + b.acompanhantes };
}

export function statusOcupacao(ocupados: number, capacidade: number): StatusOcupacao {
  if (ocupados > capacidade) return "acima";
  if (ocupados === capacidade) return "lotado";
  return "livre";
}

export function ocupadosDaViagem(viagem: ViagemBase): OcupacaoPar {
  const ativos = viagem.membros.filter((m) => m.usuario_ativo && m.atendimento_ativo);
  return { usuarios: ativos.length, acompanhantes: ativos.filter((m) => m.acompanhante).length };
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
  ocupados: OcupacaoPar;
  statusUsuarios: StatusOcupacao;
  statusAcompanhantes: StatusOcupacao;
  viagens: ViagemResumo[];
}

export interface LinhaHoraDia {
  hora: string;
  porCarro: (CelulaHoraCarro | null)[];
  totalOcupados: OcupacaoPar;
}

export interface MatrizDiaSimples {
  totalCarros: number;
  linhas: LinhaHoraDia[];
  totalPorCarro: OcupacaoPar[];
  totalGeral: OcupacaoPar;
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
    let totalOcupados: OcupacaoPar = { usuarios: 0, acompanhantes: 0 };
    for (const grupo of gruposDoPeriodo) {
      const viagensNaHora = grupo.viagens.filter((v) => v.hora === hora);
      if (viagensNaHora.length === 0) {
        porCarro.push(null);
        continue;
      }
      const ocupados = viagensNaHora.reduce((soma, v) => somaPar(soma, ocupadosDaViagem(v)), { usuarios: 0, acompanhantes: 0 });
      totalOcupados = somaPar(totalOcupados, ocupados);
      porCarro.push({
        ocupados,
        statusUsuarios: statusOcupacao(ocupados.usuarios, CAPACIDADE_USUARIOS_BASE),
        statusAcompanhantes: statusOcupacao(ocupados.acompanhantes, CAPACIDADE_ACOMPANHANTES_BASE),
        viagens: viagensNaHora.map((v) => ({ viagemId: v.id, sentido: v.sentido, membros: v.membros })),
      });
    }
    return { hora, porCarro, totalOcupados };
  });

  const totalPorCarro: OcupacaoPar[] = gruposDoPeriodo.map((_, indice) => ({
    usuarios: linhas.reduce((soma, l) => soma + (l.porCarro[indice]?.ocupados.usuarios ?? 0), 0),
    acompanhantes: linhas.reduce((soma, l) => soma + (l.porCarro[indice]?.ocupados.acompanhantes ?? 0), 0),
  }));
  const totalGeral = totalPorCarro.reduce(somaPar, { usuarios: 0, acompanhantes: 0 });

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
  ocupados: OcupacaoPar;
  capacidade: OcupacaoPar;
  statusUsuarios: StatusOcupacao;
  statusAcompanhantes: StatusOcupacao;
  porCarro: CarroNaCelula[];
}

export interface LinhaHoraSemana {
  hora: string;
  porDia: (CelulaHoraDiaSemana | null)[];
  totalOcupados: OcupacaoPar;
  totalCapacidade: OcupacaoPar;
}

export interface DiaComGrupos {
  dia: DiaSemana;
  grupos: GrupoBase[];
}

export interface MatrizSemana {
  dias: DiaSemana[];
  linhas: LinhaHoraSemana[];
  totalPorDia: { ocupados: OcupacaoPar; capacidade: OcupacaoPar }[];
  totalGeral: { ocupados: OcupacaoPar; capacidade: OcupacaoPar };
}

export function montarMatrizSemana(diasComGrupos: DiaComGrupos[]): MatrizSemana {
  const horas = horasDosGrupos(diasComGrupos.flatMap((d) => d.grupos));

  const linhas: LinhaHoraSemana[] = horas.map((hora) => {
    let totalOcupados: OcupacaoPar = { usuarios: 0, acompanhantes: 0 };
    let totalCapacidade: OcupacaoPar = { usuarios: 0, acompanhantes: 0 };
    const porDia: (CelulaHoraDiaSemana | null)[] = diasComGrupos.map(({ grupos }) => {
      const porCarro: CarroNaCelula[] = [];
      let ocupados: OcupacaoPar = { usuarios: 0, acompanhantes: 0 };
      for (const grupo of grupos) {
        const viagensNaHora = grupo.viagens.filter((v) => v.hora === hora);
        if (viagensNaHora.length === 0) continue;
        porCarro.push({ grupoId: grupo.id, viagens: viagensNaHora.map((v) => ({ viagemId: v.id, sentido: v.sentido, membros: v.membros })) });
        ocupados = viagensNaHora.reduce((soma, v) => somaPar(soma, ocupadosDaViagem(v)), ocupados);
      }
      if (porCarro.length === 0) return null;
      const capacidade: OcupacaoPar = {
        usuarios: porCarro.length * CAPACIDADE_USUARIOS_BASE,
        acompanhantes: porCarro.length * CAPACIDADE_ACOMPANHANTES_BASE,
      };
      totalOcupados = somaPar(totalOcupados, ocupados);
      totalCapacidade = somaPar(totalCapacidade, capacidade);
      return {
        ocupados,
        capacidade,
        statusUsuarios: statusOcupacao(ocupados.usuarios, capacidade.usuarios),
        statusAcompanhantes: statusOcupacao(ocupados.acompanhantes, capacidade.acompanhantes),
        porCarro,
      };
    });
    return { hora, porDia, totalOcupados, totalCapacidade };
  });

  const totalPorDia = diasComGrupos.map((_, indice) => {
    const ocupados: OcupacaoPar = {
      usuarios: linhas.reduce((soma, l) => soma + (l.porDia[indice]?.ocupados.usuarios ?? 0), 0),
      acompanhantes: linhas.reduce((soma, l) => soma + (l.porDia[indice]?.ocupados.acompanhantes ?? 0), 0),
    };
    const capacidade: OcupacaoPar = {
      usuarios: linhas.reduce((soma, l) => soma + (l.porDia[indice]?.capacidade.usuarios ?? 0), 0),
      acompanhantes: linhas.reduce((soma, l) => soma + (l.porDia[indice]?.capacidade.acompanhantes ?? 0), 0),
    };
    return { ocupados, capacidade };
  });
  const totalGeral = totalPorDia.reduce(
    (acc, t) => ({ ocupados: somaPar(acc.ocupados, t.ocupados), capacidade: somaPar(acc.capacidade, t.capacidade) }),
    { ocupados: { usuarios: 0, acompanhantes: 0 }, capacidade: { usuarios: 0, acompanhantes: 0 } },
  );

  return { dias: diasComGrupos.map((d) => d.dia), linhas, totalPorDia, totalGeral };
}
