import { useEffect, useMemo, useState } from "react";
import type { MouseEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana, EstruturaBase, Local } from "../../api/types";
import {
  CAPACIDADE_ACOMPANHANTES_BASE,
  CAPACIDADE_USUARIOS_BASE,
  montarMatrizDiaSimples,
  montarMatrizSemana,
  type CarroNaCelula,
  type CelulaHoraCarro,
  type CelulaHoraDiaSemana,
  type StatusOcupacao,
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

function CelulaDupla({
  usuarios,
  capacidadeUsuarios,
  statusUsuarios,
  acompanhantes,
  capacidadeAcompanhantes,
  statusAcompanhantes,
  onClick,
}: {
  usuarios: number;
  capacidadeUsuarios?: number;
  statusUsuarios: StatusOcupacao;
  acompanhantes: number;
  capacidadeAcompanhantes?: number;
  statusAcompanhantes: StatusOcupacao;
  onClick: (e: MouseEvent<HTMLButtonElement>) => void;
}) {
  return (
    <button type="button" className="ocupacao-celula-dupla" onClick={onClick}>
      <span className={`ocupacao-celula-parte ocupacao-${statusUsuarios}`}>
        {usuarios}
        {capacidadeUsuarios !== undefined ? `/${capacidadeUsuarios}` : ""}
      </span>
      <span className={`ocupacao-celula-parte ocupacao-${statusAcompanhantes}`}>
        {acompanhantes}
        {capacidadeAcompanhantes !== undefined ? `/${capacidadeAcompanhantes}` : ""}
      </span>
    </button>
  );
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

  const diasComDados = (estruturasQuery.data ?? []).filter(
    ({ estrutura }) => estrutura.grupos.length > 0 || estrutura.nao_classificados.length > 0,
  );

  const matrizManha = useMemo(() => {
    if (escopo !== "dia") return null;
    const dados = diasComDados.find((d) => d.dia === diaSelecionado);
    return dados ? montarMatrizDiaSimples(dados.estrutura.grupos, "Manha", dados.estrutura.nao_classificados) : null;
  }, [escopo, diasComDados, diaSelecionado]);

  const matrizTarde = useMemo(() => {
    if (escopo !== "dia") return null;
    const dados = diasComDados.find((d) => d.dia === diaSelecionado);
    return dados ? montarMatrizDiaSimples(dados.estrutura.grupos, "Tarde", dados.estrutura.nao_classificados) : null;
  }, [escopo, diasComDados, diaSelecionado]);

  const matrizSemana = useMemo(() => {
    if (escopo !== "semana") return null;
    return montarMatrizSemana(
      diasComDados.map(({ dia, estrutura }) => ({ dia, grupos: estrutura.grupos, naoClassificados: estrutura.nao_classificados })),
    );
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

  function matrizDiaVazia(matriz: ReturnType<typeof montarMatrizDiaSimples> | null): boolean {
    if (!matriz) return true;
    return matriz.totalCarros === 0 && matriz.naoClassificados.usuarios === 0 && matriz.naoClassificados.acompanhantes === 0;
  }

  const semVazio = escopo === "dia" ? matrizDiaVazia(matrizManha) && matrizDiaVazia(matrizTarde) : diasComDados.length === 0;

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" style={{ width: "min(96vw, 1150px)" }} onClick={(e) => e.stopPropagation()}>
        <h3>Ocupacao por carro / horario</h3>
        <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
          Perfil de ocupacao do molde semanal, assumindo {CAPACIDADE_USUARIOS_BASE} usuarios + {CAPACIDADE_ACOMPANHANTES_BASE}{" "}
          acompanhantes por viagem (dois pools independentes). Clique numa celula para ver os passageiros daquela viagem. As linhas
          "Nao classificados" e "Total (todos)" no rodape somam tambem quem ja e elegivel no dia mas ainda nao foi alocado em
          nenhum carro.
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
          <span className="ocupacao-legenda-item">Cada celula: usuarios · +acompanhantes (status independente)</span>
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
              !matrizDiaVazia(matriz) && (
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
                                <CelulaDupla
                                  usuarios={celula.ocupados.usuarios}
                                  statusUsuarios={celula.statusUsuarios}
                                  acompanhantes={celula.ocupados.acompanhantes}
                                  statusAcompanhantes={celula.statusAcompanhantes}
                                  onClick={(e) =>
                                    abrirPopover(
                                      e,
                                      `Carro ${indiceCarro + 1} · ${formatarHoraCurta(linha.hora)}`,
                                      gruposPopoverCarro(celula),
                                    )
                                  }
                                />
                              </td>
                            ) : (
                              <td key={indiceCarro}>
                                <div className="ocupacao-celula ocupacao-vazia">–</div>
                              </td>
                            ),
                          )}
                          <td className="ocupacao-col-total">
                            {linha.totalOcupados.usuarios}/{linha.totalOcupados.acompanhantes}
                          </td>
                          <td className="ocupacao-col-percentual">
                            {percentual(
                              linha.totalOcupados.usuarios + linha.totalOcupados.acompanhantes,
                              matriz.totalGeral.usuarios + matriz.totalGeral.acompanhantes,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="ocupacao-linha-total">
                        <td className="ocupacao-td-hora">Alocados</td>
                        {matriz.totalPorCarro.map((total, indice) => (
                          <td key={indice} className="ocupacao-col-total">
                            {total.usuarios}/{total.acompanhantes}
                          </td>
                        ))}
                        <td className="ocupacao-col-total">
                          {matriz.totalGeral.usuarios}/{matriz.totalGeral.acompanhantes}
                        </td>
                        <td className="ocupacao-col-percentual"></td>
                      </tr>
                      <tr className="ocupacao-linha-total">
                        <td className="ocupacao-td-hora">Nao classificados</td>
                        <td colSpan={matriz.totalCarros} className="aviso-discreto" style={{ textAlign: "center" }}>
                          ainda sem carro
                        </td>
                        <td className="ocupacao-col-total">
                          {matriz.naoClassificados.usuarios}/{matriz.naoClassificados.acompanhantes}
                        </td>
                        <td className="ocupacao-col-percentual"></td>
                      </tr>
                      <tr className="ocupacao-linha-total">
                        <td className="ocupacao-td-hora">Total do periodo</td>
                        <td colSpan={matriz.totalCarros} className="aviso-discreto" style={{ textAlign: "center" }}>
                          todos os efetivos, alocados ou nao
                        </td>
                        <td className="ocupacao-col-total">
                          {matriz.totalComNaoClassificados.usuarios}/{matriz.totalComNaoClassificados.acompanhantes}
                        </td>
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
                          <CelulaDupla
                            usuarios={celula.ocupados.usuarios}
                            capacidadeUsuarios={celula.capacidade.usuarios}
                            statusUsuarios={celula.statusUsuarios}
                            acompanhantes={celula.ocupados.acompanhantes}
                            capacidadeAcompanhantes={celula.capacidade.acompanhantes}
                            statusAcompanhantes={celula.statusAcompanhantes}
                            onClick={(e) =>
                              abrirPopover(
                                e,
                                `${DIAS_SEMANA_LABEL[matrizSemana.dias[indiceDia]]} · ${formatarHoraCurta(linha.hora)}`,
                                gruposPopoverSemana(matrizSemana.dias[indiceDia], celula),
                              )
                            }
                          />
                        </td>
                      ) : (
                        <td key={indiceDia}>
                          <div className="ocupacao-celula ocupacao-vazia">–</div>
                        </td>
                      ),
                    )}
                    <td className="ocupacao-col-total">
                      {linha.totalOcupados.usuarios}/{linha.totalCapacidade.usuarios} | {linha.totalOcupados.acompanhantes}/
                      {linha.totalCapacidade.acompanhantes}
                    </td>
                    <td className="ocupacao-col-percentual">
                      {percentual(
                        linha.totalOcupados.usuarios + linha.totalOcupados.acompanhantes,
                        linha.totalCapacidade.usuarios + linha.totalCapacidade.acompanhantes,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="ocupacao-linha-total">
                  <td className="ocupacao-td-hora">Alocados</td>
                  {matrizSemana.totalPorDia.map((total, indice) => (
                    <td key={indice} className="ocupacao-col-total">
                      {total.ocupados.usuarios}/{total.capacidade.usuarios} | {total.ocupados.acompanhantes}/
                      {total.capacidade.acompanhantes}
                    </td>
                  ))}
                  <td className="ocupacao-col-total">
                    {matrizSemana.totalGeral.ocupados.usuarios}/{matrizSemana.totalGeral.capacidade.usuarios} |{" "}
                    {matrizSemana.totalGeral.ocupados.acompanhantes}/{matrizSemana.totalGeral.capacidade.acompanhantes}
                  </td>
                  <td className="ocupacao-col-percentual">
                    {percentual(
                      matrizSemana.totalGeral.ocupados.usuarios + matrizSemana.totalGeral.ocupados.acompanhantes,
                      matrizSemana.totalGeral.capacidade.usuarios + matrizSemana.totalGeral.capacidade.acompanhantes,
                    )}
                  </td>
                </tr>
                <tr className="ocupacao-linha-total">
                  <td className="ocupacao-td-hora">Nao classificados</td>
                  {matrizSemana.naoClassificadosPorDia.map((total, indice) => (
                    <td key={indice} className="ocupacao-col-total">
                      {total.usuarios}/{total.acompanhantes}
                    </td>
                  ))}
                  <td className="ocupacao-col-total">
                    {matrizSemana.naoClassificadosGeral.usuarios}/{matrizSemana.naoClassificadosGeral.acompanhantes}
                  </td>
                  <td className="ocupacao-col-percentual"></td>
                </tr>
                <tr className="ocupacao-linha-total">
                  <td className="ocupacao-td-hora">Total (todos)</td>
                  {matrizSemana.totalPorDia.map((total, indice) => {
                    const naoClass = matrizSemana.naoClassificadosPorDia[indice];
                    return (
                      <td key={indice} className="ocupacao-col-total">
                        {total.ocupados.usuarios + naoClass.usuarios}/{total.ocupados.acompanhantes + naoClass.acompanhantes}
                      </td>
                    );
                  })}
                  <td className="ocupacao-col-total">
                    {matrizSemana.totalGeralComNaoClassificados.usuarios}/{matrizSemana.totalGeralComNaoClassificados.acompanhantes}
                  </td>
                  <td className="ocupacao-col-percentual"></td>
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
