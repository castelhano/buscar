import type { ViagemDia } from "./types";

export const CORTE_TARDE_MINUTOS = 14 * 60;

export function minutosDaHora(hora: string): number {
  const [h, m] = hora.split(":").map(Number);
  return h * 60 + m;
}

export function primeiraHora(viagem: ViagemDia): string {
  const horas = viagem.passageiros.map((p) => p.hora).sort();
  return horas[0] ?? viagem.horario_saida;
}

export function periodoDaViagem(viagem: ViagemDia): "Manha" | "Tarde" {
  return minutosDaHora(primeiraHora(viagem)) >= CORTE_TARDE_MINUTOS ? "Tarde" : "Manha";
}
