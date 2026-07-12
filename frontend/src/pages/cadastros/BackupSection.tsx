import { useState } from "react";
import { api } from "../../api/client";

export default function BackupSection() {
  const [erro, setErro] = useState<string | null>(null);

  return (
    <div>
      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}
      <h4 style={{ marginTop: 0 }}>Backup dos dados</h4>
      <p style={{ fontSize: "0.85rem", color: "var(--cor-texto-suave)" }}>
        Baixa uma copia completa dos dados do sistema neste momento. Guarde o arquivo em algum lugar fora deste
        computador (pendrive, pasta de nuvem, etc.) -- o ideal e repetir isso periodicamente, principalmente apos o
        uso, pra nao perder informacao em caso de problema com esta maquina.
      </p>
      <button
        className="btn btn-primario"
        onClick={() =>
          api.download("/backup").catch((e: unknown) => setErro(e instanceof Error ? e.message : "Erro ao baixar backup"))
        }
      >
        Baixar backup
      </button>
    </div>
  );
}
