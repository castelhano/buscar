import type { Condutor, Empresa, Local, Regiao, Veiculo, ViagemDia, ViagemDiaPassageiro } from "../../api/types";
import LegBlock from "./LegBlock";

interface Props {
  viagens: ViagemDia[];
  empresas: Empresa[];
  veiculos: Veiculo[];
  condutores: Condutor[];
  locais: Local[];
  regioes: Regiao[];
  tituloSemVeiculo?: string;
  onAdicionarPassageiro?: (viagemId: number) => void;
  onRemoverPassageiro?: (id: number) => void;
  onCancelarPassageiro?: (id: number) => void;
  onEditarPassageiro?: (passageiro: ViagemDiaPassageiro) => void;
  onAtribuir?: (dados: { viagemIds: number[]; condutorAtualId: number | null; veiculoAtualId: number | null }) => void;
  onRemoverCarro?: (viagemId: number) => void;
}

export default function CarroCard({
  viagens,
  empresas,
  veiculos,
  condutores,
  locais,
  regioes,
  tituloSemVeiculo = "Carro sem veiculo",
  onAdicionarPassageiro,
  onRemoverPassageiro,
  onCancelarPassageiro,
  onEditarPassageiro,
  onAtribuir,
  onRemoverCarro,
}: Props) {
  const pernas = [...viagens].sort((a, b) => {
    const horaA = a.passageiros[0]?.hora ?? a.horario_saida;
    const horaB = b.passageiros[0]?.hora ?? b.horario_saida;
    return horaA.localeCompare(horaB);
  });

  const primeira = pernas[0];
  const veiculo = veiculos.find((v) => v.id === primeira.veiculo_id);
  const empresa = empresas.find((e) => e.id === primeira.empresa_id);
  const condutor = condutores.find((c) => c.id === primeira.condutor_id);

  // Regiao de cada passageiro (nao da viagem/leg) -- cobre tanto o condutor
  // com pernas em regioes diferentes ao longo do dia quanto um unico carro
  // misturando passageiros de regioes diferentes (pin cross-regiao).
  const regiaoIdsPassageiros = pernas.flatMap((v) =>
    v.passageiros.map((p) => (p.sentido === "Retorno" && p.regiao_destino_id != null ? p.regiao_destino_id : p.regiao_origem_id)),
  );
  const regiaoNomes = [...new Set(regiaoIdsPassageiros)].map((id) => regioes.find((r) => r.id === id)?.nome ?? "?");

  return (
    <div className="carro-card">
      <div className="carro-card-topo">
        <div className="titulo">{veiculo ? veiculo.prefixo : tituloSemVeiculo}</div>
        <span className="tag tag-regiao" title="Regiao do veiculo">
          {regiaoNomes.join(" · ")}
        </span>
      </div>
      {onAtribuir && (
        <>
          <div className="meta">
            {empresa?.nome ?? "Sem empresa"} · {condutor?.nome ?? "Sem condutor"}
          </div>
          {primeira.intervalo_inicio && primeira.intervalo_fim && (
            <div className="meta">
              Intervalo {primeira.intervalo_inicio.slice(0, 5)} - {primeira.intervalo_fim.slice(0, 5)}
            </div>
          )}
          <div style={{ marginTop: "0.3rem" }}>
            <button
              className="btn btn-sm"
              onClick={() =>
                onAtribuir({
                  viagemIds: pernas.map((v) => v.id),
                  condutorAtualId: primeira.condutor_id,
                  veiculoAtualId: primeira.veiculo_id,
                })
              }
            >
              Condutor/veiculo
            </button>
          </div>
        </>
      )}

      {pernas.map((viagem, indice) => (
        <LegBlock
          key={viagem.id}
          viagem={viagem}
          isPrimeira={indice === 0}
          locais={locais}
          onAdicionarPassageiro={onAdicionarPassageiro}
          onRemoverPassageiro={onRemoverPassageiro}
          onCancelarPassageiro={onCancelarPassageiro}
          onEditarPassageiro={onEditarPassageiro}
          onRemoverCarro={onRemoverCarro}
        />
      ))}
    </div>
  );
}
