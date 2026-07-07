import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Local, Regiao, TipoLocal } from "../../api/types";

const TIPOS: TipoLocal[] = ["Escola", "Fisioterapia", "Trabalho", "Hemodialise", "Outros"];

interface FormState {
  nome: string;
  tipo: TipoLocal;
  regiao_id: number | "";
}

const vazio: FormState = { nome: "", tipo: "Escola", regiao_id: "" };

export default function LocaisSection() {
  const { data: locais, error } = useList<Local>("locais", "/locais");
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const criar = useCreate<Local, FormState>("locais", "/locais");
  const atualizar = useUpdate<Local, FormState>("locais", "/locais");
  const remover = useRemove("locais", "/locais");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  function salvar() {
    if (!form.nome.trim() || form.regiao_id === "") return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: form }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(form, { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(local: Local) {
    setEditandoId(local.id);
    setForm({ nome: local.nome, tipo: local.tipo, regiao_id: local.regiao_id });
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
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(locais ?? []).map((l) => (
            <tr key={l.id}>
              <td>{l.nome}</td>
              <td>{l.tipo}</td>
              <td>{nomeRegiao(l.regiao_id)}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(l)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => remover.mutate(l.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
