import { useQueryObj } from "../../api/hooks";
import type { ResumoOutros } from "../../api/types";

interface Props {
  ano: number;
  mes: number;
  empresaId?: number;
}

export default function OutrosView({ ano, mes, empresaId }: Props) {
  const { data, isLoading, error } = useQueryObj<ResumoOutros>("resumo-outros", "/resumos/outros", { ano, mes, empresa_id: empresaId });

  if (isLoading) return <p>Carregando...</p>;
  if (error || !data) return <div className="erro-box">Erro ao carregar outros indicadores.</div>;

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
        <h3>Ranking de cancelamento por regiao</h3>
        {data.ranking_cancelamento_regiao.length === 0 ? (
          <p>Sem cancelamentos no periodo.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Regiao</th>
                <th>Cancelamentos</th>
              </tr>
            </thead>
            <tbody>
              {data.ranking_cancelamento_regiao.map((r) => (
                <tr key={r.regiao_id}>
                  <td>{r.regiao_nome}</td>
                  <td>{r.cancelamentos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
