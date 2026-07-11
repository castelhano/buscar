import { useState } from "react";
import { useList } from "../../api/hooks";
import type { Local, Regiao, Sentido, Usuario } from "../../api/types";

export interface PassageiroFormValores {
  sentido: Sentido;
  hora: string;
  origem: string;
  regiao_origem_id: number | "";
  destino_id: number | "";
  observacoes: string;
}

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
    observacoes: string | null;
  }) => void;
  titulo?: string;
  textoConfirmar?: string;
  /** Quando informado, o usuario nao pode ser trocado (usado ao editar um atendimento ja lancado). */
  usuarioFixo?: { id: number; nome: string };
  valoresIniciais?: Partial<PassageiroFormValores>;
}

export default function AdicionarPassageiroModal({
  onFechar,
  onConfirmar,
  titulo = "Adicionar passageiro",
  textoConfirmar = "Adicionar",
  usuarioFixo,
  valoresIniciais,
}: Props) {
  const { data: usuarios } = useList<Usuario>("usuarios", "/usuarios", { status: "Ativo" });
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: locais } = useList<Local>("locais", "/locais");

  const [usuarioId, setUsuarioId] = useState<number | "">(usuarioFixo?.id ?? "");
  const [sentido, setSentido] = useState<Sentido>(valoresIniciais?.sentido ?? "Ida");
  const [hora, setHora] = useState(valoresIniciais?.hora ?? "");
  const [origem, setOrigem] = useState(valoresIniciais?.origem ?? "");
  const [regiaoOrigemId, setRegiaoOrigemId] = useState<number | "">(valoresIniciais?.regiao_origem_id ?? "");
  const [destinoId, setDestinoId] = useState<number | "">(valoresIniciais?.destino_id ?? "");
  const [observacoes, setObservacoes] = useState(valoresIniciais?.observacoes ?? "");

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
      observacoes: observacoes.trim() === "" ? null : observacoes,
    });
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
          <div className="campo">
            <label>Usuario</label>
            {usuarioFixo ? (
              <input value={usuarioFixo.nome} disabled />
            ) : (
              <select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Selecione</option>
                {(usuarios ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </select>
            )}
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
          <div className="campo">
            <label>Observacoes</label>
            <textarea rows={3} value={observacoes} onChange={(e) => setObservacoes(e.target.value)} />
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primario" onClick={confirmar}>
            {textoConfirmar}
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
