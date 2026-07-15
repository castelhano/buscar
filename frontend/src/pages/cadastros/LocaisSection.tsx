import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Local, Regiao, TipoLocal } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";

const TIPOS: TipoLocal[] = ["Escola", "Fisioterapia", "Equoterapia", "Trabalho", "Hemodialise", "Medico", "Outros"];

interface FormState {
  nome: string;
  tipo: TipoLocal;
  regiao_id: number | "";
  observacao: string;
}

const vazio: FormState = { nome: "", tipo: "Escola", regiao_id: "", observacao: "" };

export default function LocaisSection() {
  const { data: locais, error } = useList<Local>("locais", "/locais");
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const criar = useCreate<Local, unknown>("locais", "/locais");
  const atualizar = useUpdate<Local, unknown>("locais", "/locais");
  const remover = useRemove("locais", "/locais");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);

  function payload() {
    return { nome: form.nome, tipo: form.tipo, regiao_id: form.regiao_id, observacao: form.observacao || null };
  }

  function salvar() {
    if (!form.nome.trim() || form.regiao_id === "") return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: payload() }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(payload(), { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(local: Local) {
    setEditandoId(local.id);
    setForm({ nome: local.nome, tipo: local.tipo, regiao_id: local.regiao_id, observacao: local.observacao ?? "" });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  function nomeRegiao(id: number) {
    return regioes?.find((r) => r.id === id)?.nome ?? "-";
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar locais.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Nome</label>
          <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex: Escola Municipal X" />
        </div>
        <div className="campo">
          <label>Tipo</label>
          <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoLocal })}>
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Regiao</label>
          <select
            value={form.regiao_id}
            onChange={(e) => setForm({ ...form, regiao_id: e.target.value ? Number(e.target.value) : "" })}
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
            <th>Nome</th>
            <th>Tipo</th>
            <th>Regiao</th>
            <th>Observacao</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(locais ?? []).map((l) => (
            <tr key={l.id}>
              <td>{l.nome}</td>
              <td>{l.tipo}</td>
              <td>{nomeRegiao(l.regiao_id)}</td>
              <td>{l.observacao ?? "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(l)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(l.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover local"
          mensagem="Remover este local? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover local");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
