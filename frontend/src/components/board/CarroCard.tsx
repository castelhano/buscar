import type { Condutor, Empresa, Local, Veiculo, ViagemDia, ViagemDiaPassageiro } from "../../api/types";
import LegBlock from "./LegBlock";

interface Props {
  viagens: ViagemDia[];
  empresas: Empresa[];
  veiculos: Veiculo[];
  condutores: Condutor[];
  locais: Local[];
  onAdicionarPassageiro: (viagemId: number) => void;
  onRemoverPassageiro: (id: number) => void;
  onCancelarPassageiro: (id: number) => void;
  onEditarPassageiro: (passageiro: ViagemDiaPassageiro) => void;
  onAtribuir: (viagemId: number) => void;
  onRemoverCarro: (viagemId: number) => void;
}

export default function CarroCard({
  viagens,
  empresas,
  veiculos,
  condutores,
  locais,
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

  return (
    <div className="carro-card">
      <div className="titulo">{veiculo ? veiculo.prefixo : "Carro sem veiculo"}</div>
      <div className="meta">
        {empresa?.nome ?? "Sem empresa"} · {condutor?.nome ?? "Sem condutor"}
      </div>

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
          onAtribuir={onAtribuir}
          onRemoverCarro={onRemoverCarro}
        />
      ))}
    </div>
  );
}
