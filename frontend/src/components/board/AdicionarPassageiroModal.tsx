import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useList } from "../../api/hooks";
import type { DiaSemana, Local, Regiao, Sentido, Usuario, UsuarioAgendaSemanal } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

export interface PassageiroFormValores {
  sentido: Sentido;
  hora: string;
  origem: string;
  regiao_origem_id: number | "";
  destino_id: number | "";
  acompanhante: boolean;
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
    acompanhante: boolean;
    observacoes: string | null;
  }) => void;
  titulo?: string;
  textoConfirmar?: string;
  /** Quando informado, o usuario nao pode ser trocado (usado ao editar um atendimento ja lancado). */
  usuarioFixo?: { id: number; nome: string };
  valoresIniciais?: Partial<PassageiroFormValores>;
  /** Dia da semana da viagem, pra sugerir os dados do Eventual cadastrado do usuario (so na insercao nova). */
  diaSemana: DiaSemana;
  /** Dia travado: mostra os dados so pra consulta, sem permitir edicao. */
  somenteLeitura?: boolean;
}

export default function AdicionarPassageiroModal({
  onFechar,
  onConfirmar,
  titulo = "Adicionar passageiro",
  textoConfirmar = "Adicionar",
  usuarioFixo,
  valoresIniciais,
  diaSemana,
  somenteLeitura = false,
}: Props) {
  useLockBodyScroll();
  const { data: usuarios } = useList<Usuario>("usuarios", "/usuarios", { status: "Ativo" });
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: locais } = useList<Local>("locais", "/locais");

  const [usuarioId, setUsuarioId] = useState<number | "">(usuarioFixo?.id ?? "");
  const [sentido, setSentido] = useState<Sentido>(valoresIniciais?.sentido ?? "Ida");
  const [hora, setHora] = useState(valoresIniciais?.hora ?? "");
  const [origem, setOrigem] = useState(valoresIniciais?.origem ?? "");
  const [regiaoOrigemId, setRegiaoOrigemId] = useState<number | "">(valoresIniciais?.regiao_origem_id ?? "");
  const [destinoId, setDestinoId] = useState<number | "">(valoresIniciais?.destino_id ?? "");
  const [acompanhante, setAcompanhante] = useState(valoresIniciais?.acompanhante ?? false);
  const [observacoes, setObservacoes] = useState(valoresIniciais?.observacoes ?? "");

  const eventuaisQuery = useQuery({
    queryKey: ["usuario-agenda-semanal", usuarioId],
    queryFn: () => api.get<UsuarioAgendaSemanal[]>(`/usuarios/${usuarioId}/agenda-semanal`),
    enabled: !usuarioFixo && usuarioId !== "",
  });
  const eventuais = (eventuaisQuery.data ?? []).filter((a) => a.tipo === "Eventual" && a.dia_semana === diaSemana);

  function usarEventual(ev: UsuarioAgendaSemanal) {
    const horaEventual = sentido === "Ida" ? ev.saida : ev.retorno;
    if (horaEventual) setHora(horaEventual.slice(0, 5));
    setOrigem(ev.origem ?? "");
    setRegiaoOrigemId(ev.regiao_origem_id ?? "");
    setDestinoId(ev.destino_id ?? "");
    setAcompanhante(ev.acompanhante);
  }

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
      acompanhante,
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
              <select
                value={usuarioId}
                disabled={somenteLeitura}
                onChange={(e) => setUsuarioId(e.target.value ? Number(e.target.value) : "")}
              >
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
            <select value={sentido} disabled={somenteLeitura} onChange={(e) => setSentido(e.target.value as Sentido)}>
              <option value="Ida">Ida</option>
              <option value="Retorno">Retorno</option>
            </select>
          </div>
          {!somenteLeitura && eventuais.length > 0 && (
            <div className="campo">
              <label>Eventual cadastrado pra esse dia</label>
              <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                {eventuais.map((ev) => (
                  <button key={ev.id} type="button" className="btn btn-sm" onClick={() => usarEventual(ev)}>
                    Usar {ev.saida?.slice(0, 5) ?? "-"} / {ev.retorno?.slice(0, 5) ?? "-"} ·{" "}
                    {locais?.find((l) => l.id === ev.destino_id)?.nome ?? "sem destino"}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="campo">
            <label>Hora</label>
            <input type="time" value={hora} disabled={somenteLeitura} onChange={(e) => setHora(e.target.value)} />
          </div>
          <div className="campo">
            <label>Origem</label>
            <input
              value={origem}
              disabled={somenteLeitura}
              onChange={(e) => setOrigem(e.target.value)}
              placeholder="Endereco de origem"
            />
          </div>
          <div className="campo">
            <label>Regiao de origem</label>
            <select
              value={regiaoOrigemId}
              disabled={somenteLeitura}
              onChange={(e) => setRegiaoOrigemId(e.target.value ? Number(e.target.value) : "")}
            >
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
            <select
              value={destinoId}
              disabled={somenteLeitura}
              onChange={(e) => setDestinoId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">Selecione</option>
              {(locais ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          </div>
          <label style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={acompanhante}
              disabled={somenteLeitura}
              onChange={(e) => setAcompanhante(e.target.checked)}
            />
            Acompanhante (ocupa 2 lugares no veiculo)
          </label>
          <div className="campo">
            <label>Observacoes</label>
            <textarea rows={3} value={observacoes} disabled={somenteLeitura} onChange={(e) => setObservacoes(e.target.value)} />
          </div>
        </div>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          {!somenteLeitura && (
            <button className="btn btn-primario" onClick={confirmar}>
              {textoConfirmar}
            </button>
          )}
          <button className="btn" onClick={onFechar}>
            {somenteLeitura ? "Fechar" : "Cancelar"}
          </button>
        </div>
      </div>
    </div>
  );
}
