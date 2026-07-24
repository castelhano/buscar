import { useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import type { GrupoBase, GrupoRevezamento, Local, Regiao, ViagemBase } from "../../api/types";
import ViagemBaseBlock from "./ViagemBaseBlock";
import { corRevezamento } from "./coresRevezamento";

interface Props {
  grupo: GrupoBase;
  viagensExibir: ViagemBase[];
  indice: number;
  periodo: "Manha" | "Tarde";
  locais: Local[];
  regioes: Regiao[];
  revezamento: { grupo: GrupoRevezamento; numeroGrupo: number; ordem: number } | null;
  selecionadoPraRevezamento: boolean;
  onToggleSelecaoRevezamento: (grupoId: number, marcado: boolean) => void;
  onSairDoGrupoRevezamento: (grupoRevezamentoId: number) => void;
  onNovaViagem: (grupoId: number, hora: string) => void;
  onRemoverGrupo: (grupoId: number) => void;
  onRemoverViagem: (viagemId: number) => void;
  onRemoverMembro: (membroId: number) => void;
  onAlterarHoraViagem: (viagemId: number, hora: string) => void;
  gruposFamiliaresDesvinculados: Set<number>;
  onToggleDesvincularGrupoFamiliar: (grupoFamiliarId: number) => void;
}

export default function CarroBaseCard({
  grupo,
  viagensExibir,
  indice,
  periodo,
  locais,
  regioes,
  revezamento,
  selecionadoPraRevezamento,
  onToggleSelecaoRevezamento,
  onSairDoGrupoRevezamento,
  onNovaViagem,
  onRemoverGrupo,
  onRemoverViagem,
  onRemoverMembro,
  onAlterarHoraViagem,
  gruposFamiliaresDesvinculados,
  onToggleDesvincularGrupoFamiliar,
}: Props) {
  const [novaViagem, setNovaViagem] = useState(false);
  const [hora, setHora] = useState(periodo === "Tarde" ? "14:00" : "06:00");

  const { setNodeRef, isOver } = useDroppable({
    id: `grupo-base-${grupo.id}`,
    data: { tipo: "grupo-base", grupoBaseId: grupo.id },
  });

  const regiaoIds = grupo.viagens.flatMap((v) => v.membros.map((m) => m.regiao_origem_id ?? m.regiao_destino_id));
  const regiaoNomes = [...new Set(regiaoIds)].map((id) => regioes.find((r) => r.id === id)?.nome ?? "?");
  const carroVazio = grupo.viagens.every((v) => v.membros.length === 0);

  const n = revezamento?.grupo.condutores.length ?? 0;
  const proximoCondutor =
    revezamento && n > 0
      ? revezamento.grupo.condutores[(((revezamento.ordem - revezamento.grupo.deslocamento) % n) + n) % n]
      : null;
  const configIncompleta = revezamento != null && revezamento.grupo.carros.length !== revezamento.grupo.condutores.length;
  const cor = revezamento ? corRevezamento(revezamento.grupo.id) : undefined;

  return (
    <div
      ref={setNodeRef}
      className="carro-card"
      style={{
        outline: isOver ? "2px solid var(--cor-primaria)" : "none",
        borderLeft: cor ? `4px solid ${cor}` : undefined,
      }}
    >
      <div className="carro-card-topo">
        <div className="titulo">{grupo.rotulo ?? `Carro ${indice + 1}`}</div>
        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
          {regiaoNomes.length > 0 && (
            <span className="tag tag-regiao" title="Regioes dos passageiros">
              {regiaoNomes.join(" · ")}
            </span>
          )}
          {revezamento == null && (
            <input
              type="checkbox"
              checked={selecionadoPraRevezamento}
              onChange={(e) => onToggleSelecaoRevezamento(grupo.id, e.target.checked)}
              title="Selecionar pra criar ou entrar num grupo de revezamento"
            />
          )}
        </div>
      </div>

      {revezamento && (
        <div className="meta" style={{ fontSize: "0.75rem", color: cor }}>
          Grupo {revezamento.numeroGrupo} · vaga {revezamento.ordem + 1}
          {configIncompleta ? (
            <span title="Numero de carros e condutores do grupo de revezamento nao bate -- rodizio desativado ate corrigir">
              {" "}
              · config. incompleta
            </span>
          ) : (
            proximoCondutor && <span> · próximo: {proximoCondutor.apelido || proximoCondutor.nome}</span>
          )}
          {" · "}
          <button
            className="btn btn-sm"
            style={{ fontSize: "0.7rem", padding: "0.1rem 0.4rem" }}
            onClick={() => onSairDoGrupoRevezamento(revezamento.grupo.id)}
          >
            sair do grupo
          </button>
        </div>
      )}

      {viagensExibir.map((viagem) => (
        <ViagemBaseBlock
          key={viagem.id}
          viagem={viagem}
          locais={locais}
          onRemoverViagem={onRemoverViagem}
          onRemoverMembro={onRemoverMembro}
          onAlterarHora={onAlterarHoraViagem}
          gruposFamiliaresDesvinculados={gruposFamiliaresDesvinculados}
          onToggleDesvincularGrupoFamiliar={onToggleDesvincularGrupoFamiliar}
        />
      ))}

      {viagensExibir.length < grupo.viagens.length && (
        <div className="meta" style={{ fontSize: "0.75rem" }}>
          + {grupo.viagens.length - viagensExibir.length} viagem(ns) no outro periodo
        </div>
      )}

      {novaViagem ? (
        <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem", alignItems: "center", flexWrap: "wrap" }}>
          <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
          <button
            className="btn btn-sm btn-primario"
            onClick={() => {
              onNovaViagem(grupo.id, hora);
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
