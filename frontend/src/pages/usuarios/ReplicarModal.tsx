import { useState } from "react";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana } from "../../api/types";

interface Props {
  diaAtual: DiaSemana;
  onFechar: () => void;
  onConfirmar: (dias: DiaSemana[]) => void;
  enviando?: boolean;
}

export default function ReplicarModal({ diaAtual, onFechar, onConfirmar, enviando = false }: Props) {
  useLockBodyScroll();
  const [selecionados, setSelecionados] = useState<DiaSemana[]>([]);

  function alternar(dia: DiaSemana) {
    setSelecionados((atual) => (atual.includes(dia) ? atual.filter((d) => d !== dia) : [...atual, dia]));
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" style={{ width: "min(90vw, 400px)" }} onClick={(e) => e.stopPropagation()}>
        <h3>Replicar atendimento</h3>
        <p>Selecione os dias que devem receber uma copia deste atendimento.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {DIAS_SEMANA.map((dia) => (
            <label
              key={dia}
              style={{ display: "flex", gap: "0.5rem", alignItems: "center", fontWeight: "normal" }}
            >
              <input
                type="checkbox"
                disabled={dia === diaAtual}
                checked={dia === diaAtual || selecionados.includes(dia)}
                onChange={() => alternar(dia)}
              />
              {DIAS_SEMANA_LABEL[dia]}
              {dia === diaAtual && " (atual)"}
            </label>
          ))}
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primario"
            onClick={() => onConfirmar(selecionados)}
            disabled={enviando || selecionados.length === 0}
          >
            Replicar
          </button>
          <button className="btn" onClick={onFechar} disabled={enviando}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
