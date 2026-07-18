import type { GrupoRevezamento } from "../../api/types";
import { corRevezamento } from "./coresRevezamento";

interface Props {
  gruposRevezamento: { grupo: GrupoRevezamento; numeroGrupo: number }[];
  carrosSelecionadosCount: number;
  onAbrirModalCondutores: (grupoRevezamentoId: number) => void;
  onRemoverGrupo: (grupoRevezamentoId: number) => void;
  onGirarGrupo: (grupoRevezamentoId: number) => void;
  onCriarGrupo: () => void;
  onAdicionarAoGrupo: (grupoRevezamentoId: number) => void;
  onLimparSelecao: () => void;
}

export default function GruposRevezamentoBar({
  gruposRevezamento,
  carrosSelecionadosCount,
  onAbrirModalCondutores,
  onRemoverGrupo,
  onGirarGrupo,
  onCriarGrupo,
  onAdicionarAoGrupo,
  onLimparSelecao,
}: Props) {
  return (
    <div style={{ marginBottom: "0.6rem" }}>
      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center" }}>
        {gruposRevezamento.map(({ grupo, numeroGrupo }) => {
          const cor = corRevezamento(grupo.id);
          const configIncompleta = grupo.carros.length !== grupo.condutores.length;
          return (
            <span
              key={grupo.id}
              className="tag"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                border: `1px solid ${cor}`,
                color: cor,
                cursor: "pointer",
              }}
              onClick={() => onAbrirModalCondutores(grupo.id)}
              title="Clique pra editar os condutores desse grupo"
            >
              Grupo {numeroGrupo} ({grupo.carros.length} carro{grupo.carros.length === 1 ? "" : "s"},{" "}
              {grupo.condutores.length} condutor{grupo.condutores.length === 1 ? "" : "es"})
              {configIncompleta && <span title="Numero de carros e condutores nao bate -- rodizio desativado"> ⚠</span>}
              <button
                className="btn btn-sm"
                style={{ padding: "0 0.3rem", fontSize: "0.7rem" }}
                title={`Deslocamento atual: ${grupo.deslocamento}. Clique pra avancar o rodizio desse grupo em 1 posicao (mesmo ajuste que a geracao faz sozinha) -- usa isso pra escalonar o ponto de partida de cada dia da semana`}
                disabled={grupo.condutores.length === 0}
                onClick={(e) => {
                  e.stopPropagation();
                  onGirarGrupo(grupo.id);
                }}
              >
                ↻ {grupo.deslocamento}
              </button>
              <button
                className="btn btn-sm"
                style={{ padding: "0 0.3rem", fontSize: "0.7rem" }}
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoverGrupo(grupo.id);
                }}
              >
                ×
              </button>
            </span>
          );
        })}
      </div>

      {carrosSelecionadosCount > 0 && (
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center", marginTop: "0.4rem" }}>
          <span className="meta">{carrosSelecionadosCount} carro(s) selecionado(s):</span>
          <button className="btn btn-sm btn-primario" onClick={onCriarGrupo}>
            Criar grupo
          </button>
          {gruposRevezamento.map(({ grupo, numeroGrupo }) => (
            <button key={grupo.id} className="btn btn-sm" onClick={() => onAdicionarAoGrupo(grupo.id)}>
              + Grupo {numeroGrupo}
            </button>
          ))}
          <button className="btn btn-sm" onClick={onLimparSelecao}>
            Cancelar seleção
          </button>
        </div>
      )}
    </div>
  );
}
