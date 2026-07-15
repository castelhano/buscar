import type { DiaSemana, GrupoBase, MembroBase, Sentido, ViagemBase } from "../api/types";

/** Assuncao fixa (sem campo de capacidade no modo Base -- ver GrupoBase): todo
 * carro tem 4 lugares por viagem. */
export const CAPACIDADE_VIAGEM_BASE = 4;

export type StatusOcupacao = "livre" | "lotado" | "acima";

export interface CelulaOcupacao {
  viagemId: number;
  hora: string;
  ocupados: number;
  status: StatusOcupacao;
  membros: MembroBase[];
}

export interface CarroOcupacao {
  grupoId: number | null;
  ida: CelulaOcupacao[];
  volta: CelulaOcupacao[];
}

export interface ColunaDiaOcupacao {
  diaSemana: DiaSemana;
  carros: CarroOcupacao[];
}

export function statusOcupacao(ocupados: number): StatusOcupacao {
  if (ocupados > CAPACIDADE_VIAGEM_BASE) return "acima";
  if (ocupados === CAPACIDADE_VIAGEM_BASE) return "lotado";
  return "livre";
}

function ocuparViagem(viagem: ViagemBase): CelulaOcupacao {
  const ocupados = viagem.membros
    .filter((m) => m.usuario_ativo)
    .reduce((soma, m) => soma + (m.acompanhante ? 2 : 1), 0);
  return { viagemId: viagem.id, hora: viagem.hora, ocupados, status: statusOcupacao(ocupados), membros: viagem.membros };
}

function celulasDoSentido(grupo: GrupoBase | undefined, sentido: Sentido): CelulaOcupacao[] {
  if (!grupo) return [];
  return grupo.viagens
    .filter((v) => v.sentido === sentido)
    .sort((a, b) => a.hora.localeCompare(b.hora))
    .map(ocuparViagem);
}

/** Monta uma coluna (um dia) da matriz de ocupacao, alinhando os carros por
 * posicao (`ordem_exibicao`) -- carros do modo Base sao por dia, sem
 * identidade estavel entre dias, entao a linha N da matriz e "o carro na
 * posicao N daquele dia", nao um carro especifico. */
export function montarColunaDia(diaSemana: DiaSemana, grupos: GrupoBase[], totalCarros: number): ColunaDiaOcupacao {
  const carros: CarroOcupacao[] = [];
  for (let i = 0; i < totalCarros; i++) {
    const grupo = grupos[i];
    carros.push({
      grupoId: grupo?.id ?? null,
      ida: celulasDoSentido(grupo, "Ida"),
      volta: celulasDoSentido(grupo, "Retorno"),
    });
  }
  return { diaSemana, carros };
}
