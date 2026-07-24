import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { ViagemDiaPassageiro } from "../../api/types";
import { rotuloPonto, rotuloTrecho } from "../../api/types";
import { rotuloIdade } from "../../utils/data";

interface Props {
  viagemId: number;
  passageiro: ViagemDiaPassageiro;
  origemLocalNome?: string;
  destinoLocalNome?: string;
  onRemover?: (id: number) => void;
  onCancelar?: (id: number) => void;
  onRetomar?: (id: number) => void;
  onEditar?: (passageiro: ViagemDiaPassageiro) => void;
}

export default function PassageiroCard({
  viagemId,
  passageiro,
  origemLocalNome,
  destinoLocalNome,
  onRemover,
  onCancelar,
  onRetomar,
  onEditar,
}: Props) {
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
  if (!passageiro.fixo) classes.push("eventual");

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
      <div className="passageiro-card-conteudo">
        <div className="linha-1">
          <span>
            {passageiro.usuario.abbr || passageiro.usuario.nome}{" "}
            <span style={{ color: "var(--cor-texto-suave)" }}>{rotuloIdade(passageiro.usuario.data_nascimento)}</span>
          </span>
          <span>
            {rotuloTrecho(passageiro.ordem_trecho)} {passageiro.hora.slice(0, 5)}
          </span>
        </div>
        {passageiro.acompanhante && (
          <div className="tag-acompanhante" title="Usuario leva acompanhante: ocupa 2 lugares no veiculo">
            Com acompanhante · 2 lugares
          </div>
        )}
        {!passageiro.fixo && (
          <div className="tag-eventual" title="Atendimento eventual: inserido manualmente, nao faz parte da Base">
            Eventual
          </div>
        )}
        <div className="linha-2 linha-origem-destino">
          <span>
            {rotuloPonto(
              passageiro.origem_tipo,
              origemLocalNome,
              passageiro.origem_texto,
              passageiro.usuario.abbr,
              passageiro.usuario.nome,
            )}
          </span>
          <span>
            {rotuloPonto(
              passageiro.destino_tipo,
              destinoLocalNome,
              passageiro.destino_texto,
              passageiro.usuario.abbr,
              passageiro.usuario.nome,
            )}
          </span>
        </div>
        {passageiro.irregular && (
          <div className="linha-2" title={passageiro.motivo_irregular ?? ""} style={{ color: "var(--cor-alerta-borda)", fontWeight: 600 }}>
            ⚠ {passageiro.motivo_irregular}
          </div>
        )}
        {passageiro.status === "Em analise" && <span className="tag">Em analise</span>}
      </div>
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
      {cancelado && onRetomar && (
        <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem" }}>
          <button
            className="btn btn-sm"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              onRetomar(passageiro.id);
            }}
          >
            Retomar
          </button>
        </div>
      )}
    </div>
  );
}
