import { useState } from "react";
import type { Regiao } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  regioes: Regiao[];
  onFechar: () => void;
  onConfirmar: (dados: {
    regiao_id: number;
    horario_saida: string;
    capacidade_usuarios: number;
    capacidade_acompanhantes: number;
  }) => void;
}

export default function AbrirCarroModal({ regioes, onFechar, onConfirmar }: Props) {
  useLockBodyScroll();
  const [regiaoId, setRegiaoId] = useState<number | "">("");
  const [horario, setHorario] = useState("06:00");
  const [capacidadeUsuarios, setCapacidadeUsuarios] = useState(4);
  const [capacidadeAcompanhantes, setCapacidadeAcompanhantes] = useState(2);

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Abrir novo carro</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          <div className="campo">
            <label>Regiao</label>
            <select value={regiaoId} onChange={(e) => setRegiaoId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Selecione</option>
              {regioes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Horario de saida</label>
            <input type="time" value={horario} onChange={(e) => setHorario(e.target.value)} />
          </div>
          <div className="campo">
            <label>Lugares</label>
            <input
              type="number"
              min={1}
              value={capacidadeUsuarios}
              onChange={(e) => setCapacidadeUsuarios(Number(e.target.value))}
            />
          </div>
          <div className="campo">
            <label>Acompanhantes</label>
            <input
              type="number"
              min={0}
              value={capacidadeAcompanhantes}
              onChange={(e) => setCapacidadeAcompanhantes(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primario"
            onClick={() => {
              if (regiaoId === "") return;
              onConfirmar({
                regiao_id: regiaoId,
                horario_saida: horario,
                capacidade_usuarios: capacidadeUsuarios,
                capacidade_acompanhantes: capacidadeAcompanhantes,
              });
            }}
          >
            Abrir
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
