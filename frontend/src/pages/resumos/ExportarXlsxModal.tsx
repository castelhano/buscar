import { useState } from "react";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  onFechar: () => void;
  onExportar: (incluirCanceladosEmpresa: boolean) => void;
}

export default function ExportarXlsxModal({ onFechar, onExportar }: Props) {
  useLockBodyScroll();
  const [incluirCanceladosEmpresa, setIncluirCanceladosEmpresa] = useState(true);

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Exportar XLSX</h3>
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={incluirCanceladosEmpresa}
              onChange={(e) => setIncluirCanceladosEmpresa(e.target.checked)}
              autoFocus
            />{" "}
            Incluir cancelamentos motivados pela empresa na aba Dados
          </label>
        </div>
        <p style={{ fontSize: "0.85em", opacity: 0.75 }}>
          Afeta somente a aba Dados. Os resumos de cancelamento sempre desconsideram os cancelamentos da empresa.
        </p>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primario" onClick={() => onExportar(incluirCanceladosEmpresa)}>
            Exportar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
