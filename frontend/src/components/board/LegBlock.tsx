import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Local, ViagemDia, ViagemDiaPassageiro } from "../../api/types";
import { periodoDaViagem } from "../../api/periodo";
import PassageiroCard from "./PassageiroCard";

interface Props {
  viagem: ViagemDia;
  isPrimeira: boolean;
  locais: Local[];
  periodoAtual: "Manha" | "Tarde";
  onAdicionarPassageiro?: (viagemId: number) => void;
  onRemoverPassageiro?: (id: number) => void;
  onCancelarPassageiro?: (id: number) => void;
  onEditarPassageiro?: (passageiro: ViagemDiaPassageiro) => void;
  onRemoverViagem?: (viagemId: number) => void;
}

export default function LegBlock({
  viagem,
  isPrimeira,
  locais,
  periodoAtual,
  onAdicionarPassageiro,
  onRemoverPassageiro,
  onCancelarPassageiro,
  onEditarPassageiro,
  onRemoverViagem,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `carro-${viagem.id}`, data: { viagemId: viagem.id } });
  const periodoDaPerna = periodoDaViagem(viagem);
  const foraDoPeriodo = periodoDaPerna !== periodoAtual;

  const passageirosOrdenados = [...viagem.passageiros].sort((a, b) => a.hora.localeCompare(b.hora) || a.ordem - b.ordem);
  const primeiro = passageirosOrdenados[0];
  const labelHorario = primeiro ? `${primeiro.sentido} · ${primeiro.hora.slice(0, 5)}` : viagem.horario_saida.slice(0, 5);

  const lugaresOcupados = viagem.passageiros
    .filter((p) => p.status !== "Cancelado")
    .reduce((soma, p) => soma + (p.acompanhante ? 2 : 1), 0);

  const avisos: string[] = [];
  if (foraDoPeriodo) avisos.push(`Perna de periodo diferente (${periodoDaPerna})`);
  if (viagem.condutor_em_ferias) avisos.push("Condutor em ferias nessa data");
  if (viagem.conflito_horario) avisos.push(viagem.motivo_conflito_horario ?? "Conflito de horario");
  if (lugaresOcupados > viagem.capacidade) avisos.push("Lugares ocupados acima da capacidade do veiculo");

  return (
    <div
      ref={setNodeRef}
      className={`leg-block ${isPrimeira ? "leg-block-primeira" : ""} ${foraDoPeriodo ? "leg-block-periodo-errado" : ""}`}
      style={{ outline: isOver ? "2px solid var(--cor-primaria)" : "none" }}
    >
      <div className="leg-block-header">
        <div className="horario-grupo-label">{labelHorario}</div>
        <div className="meta">
          Saida {viagem.horario_saida.slice(0, 5)} · {lugaresOcupados}/{viagem.capacidade} lugares
          {viagem.status !== "Planejada" && <span className="tag" style={{ marginLeft: "0.4rem" }}>{viagem.status}</span>}
        </div>
        {avisos.map((aviso) => (
          <div
            key={aviso}
            style={{ color: "var(--cor-alerta-borda)", fontWeight: 600, fontSize: "0.78rem", marginTop: "0.2rem" }}
            title={aviso}
          >
            ⚠ {aviso}
          </div>
        ))}
        {viagem.passageiros.length === 0 && onRemoverViagem && (
          <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem" }}>
            <button className="btn btn-sm btn-perigo" onClick={() => onRemoverViagem(viagem.id)}>
              Remover viagem
            </button>
          </div>
        )}
      </div>

      <SortableContext items={passageirosOrdenados.map((p) => p.id)} strategy={verticalListSortingStrategy}>
        {passageirosOrdenados.map((p) => (
          <PassageiroCard
            key={p.id}
            viagemId={viagem.id}
            passageiro={p}
            destinoNome={locais.find((l) => l.id === p.destino_id)?.nome}
            onRemover={onRemoverPassageiro}
            onCancelar={onCancelarPassageiro}
            onEditar={onEditarPassageiro}
          />
        ))}
      </SortableContext>

      {onAdicionarPassageiro && (
        <button className="carro-card-add" onClick={() => onAdicionarPassageiro(viagem.id)}>
          + adicionar passageiro
        </button>
      )}
    </div>
  );
}
