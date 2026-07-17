import type { ViagemDia } from "./types";

function primeiraHora(viagem: ViagemDia): string {
  const horas = viagem.passageiros.map((p) => p.hora).sort();
  return horas[0] ?? viagem.horario_saida;
}

/** Agrupa as pernas (ida/volta/varios horarios) de um dia em blocos (carros),
 * reproduzindo a ordem definida na tela Base (GrupoBase.ordem_exibicao,
 * gravada na ancora do bloco na geracao) em vez de reordenar por horario;
 * carros sem ordem (abertos manualmente) vao pro fim, por horario.
 */
export function agruparPorBloco(viagens: ViagemDia[]): ViagemDia[][] {
  const grupos = new Map<number, ViagemDia[]>();
  for (const viagem of viagens) {
    const chave = viagem.grupo_viagem_id ?? viagem.id;
    const grupo = grupos.get(chave);
    if (grupo) grupo.push(viagem);
    else grupos.set(chave, [viagem]);
  }
  const lista = [...grupos.values()];
  for (const grupo of lista) {
    grupo.sort((a, b) => primeiraHora(a).localeCompare(primeiraHora(b)));
  }
  const ordemDoBloco = (grupo: ViagemDia[]) => grupo.find((v) => v.grupo_viagem_id === null)?.ordem_exibicao ?? null;
  lista.sort((a, b) => {
    const ordemA = ordemDoBloco(a);
    const ordemB = ordemDoBloco(b);
    if (ordemA !== null && ordemB !== null) return ordemA - ordemB;
    if (ordemA !== null) return -1;
    if (ordemB !== null) return 1;
    return primeiraHora(a[0]).localeCompare(primeiraHora(b[0]));
  });
  return lista;
}

export function ancoraIdDoBloco(grupo: ViagemDia[]): number {
  return grupo.find((v) => v.grupo_viagem_id === null)?.id ?? grupo[0].id;
}
