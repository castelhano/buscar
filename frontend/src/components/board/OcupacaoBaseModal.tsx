import { useEffect, useMemo, useState } from "react";
import type { MouseEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana, EstruturaBase, Local } from "../../api/types";
import {
  CAPACIDADE_VIAGEM_BASE,
  montarMatrizDiaSimples,
  montarMatrizSemana,
  type CarroNaCelula,
  type CelulaHoraCarro,
  type CelulaHoraDiaSemana,
  type ViagemResumo,
} from "../../utils/ocupacao";

interface Props {
  diaSemanaInicial: DiaSemana;
  locais: Local[];
  onFechar: () => void;
}

interface GrupoPopover {
  titulo: string;
  viagens: ViagemResumo[];
}

interface PopoverState {
  x: number;
  y: number;
  titulo: string;
  grupos: GrupoPopover[];
}

function formatarHoraCurta(hora: string): string {
  return hora.slice(0, 5).replace(":", "h");
}

function percentual(parte: number, total: number): string {
  if (total <= 0) return "–";
  return `${Math.round((parte / total) * 100)}%`;
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

  function abrirPopover(e: MouseEvent<HTMLElement>, titulo: string, grupos: GrupoPopover[]) {
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({ x: rect.left, y: rect.bottom + 4, titulo, grupos });
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

  const matrizManha = useMemo(() => {
    if (escopo !== "dia") return null;
    const dados = diasComDados.find((d) => d.dia === diaSelecionado);
    return dados ? montarMatrizDiaSimples(dados.estrutura.grupos, "Manha") : null;
  }, [escopo, diasComDados, diaSelecionado]);

  const matrizTarde = useMemo(() => {
    if (escopo !== "dia") return null;
    const dados = diasComDados.find((d) => d.dia === diaSelecionado);
    return dados ? montarMatrizDiaSimples(dados.estrutura.grupos, "Tarde") : null;
  }, [escopo, diasComDados, diaSelecionado]);

  const matrizSemana = useMemo(() => {
    if (escopo !== "semana") return null;
    return montarMatrizSemana(diasComDados.map(({ dia, estrutura }) => ({ dia, grupos: estrutura.grupos })));
  }, [escopo, diasComDados]);

  function labelCarroNoDia(dia: DiaSemana, grupoId: number): string {
    const dados = diasComDados.find((d) => d.dia === dia);
    const indice = dados?.estrutura.grupos.findIndex((g) => g.id === grupoId) ?? -1;
    return `Carro ${indice + 1}`;
  }

  function gruposPopoverCarro(celula: CelulaHoraCarro): GrupoPopover[] {
    return [{ titulo: "", viagens: celula.viagens }];
  }

  function gruposPopoverSemana(dia: DiaSemana, celula: CelulaHoraDiaSemana): GrupoPopover[] {
    return celula.porCarro.map((c: CarroNaCelula) => ({ titulo: labelCarroNoDia(dia, c.grupoId), viagens: c.viagens }));
  }

  const semVazio =
    escopo === "dia"
      ? (matrizManha?.totalCarros ?? 0) === 0 && (matrizTarde?.totalCarros ?? 0) === 0
      : diasComDados.length === 0;

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
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>

        <div className="ocupacao-legenda">
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-livre" />
            Com vaga
          </span>
          <span className="ocupacao-legenda-item">
            <span className="ocupacao-legenda-swatch ocupacao-swatch-lotado" />
            Lotado
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

        {!estruturasQuery.isLoading && semVazio && (
          <p className="aviso-discreto">Nenhum carro cadastrado no molde base para essa selecao.</p>
        )}

        {escopo === "dia" &&
          [
            { titulo: "Manha", matriz: matrizManha },
            { titulo: "Tarde", matriz: matrizTarde },
          ].map(
            ({ titulo, matriz }) =>
              matriz &&
              matriz.totalCarros > 0 && (
                <div key={titulo} className="ocupacao-matriz-wrap" style={{ marginTop: "0.6rem" }}>
                  <div style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: "0.2rem" }}>{titulo}</div>
                  <table className="ocupacao-tabela">
                    <thead>
                      <tr>
                        <th className="ocupacao-th-hora">Horario</th>
                        {Array.from({ length: matriz.totalCarros }, (_, i) => (
                          <th key={i}>{String(i + 1).padStart(2, "0")}</th>
                        ))}
                        <th className="ocupacao-col-total">Total</th>
                        <th className="ocupacao-col-percentual">%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {matriz.linhas.map((linha) => (
                        <tr key={linha.hora}>
                          <td className="ocupacao-td-hora">{formatarHoraCurta(linha.hora)}</td>
                          {linha.porCarro.map((celula, indiceCarro) =>
                            celula ? (
                              <td key={indiceCarro}>
                                <button
                                  type="button"
                                  className={`ocupacao-celula ocupacao-${celula.status}`}
                                  onClick={(e) =>
                                    abrirPopover(
                                      e,
                                      `Carro ${indiceCarro + 1} · ${formatarHoraCurta(linha.hora)}`,
                                      gruposPopoverCarro(celula),
                                    )
                                  }
                                >
                                  {celula.ocupados}
                                </button>
                              </td>
                            ) : (
                              <td key={indiceCarro}>
                                <div className="ocupacao-celula ocupacao-vazia">–</div>
                              </td>
                            ),
                          )}
                          <td className="ocupacao-col-total">{linha.totalOcupados}</td>
                          <td className="ocupacao-col-percentual">{percentual(linha.totalOcupados, matriz.totalGeral)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="ocupacao-linha-total">
                        <td className="ocupacao-td-hora">Total</td>
                        {matriz.totalPorCarro.map((total, indice) => (
                          <td key={indice} className="ocupacao-col-total">
                            {total}
                          </td>
                        ))}
                        <td className="ocupacao-col-total">{matriz.totalGeral}</td>
                        <td className="ocupacao-col-percentual"></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ),
          )}

        {escopo === "semana" && matrizSemana && matrizSemana.dias.length > 0 && (
          <div className="ocupacao-matriz-wrap">
            <table className="ocupacao-tabela">
              <thead>
                <tr>
                  <th className="ocupacao-th-hora">Horario</th>
                  {matrizSemana.dias.map((dia) => (
                    <th key={dia}>{DIAS_SEMANA_LABEL[dia]}</th>
                  ))}
                  <th className="ocupacao-col-total">Total</th>
                  <th className="ocupacao-col-percentual">%</th>
                </tr>
              </thead>
              <tbody>
                {matrizSemana.linhas.map((linha) => (
                  <tr key={linha.hora}>
                    <td className="ocupacao-td-hora">{formatarHoraCurta(linha.hora)}</td>
                    {linha.porDia.map((celula, indiceDia) =>
                      celula ? (
                        <td key={indiceDia}>
                          <button
                            type="button"
                            className={`ocupacao-celula ocupacao-${celula.status}`}
                            onClick={(e) =>
                              abrirPopover(
                                e,
                                `${DIAS_SEMANA_LABEL[matrizSemana.dias[indiceDia]]} · ${formatarHoraCurta(linha.hora)}`,
                                gruposPopoverSemana(matrizSemana.dias[indiceDia], celula),
                              )
                            }
                          >
                            {celula.ocupados}/{celula.capacidade}
                          </button>
                        </td>
                      ) : (
                        <td key={indiceDia}>
                          <div className="ocupacao-celula ocupacao-vazia">–</div>
                        </td>
                      ),
                    )}
                    <td className="ocupacao-col-total">
                      {linha.totalOcupados}/{linha.totalCapacidade}
                    </td>
                    <td className="ocupacao-col-percentual">{percentual(linha.totalOcupados, linha.totalCapacidade)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="ocupacao-linha-total">
                  <td className="ocupacao-td-hora">Total</td>
                  {matrizSemana.totalPorDia.map((total, indice) => (
                    <td key={indice} className="ocupacao-col-total">
                      {total.ocupados}/{total.capacidade}
                    </td>
                  ))}
                  <td className="ocupacao-col-total">
                    {matrizSemana.totalGeral.ocupados}/{matrizSemana.totalGeral.capacidade}
                  </td>
                  <td className="ocupacao-col-percentual">
                    {percentual(matrizSemana.totalGeral.ocupados, matrizSemana.totalGeral.capacidade)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {popover && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 19 }}
            onClick={(e) => {
              e.stopPropagation();
              setPopover(null);
            }}
          />
          <div className="ocupacao-tooltip" style={{ top: popover.y, left: popover.x }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontWeight: 600, marginBottom: "0.3rem" }}>{popover.titulo}</div>
            {popover.grupos.every((g) => g.viagens.every((v) => v.membros.length === 0)) ? (
              <div className="meta">Sem passageiros</div>
            ) : (
              popover.grupos.map((grupo, indiceGrupo) => (
                <div key={indiceGrupo} style={{ marginBottom: indiceGrupo < popover.grupos.length - 1 ? "0.4rem" : 0 }}>
                  {grupo.titulo && <div style={{ fontWeight: 600, fontSize: "0.75rem", marginBottom: "0.15rem" }}>{grupo.titulo}</div>}
                  <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                    {grupo.viagens.flatMap((v) =>
                      v.membros.map((m) => (
                        <li
                          key={m.id}
                          style={{
                            opacity: m.usuario_ativo && m.atendimento_ativo ? 1 : 0.55,
                            textDecoration: m.usuario_ativo && m.atendimento_ativo ? "none" : "line-through",
                          }}
                        >
                          {m.usuario_abbr || m.usuario_nome} · {nomeLocal(m.destino_id)}
                          {m.acompanhante ? " (+1 acomp.)" : ""}
                        </li>
                      )),
                    )}
                  </ul>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
