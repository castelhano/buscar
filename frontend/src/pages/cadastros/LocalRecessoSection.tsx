import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Local, LocalRecesso } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";

interface FormState {
  local_id: number | "";
  data_inicio: string;
  data_fim: string;
  observacao: string;
}

const vazio: FormState = { local_id: "", data_inicio: "", data_fim: "", observacao: "" };

export default function LocalRecessoSection() {
  const { data: recessos, error } = useList<LocalRecesso>("locais-recesso", "/locais-recesso");
  const { data: locais } = useList<Local>("locais", "/locais");
  const criar = useCreate<LocalRecesso, unknown>("locais-recesso", "/locais-recesso");
  const atualizar = useUpdate<LocalRecesso, unknown>("locais-recesso", "/locais-recesso");
  const remover = useRemove("locais-recesso", "/locais-recesso");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);

  function payload() {
    return { local_id: form.local_id, data_inicio: form.data_inicio, data_fim: form.data_fim, observacao: form.observacao || null };
  }

  function salvar() {
    if (form.local_id === "" || !form.data_inicio || !form.data_fim) return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: payload() }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(payload(), { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(r: LocalRecesso) {
    setEditandoId(r.id);
    setForm({ local_id: r.local_id, data_inicio: r.data_inicio, data_fim: r.data_fim, observacao: r.observacao ?? "" });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  function nomeLocal(id: number) {
    return locais?.find((l) => l.id === id)?.nome ?? "-";
  }

  return (
    <div>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Periodo em que um local fica fechado (ex: recesso escolar) -- usuarios com destino nesse local nao sao
        agendados nesse intervalo.
      </p>
      {error && <div className="erro-box">Erro ao carregar recessos.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Local</label>
          <select value={form.local_id} onChange={(e) => setForm({ ...form, local_id: e.target.value ? Number(e.target.value) : "" })}>
            <option value="">Selecione</option>
            {(locais ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.nome}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Inicio</label>
          <input type="date" value={form.data_inicio} onChange={(e) => setForm({ ...form, data_inicio: e.target.value })} />
        </div>
        <div className="campo">
          <label>Fim</label>
          <input type="date" value={form.data_fim} onChange={(e) => setForm({ ...form, data_fim: e.target.value })} />
        </div>
        <div className="campo">
          <label>Observacao</label>
          <input value={form.observacao} onChange={(e) => setForm({ ...form, observacao: e.target.value })} placeholder="Ex: Recesso escolar de julho" />
        </div>
        <button className="btn btn-primario" onClick={salvar} disabled={criar.isPending || atualizar.isPending}>
          {editandoId !== null ? "Salvar edicao" : "Adicionar"}
        </button>
        {editandoId !== null && (
          <button className="btn" onClick={cancelarEdicao}>
            Cancelar
          </button>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Local</th>
            <th>Inicio</th>
            <th>Fim</th>
            <th>Observacao</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(recessos ?? []).map((r) => (
            <tr key={r.id}>
              <td>{nomeLocal(r.local_id)}</td>
              <td>{r.data_inicio}</td>
              <td>{r.data_fim}</td>
              <td>{r.observacao ?? "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(r)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(r.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover recesso"
          mensagem="Remover este periodo de recesso? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover recesso");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
