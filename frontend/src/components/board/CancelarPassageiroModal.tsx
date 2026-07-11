import { useState } from "react";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  onFechar: () => void;
  onConfirmar: (motivo: string) => void;
}

export default function CancelarPassageiroModal({ onFechar, onConfirmar }: Props) {
  useLockBodyScroll();
  const [motivo, setMotivo] = useState("");

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Cancelar atendimento</h3>
        <div className="campo">
          <label>Motivo (quem cancelou, por que, etc.)</label>
          <textarea
            rows={3}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ex: usuario avisou que nao vai precisar hoje"
            autoFocus
          />
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-perigo" onClick={() => onConfirmar(motivo)}>
            Confirmar cancelamento
          </button>
          <button className="btn" onClick={onFechar}>
            Voltar
          </button>
        </div>
      </div>
    </div>
  );
}
