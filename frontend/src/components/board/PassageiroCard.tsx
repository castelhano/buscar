import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { ViagemDiaPassageiro } from "../../api/types";

interface Props {
  viagemId: number;
  passageiro: ViagemDiaPassageiro;
  destinoNome?: string;
  onRemover?: (id: number) => void;
  onCancelar?: (id: number) => void;
  onEditar?: (passageiro: ViagemDiaPassageiro) => void;
}

export default function PassageiroCard({ viagemId, passageiro, destinoNome, onRemover, onCancelar, onEditar }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: passageiro.id,
    data: { viagemId, passageiroId: passageiro.id },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const cancelado = passageiro.status === "Cancelado";
  const classes = ["passageiro-card"];
  if (passageiro.irregular) classes.push("irregular");
  if (cancelado) classes.push("cancelado");
  if (passageiro.acompanhante) classes.push("com-acompanhante");

  return (
    <div ref={setNodeRef} style={style} className={classes.join(" ")} {...attributes} {...listeners}>
      {onRemover && (
        <button
          className="remover"
          title="Remover do atendimento"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onRemover(passageiro.id);
          }}
        >
          ✕
        </button>
      )}
      <div className="linha-1">
        <span>{passageiro.usuario.abbr || passageiro.usuario.nome}</span>
        <span>
          {passageiro.sentido} {passageiro.hora.slice(0, 5)}
        </span>
      </div>
      {passageiro.acompanhante && (
        <div className="tag-acompanhante" title="Usuario leva acompanhante: ocupa 2 lugares no veiculo">
          Com acompanhante · 2 lugares
        </div>
      )}
      <div className="linha-2 linha-origem-destino">
        {passageiro.sentido === "Retorno" ? (
          <>
            <span title={destinoNome}>{passageiro.destino_id ? destinoNome ?? "destino cadastrado" : "-"}</span>
            <span title={passageiro.origem ?? undefined}>{passageiro.origem ?? "-"}</span>
          </>
        ) : (
          <>
            <span title={passageiro.origem ?? undefined}>{passageiro.origem ?? "-"}</span>
            <span title={destinoNome}>{passageiro.destino_id ? destinoNome ?? "destino cadastrado" : "-"}</span>
          </>
        )}
      </div>
      {passageiro.irregular && (
        <div className="linha-2" title={passageiro.motivo_irregular ?? ""} style={{ color: "var(--cor-alerta-borda)", fontWeight: 600 }}>
          ⚠ {passageiro.motivo_irregular}
        </div>
      )}
      {passageiro.status === "Em analise" && <span className="tag">Em analise</span>}
      {!cancelado && (onEditar || onCancelar) && (
        <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem" }}>
          {onEditar && (
            <button
              className="btn btn-sm"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                onEditar(passageiro);
              }}
            >
              Editar
            </button>
          )}
          {onCancelar && (
            <button
              className="btn btn-sm"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                onCancelar(passageiro.id);
              }}
            >
              Cancelar
            </button>
          )}
        </div>
      )}
    </div>
  );
}
