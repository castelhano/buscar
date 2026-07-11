import type { UsuarioDesconsiderado } from "../../api/types";

interface Props {
  desconsiderados: UsuarioDesconsiderado[];
}

export default function DesconsideradosPanel({ desconsiderados }: Props) {
  if (desconsiderados.length === 0) return null;

  return (
    <div className="painel">
      <h3>Desconsiderados no dia ({desconsiderados.length})</h3>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Usuarios com atendimento Fixo previsto pra essa data que nao entraram na geracao do dia.
      </p>
      <table>
        <thead>
          <tr>
            <th>Usuario</th>
            <th>Motivo</th>
          </tr>
        </thead>
        <tbody>
          {desconsiderados.map((d) => (
            <tr key={d.usuario_id}>
              <td>{d.usuario_nome}</td>
              <td>{d.motivo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
