import { useState } from "react";
import { useList } from "../../api/hooks";
import type { Local, Regiao, Sentido, Usuario } from "../../api/types";

interface Props {
  onFechar: () => void;
  onConfirmar: (dados: {
    usuario_id: number;
    sentido: Sentido;
    hora: string;
    origem: string | null;
    regiao_origem_id: number | null;
    destino_id: number | null;
    regiao_destino_id: number | null;
  }) => void;
}

export default function AdicionarPassageiroModal({ onFechar, onConfirmar }: Props) {
  const { data: usuarios } = useList<Usuario>("usuarios", "/usuarios", { status: "Ativo" });
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: locais } = useList<Local>("locais", "/locais");

  const [usuarioId, setUsuarioId] = useState<number | "">("");
  const [sentido, setSentido] = useState<Sentido>("Ida");
  const [hora, setHora] = useState("");
  const [origem, setOrigem] = useState("");
  const [regiaoOrigemId, setRegiaoOrigemId] = useState<number | "">("");
  const [destinoId, setDestinoId] = useState<number | "">("");

  function confirmar() {
    if (usuarioId === "" || !hora) return;
    const destino = destinoId === "" ? null : locais?.find((l) => l.id === destinoId);
    onConfirmar({
      usuario_id: usuarioId,
      sentido,
      hora,
      origem: origem || null,
      regiao_origem_id: regiaoOrigemId === "" ? null : regiaoOrigemId,
      destino_id: destinoId === "" ? null : destinoId,
      regiao_destino_id: destino ? destino.regiao_id : null,
    });
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Adicionar passageiro</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          <div className="campo">
            <label>Usuario</label>
            <select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Selecione</option>
              {(usuarios ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Sentido</label>
            <select value={sentido} onChange={(e) => setSentido(e.target.value as Sentido)}>
              <option value="Ida">Ida</option>
              <option value="Retorno">Retorno</option>
            </select>
          </div>
          <div className="campo">
            <label>Hora</label>
            <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
          </div>
          <div className="campo">
            <label>Origem</label>
            <input value={origem} onChange={(e) => setOrigem(e.target.value)} placeholder="Endereco de origem" />
          </div>
          <div className="campo">
            <label>Regiao de origem</label>
            <select value={regiaoOrigemId} onChange={(e) => setRegiaoOrigemId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Selecione</option>
              {(regioes ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Destino</label>
            <select value={destinoId} onChange={(e) => setDestinoId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Selecione</option>
              {(locais ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primario" onClick={confirmar}>
            Adicionar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
