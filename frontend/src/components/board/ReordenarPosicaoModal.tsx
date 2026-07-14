import { useState } from "react";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  posicaoAtual: number;
  total: number;
  onFechar: () => void;
  onConfirmar: (novaPosicao: number) => void;
}

export default function ReordenarPosicaoModal({ posicaoAtual, total, onFechar, onConfirmar }: Props) {
  useLockBodyScroll();
  const [posicao, setPosicao] = useState(posicaoAtual);

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Mover carro</h3>
        <div className="campo">
          <label>Nova posicao (1 a {total})</label>
          <input
            type="number"
            min={1}
            max={total}
            value={posicao}
            onChange={(e) => setPosicao(Number(e.target.value))}
          />
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primario"
            onClick={() => onConfirmar(Math.max(1, Math.min(posicao, total)))}
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
