import { useState } from "react";
import { api } from "../../api/client";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  data: string;
  opcoes: { valor: string; label: string }[];
  onFechar: () => void;
  onErro: (mensagem: string) => void;
}

export default function ExportarAgendamentosModal({ data, opcoes, onFechar, onErro }: Props) {
  useLockBodyScroll();
  const [selecionado, setSelecionado] = useState("");

  function gerar() {
    const [tipo, id] = selecionado.split("-");
    const download =
      selecionado === ""
        ? api.download("/viagens/agendamentos/zip", { data })
        : api.download("/viagens/agendamentos/pdf", {
            data,
            ...(tipo === "c" ? { condutor_id: Number(id) } : { bloco_id: Number(id) }),
          });
    download.catch((e: unknown) => onErro(e instanceof Error ? e.message : "Erro ao baixar agendamentos"));
    onFechar();
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Agendamentos</h3>
        <div className="campo">
          <label>Condutor</label>
          <select value={selecionado} onChange={(e) => setSelecionado(e.target.value)}>
            <option value="">Todos</option>
            {opcoes.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.label}
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
