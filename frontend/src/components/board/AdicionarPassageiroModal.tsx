import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useList } from "../../api/hooks";
import type { DiaSemana, Local, Regiao, TrechoInput, Usuario, UsuarioAgendaSemanal } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import TrechoListEditor, { trechoVazio } from "../usuarios/TrechoListEditor";

interface ConfirmarDados {
  usuario_id: number;
  /** Cada item vira um `ViagemDiaPassageiro`. No modo edicao (usuarioFixo
   * definido) o array sempre tem exatamente 1 item -- o trecho editado. No
   * modo criacao pode ter N itens (itinerario completo do dia), todos
   * lancados no mesmo carro clicado; o operador reposiciona depois via
   * arrastar, igual a qualquer outro passageiro. */
  trechos: TrechoInput[];
  observacoes: string | null;
}

interface Props {
  onFechar: () => void;
  onConfirmar: (dados: ConfirmarDados) => void;
  titulo?: string;
  textoConfirmar?: string;
  /** Quando informado, o usuario nao pode ser trocado e o modal edita um
   * unico trecho ja lancado (nao permite adicionar/remover trechos). */
  usuarioFixo?: { id: number; nome: string };
  valoresIniciais?: TrechoInput & { ordem_trecho?: number };
  observacoesIniciais?: string;
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
  observacoesIniciais,
  diaSemana,
  somenteLeitura = false,
}: Props) {
  useLockBodyScroll();
  const modoEdicao = !!usuarioFixo;
  const { data: usuarios } = useList<Usuario>("usuarios", "/usuarios", { status: "Ativo" });
  const { data: locais } = useList<Local>("locais", "/locais");
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");

  const [usuarioId, setUsuarioId] = useState<number | "">(usuarioFixo?.id ?? "");
  const [trechos, setTrechos] = useState<TrechoInput[]>(valoresIniciais ? [valoresIniciais] : [trechoVazio(true)]);
  const [ordemTrechoEdicao, setOrdemTrechoEdicao] = useState(valoresIniciais?.ordem_trecho ?? 0);
  const [observacoes, setObservacoes] = useState(observacoesIniciais ?? "");

  const eventuaisQuery = useQuery({
    queryKey: ["usuario-agenda-semanal", usuarioId],
    queryFn: () => api.get<UsuarioAgendaSemanal[]>(`/usuarios/${usuarioId}/agenda-semanal`),
    enabled: !modoEdicao && usuarioId !== "",
  });
  const eventuais = (eventuaisQuery.data ?? []).filter((a) => a.tipo === "Eventual" && a.dia_semana === diaSemana);

  function usarEventual(ev: UsuarioAgendaSemanal) {
    if (ev.trechos.length === 0) return;
    setTrechos(
      ev.trechos.map((t) => ({
        hora: t.hora.slice(0, 5),
        origem_tipo: t.origem_tipo,
        origem_id: t.origem_id,
        origem_texto: t.origem_texto,
        origem_detalhe: t.origem_detalhe,
        regiao_origem_id: t.regiao_origem_id,
        destino_tipo: t.destino_tipo,
        destino_id: t.destino_id,
        destino_texto: t.destino_texto,
        destino_detalhe: t.destino_detalhe,
        regiao_destino_id: t.regiao_destino_id,
        acompanhante: t.acompanhante,
      })),
    );
  }

  function confirmar() {
    if (usuarioId === "" || trechos.some((t) => !t.hora)) return;
    onConfirmar({
      usuario_id: usuarioId,
      trechos: modoEdicao ? [{ ...trechos[0], ordem_trecho: ordemTrechoEdicao } as TrechoInput] : trechos,
      observacoes: observacoes.trim() === "" ? null : observacoes,
    });
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
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

          {modoEdicao && (
            <div className="campo" style={{ width: "160px" }}>
              <label>Posicao no itinerario</label>
              <input
                type="number"
                min={0}
                value={ordemTrechoEdicao}
                disabled={somenteLeitura}
                onChange={(e) => setOrdemTrechoEdicao(Math.max(0, Number(e.target.value)))}
              />
            </div>
          )}

          {!modoEdicao && eventuais.length > 0 && (
            <div className="campo">
              <label>Eventual cadastrado pra esse dia</label>
              <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                {eventuais.map((ev) => (
                  <button key={ev.id} type="button" className="btn btn-sm" onClick={() => usarEventual(ev)}>
                    Usar itinerario ({ev.trechos.length} trecho{ev.trechos.length !== 1 ? "s" : ""})
                  </button>
                ))}
              </div>
            </div>
          )}

          <TrechoListEditor
            trechos={trechos}
            onChange={setTrechos}
            regioes={regioes ?? []}
            locais={locais ?? []}
            somenteLeitura={somenteLeitura}
            permitirAdicionarRemover={!modoEdicao}
          />

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
