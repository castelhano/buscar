export const PALETA_GRAFICOS = ["#2d3748", "#2e7d32", "#c0392b", "#f0a500", "#3b82f6", "#8e44ad", "#0f766e", "#b45309"];

export function corDaSerie(indice: number): string {
  return PALETA_GRAFICOS[indice % PALETA_GRAFICOS.length];
}
