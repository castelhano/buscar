import { useState } from "react";
import type { Condutor, Empresa, Veiculo } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  condutores: Condutor[];
  veiculos: Veiculo[];
  empresas: Empresa[];
  condutorAtualId?: number | null;
  veiculoAtualId?: number | null;
  periodo: "Manha" | "Tarde";
  veiculosEscaladosIds: Set<number>;
  condutoresEscaladosIds: Set<number>;
  condutoresFeriasIds: Set<number>;
  onFechar: () => void;
  onConfirmar: (dados: { condutor_id: number | null; veiculo_id: number | null }) => void;
}

function iniciaisEmpresa(nome: string): string {
  return nome.slice(0, 2).toUpperCase();
}

function prefixoPeriodo(condutor: Condutor): string {
  return condutor.periodo === "Manha" ? "1P" : "2P";
}

function labelCondutor(condutor: Condutor, empresas: Empresa[]): string {
  const empresa = empresas.find((e) => e.id === condutor.empresa_id);
  const nome = condutor.apelido || condutor.nome;
  const prefixo = prefixoPeriodo(condutor);
  return empresa ? `${prefixo} ${nome} - ${iniciaisEmpresa(empresa.nome)}` : `${prefixo} ${nome}`;
}

function Badge({
  label,
  selecionado,
  estado,
  riscado,
  onClick,
}: {
  label: string;
  selecionado: boolean;
  estado: "atual" | "escalado" | "livre";
  riscado?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`badge-selecao badge-selecao-${estado}`}
      style={{
        outline: selecionado ? "2px solid var(--cor-primaria)" : "none",
        outlineOffset: "1px",
        textDecoration: riscado ? "line-through" : "none",
      }}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function Legenda() {
  return (
    <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", fontSize: "0.75rem", color: "var(--cor-texto-suave)" }}>
      <span>
        <span className="badge-selecao badge-selecao-atual badge-legenda" /> Atual
      </span>
      <span>
        <span className="badge-selecao badge-selecao-escalado badge-legenda" /> Escalado no periodo
      </span>
      <span>
        <span className="badge-selecao badge-selecao-livre badge-legenda" /> Livre no periodo
      </span>
    </div>
  );
}

export default function AtribuirModal({
  condutores,
  veiculos,
  empresas,
  condutorAtualId,
  veiculoAtualId,
  periodo,
  veiculosEscaladosIds,
  condutoresEscaladosIds,
  condutoresFeriasIds,
  onFechar,
  onConfirmar,
}: Props) {
  useLockBodyScroll();
  const [condutorId, setCondutorId] = useState<number | null>(condutorAtualId ?? null);
  const [veiculoId, setVeiculoId] = useState<number | null>(veiculoAtualId ?? null);

  const condutorSelecionado = condutores.find((c) => c.id === condutorId);
  const condutorSelecionadoEmFerias = condutorSelecionado != null && condutoresFeriasIds.has(condutorSelecionado.id);

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <h3>Atribuir condutor/veiculo - Periodo {periodo}</h3>
        <Legenda />

        <div className="campo" style={{ marginTop: "0.8rem" }}>
          <label>Carro</label>
          <div className="badge-grade">
            {veiculos.map((v) => (
              <Badge
                key={v.id}
                label={v.prefixo}
                selecionado={veiculoId === v.id}
                estado={v.id === veiculoAtualId ? "atual" : veiculosEscaladosIds.has(v.id) ? "escalado" : "livre"}
                onClick={() => setVeiculoId(v.id)}
              />
            ))}
          </div>
        </div>

        <div className="campo" style={{ marginTop: "1rem" }}>
          <label>Condutor</label>
          <div className="badge-grade">
            {condutores.map((c) => (
              <Badge
                key={c.id}
                label={labelCondutor(c, empresas)}
                selecionado={condutorId === c.id}
                estado={c.id === condutorAtualId ? "atual" : condutoresEscaladosIds.has(c.id) ? "escalado" : "livre"}
                riscado={condutoresFeriasIds.has(c.id)}
                onClick={() => setCondutorId(c.id)}
              />
            ))}
          </div>
          {condutorSelecionadoEmFerias && (
            <div className="aviso-discreto" style={{ marginTop: "0.5rem" }}>
              Atencao: {labelCondutor(condutorSelecionado, empresas)} esta de ferias nessa data.
            </div>
          )}
        </div>

        <div className="linha-toolbar" style={{ marginTop: "1.2rem" }}>
          <button
            className="btn btn-primario"
            onClick={() =>
              onConfirmar({
                condutor_id: condutorId,
                veiculo_id: veiculoId,
              })
            }
          >
            Salvar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
