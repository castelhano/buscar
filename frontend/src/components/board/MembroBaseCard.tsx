import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { MembroBase, Sentido } from "../../api/types";

interface Props {
  viagemBaseId: number;
  grupoBaseId: number;
  sentido: Sentido;
  hora: string;
  membro: MembroBase;
  destinoNome?: string;
  onRemover: (membroId: number) => void;
}

export default function MembroBaseCard({ viagemBaseId, grupoBaseId, sentido, hora, membro, destinoNome, onRemover }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `membro-${membro.id}`,
    data: { tipo: "membro-base", agendaId: membro.agenda_id, viagemBaseId, grupoBaseId, sentido, hora },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className={`passageiro-card ${membro.acompanhante ? "com-acompanhante" : ""}`} {...attributes} {...listeners}>
      <button
        className="remover"
        title="Tirar do carro (volta pra nao classificados)"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          onRemover(membro.id);
        }}
      >
        ✕
      </button>
      <div className="linha-1">
        <span>{membro.usuario_abbr || membro.usuario_nome}</span>
      </div>
      {membro.acompanhante && (
        <div className="tag-acompanhante" title="Usuario leva acompanhante: ocupa 2 lugares no veiculo">
          Com acompanhante · 2 lugares
        </div>
      )}
      <div className="linha-2 linha-origem-destino">
        {sentido === "Retorno" ? (
          <>
            <span title={destinoNome}>{membro.destino_id ? destinoNome ?? "destino cadastrado" : "-"}</span>
            <span title={membro.origem ?? undefined}>{membro.origem ?? "-"}</span>
          </>
        ) : (
          <>
            <span title={membro.origem ?? undefined}>{membro.origem ?? "-"}</span>
            <span title={destinoNome}>{membro.destino_id ? destinoNome ?? "destino cadastrado" : "-"}</span>
          </>
        )}
      </div>
    </div>
  );
}
