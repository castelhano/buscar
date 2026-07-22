import type { ViagemDia, ViagemDiaPassageiro } from "../../api/types";

interface Props {
  viagens: ViagemDia[];
  passageirosSemVaga?: ViagemDiaPassageiro[];
}

interface CancelamentoUsuario {
  usuarioId: number;
  usuarioNome: string;
  ida: boolean;
  retorno: boolean;
}

function agruparCancelamentos(passageiros: ViagemDiaPassageiro[]): CancelamentoUsuario[] {
  const porUsuario = new Map<number, CancelamentoUsuario>();

  for (const passageiro of passageiros) {
    if (passageiro.status !== "Cancelado") continue;

    const atual = porUsuario.get(passageiro.usuario_id) ?? {
      usuarioId: passageiro.usuario_id,
      usuarioNome: passageiro.usuario.nome,
      ida: false,
      retorno: false,
    };
    if (passageiro.sentido === "Ida") atual.ida = true;
    else atual.retorno = true;
    porUsuario.set(passageiro.usuario_id, atual);
  }

  return [...porUsuario.values()].sort((a, b) => a.usuarioNome.localeCompare(b.usuarioNome));
}

export default function CancelamentosPanel({ viagens, passageirosSemVaga = [] }: Props) {
  const cancelamentos = agruparCancelamentos([
    ...viagens.flatMap((v) => v.passageiros),
    ...passageirosSemVaga,
  ]);
  if (cancelamentos.length === 0) return null;

  return (
    <div className="painel">
      <h3>Cancelamentos do dia ({cancelamentos.length})</h3>
      <ol>
        {cancelamentos.map((c) => (
          <li key={c.usuarioId}>
            {c.usuarioNome}
            {c.ida && c.retorno ? " (Ida e Retorno)" : c.ida ? " (Ida)" : " (Retorno)"}
          </li>
        ))}
      </ol>
    </div>
  );
}
