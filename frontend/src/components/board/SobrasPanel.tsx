import { useState } from "react";
import type { Sobras } from "../../api/types";

interface Props {
  sobras: Sobras;
  onMarcarFolga: (condutorIds: number[]) => void;
  aplicando: boolean;
}

export default function SobrasPanel({ sobras, onMarcarFolga, aplicando }: Props) {
  const [selecionados, setSelecionados] = useState<number[]>([]);

  function alternar(id: number) {
    setSelecionados((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function aplicar() {
    if (selecionados.length === 0) return;
    onMarcarFolga(selecionados);
    setSelecionados([]);
  }

  return (
    <div className="painel">
      <h3>Sobrando no dia</h3>
      <div className="sobras-painel">
        <div className="sobras-lista">
          <h4>Condutores ({sobras.condutores.length})</h4>
          {sobras.condutores.map((c) => (
            <label key={c.id} className="sobras-item">
              <span>
                <input type="checkbox" checked={selecionados.includes(c.id)} onChange={() => alternar(c.id)} /> {c.nome}
                {c.em_ferias && <span className="tag" style={{ marginLeft: "0.4rem" }}>Ferias</span>}
              </span>
            </label>
          ))}
          {sobras.condutores.length === 0 && <p style={{ color: "var(--cor-texto-suave)", fontSize: "0.85rem" }}>Nenhum condutor sobrando.</p>}
          <button className="btn btn-sm btn-primario" style={{ marginTop: "0.5rem" }} onClick={aplicar} disabled={aplicando || selecionados.length === 0}>
            Marcar Folga nos selecionados
          </button>
        </div>
        <div className="sobras-lista">
          <h4>Veiculos ({sobras.veiculos.length})</h4>
          {sobras.veiculos.map((v) => (
            <div key={v.id} className="sobras-item">
              <span>{v.prefixo} ({v.placa})</span>
            </div>
          ))}
          {sobras.veiculos.length === 0 && <p style={{ color: "var(--cor-texto-suave)", fontSize: "0.85rem" }}>Nenhum veiculo sobrando.</p>}
        </div>
      </div>
    </div>
  );
}
