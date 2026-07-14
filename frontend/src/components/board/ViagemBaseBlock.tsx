import { useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Local, ViagemBase } from "../../api/types";
import MembroBaseCard from "./MembroBaseCard";

const LIMITE_ALERTA = 4;

interface Props {
  viagem: ViagemBase;
  locais: Local[];
  onRemoverViagem: (viagemId: number) => void;
  onRemoverMembro: (membroId: number) => void;
  onAlterarHora: (viagemId: number, hora: string) => void;
}

export default function ViagemBaseBlock({ viagem, locais, onRemoverViagem, onRemoverMembro, onAlterarHora }: Props) {
  const { setNodeRef, isOver } = useDroppable({
    id: `viagem-base-${viagem.id}`,
    data: {
      tipo: "viagem-base",
      viagemBaseId: viagem.id,
      grupoBaseId: viagem.grupo_base_id,
      sentido: viagem.sentido,
      hora: viagem.hora,
    },
  });

  const [editandoHora, setEditandoHora] = useState(false);
  const [novaHora, setNovaHora] = useState(viagem.hora.slice(0, 5));

  const lugaresOcupados = viagem.membros
    .filter((m) => m.usuario_ativo)
    .reduce((soma, m) => soma + (m.acompanhante ? 2 : 1), 0);

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
            {viagem.sentido} · {viagem.hora.slice(0, 5)}
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
        <div className="meta">{lugaresOcupados} pessoa(s)</div>
        {lugaresOcupados > LIMITE_ALERTA && (
          <div style={{ color: "var(--cor-alerta-borda)", fontWeight: 600, fontSize: "0.78rem", marginTop: "0.2rem" }}>
            ⚠ Mais de {LIMITE_ALERTA} pessoas nesse horario
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
        {viagem.membros.map((m) => (
          <MembroBaseCard
            key={m.id}
            viagemBaseId={viagem.id}
            grupoBaseId={viagem.grupo_base_id}
            sentido={viagem.sentido}
            hora={viagem.hora}
            membro={m}
            destinoNome={locais.find((l) => l.id === m.destino_id)?.nome}
            onRemover={onRemoverMembro}
          />
        ))}
      </SortableContext>
    </div>
  );
}
