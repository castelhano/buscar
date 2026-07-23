import type { DiaSemana, GrupoBase, MembroBase, NaoClassificadoBase, Sentido, ViagemBase } from "../api/types";
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

export type StatusOcupacao = "livre" | "atencao" | "lotado" | "acima";

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

const LIMIAR_ATENCAO = 0.7;

export function statusOcupacao(ocupados: number, capacidade: number): StatusOcupacao {
  if (ocupados > capacidade) return "acima";
  if (ocupados === capacidade) return "lotado";
  if (capacidade > 0 && ocupados / capacidade > LIMIAR_ATENCAO) return "atencao";
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

export interface CelulaNaoAlocados {
  usuarios: number;
  acompanhantes: number;
}

export interface LinhaHoraDia {
  hora: string;
  porCarro: (CelulaHoraCarro | null)[];
  /** Efetivos elegiveis nesse horario que ainda nao foram alocados em nenhum
   * carro -- `null` quando a coluna "N/Aloc" existe no periodo mas ninguem
   * cai nesse horario especifico (ver `MatrizDiaSimples.temNaoAlocados`). */
  celulaNaoAlocados: CelulaNaoAlocados | null;
  /** Capacidade de usuarios so dos carros reais presentes nesse horario --
   * "N/Aloc" nao tem carro, entao nao soma capacidade, so entra no total
   * ocupado (ver `totalOcupados`). */
  capacidadeUsuarios: number;
  /** Usuarios+acompanhantes dos carros reais + "N/Aloc" nesse horario. */
  totalOcupados: OcupacaoPar;
}

export interface MatrizDiaSimples {
  totalCarros: number;
  /** true quando ha alguem ainda nao alocado em nenhum carro no periodo --
   * so nesse caso a coluna "N/Aloc" aparece. */
  temNaoAlocados: boolean;
  linhas: LinhaHoraDia[];
  totalPorCarro: OcupacaoPar[];
  /** Soma de "N/Aloc" no periodo todo (coluna de totais). */
  naoAlocadosTotal: OcupacaoPar;
  /** Usuarios+acompanhantes de todo mundo (carros reais + "N/Aloc") somados
   * num unico numero, pra celula "Total" da linha totalizadora. */
  totalGeralTodos: number;
}

/** Filtra grupos/viagens para um periodo especifico antes de montar a matriz --
 * carros sem nenhuma viagem no periodo nao entram como coluna, e as horas
 * consideradas ficam restritas ao periodo, evitando colunas/linhas em branco
 * quando um mesmo dia tem carros de manha e de tarde.
 *
 * Quem ainda nao foi alocado em nenhum carro vira uma coluna "N/Aloc" a mais
 * (sem capacidade fixa, ja que nao e um carro real) -- assim o percentual de
 * cada linha reflete toda a demanda (carros + nao alocados) sobre a
 * capacidade real disponivel. Mantem paridade com `gerar_pdf_ocupacao_base`
 * no backend (`app/services/exportacao.py`). */
export function montarMatrizDiaSimples(
  grupos: GrupoBase[],
  periodo?: PeriodoOcupacao,
  naoClassificados: NaoClassificadoBase[] = [],
): MatrizDiaSimples {
  const gruposDoPeriodo = periodo === undefined ? grupos : grupos.filter((g) => g.viagens.some((v) => periodoDaHora(v.hora) === periodo));
  const totalCarros = gruposDoPeriodo.length;
  const ncDoPeriodo = periodo === undefined ? naoClassificados : naoClassificados.filter((n) => periodoDaHora(n.hora) === periodo);
  const temNaoAlocados = ncDoPeriodo.length > 0;

  const horasReais = horasDosGrupos(gruposDoPeriodo).filter((hora) => periodo === undefined || periodoDaHora(hora) === periodo);
  const horas = [...new Set([...horasReais, ...ncDoPeriodo.map((n) => n.hora)])].sort();

  const linhas: LinhaHoraDia[] = horas.map((hora) => {
    const porCarro: (CelulaHoraCarro | null)[] = [];
    let totalUsuariosReais = 0;
    let totalAcompanhantesReais = 0;
    let carrosNaHora = 0;
    for (const grupo of gruposDoPeriodo) {
      const viagensNaHora = grupo.viagens.filter((v) => v.hora === hora);
      if (viagensNaHora.length === 0) {
        porCarro.push(null);
        continue;
      }
      carrosNaHora += 1;
      const ocupados = viagensNaHora.reduce((soma, v) => somaPar(soma, ocupadosDaViagem(v)), { usuarios: 0, acompanhantes: 0 });
      totalUsuariosReais += ocupados.usuarios;
      totalAcompanhantesReais += ocupados.acompanhantes;
      porCarro.push({
        ocupados,
        statusUsuarios: statusOcupacao(ocupados.usuarios, CAPACIDADE_USUARIOS_BASE),
        statusAcompanhantes: statusOcupacao(ocupados.acompanhantes, CAPACIDADE_ACOMPANHANTES_BASE),
        viagens: viagensNaHora.map((v) => ({ viagemId: v.id, sentido: v.sentido, membros: v.membros })),
      });
    }

    let celulaNaoAlocados: CelulaNaoAlocados | null = null;
    if (temNaoAlocados) {
      const ncNaHora = ncDoPeriodo.filter((n) => n.hora === hora);
      if (ncNaHora.length > 0) {
        celulaNaoAlocados = { usuarios: ncNaHora.length, acompanhantes: ncNaHora.filter((n) => n.acompanhante).length };
      }
    }

    const capacidadeUsuarios = carrosNaHora * CAPACIDADE_USUARIOS_BASE;
    const totalOcupados: OcupacaoPar = {
      usuarios: totalUsuariosReais + (celulaNaoAlocados?.usuarios ?? 0),
      acompanhantes: totalAcompanhantesReais + (celulaNaoAlocados?.acompanhantes ?? 0),
    };
    return { hora, porCarro, celulaNaoAlocados, capacidadeUsuarios, totalOcupados };
  });

  const totalPorCarro: OcupacaoPar[] = gruposDoPeriodo.map((_, indice) => ({
    usuarios: linhas.reduce((soma, l) => soma + (l.porCarro[indice]?.ocupados.usuarios ?? 0), 0),
    acompanhantes: linhas.reduce((soma, l) => soma + (l.porCarro[indice]?.ocupados.acompanhantes ?? 0), 0),
  }));
  const naoAlocadosTotal: OcupacaoPar = {
    usuarios: linhas.reduce((soma, l) => soma + (l.celulaNaoAlocados?.usuarios ?? 0), 0),
    acompanhantes: linhas.reduce((soma, l) => soma + (l.celulaNaoAlocados?.acompanhantes ?? 0), 0),
  };
  const totalGeralTodos =
    totalPorCarro.reduce((soma, t) => soma + t.usuarios + t.acompanhantes, 0) +
    naoAlocadosTotal.usuarios +
    naoAlocadosTotal.acompanhantes;

  return { totalCarros, temNaoAlocados, linhas, totalPorCarro, naoAlocadosTotal, totalGeralTodos };
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

  return {
    dias: diasComGrupos.map((d) => d.dia),
    linhas,
    totalPorDia,
    totalGeral,
  };
}
