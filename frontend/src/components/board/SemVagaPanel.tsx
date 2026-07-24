import { useState } from "react";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Local, Regiao, ViagemDiaPassageiro } from "../../api/types";
import PassageiroCard from "./PassageiroCard";

interface Props {
  passageiros: ViagemDiaPassageiro[];
  locais: Local[];
  regioes: Regiao[];
  onRemover?: (id: number) => void;
  onCancelar?: (id: number) => void;
  onRetomar?: (id: number) => void;
  onEditar: (passageiro: ViagemDiaPassageiro) => void;
}

export default function SemVagaPanel({ passageiros, locais, regioes, onRemover, onCancelar, onRetomar, onEditar }: Props) {
  const [filtroNome, setFiltroNome] = useState("");
  const [filtroRegiao, setFiltroRegiao] = useState<number | "">("");
  const [filtroDestino, setFiltroDestino] = useState<number | "">("");

  if (passageiros.length === 0) return null;

  const filtrados = passageiros.filter((p) => {
    if (filtroNome && !p.usuario.nome.toLowerCase().includes(filtroNome.toLowerCase())) return false;
    if (filtroRegiao !== "" && p.regiao_origem_id !== filtroRegiao) return false;
    if (filtroDestino !== "" && p.destino_id !== filtroDestino) return false;
    return true;
  });

  const temFiltroAtivo = filtroNome !== "" || filtroRegiao !== "" || filtroDestino !== "";

  function limparFiltros() {
    setFiltroNome("");
    setFiltroRegiao("");
    setFiltroDestino("");
  }

  return (
    <div className="painel sem-vaga-painel">
      <h3>Fora de escala ({passageiros.length})</h3>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Usuarios que nao entraram em nenhum carro na geracao (fora da Base, excecao de horario, ou frota esgotada) --
        arraste pra um carro pra alocar manualmente.
      </p>
      <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
        <input
          placeholder="Filtrar por nome"
          value={filtroNome}
          onChange={(e) => setFiltroNome(e.target.value)}
          onFocus={(e) => e.target.select()}
          style={{ flex: 1, minWidth: "8rem" }}
        />
        <select value={filtroRegiao} onChange={(e) => setFiltroRegiao(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Regiao</option>
          {regioes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nome}
            </option>
          ))}
        </select>
        <select value={filtroDestino} onChange={(e) => setFiltroDestino(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Destino</option>
          {locais.map((l) => (
            <option key={l.id} value={l.id}>
              {l.nome}
            </option>
          ))}
        </select>
        <button className="btn btn-sm" onClick={limparFiltros} disabled={!temFiltroAtivo}>
          Limpar filtros
        </button>
      </div>
      <SortableContext items={filtrados.map((p) => p.id)} strategy={verticalListSortingStrategy}>
        <div className="sem-vaga-lista">
          {filtrados.map((p) => (
            <PassageiroCard
              key={p.id}
              viagemId={-1}
              passageiro={p}
              origemLocalNome={locais.find((l) => l.id === p.origem_id)?.nome}
              destinoLocalNome={locais.find((l) => l.id === p.destino_id)?.nome}
              onRemover={onRemover}
              onCancelar={onCancelar}
              onRetomar={onRetomar}
              onEditar={onEditar}
            />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}
