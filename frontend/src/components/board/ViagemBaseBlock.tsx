import { useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Local, MembroBase, ViagemBase } from "../../api/types";
import { CAPACIDADE_ACOMPANHANTES_BASE, CAPACIDADE_USUARIOS_BASE } from "../../utils/ocupacao";
import { corGrupoFamiliar } from "./coresGrupoFamiliar";
import MembroBaseCard from "./MembroBaseCard";

interface Props {
  viagem: ViagemBase;
  locais: Local[];
  onRemoverViagem: (viagemId: number) => void;
  onRemoverMembro: (membroId: number) => void;
  onAlterarHora: (viagemId: number, hora: string) => void;
  gruposFamiliaresDesvinculados: Set<number>;
  onToggleDesvincularGrupoFamiliar: (grupoFamiliarId: number) => void;
}

/** Agrupa membros co-locados nessa viagem que sao do mesmo grupo familiar
 * (2+ presentes aqui) -- usados pra desenhar o container visual compartilhado;
 * membros sem grupo, ou cujo grupo so tem 1 representante nessa viagem, ficam
 * soltos (array de 1). */
function agruparPorFamilia(membros: MembroBase[]): MembroBase[][] {
  const vistos = new Set<number>();
  const resultado: MembroBase[][] = [];
  for (const m of membros) {
    if (vistos.has(m.id)) continue;
    if (m.usuario_grupo_familiar_id === null) {
      resultado.push([m]);
      continue;
    }
    const doGrupo = membros.filter((x) => x.usuario_grupo_familiar_id === m.usuario_grupo_familiar_id);
    doGrupo.forEach((x) => vistos.add(x.id));
    resultado.push(doGrupo);
  }
  return resultado;
}

export default function ViagemBaseBlock({
  viagem,
  locais,
  onRemoverViagem,
  onRemoverMembro,
  onAlterarHora,
  gruposFamiliaresDesvinculados,
  onToggleDesvincularGrupoFamiliar,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({
    id: `viagem-base-${viagem.id}`,
    data: {
      tipo: "viagem-base",
      viagemBaseId: viagem.id,
      grupoBaseId: viagem.grupo_base_id,
      hora: viagem.hora,
    },
  });

  const [editandoHora, setEditandoHora] = useState(false);
  const [novaHora, setNovaHora] = useState(viagem.hora.slice(0, 5));

  const membrosAtivos = viagem.membros.filter((m) => m.usuario_ativo && m.atendimento_ativo);
  const usuariosOcupados = membrosAtivos.length;
  const acompanhantesOcupados = membrosAtivos.filter((m) => m.acompanhante).length;

  return (
    <div
      ref={setNodeRef}
      className={`leg-block ${viagem.membros.length === 0 ? "leg-block-vazio" : ""}`}
      style={{ outline: isOver ? "2px solid var(--cor-primaria)" : "none" }}
    >
      <div className="leg-block-header">
        {editandoHora ? (
          <div style={{ display: "flex", gap: "0.3rem", alignItems: "center", flexWrap: "wrap" }}>
            <input type="time" value={novaHora} onChange={(e) => setNovaHora(e.target.value)} />
            <button
              className="btn btn-sm btn-primario"
              onClick={() => {
                onAlterarHora(viagem.id, novaHora);
                setEditandoHora(false);
              }}
            >
              Salvar
            </button>
            <button
              className="btn btn-sm"
              onClick={() => {
                setNovaHora(viagem.hora.slice(0, 5));
                setEditandoHora(false);
              }}
            >
              Cancelar
            </button>
          </div>
        ) : (
          <div className="horario-grupo-label" style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            {viagem.hora.slice(0, 5)}
            <button
              className="btn btn-sm"
              title="Alterar horario da viagem (ajusta a agenda de todos os passageiros)"
              onClick={() => {
                setNovaHora(viagem.hora.slice(0, 5));
                setEditandoHora(true);
              }}
            >
              alterar horario
            </button>
          </div>
        )}
        <div className="meta">
          {usuariosOcupados} usuario(s) · {acompanhantesOcupados} acompanhante(s)
        </div>
        {usuariosOcupados > CAPACIDADE_USUARIOS_BASE && (
          <div style={{ color: "var(--cor-alerta-borda)", fontWeight: 600, fontSize: "0.78rem", marginTop: "0.2rem" }}>
            ⚠ Mais de {CAPACIDADE_USUARIOS_BASE} usuarios nesse horario
          </div>
        )}
        {acompanhantesOcupados > CAPACIDADE_ACOMPANHANTES_BASE && (
          <div style={{ color: "var(--cor-alerta-borda)", fontWeight: 600, fontSize: "0.78rem", marginTop: "0.2rem" }}>
            ⚠ Mais de {CAPACIDADE_ACOMPANHANTES_BASE} acompanhantes nesse horario
          </div>
        )}
        {viagem.membros.length === 0 && (
          <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem" }}>
            <button className="btn btn-sm btn-perigo" onClick={() => onRemoverViagem(viagem.id)}>
              Remover viagem
            </button>
          </div>
        )}
      </div>

      <SortableContext items={viagem.membros.map((m) => `membro-${m.id}`)} strategy={verticalListSortingStrategy}>
        {agruparPorFamilia(viagem.membros).map((membrosDoGrupo) => {
          const [primeiro] = membrosDoGrupo;
          const cartoes = membrosDoGrupo.map((m) => (
            <MembroBaseCard
              key={m.id}
              viagemBaseId={viagem.id}
              grupoBaseId={viagem.grupo_base_id}
              hora={viagem.hora}
              membro={m}
              origemLocalNome={locais.find((l) => l.id === m.origem_id)?.nome}
              destinoLocalNome={locais.find((l) => l.id === m.destino_id)?.nome}
              onRemover={onRemoverMembro}
            />
          ));

          if (membrosDoGrupo.length < 2 || primeiro.usuario_grupo_familiar_id === null) {
            return cartoes;
          }

          const grupoFamiliarId = primeiro.usuario_grupo_familiar_id;
          const desvinculado = gruposFamiliaresDesvinculados.has(grupoFamiliarId);
          return (
            <div
              key={`familia-${grupoFamiliarId}`}
              className="grupo-familiar-container"
              style={{ borderColor: corGrupoFamiliar(grupoFamiliarId) }}
            >
              <div className="grupo-familiar-cabecalho">
                <span>{desvinculado ? "Grupo familiar (desmembrado)" : "Grupo familiar · move junto"}</span>
                <button
                  type="button"
                  className="btn btn-sm"
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleDesvincularGrupoFamiliar(grupoFamiliarId);
                  }}
                >
                  {desvinculado ? "Vincular" : "Desmembrar"}
                </button>
              </div>
              {cartoes}
            </div>
          );
        })}
      </SortableContext>
    </div>
  );
}
