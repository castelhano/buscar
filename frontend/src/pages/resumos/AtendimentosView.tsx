import { useQueryObj } from "../../api/hooks";
import type { ResumoAtendimentos } from "../../api/types";
import { formatarData } from "../../utils/data";

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
  let maxQuantidade = 0;
  for (const c of data.grade) {
    porCelula.set(`${c.data}|${c.hora}`, c.quantidade);
    maxQuantidade = Math.max(maxQuantidade, c.quantidade);
  }

  function corCelula(qtd: number) {
    if (qtd === 0) return undefined;
    const intensidade = maxQuantidade ? qtd / maxQuantidade : 0;
    return `rgba(45, 55, 72, ${0.12 + intensidade * 0.55})`;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <section>
        <h3>Atendimentos planejados por dia x horario</h3>
        {datas.length === 0 ? (
          <p>Nenhum atendimento no periodo.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Dia</th>
                  {horas.map((h) => (
                    <th key={h}>{h.slice(0, 5)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {datas.map((data) => (
                  <tr key={data}>
                    <td>{formatarData(data)}</td>
                    {horas.map((h) => {
                      const qtd = porCelula.get(`${data}|${h}`) ?? 0;
                      return (
                        <td key={h} style={{ background: corCelula(qtd), textAlign: "center" }}>
                          {qtd || ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3>Cancelamentos e viagens perdidas por usuario</h3>
        <table>
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Cancelamentos</th>
              <th>Viagens perdidas</th>
            </tr>
          </thead>
          <tbody>
            {data.cancelamento_por_usuario.map((c) => (
              <tr key={c.usuario_id}>
                <td>{c.usuario_nome}</td>
                <td>{c.cancelamentos}</td>
                <td>{c.viagens_perdidas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
