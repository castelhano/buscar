import { useState } from "react";
import { useDraggable } from "@dnd-kit/core";
import type { Local, NaoClassificadoBase, Regiao } from "../../api/types";
import { rotuloPonto, rotuloTrecho } from "../../api/types";
import { rotuloIdade } from "../../utils/data";
import { corGrupoFamiliar } from "./coresGrupoFamiliar";

function MembroNaoClassificadoCard({
  membro,
  origemLocalNome,
  destinoLocalNome,
}: {
  membro: NaoClassificadoBase;
  origemLocalNome?: string;
  destinoLocalNome?: string;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `nc-${membro.agenda_trecho_id}`,
    data: { tipo: "nao-classificado", agendaTrechoId: membro.agenda_trecho_id, hora: membro.hora },
  });
  const style = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="passageiro-card" {...attributes} {...listeners}>
      <div className="linha-1">
        <span>
          {membro.usuario_grupo_familiar_id !== null && (
            <span
              className="dot-grupo-familiar"
              title={`Grupo familiar: ${membro.usuario_grupo_familiar_nome ?? ""}`}
              style={{ background: corGrupoFamiliar(membro.usuario_grupo_familiar_id) }}
            />
          )}
          {membro.usuario_abbr || membro.usuario_nome}{" "}
          <span style={{ color: "var(--cor-texto-suave)" }}>{rotuloIdade(membro.usuario_data_nascimento)}</span>
        </span>
        <span>
          {rotuloTrecho(membro.ordem_trecho)} {membro.hora.slice(0, 5)}
        </span>
      </div>
      {membro.acompanhante && (
        <div className="tag-acompanhante" title="Usuario leva acompanhante: ocupa 2 lugares no veiculo">
          Com acompanhante · 2 lugares
        </div>
      )}
      <div className="linha-2 linha-origem-destino">
        <span>
          {rotuloPonto(membro.origem_tipo, origemLocalNome, membro.origem_texto, membro.usuario_abbr, membro.usuario_nome)}
        </span>
        <span>
          {rotuloPonto(membro.destino_tipo, destinoLocalNome, membro.destino_texto, membro.usuario_abbr, membro.usuario_nome)}
        </span>
      </div>
    </div>
  );
}

interface Props {
  membros: NaoClassificadoBase[];
  locais: Local[];
  regioes: Regiao[];
}

export default function NaoClassificadosBasePanel({ membros, locais, regioes }: Props) {
  const [filtroNome, setFiltroNome] = useState("");
  const [filtroRegiao, setFiltroRegiao] = useState<number | "">("");
  const [filtroDestino, setFiltroDestino] = useState<number | "">("");

  const filtrados = membros.filter((m) => {
    if (filtroNome && !m.usuario_nome.toLowerCase().includes(filtroNome.toLowerCase())) return false;
    if (filtroRegiao !== "" && m.regiao_origem_id !== filtroRegiao) return false;
    if (filtroDestino !== "" && m.destino_id !== filtroDestino) return false;
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
      <h3>Nao classificados ({membros.length})</h3>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Usuarios sem carro definido na Base pra esse trecho -- arraste pra dentro de um carro.
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
      <div className="sem-vaga-lista">
        {filtrados.map((m) => (
          <MembroNaoClassificadoCard
            key={m.agenda_trecho_id}
            membro={m}
            origemLocalNome={locais.find((l) => l.id === m.origem_id)?.nome}
            destinoLocalNome={locais.find((l) => l.id === m.destino_id)?.nome}
          />
        ))}
      </div>
    </div>
  );
}
