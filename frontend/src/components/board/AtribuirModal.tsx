import { useState } from "react";
import type { Condutor, Veiculo } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  condutores: Condutor[];
  veiculos: Veiculo[];
  onFechar: () => void;
  onConfirmar: (dados: { condutor_id: number | null; veiculo_id: number | null }) => void;
}

export default function AtribuirModal({ condutores, veiculos, onFechar, onConfirmar }: Props) {
  useLockBodyScroll();
  const [condutorId, setCondutorId] = useState<number | "">("");
  const [veiculoId, setVeiculoId] = useState<number | "">("");

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Atribuir condutor/veiculo</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          <div className="campo">
            <label>Veiculo</label>
            <select value={veiculoId} onChange={(e) => setVeiculoId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Manter atual</option>
              {veiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.prefixo} ({v.placa})
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Condutor</label>
            <select value={condutorId} onChange={(e) => setCondutorId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Manter atual</option>
              {condutores.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primario"
            onClick={() =>
              onConfirmar({
                condutor_id: condutorId === "" ? null : condutorId,
                veiculo_id: veiculoId === "" ? null : veiculoId,
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
