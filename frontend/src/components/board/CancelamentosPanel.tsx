import type { ViagemDiaPassageiro, ViagemDia } from "../../api/types";
import { rotuloTrecho } from "../../api/types";

interface Props {
  viagens: ViagemDia[];
  passageirosSemVaga?: ViagemDiaPassageiro[];
}

interface CancelamentoUsuario {
  usuarioId: number;
  usuarioNome: string;
  // ordem_trecho -> viagem_perdida
  trechosCancelados: Map<number, boolean>;
}

function agruparCancelamentos(passageiros: ViagemDiaPassageiro[]): CancelamentoUsuario[] {
  const porUsuario = new Map<number, CancelamentoUsuario>();

  for (const passageiro of passageiros) {
    if (passageiro.status !== "Cancelado") continue;

    const atual = porUsuario.get(passageiro.usuario_id) ?? {
      usuarioId: passageiro.usuario_id,
      usuarioNome: passageiro.usuario.nome,
      trechosCancelados: new Map<number, boolean>(),
    };
    atual.trechosCancelados.set(passageiro.ordem_trecho, passageiro.viagem_perdida);
    porUsuario.set(passageiro.usuario_id, atual);
  }

  return [...porUsuario.values()].sort((a, b) => a.usuarioNome.localeCompare(b.usuarioNome));
}

function rotuloContador(total: number, perdidas: number): string {
  if (perdidas === 0) return `(${total})`;
  if (perdidas === total) return `(${total} V PERDIDA)`;
  return `(${total}, ${perdidas} V PERDIDA)`;
}

export default function CancelamentosPanel({ viagens, passageirosSemVaga = [] }: Props) {
  const cancelamentos = agruparCancelamentos([
    ...viagens.flatMap((v) => v.passageiros),
    ...passageirosSemVaga,
  ]);
  if (cancelamentos.length === 0) return null;

  const perdidas = cancelamentos.filter((c) => [...c.trechosCancelados.values()].some(Boolean)).length;

  return (
    <div className="painel">
      <h3>Cancelamentos do dia {rotuloContador(cancelamentos.length, perdidas)}</h3>
      <ol>
        {cancelamentos.map((c) => (
          <li key={c.usuarioId}>
            {c.usuarioNome}{" "}
            {[...c.trechosCancelados.entries()]
              .sort(([a], [b]) => a - b)
              .map(([ordem, viagemPerdida]) => (
                <span key={ordem} style={{ marginLeft: "0.25rem" }}>
                  <span className="badge-rotulo">{rotuloTrecho(ordem)}</span>
                  {viagemPerdida && (
                    <span className="tag tag-inativo" style={{ marginLeft: "0.25rem" }}>
                      V PERDIDA
                    </span>
                  )}
                </span>
              ))}
          </li>
        ))}
      </ol>
    </div>
  );
}
