import { useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import type { GrupoBase, Local, Regiao, Sentido } from "../../api/types";
import ViagemBaseBlock from "./ViagemBaseBlock";

interface Props {
  grupo: GrupoBase;
  indice: number;
  locais: Local[];
  regioes: Regiao[];
  onNovaViagem: (grupoId: number, sentido: Sentido, hora: string) => void;
  onRemoverGrupo: (grupoId: number) => void;
  onRemoverViagem: (viagemId: number) => void;
  onRemoverMembro: (membroId: number) => void;
}

export default function CarroBaseCard({
  grupo,
  indice,
  locais,
  regioes,
  onNovaViagem,
  onRemoverGrupo,
  onRemoverViagem,
  onRemoverMembro,
}: Props) {
  const [novaViagem, setNovaViagem] = useState(false);
  const [sentido, setSentido] = useState<Sentido>("Ida");
  const [hora, setHora] = useState("06:00");

  const { setNodeRef, isOver } = useDroppable({
    id: `grupo-base-${grupo.id}`,
    data: { tipo: "grupo-base", grupoBaseId: grupo.id },
  });

  const regiaoIds = grupo.viagens.flatMap((v) =>
    v.membros.map((m) => (v.sentido === "Retorno" && m.regiao_destino_id != null ? m.regiao_destino_id : m.regiao_origem_id)),
  );
  const regiaoNomes = [...new Set(regiaoIds)].map((id) => regioes.find((r) => r.id === id)?.nome ?? "?");
  const carroVazio = grupo.viagens.every((v) => v.membros.length === 0);

  return (
    <div ref={setNodeRef} className="carro-card" style={{ outline: isOver ? "2px solid var(--cor-primaria)" : "none" }}>
      <div className="carro-card-topo">
        <div className="titulo">{grupo.rotulo ?? `Carro ${indice + 1}`}</div>
        {regiaoNomes.length > 0 && (
          <span className="tag tag-regiao" title="Regioes dos passageiros">
            {regiaoNomes.join(" · ")}
          </span>
        )}
      </div>

      {grupo.viagens.map((viagem) => (
        <ViagemBaseBlock key={viagem.id} viagem={viagem} locais={locais} onRemoverViagem={onRemoverViagem} onRemoverMembro={onRemoverMembro} />
      ))}

      {novaViagem ? (
        <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem", alignItems: "center", flexWrap: "wrap" }}>
          <select value={sentido} onChange={(e) => setSentido(e.target.value as Sentido)}>
            <option value="Ida">Ida</option>
            <option value="Retorno">Retorno</option>
          </select>
          <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
          <button
            className="btn btn-sm btn-primario"
            onClick={() => {
              onNovaViagem(grupo.id, sentido, hora);
              setNovaViagem(false);
            }}
          >
            Criar
          </button>
          <button className="btn btn-sm" onClick={() => setNovaViagem(false)}>
            Cancelar
          </button>
        </div>
      ) : (
        <button className="carro-card-add" onClick={() => setNovaViagem(true)}>
          + nova viagem
        </button>
      )}

      {carroVazio && (
        <div style={{ marginTop: "0.4rem" }}>
          <button className="btn btn-sm btn-perigo" onClick={() => onRemoverGrupo(grupo.id)}>
            Remover carro
          </button>
        </div>
      )}
    </div>
  );
}
