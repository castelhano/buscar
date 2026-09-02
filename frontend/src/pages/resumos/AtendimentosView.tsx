import { useQueryObj } from "../../api/hooks";
import type { ResumoAtendimentos } from "../../api/types";
import BotaoExportarCsv from "../../components/board/BotaoExportarCsv";
import { diaSemanaAbrev } from "../../utils/data";
import { formatarMilhar } from "../../utils/numero";

interface Props {
  ano: number;
  mes: number;
  empresaId?: number;
}

export default function AtendimentosView({ ano, mes, empresaId }: Props) {
  const { data, isLoading, error } = useQueryObj<ResumoAtendimentos>("resumo-atendimentos", "/resumos/atendimentos", { ano, mes, empresa_id: empresaId });

  if (isLoading) return <p>Carregando...</p>;
  if (error || !data) return <div className="erro-box">Erro ao carregar resumo de atendimentos.</div>;

  const datas = Array.from(new Set(data.grade.map((c) => c.data))).sort();
  const horas = Array.from(new Set(data.grade.map((c) => c.hora))).sort();
  const porCelula = new Map<string, number>();
  const totalPorData = new Map<string, number>();
  const totalPorHora = new Map<string, number>();
  let maxQuantidade = 0;
  let totalGeral = 0;
  for (const c of data.grade) {
    porCelula.set(`${c.data}|${c.hora}`, c.quantidade);
    totalPorData.set(c.data, (totalPorData.get(c.data) ?? 0) + c.quantidade);
    totalPorHora.set(c.hora, (totalPorHora.get(c.hora) ?? 0) + c.quantidade);
    totalGeral += c.quantidade;
    maxQuantidade = Math.max(maxQuantidade, c.quantidade);
  }

  const mesRef = `${ano}-${String(mes).padStart(2, "0")}`;

  const totalPlanejadosCancelamento = data.cancelamento_por_usuario.reduce((s, c) => s + c.planejados, 0);
  const totalCancelamentos = data.cancelamento_por_usuario.reduce((s, c) => s + c.cancelamentos, 0);
  const totalViagensPerdidas = data.cancelamento_por_usuario.reduce((s, c) => s + c.viagens_perdidas, 0);

  function corCelula(qtd: number) {
    if (qtd === 0) return undefined;
    const intensidade = maxQuantidade ? qtd / maxQuantidade : 0;
    return `rgba(45, 55, 72, ${0.12 + intensidade * 0.55})`;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Atendimentos planejados por dia x horario</h3>
          {datas.length > 0 && (
            <BotaoExportarCsv
              nomeArquivo={`atendimentos-grade-${mesRef}.csv`}
              cabecalhos={["Dia", "DDD", ...horas.map((h) => h.slice(0, 5)), "Total"]}
              linhas={[
                ...datas.map((data) => [
                  data.slice(-2),
                  diaSemanaAbrev(data),
                  ...horas.map((h) => porCelula.get(`${data}|${h}`) ?? 0),
                  totalPorData.get(data) ?? 0,
                ]),
                ["Total", "", ...horas.map((h) => totalPorHora.get(h) ?? 0), totalGeral],
              ]}
            />
          )}
        </div>
        {datas.length === 0 ? (
          <p>Nenhum atendimento no periodo.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Dia</th>
                  <th>DDD</th>
                  {horas.map((h) => (
                    <th key={h} className="col-num">
                      {h.slice(0, 5)}
                    </th>
                  ))}
                  <th className="col-num">Total</th>
                </tr>
              </thead>
              <tbody>
                {datas.map((data) => (
                  <tr key={data}>
                    <td>{data.slice(-2)}</td>
                    <td>{diaSemanaAbrev(data)}</td>
                    {horas.map((h) => {
                      const qtd = porCelula.get(`${data}|${h}`) ?? 0;
                      return (
                        <td key={h} className="col-num" style={{ background: corCelula(qtd) }}>
                          {qtd || ""}
                        </td>
                      );
                    })}
                    <td className="col-num">
                      <strong>{totalPorData.get(data) ?? 0}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={2}>
                    <strong>Total</strong>
                  </td>
                  {horas.map((h) => (
                    <td key={h} className="col-num">
                      <strong>{totalPorHora.get(h) ?? 0}</strong>
                    </td>
                  ))}
                  <td className="col-num">
                    <strong>{totalGeral}</strong>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Cancelamentos e viagens perdidas por usuario</h3>
          {data.cancelamento_por_usuario.length > 0 && (
            <BotaoExportarCsv
              nomeArquivo={`cancelamentos-${mesRef}.csv`}
              cabecalhos={["Usuario", "Planejados", "Cancelamentos", "%", "Viagens perdidas"]}
              linhas={[
                ...data.cancelamento_por_usuario.map((c) => [
                  c.usuario_nome,
                  c.planejados,
                  c.cancelamentos,
                  `${c.percentual_cancelamento.toFixed(1)}%`,
                  c.viagens_perdidas,
                ]),
                [
                  "Total",
                  totalPlanejadosCancelamento,
                  totalCancelamentos,
                  `${(totalPlanejadosCancelamento ? (totalCancelamentos / totalPlanejadosCancelamento) * 100 : 0).toFixed(1)}%`,
                  totalViagensPerdidas,
                ],
              ]}
            />
          )}
        </div>
        {data.cancelamento_por_usuario.length === 0 ? (
          <p>Nenhum cancelamento no periodo.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Usuario</th>
                <th className="col-num">Planejados</th>
                <th className="col-num">Cancelamentos</th>
                <th className="col-num">%</th>
                <th className="col-num">Viagens perdidas</th>
              </tr>
            </thead>
            <tbody>
              {data.cancelamento_por_usuario.map((c) => (
                <tr key={c.usuario_id}>
                  <td>{c.usuario_nome}</td>
                  <td className="col-num">{formatarMilhar(c.planejados)}</td>
                  <td className="col-num">{formatarMilhar(c.cancelamentos)}</td>
                  <td className="col-num">{c.percentual_cancelamento.toFixed(1)}%</td>
                  <td className="col-num">{formatarMilhar(c.viagens_perdidas)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>
                  <strong>Total</strong>
                </td>
                <td className="col-num">
                  <strong>{formatarMilhar(totalPlanejadosCancelamento)}</strong>
                </td>
                <td className="col-num">
                  <strong>{formatarMilhar(totalCancelamentos)}</strong>
                </td>
                <td className="col-num">
                  <strong>{(totalPlanejadosCancelamento ? (totalCancelamentos / totalPlanejadosCancelamento) * 100 : 0).toFixed(1)}%</strong>
                </td>
                <td className="col-num">
                  <strong>{formatarMilhar(totalViagensPerdidas)}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
        )}
      </section>
    </div>
  );
}
