import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Condutor, Empresa, Veiculo, ViagemDia, ViagemDiaPassageiro } from "../../api/types";
import PassageiroCard from "./PassageiroCard";

interface Props {
  viagem: ViagemDia;
  empresas: Empresa[];
  veiculos: Veiculo[];
  condutores: Condutor[];
  onAdicionarPassageiro: (viagemId: number) => void;
  onRemoverPassageiro: (id: number) => void;
  onCancelarPassageiro: (id: number) => void;
  onEditarPassageiro: (passageiro: ViagemDiaPassageiro) => void;
  onAtribuir: (viagemId: number) => void;
  onRemoverCarro: (viagemId: number) => void;
}

export default function CarroCard({
  viagem,
  empresas,
  veiculos,
  condutores,
  onAdicionarPassageiro,
  onRemoverPassageiro,
  onCancelarPassageiro,
  onEditarPassageiro,
  onAtribuir,
  onRemoverCarro,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `carro-${viagem.id}`, data: { viagemId: viagem.id } });

  const empresa = empresas.find((e) => e.id === viagem.empresa_id);
  const veiculo = veiculos.find((v) => v.id === viagem.veiculo_id);
  const condutor = condutores.find((c) => c.id === viagem.condutor_id);

  const passageirosOrdenados = [...viagem.passageiros].sort((a, b) => a.hora.localeCompare(b.hora) || a.ordem - b.ordem);
  const grupos: { hora: string; itens: typeof passageirosOrdenados }[] = [];
  for (const p of passageirosOrdenados) {
    const horaLabel = p.hora.slice(0, 5);
    const grupo = grupos.find((g) => g.hora === horaLabel);
    if (grupo) grupo.itens.push(p);
    else grupos.push({ hora: horaLabel, itens: [p] });
  }

  const avisos: string[] = [];
  if (viagem.condutor_em_ferias) avisos.push("Condutor em ferias nessa data");
  if (viagem.conflito_horario) avisos.push(viagem.motivo_conflito_horario ?? "Conflito de horario");
  const temAviso = avisos.length > 0;

  return (
    <div
      className="carro-card"
      ref={setNodeRef}
      style={{ outline: isOver ? "2px solid var(--cor-primaria)" : temAviso ? "2px solid var(--cor-alerta-borda)" : "none" }}
    >
      <div className="carro-card-header">
        <div>
          <div className="titulo">{veiculo ? `${veiculo.prefixo}` : "Carro sem veiculo"}</div>
          <div className="meta">
            {empresa?.nome ?? "Sem empresa"} · {condutor?.nome ?? "Sem condutor"}
          </div>
          <div className="meta">Saida {viagem.horario_saida.slice(0, 5)} · cap. {viagem.capacidade}</div>
          {viagem.status !== "Planejada" && <span className="tag">{viagem.status}</span>}
          {avisos.map((aviso) => (
            <div
              key={aviso}
              style={{ color: "var(--cor-alerta-borda)", fontWeight: 600, fontSize: "0.78rem", marginTop: "0.2rem" }}
              title={aviso}
            >
              ⚠ {aviso}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
          <button className="btn btn-sm" onClick={() => onAtribuir(viagem.id)}>
            Condutor/veiculo
          </button>
          {viagem.passageiros.length === 0 && (
            <button className="btn btn-sm btn-perigo" onClick={() => onRemoverCarro(viagem.id)}>
              Remover carro
            </button>
          )}
        </div>
      </div>

      <SortableContext items={passageirosOrdenados.map((p) => p.id)} strategy={verticalListSortingStrategy}>
        {grupos.map((grupo) => (
          <div key={grupo.hora} className="horario-grupo">
            <div className="horario-grupo-label">{grupo.hora}</div>
            {grupo.itens.map((p) => (
              <PassageiroCard
                key={p.id}
                viagemId={viagem.id}
                passageiro={p}
                onRemover={onRemoverPassageiro}
                onCancelar={onCancelarPassageiro}
                onEditar={onEditarPassageiro}
              />
            ))}
          </div>
        ))}
      </SortableContext>

      <button className="carro-card-add" onClick={() => onAdicionarPassageiro(viagem.id)}>
        + adicionar passageiro
      </button>
    </div>
  );
}
