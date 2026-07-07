import { useState } from "react";
import { api } from "../../api/client";
import { useList } from "../../api/hooks";
import type { Condutor } from "../../api/types";

interface Props {
  onFechar: () => void;
}

export default function ExportarEscalasModal({ onFechar }: Props) {
  const { data: condutores } = useList<Condutor>("condutores", "/condutores");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [formato, setFormato] = useState<"pdf" | "csv">("csv");
  const [condutorId, setCondutorId] = useState<number | "">("");

  function exportar() {
    if (!inicio || !fim) return;
    const url = api.downloadUrl("/frequencia/escalas/exportar", {
      inicio,
      fim,
      formato,
      condutor_id: condutorId === "" ? undefined : condutorId,
    });
    window.open(url, "_blank");
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Exportar escalas</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          <div className="campo">
            <label>Periodo - inicio</label>
            <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
          </div>
          <div className="campo">
            <label>Periodo - fim</label>
            <input type="date" value={fim} onChange={(e) => setFim(e.target.value)} />
          </div>
          <div className="campo">
            <label>Condutor</label>
            <select value={condutorId} onChange={(e) => setCondutorId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Todos</option>
              {(condutores ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Formato</label>
            <select value={formato} onChange={(e) => setFormato(e.target.value as "pdf" | "csv")}>
              <option value="csv">CSV</option>
              <option value="pdf">PDF</option>
            </select>
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primario" onClick={exportar}>
            Exportar
          </button>
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
