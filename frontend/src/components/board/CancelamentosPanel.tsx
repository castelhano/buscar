import type { ViagemDiaPassageiro, ViagemDia } from "../../api/types";
import { rotuloTrecho } from "../../api/types";

interface Props {
  viagens: ViagemDia[];
  passageirosSemVaga?: ViagemDiaPassageiro[];
}

interface InfoTrechoCancelado {
  viagemPerdida: boolean;
  canceladoPelaEmpresa: boolean;
}

interface CancelamentoUsuario {
  usuarioId: number;
  usuarioNome: string;
  trechosCancelados: Map<number, InfoTrechoCancelado>;
}

function agruparCancelamentos(passageiros: ViagemDiaPassageiro[]): CancelamentoUsuario[] {
  const porUsuario = new Map<number, CancelamentoUsuario>();

  for (const passageiro of passageiros) {
    if (passageiro.status !== "Cancelado") continue;

    const atual = porUsuario.get(passageiro.usuario_id) ?? {
      usuarioId: passageiro.usuario_id,
      usuarioNome: passageiro.usuario.nome,
      trechosCancelados: new Map<number, InfoTrechoCancelado>(),
    };
    atual.trechosCancelados.set(passageiro.ordem_trecho, {
      viagemPerdida: passageiro.viagem_perdida,
      canceladoPelaEmpresa: passageiro.cancelado_pela_empresa,
    });
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

  const perdidas = cancelamentos.filter((c) => [...c.trechosCancelados.values()].some((v) => v.viagemPerdida)).length;

  return (
    <div className="painel">
      <h3>Cancelamentos do dia {rotuloContador(cancelamentos.length, perdidas)}</h3>
      <ol>
        {/* value explicito: ao trocar de dia o React reaproveita os <li> de
            mesmo usuario e remove os anteriores, e o Chrome nao recalcula a
            numeracao automatica do <ol> (ex: lista comecando em 5). */}
        {cancelamentos.map((c, i) => (
          <li key={c.usuarioId} value={i + 1}>
            {c.usuarioNome}{" "}
            {[...c.trechosCancelados.entries()]
              .sort(([a], [b]) => a - b)
              .map(([ordem, info]) => (
                <span key={ordem} style={{ marginLeft: "0.25rem" }}>
                  <span className="badge-rotulo">{rotuloTrecho(ordem)}</span>
                  {info.viagemPerdida && (
                    <span className="tag tag-inativo" style={{ marginLeft: "0.25rem" }}>
                      V PERDIDA
                    </span>
                  )}
                  {info.canceladoPelaEmpresa && (
                    <span className="tag tag-empresa" style={{ marginLeft: "0.25rem" }}>
                      EMPRESA
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
