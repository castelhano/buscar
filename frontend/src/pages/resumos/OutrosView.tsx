import { useQueryObj } from "../../api/hooks";
import type { ResumoOutros } from "../../api/types";
import BotaoExportarCsv from "../../components/board/BotaoExportarCsv";
import { formatarMilhar } from "../../utils/numero";

interface Props {
  ano: number;
  mes: number;
  empresaId?: number;
}

export default function OutrosView({ ano, mes, empresaId }: Props) {
  const { data, isLoading, error } = useQueryObj<ResumoOutros>("resumo-outros", "/resumos/outros", { ano, mes, empresa_id: empresaId });

  if (isLoading) return <p>Carregando...</p>;
  if (error || !data) return <div className="erro-box">Erro ao carregar outros indicadores.</div>;

  const mesRef = `${ano}-${String(mes).padStart(2, "0")}`;
  const totalCancelamentosRegiao = data.ranking_cancelamento_regiao.reduce((s, r) => s + r.cancelamentos, 0);
  const totalAtendimentosLocal = data.atendimentos_por_local.reduce((s, a) => s + a.atendimentos, 0);
  const totalPercentualLocal = data.atendimentos_por_local.reduce((s, a) => s + a.percentual, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <section className="resumo-stats">
        <div className="resumo-stat-card">
          <span className="resumo-stat-label">Ociosidade de frota</span>
          <span className="resumo-stat-valor">{data.ociosidade_frota.percentual_ocioso}%</span>
          <span className="resumo-stat-detalhe">
            {data.ociosidade_frota.veiculos_utilizados} de {data.ociosidade_frota.veiculos_ativos} veiculos ativos usados
          </span>
        </div>
        <div className="resumo-stat-card">
          <span className="resumo-stat-label">Taxa de ocupacao</span>
          <span className="resumo-stat-valor">{data.taxa_ocupacao.percentual}%</span>
          <span className="resumo-stat-detalhe">
            {data.taxa_ocupacao.passageiros} de {data.taxa_ocupacao.capacidade_total} vagas ocupadas
          </span>
        </div>
        <div className="resumo-stat-card">
          <span className="resumo-stat-label">Km por atendimento</span>
          <span className="resumo-stat-valor">{data.km_por_atendimento ?? "-"}</span>
        </div>
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Ranking de cancelamento por regiao</h3>
          {data.ranking_cancelamento_regiao.length > 0 && (
            <BotaoExportarCsv
              nomeArquivo={`ranking-cancelamento-regiao-${mesRef}.csv`}
              cabecalhos={["Regiao", "Cancelamentos"]}
              linhas={[
                ...data.ranking_cancelamento_regiao.map((r) => [r.regiao_nome, r.cancelamentos]),
                ["Total", totalCancelamentosRegiao],
              ]}
            />
          )}
        </div>
        {data.ranking_cancelamento_regiao.length === 0 ? (
          <p>Sem cancelamentos no periodo.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Regiao</th>
                <th className="col-num">Cancelamentos</th>
              </tr>
            </thead>
            <tbody>
              {data.ranking_cancelamento_regiao.map((r) => (
                <tr key={r.regiao_id}>
                  <td>{r.regiao_nome}</td>
                  <td className="col-num">{formatarMilhar(r.cancelamentos)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>
                  <strong>Total</strong>
                </td>
                <td className="col-num">
                  <strong>{formatarMilhar(totalCancelamentosRegiao)}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
        )}
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Atendimentos por local</h3>
          {data.atendimentos_por_local.length > 0 && (
            <BotaoExportarCsv
              nomeArquivo={`atendimentos-por-local-${mesRef}.csv`}
              cabecalhos={["Local", "Atendimentos", "%"]}
              linhas={[
                ...data.atendimentos_por_local.map((a) => [a.local_nome, a.atendimentos, `${a.percentual.toFixed(1)}%`]),
                ["Total", totalAtendimentosLocal, `${totalPercentualLocal.toFixed(1)}%`],
              ]}
            />
          )}
        </div>
        <p style={{ fontSize: "0.85rem", color: "var(--cor-texto-suave)", marginTop: "-0.5rem" }}>
          Ida e volta no mesmo dia pro mesmo local conta como um unico atendimento.
        </p>
        {data.atendimentos_por_local.length === 0 ? (
          <p>Nenhum atendimento em local no periodo.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Local</th>
                <th className="col-num">Atendimentos</th>
                <th className="col-num">%</th>
              </tr>
            </thead>
            <tbody>
              {data.atendimentos_por_local.map((a) => (
                <tr key={a.local_id}>
                  <td>{a.local_nome}</td>
                  <td className="col-num">{formatarMilhar(a.atendimentos)}</td>
                  <td className="col-num">{a.percentual.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>
                  <strong>Total</strong>
                </td>
                <td className="col-num">
                  <strong>{formatarMilhar(totalAtendimentosLocal)}</strong>
                </td>
                <td className="col-num">
                  <strong>{totalPercentualLocal.toFixed(1)}%</strong>
                </td>
              </tr>
            </tfoot>
          </table>
        )}
      </section>
    </div>
  );
}
