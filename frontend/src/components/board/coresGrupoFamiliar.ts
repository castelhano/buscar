const CORES_GRUPO_FAMILIAR = ["#e0578a", "#578ae0", "#57c2a3", "#c2a357", "#a357c2", "#57c257"];

export function corGrupoFamiliar(grupoFamiliarId: number): string {
  return CORES_GRUPO_FAMILIAR[grupoFamiliarId % CORES_GRUPO_FAMILIAR.length];
}
