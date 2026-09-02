import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useQueryObj } from "../../api/hooks";
import type { ResumoRodagem } from "../../api/types";
import BotaoExportarCsv from "../../components/board/BotaoExportarCsv";
import { corDaSerie } from "./cores";

interface Props {
  ano: number;
  mes: number;
  empresaId?: number;
}

function BarraVariacao({ variacao, escalaMax }: { variacao: number; escalaMax: number }) {
  const acimaContrato = variacao > 0;
  const largura = (Math.min(Math.abs(variacao), escalaMax) / escalaMax) * 50;
  const cor = acimaContrato ? "var(--cor-perigo)" : "var(--cor-sucesso)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
      <div style={{ position: "relative", width: "110px", height: "10px", background: "var(--cor-fundo)", borderRadius: "4px", flexShrink: 0 }}>
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: "1px", background: "var(--cor-borda)" }} />
        {variacao !== 0 && (
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: acimaContrato ? "50%" : `${50 - largura}%`,
              width: `${largura}%`,
              background: cor,
              borderRadius: "2px",
            }}
          />
        )}
      </div>
      <span style={{ color: cor, fontWeight: acimaContrato ? 600 : 400, fontSize: "0.85rem", whiteSpace: "nowrap" }}>
        {variacao > 0 ? "+" : ""}
        {variacao.toFixed(1)} p.p.
      </span>
    </div>
  );
}

export default function RodagemView({ ano, mes, empresaId }: Props) {
  const { data, isLoading, error } = useQueryObj<ResumoRodagem>("resumo-rodagem", "/resumos/rodagem", { ano, mes, empresa_id: empresaId });

  if (isLoading) return <p>Carregando...</p>;
  if (error || !data) return <div className="erro-box">Erro ao carregar resumo de rodagem.</div>;

  const empresasNomes = Array.from(new Set(data.evolucao_km_empresa.map((e) => e.empresa_nome)));
  const evolucaoPorMes = new Map<string, Record<string, number | string>>();
  for (const item of data.evolucao_km_empresa) {
    const chave = `${String(item.mes).padStart(2, "0")}/${item.ano}`;
    if (!evolucaoPorMes.has(chave)) evolucaoPorMes.set(chave, { mes: chave });
    evolucaoPorMes.get(chave)![item.empresa_nome] = item.km_total;
  }
  const evolucaoDados = Array.from(evolucaoPorMes.values());

  const variacoes = data.km_por_empresa.map((e) => e.percentual_km_periodo - e.percentual_contrato);
  const escalaMaxVariacao = Math.max(5, ...variacoes.map((v) => Math.abs(v)));
  const totalKmEmpresas = data.km_por_empresa.reduce((s, e) => s + e.km_total, 0);
  const totalPercentualKm = data.km_por_empresa.reduce((s, e) => s + e.percentual_km_periodo, 0);
  const totalPercentualContrato = data.km_por_empresa.reduce((s, e) => s + e.percentual_contrato, 0);
  const totalVariacao = variacoes.reduce((s, v) => s + v, 0);

  const mesRef = `${ano}-${String(mes).padStart(2, "0")}`;

  const totalPorEmpresa: Record<number, number> = {};
  let totalGeralFrota = 0;
  for (const d of data.uso_frota_diario) {
    for (const e of data.km_por_empresa) {
      const v = d.por_empresa[String(e.empresa_id)] ?? 0;
      totalPorEmpresa[e.empresa_id] = (totalPorEmpresa[e.empresa_id] ?? 0) + v;
      totalGeralFrota += v;
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <section>
        <h3>Km por veiculo</h3>
        {data.km_por_veiculo.length === 0 ? (
          <p>Nenhum km lancado no periodo.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={[...data.km_por_veiculo].sort((a, b) => b.km_total - a.km_total)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="prefixo" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="km_total" name="Km rodado" fill={corDaSerie(0)} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Km por empresa x % contrato</h3>
          <BotaoExportarCsv
            nomeArquivo={`km-por-empresa-${mesRef}.csv`}
            cabecalhos={["Empresa", "Km no periodo", "% do km total", "% contrato", "Variacao vs contrato"]}
            linhas={[
              ...data.km_por_empresa.map((e, i) => [
                e.empresa_nome,
                e.km_total,
                `${e.percentual_km_periodo}%`,
                `${e.percentual_contrato}%`,
                `${variacoes[i] > 0 ? "+" : ""}${variacoes[i].toFixed(1)} p.p.`,
              ]),
              ["Total", totalKmEmpresas, `${totalPercentualKm.toFixed(1)}%`, `${totalPercentualContrato.toFixed(1)}%`, `${totalVariacao > 0 ? "+" : ""}${totalVariacao.toFixed(1)} p.p.`],
            ]}
          />
        </div>
        <table>
          <thead>
            <tr>
              <th>Empresa</th>
              <th>Km no periodo</th>
              <th>% do km total</th>
              <th>% contrato</th>
              <th>Variacao vs contrato</th>
            </tr>
          </thead>
          <tbody>
            {data.km_por_empresa.map((e, i) => (
              <tr key={e.empresa_id}>
                <td>{e.empresa_nome}</td>
                <td>{e.km_total}</td>
                <td>{e.percentual_km_periodo}%</td>
                <td>{e.percentual_contrato}%</td>
                <td>
                  <BarraVariacao variacao={variacoes[i]} escalaMax={escalaMaxVariacao} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>
                <strong>Total</strong>
              </td>
              <td>
                <strong>{totalKmEmpresas}</strong>
              </td>
              <td>
                <strong>{totalPercentualKm.toFixed(1)}%</strong>
              </td>
              <td>
                <strong>{totalPercentualContrato.toFixed(1)}%</strong>
              </td>
              <td>
                <strong style={{ color: totalVariacao > 0 ? "var(--cor-perigo)" : "var(--cor-sucesso)" }}>
                  {totalVariacao > 0 ? "+" : ""}
                  {totalVariacao.toFixed(1)} p.p.
                </strong>
              </td>
            </tr>
          </tfoot>
        </table>
      </section>

      <section>
        <h3>Evolucao do km rodado (6 meses)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={evolucaoDados}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="mes" />
            <YAxis />
            <Tooltip />
            <Legend />
            {empresasNomes.map((nome, i) => (
              <Line key={nome} type="monotone" dataKey={nome} stroke={corDaSerie(i)} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Uso diario de frota</h3>
          <BotaoExportarCsv
            nomeArquivo={`uso-frota-${mesRef}.csv`}
            cabecalhos={["Dia", "Sem", ...data.km_por_empresa.map((e) => e.empresa_nome), "Total"]}
            linhas={[
              ...data.uso_frota_diario.map((d) => [
                d.data.slice(-2),
                d.dia_semana,
                ...data.km_por_empresa.map((e) => d.por_empresa[String(e.empresa_id)] ?? 0),
                Object.values(d.por_empresa).reduce((a, b) => a + b, 0),
              ]),
              ["Total", "", ...data.km_por_empresa.map((e) => totalPorEmpresa[e.empresa_id] ?? 0), totalGeralFrota],
            ]}
          />
        </div>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Dia</th>
                <th>SEM</th>
                {data.km_por_empresa.map((e) => (
                  <th key={e.empresa_id}>{e.empresa_nome}</th>
                ))}
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.uso_frota_diario.map((d) => {
                const totalDia = Object.values(d.por_empresa).reduce((a, b) => a + b, 0);
                return (
                  <tr key={d.data}>
                    <td>{d.data.slice(-2)}</td>
                    <td>{d.dia_semana}</td>
                    {data.km_por_empresa.map((e) => (
                      <td key={e.empresa_id}>{d.por_empresa[String(e.empresa_id)] ?? 0}</td>
                    ))}
                    <td>
                      <strong>{totalDia}</strong>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>
                  <strong>Total</strong>
                </td>
                {data.km_por_empresa.map((e) => (
                  <td key={e.empresa_id}>
                    <strong>{totalPorEmpresa[e.empresa_id] ?? 0}</strong>
                  </td>
                ))}
                <td>
                  <strong>{totalGeralFrota}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  );
}
