import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana, EstruturaBase, Local, Sentido } from "../../api/types";
import { CAPACIDADE_VIAGEM_BASE, montarColunaDia } from "../../utils/ocupacao";
import type { CelulaOcupacao, ColunaDiaOcupacao } from "../../utils/ocupacao";

interface Props {
  diaSemanaInicial: DiaSemana;
  locais: Local[];
  onFechar: () => void;
}

interface PopoverState {
  x: number;
  y: number;
  titulo: string;
  celula: CelulaOcupacao;
}

export default function OcupacaoBaseModal({ diaSemanaInicial, locais, onFechar }: Props) {
  useLockBodyScroll();
  const [escopo, setEscopo] = useState<"dia" | "semana">("dia");
  const [diaSelecionado, setDiaSelecionado] = useState<DiaSemana>(diaSemanaInicial);
  const [popover, setPopover] = useState<PopoverState | null>(null);
  const [erroExportar, setErroExportar] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);

  const diasConsultados = escopo === "dia" ? [diaSelecionado] : DIAS_SEMANA;

  const estruturasQuery = useQuery({
    queryKey: ["base-ocupacao", diasConsultados.join(",")],
    queryFn: async () => {
      const resultados = await Promise.all(diasConsultados.map((dia) => api.get<EstruturaBase>(`/base/${dia}`)));
      return diasConsultados.map((dia, indice) => ({ dia, estrutura: resultados[indice] }));
    },
  });

  useEffect(() => {
    function fechar(e: KeyboardEvent) {
      if (e.key === "Escape") setPopover(null);
    }
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, []);

  function nomeLocal(id: number | null) {
    return id ? locais.find((l) => l.id === id)?.nome ?? "destino cadastrado" : "-";
  }

  function abrirPopover(e: MouseEvent<HTMLElement>, titulo: string, celula: CelulaOcupacao) {
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({ x: rect.left, y: rect.bottom + 4, titulo, celula });
  }

  function exportarPdf() {
    setErroExportar(null);
    setExportando(true);
    const params = escopo === "semana" ? { semana: true } : { dia_semana: diaSelecionado };
    api
      .download("/base/ocupacao/pdf", params)
      .catch((e: unknown) => setErroExportar(e instanceof ApiError ? String(e.detail) : "Erro ao exportar PDF"))
      .finally(() => setExportando(false));
  }

  const diasComDados = (estruturasQuery.data ?? []).filter(({ estrutura }) => estrutura.grupos.length > 0);
  const totalCarros = Math.max(0, ...diasComDados.map(({ estrutura }) => estrutura.grupos.length));
  const colunas: ColunaDiaOcupacao[] = diasComDados.map(({ dia, estrutura }) => montarColunaDia(dia, estrutura.grupos, totalCarros));

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" style={{ width: "min(96vw, 1150px)" }} onClick={(e) => e.stopPropagation()}>
        <h3>Ocupacao por carro / horario</h3>
        <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
          Perfil de ocupacao do molde semanal, assumindo {CAPACIDADE_VIAGEM_BASE} lugares por viagem. Clique numa celula
          para ver os passageiros daquela viagem.
        </p>

        {erroExportar && (
          <div className="erro-box" onClick={() => setErroExportar(null)} style={{ cursor: "pointer" }}>
            {erroExportar} (clique para fechar)
          </div>
        )}

        <div className="linha-toolbar">
          <div className="btn-group">
            <button className={`btn btn-sm ${escopo === "dia" ? "btn-group-ativo" : ""}`} onClick={() => setEscopo("dia")}>
              Somente um dia
            </button>
            <button className={`btn btn-sm ${escopo === "semana" ? "btn-group-ativo" : ""}`} onClick={() => setEscopo("semana")}>
              Semana toda
            </button>
          </div>
          {escopo === "dia" && (
            <div className="campo">
              <select value={diaSelecionado} onChange={(e) => setDiaSelecionado(e.target.value as DiaSemana)}>
                {DIAS_SEMANA.map((dia) => (
                  <option key={dia} value={dia}>
                    {DIAS_SEMANA_LABEL[dia]}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button className="btn btn-primario" style={{ marginLeft: "auto" }} onClick={exportarPdf} disabled={exportando}>
            {exportando ? "Exportando..." : "Exportar PDF"}
          </button>
        </div>

        <div className="ocupacao-legenda">
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-livre" />
            Com vaga
          </span>
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-lotado" />
            Lotado ({CAPACIDADE_VIAGEM_BASE}/{CAPACIDADE_VIAGEM_BASE})
          </span>
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-acima" />
            Acima da capacidade
          </span>
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-vazia" />
            Sem viagem
          </span>
        </div>

        {estruturasQuery.isLoading && <p>Carregando...</p>}
        {estruturasQuery.error && <div className="erro-box">Erro ao carregar a ocupacao.</div>}

        {!estruturasQuery.isLoading && colunas.length === 0 && (
          <p className="aviso-discreto">Nenhum carro cadastrado no molde base para essa selecao.</p>
        )}

        {colunas.length > 0 && (
          <div className="ocupacao-matriz-wrap">
            <table className="ocupacao-tabela">
              <thead>
                {escopo === "semana" && (
                  <tr>
                    <th className="ocupacao-th-carro" rowSpan={2}>
                      Carro
                    </th>
                    {colunas.map((coluna) => (
                      <th key={coluna.diaSemana} colSpan={2}>
                        {DIAS_SEMANA_LABEL[coluna.diaSemana]}
                      </th>
                    ))}
                  </tr>
                )}
                <tr>
                  {escopo === "dia" && <th className="ocupacao-th-carro">Carro</th>}
                  {colunas.flatMap((coluna) => [
                    <th key={`${coluna.diaSemana}-ida`}>Ida</th>,
                    <th key={`${coluna.diaSemana}-volta`}>Volta</th>,
                  ])}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: totalCarros }, (_, indiceCarro) => (
                  <tr key={indiceCarro}>
                    <td className="ocupacao-td-carro">Carro {indiceCarro + 1}</td>
                    {colunas.map((coluna) => {
                      const carro = coluna.carros[indiceCarro];
                      return (
                        <CelulasCarro
                          key={coluna.diaSemana}
                          coluna={coluna}
                          carroLabel={`Carro ${indiceCarro + 1}`}
                          ida={carro.ida}
                          volta={carro.volta}
                          onAbrirPopover={abrirPopover}
                        />
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>

      {popover && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 19 }} onClick={() => setPopover(null)} />
          <div className="ocupacao-tooltip" style={{ top: popover.y, left: popover.x }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontWeight: 600, marginBottom: "0.3rem" }}>{popover.titulo}</div>
            {popover.celula.membros.length === 0 ? (
              <div className="meta">Sem passageiros</div>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                {popover.celula.membros.map((m) => (
                  <li
                    key={m.id}
                    style={{ opacity: m.usuario_ativo ? 1 : 0.55, textDecoration: m.usuario_ativo ? "none" : "line-through" }}
                  >
                    {m.usuario_abbr || m.usuario_nome} · {nomeLocal(m.destino_id)}
                    {m.acompanhante ? " (+1 acomp.)" : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function CelulasCarro({
  coluna,
  carroLabel,
  ida,
  volta,
  onAbrirPopover,
}: {
  coluna: ColunaDiaOcupacao;
  carroLabel: string;
  ida: CelulaOcupacao[];
  volta: CelulaOcupacao[];
  onAbrirPopover: (e: MouseEvent<HTMLElement>, titulo: string, celula: CelulaOcupacao) => void;
}) {
  return (
    <>
      <td>
        <ColunaCelulas
          celulas={ida}
          sentido="Ida"
          onClick={(e, celula) => onAbrirPopover(e, `${carroLabel} · ${DIAS_SEMANA_LABEL[coluna.diaSemana]} · Ida ${celula.hora.slice(0, 5)}`, celula)}
        />
      </td>
      <td>
        <ColunaCelulas
          celulas={volta}
          sentido="Retorno"
          onClick={(e, celula) =>
            onAbrirPopover(e, `${carroLabel} · ${DIAS_SEMANA_LABEL[coluna.diaSemana]} · Volta ${celula.hora.slice(0, 5)}`, celula)
          }
        />
      </td>
    </>
  );
}

function ColunaCelulas({
  celulas,
  onClick,
}: {
  celulas: CelulaOcupacao[];
  sentido: Sentido;
  onClick: (e: MouseEvent<HTMLElement>, celula: CelulaOcupacao) => void;
}) {
  if (celulas.length === 0) {
    return <div className="ocupacao-celula ocupacao-vazia">–</div>;
  }
  return (
    <div className="ocupacao-celula-container">
      {celulas.map((celula) => (
        <button
          key={celula.viagemId}
          type="button"
          className={`ocupacao-celula ocupacao-${celula.status}`}
          title={`${celula.hora.slice(0, 5)} · ${celula.ocupados} ocupado(s)`}
          onClick={(e) => onClick(e, celula)}
        >
          {celula.ocupados}
        </button>
      ))}
    </div>
  );
}
