import { useState } from "react";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  onFechar: () => void;
  onConfirmar: (motivo: string, cancelarTodos: boolean, viagemPerdida: boolean, canceladoPelaEmpresa: boolean) => void;
  temOutrosAtendimentos?: boolean;
}

export default function CancelarPassageiroModal({ onFechar, onConfirmar, temOutrosAtendimentos = true }: Props) {
  useLockBodyScroll();
  const [motivo, setMotivo] = useState("");
  const [cancelarTodos, setCancelarTodos] = useState(true);
  const [viagemPerdida, setViagemPerdida] = useState(false);
  const [canceladoPelaEmpresa, setCanceladoPelaEmpresa] = useState(false);

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
        {temOutrosAtendimentos && (
          <div className="campo">
            <label>
              <input
                type="checkbox"
                checked={cancelarTodos}
                onChange={(e) => setCancelarTodos(e.target.checked)}
              />{" "}
              Cancelar todos os atendimentos
            </label>
          </div>
        )}
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={viagemPerdida}
              onChange={(e) => {
                setViagemPerdida(e.target.checked);
                if (e.target.checked) setCanceladoPelaEmpresa(false);
              }}
            />{" "}
            Viagem perdida
          </label>
        </div>
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={canceladoPelaEmpresa}
              onChange={(e) => {
                setCanceladoPelaEmpresa(e.target.checked);
                if (e.target.checked) setViagemPerdida(false);
              }}
            />{" "}
            Cancelamento motivado pela empresa
          </label>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-perigo"
            onClick={() => onConfirmar(motivo, cancelarTodos, viagemPerdida, canceladoPelaEmpresa)}
          >
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
