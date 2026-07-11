import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Local, ViagemDiaPassageiro } from "../../api/types";
import PassageiroCard from "./PassageiroCard";

interface Props {
  passageiros: ViagemDiaPassageiro[];
  locais: Local[];
  onRemover: (id: number) => void;
  onCancelar: (id: number) => void;
  onEditar: (passageiro: ViagemDiaPassageiro) => void;
}

export default function SemVagaPanel({ passageiros, locais, onRemover, onCancelar, onEditar }: Props) {
  if (passageiros.length === 0) return null;

  return (
    <div className="painel">
      <h3>Sem vaga ({passageiros.length})</h3>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Usuarios que nao couberam em nenhum carro na geracao (frota esgotada) -- arraste pra um carro pra alocar
        manualmente.
      </p>
      <SortableContext items={passageiros.map((p) => p.id)} strategy={verticalListSortingStrategy}>
        <div className="sem-vaga-lista">
          {passageiros.map((p) => (
            <PassageiroCard
              key={p.id}
              viagemId={-1}
              passageiro={p}
              destinoNome={locais.find((l) => l.id === p.destino_id)?.nome}
              onRemover={onRemover}
              onCancelar={onCancelar}
              onEditar={onEditar}
            />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}
