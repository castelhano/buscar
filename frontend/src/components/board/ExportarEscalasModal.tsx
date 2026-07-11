import { useState } from "react";
import { api, ApiError } from "../../api/client";
import { useList } from "../../api/hooks";
import type { Condutor } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  onFechar: () => void;
}

export default function ExportarEscalasModal({ onFechar }: Props) {
  useLockBodyScroll();
  const { data: condutores } = useList<Condutor>("condutores", "/condutores");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [formato, setFormato] = useState<"pdf" | "csv">("csv");
  const [condutorId, setCondutorId] = useState<number | "">("");
  const [erro, setErro] = useState<string | null>(null);

  function exportar() {
    if (!inicio || !fim) return;
    setErro(null);
    api
      .download("/frequencia/escalas/exportar", {
        inicio,
        fim,
        formato,
        condutor_id: condutorId === "" ? undefined : condutorId,
      })
      .catch((e: unknown) => setErro(e instanceof ApiError ? String(e.detail) : "Erro ao exportar escalas"));
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Exportar escalas</h3>
        {erro && (
          <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
            {erro} (clique para fechar)
          </div>
        )}
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
