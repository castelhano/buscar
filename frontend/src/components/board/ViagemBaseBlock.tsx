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
}

export default function ViagemBaseBlock({ viagem, locais, onRemoverViagem, onRemoverMembro }: Props) {
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

  const lugaresOcupados = viagem.membros.reduce((soma, m) => soma + (m.acompanhante ? 2 : 1), 0);

  return (
    <div ref={setNodeRef} className="leg-block" style={{ outline: isOver ? "2px solid var(--cor-primaria)" : "none" }}>
      <div className="leg-block-header">
        <div className="horario-grupo-label">
          {viagem.sentido} · {viagem.hora.slice(0, 5)}
        </div>
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
