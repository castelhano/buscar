export const CORES_REVEZAMENTO = ["#4f8ef7", "#f7924f", "#4fd18f", "#c14fd1", "#d1c14f", "#4fd1c1"];

export function corRevezamento(grupoRevezamentoId: number): string {
  return CORES_REVEZAMENTO[grupoRevezamentoId % CORES_REVEZAMENTO.length];
}
