import type { EstruturaBase, Sentido } from "../api/types";

interface PernaAtiva {
  usuarioGrupoFamiliarId: number;
  destinoId: number | null;
  hora: string;
}

function localizarPernaAtiva(estrutura: EstruturaBase, agendaId: number, sentido: Sentido): PernaAtiva | null {
  for (const grupo of estrutura.grupos) {
    for (const viagem of grupo.viagens) {
      if (viagem.sentido !== sentido) continue;
      const membro = viagem.membros.find((m) => m.agenda_id === agendaId);
      if (membro && membro.usuario_grupo_familiar_id !== null) {
        return { usuarioGrupoFamiliarId: membro.usuario_grupo_familiar_id, destinoId: membro.destino_id, hora: viagem.hora };
      }
      if (membro) return null; // achou, mas sem grupo familiar -- nao ha irmaos pra buscar
    }
  }
  const naoClassificado = estrutura.nao_classificados.find((nc) => nc.agenda_id === agendaId && nc.sentido === sentido);
  if (naoClassificado && naoClassificado.usuario_grupo_familiar_id !== null) {
    return {
      usuarioGrupoFamiliarId: naoClassificado.usuario_grupo_familiar_id,
      destinoId: naoClassificado.destino_id,
      hora: naoClassificado.hora,
    };
  }
  return null;
}

export interface IrmaosParaMover {
  grupoFamiliarId: number;
  agendaIds: number[];
}

/** Acha os agenda_id de outros usuarios do MESMO grupo familiar, mesmo
 * sentido/horario/destino de quem esta sendo arrastado -- candidatos a se
 * mover junto (drag-n-drop vinculado no molde Base). So considera match
 * exato de horario+destino: se o horario/destino do irmao divergir nesse
 * dia da semana, ele fica de fora (nao ha "junto" possivel). */
export function encontrarIrmaosParaMover(estrutura: EstruturaBase, agendaId: number, sentido: Sentido): IrmaosParaMover | null {
  const ativa = localizarPernaAtiva(estrutura, agendaId, sentido);
  if (ativa === null) return null;

  const irmaos: number[] = [];
  for (const grupo of estrutura.grupos) {
    for (const viagem of grupo.viagens) {
      if (viagem.sentido !== sentido || viagem.hora !== ativa.hora) continue;
      for (const membro of viagem.membros) {
        if (
          membro.agenda_id !== agendaId &&
          membro.usuario_grupo_familiar_id === ativa.usuarioGrupoFamiliarId &&
          membro.destino_id === ativa.destinoId
        ) {
          irmaos.push(membro.agenda_id);
        }
      }
    }
  }
  for (const nc of estrutura.nao_classificados) {
    if (
      nc.agenda_id !== agendaId &&
      nc.sentido === sentido &&
      nc.hora === ativa.hora &&
      nc.usuario_grupo_familiar_id === ativa.usuarioGrupoFamiliarId &&
      nc.destino_id === ativa.destinoId
    ) {
      irmaos.push(nc.agenda_id);
    }
  }
  return { grupoFamiliarId: ativa.usuarioGrupoFamiliarId, agendaIds: irmaos };
}
