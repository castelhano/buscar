import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Condutor, CondutorFerias } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";
import { formatarData } from "../../utils/data";

interface FormState {
  condutor_id: number | "";
  data_inicio: string;
  data_fim: string;
  observacao: string;
}

const vazio: FormState = { condutor_id: "", data_inicio: "", data_fim: "", observacao: "" };

export default function FeriasSection() {
  const { data: ferias, error } = useList<CondutorFerias>("ferias", "/ferias");
  const { data: condutores } = useList<Condutor>("condutores", "/condutores");
  const criar = useCreate<CondutorFerias, unknown>("ferias", "/ferias");
  const atualizar = useUpdate<CondutorFerias, unknown>("ferias", "/ferias");
  const remover = useRemove("ferias", "/ferias");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);

  function payload() {
    return { condutor_id: form.condutor_id, data_inicio: form.data_inicio, data_fim: form.data_fim, observacao: form.observacao || null };
  }

  function salvar() {
    if (form.condutor_id === "" || !form.data_inicio || !form.data_fim) return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: payload() }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(payload(), { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(f: CondutorFerias) {
    setEditandoId(f.id);
    setForm({ condutor_id: f.condutor_id, data_inicio: f.data_inicio, data_fim: f.data_fim, observacao: f.observacao ?? "" });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  function nomeCondutor(id: number) {
    return condutores?.find((c) => c.id === id)?.nome ?? "-";
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar ferias.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Condutor</label>
          <select value={form.condutor_id} onChange={(e) => setForm({ ...form, condutor_id: e.target.value ? Number(e.target.value) : "" })}>
            <option value="">Selecione</option>
            {(condutores ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
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
          <input value={form.observacao} onChange={(e) => setForm({ ...form, observacao: e.target.value })} />
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
            <th>Condutor</th>
            <th>Inicio</th>
            <th>Fim</th>
            <th>Observacao</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(ferias ?? []).map((f) => (
            <tr key={f.id}>
              <td>{nomeCondutor(f.condutor_id)}</td>
              <td>{formatarData(f.data_inicio)}</td>
              <td>{formatarData(f.data_fim)}</td>
              <td>{f.observacao ?? "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(f)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(f.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover ferias"
          mensagem="Remover este periodo de ferias? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover ferias");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
