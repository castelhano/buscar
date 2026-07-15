import { useState } from "react";
import { api } from "../../api/client";
import type { Condutor } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  data: string;
  condutores: Condutor[];
  onFechar: () => void;
  onErro: (mensagem: string) => void;
}

export default function ExportarAgendamentosModal({ data, condutores, onFechar, onErro }: Props) {
  useLockBodyScroll();
  const [condutorId, setCondutorId] = useState<number | "">("");

  function gerar() {
    const download =
      condutorId === ""
        ? api.download("/viagens/agendamentos/zip", { data })
        : api.download("/viagens/agendamentos/pdf", { data, condutor_id: condutorId });
    download.catch((e: unknown) => onErro(e instanceof Error ? e.message : "Erro ao baixar agendamentos"));
    onFechar();
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Agendamentos</h3>
        <div className="campo">
          <label>Condutor</label>
          <select value={condutorId} onChange={(e) => setCondutorId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Todos</option>
            {condutores.map((c) => (
              <option key={c.id} value={c.id}>
                {c.apelido || c.nome}
              </option>
            ))}
          </select>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primario" onClick={gerar}>
            Gerar
          </button>
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
