import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Empresa, Regiao } from "../../api/types";

interface FormState {
  nome: string;
  regiao_ids: number[];
}

const vazio: FormState = { nome: "", regiao_ids: [] };

export default function EmpresasSection() {
  const { data: empresas, error } = useList<Empresa>("empresas", "/empresas");
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const criar = useCreate<Empresa, FormState>("empresas", "/empresas");
  const atualizar = useUpdate<Empresa, FormState>("empresas", "/empresas");
  const remover = useRemove("empresas", "/empresas");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  function alternarRegiao(id: number) {
    setForm((f) => ({
      ...f,
      regiao_ids: f.regiao_ids.includes(id) ? f.regiao_ids.filter((r) => r !== id) : [...f.regiao_ids, id],
    }));
  }

  function salvar() {
    if (!form.nome.trim()) return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: form }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(form, { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(empresa: Empresa) {
    setEditandoId(empresa.id);
    setForm({ nome: empresa.nome, regiao_ids: empresa.regioes.map((r) => r.id) });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar empresas.</div>}
      <div className="linha-toolbar" style={{ alignItems: "flex-start" }}>
        <div className="campo">
          <label>Nome</label>
          <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex: Transportes ABC" />
        </div>
        <div className="campo">
          <label>Regioes atendidas</label>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {(regioes ?? []).map((r) => (
              <label key={r.id} style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}>
                <input type="checkbox" checked={form.regiao_ids.includes(r.id)} onChange={() => alternarRegiao(r.id)} />
                {r.nome}
              </label>
            ))}
          </div>
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
            <th>Regioes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(empresas ?? []).map((e) => (
            <tr key={e.id}>
              <td>{e.nome}</td>
              <td>{e.regioes.map((r) => r.nome).join(", ") || "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(e)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => remover.mutate(e.id)}>
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
