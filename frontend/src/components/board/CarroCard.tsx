import { useDroppable } from "@dnd-kit/core";
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
  periodoAtual: "Manha" | "Tarde";
  posicao: number;
  totalNoPeriodo: number;
  onMoverEsquerda: () => void;
  onMoverDireita: () => void;
  onEditarPosicao: () => void;
  onAdicionarPassageiro?: (viagemId: number) => void;
  onRemoverPassageiro?: (id: number) => void;
  onCancelarPassageiro?: (id: number) => void;
  onEditarPassageiro?: (passageiro: ViagemDiaPassageiro) => void;
  onAtribuir?: (dados: { viagemIds: number[]; condutorAtualId: number | null; veiculoAtualId: number | null }) => void;
  onLimparCondutorVeiculo?: (viagemIds: number[]) => void;
  onRemoverViagem?: (viagemId: number) => void;
  /** Dia travado: desabilita reposicionamento do carro (Editar, Cancelar,
   * Adicionar, etc ja saem desligados via ausencia dos handlers acima). */
  bloqueado?: boolean;
}

export default function CarroCard({
  viagens,
  empresas,
  veiculos,
  condutores,
  locais,
  regioes,
  tituloSemVeiculo = "Carro sem veiculo",
  periodoAtual,
  posicao,
  totalNoPeriodo,
  onMoverEsquerda,
  onMoverDireita,
  onEditarPosicao,
  onAdicionarPassageiro,
  onRemoverPassageiro,
  onCancelarPassageiro,
  onEditarPassageiro,
  onAtribuir,
  onLimparCondutorVeiculo,
  onRemoverViagem,
  bloqueado = false,
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

  // Ancora do bloco: a perna com grupo_viagem_id nulo (ou a unica perna, se o
  // carro so tem uma). Usada pro droppable do bloco inteiro -- soltar um
  // passageiro fora de uma leg especifica (ex: no espaco entre pernas ou no
  // cabecalho) usa o horario/sentido dele proprio pra achar ou criar a leg
  // certa dentro desse carro, igual ao modo Base.
  const blocoId = pernas.find((v) => v.grupo_viagem_id === null)?.id ?? primeira.id;
  const { setNodeRef: setBlocoRef, isOver: isOverBloco } = useDroppable({
    id: `bloco-${blocoId}`,
    data: { blocoId },
  });

  // Regiao de cada passageiro (nao da viagem/leg) -- cobre tanto o condutor
  // com pernas em regioes diferentes ao longo do dia quanto um unico carro
  // misturando passageiros de regioes diferentes (grupo da Base cross-regiao).
  const regiaoIdsPassageiros = pernas.flatMap((v) =>
    v.passageiros.map((p) => (p.sentido === "Retorno" && p.regiao_destino_id != null ? p.regiao_destino_id : p.regiao_origem_id)),
  );
  const regiaoNomes = [...new Set(regiaoIdsPassageiros)].map((id) => regioes.find((r) => r.id === id)?.nome ?? "?");

  return (
    <div ref={setBlocoRef} className="carro-card" style={{ outline: isOverBloco ? "2px dashed var(--cor-primaria)" : "none" }}>
      <div className="carro-card-ordem">
        <button
          type="button"
          className="btn btn-sm"
          disabled={bloqueado || posicao <= 1}
          title="Mover carro para tras"
          onClick={onMoverEsquerda}
        >
          ←
        </button>
        <button
          type="button"
          className="badge-ordem"
          disabled={bloqueado}
          title={bloqueado ? "Dia travado" : "Definir posicao"}
          onClick={onEditarPosicao}
        >
          {posicao}/{totalNoPeriodo}
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={bloqueado || posicao >= totalNoPeriodo}
          title="Mover carro para frente"
          onClick={onMoverDireita}
        >
          →
        </button>
      </div>
      <div className="carro-card-topo">
        <div className="titulo">{veiculo ? veiculo.prefixo : tituloSemVeiculo}</div>
        <span className="tag tag-regiao" title="Regiao do veiculo">
          {regiaoNomes.join(" · ")}
        </span>
      </div>
      {onAtribuir && (
        <>
          <div className="meta">
            {empresa?.nome ?? "Sem empresa"} ·{" "}
            <b style={{ textTransform: "uppercase" }}>
              {condutor ? condutor.apelido || condutor.nome : "Sem condutor"}
            </b>
          </div>
          {primeira.intervalo_inicio && primeira.intervalo_fim && (
            <div className="meta">
              Intervalo {primeira.intervalo_inicio.slice(0, 5)} - {primeira.intervalo_fim.slice(0, 5)}
            </div>
          )}
          <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.3rem" }}>
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
            {onLimparCondutorVeiculo && (primeira.condutor_id !== null || primeira.veiculo_id !== null) && (
              <button
                className="btn btn-sm"
                title="Remove condutor e veiculo do carro, mantendo as viagens e passageiros"
                onClick={() => onLimparCondutorVeiculo(pernas.map((v) => v.id))}
              >
                Limpar
              </button>
            )}
          </div>
        </>
      )}

      {pernas.map((viagem, indice) => (
        <LegBlock
          key={viagem.id}
          viagem={viagem}
          isPrimeira={indice === 0}
          locais={locais}
          periodoAtual={periodoAtual}
          onAdicionarPassageiro={onAdicionarPassageiro}
          onRemoverPassageiro={onRemoverPassageiro}
          onCancelarPassageiro={onCancelarPassageiro}
          onEditarPassageiro={onEditarPassageiro}
          onRemoverViagem={onRemoverViagem}
        />
      ))}
    </div>
  );
}
