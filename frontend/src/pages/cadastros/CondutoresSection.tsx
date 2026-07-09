import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Condutor, Empresa, PeriodoCondutor, StatusCondutor, Veiculo } from "../../api/types";

const STATUS: StatusCondutor[] = ["Ativo", "Desligado", "Afastado"];
const PERIODOS: PeriodoCondutor[] = ["Manha", "Tarde"];

interface FormState {
  empresa_id: number | "";
  matricula: string;
  nome: string;
  apelido: string;
  status: StatusCondutor;
  periodo: PeriodoCondutor;
  veiculo_preferencial_id: number | "";
}

const vazio: FormState = {
  empresa_id: "",
  matricula: "",
  nome: "",
  apelido: "",
  status: "Ativo",
  periodo: "Manha",
  veiculo_preferencial_id: "",
};

export default function CondutoresSection() {
  const { data: condutores, error } = useList<Condutor>("condutores", "/condutores");
  const { data: empresas } = useList<Empresa>("empresas", "/empresas");
  const { data: veiculos } = useList<Veiculo>("veiculos", "/veiculos");
  const criar = useCreate<Condutor, unknown>("condutores", "/condutores");
  const atualizar = useUpdate<Condutor, unknown>("condutores", "/condutores");
  const remover = useRemove("condutores", "/condutores");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  function payload(f: FormState) {
    return {
      empresa_id: f.empresa_id,
      matricula: f.matricula,
      nome: f.nome,
      apelido: f.apelido || null,
      status: f.status,
      periodo: f.periodo,
      veiculo_preferencial_id: f.veiculo_preferencial_id === "" ? null : f.veiculo_preferencial_id,
    };
  }

  function salvar() {
    if (!form.nome.trim() || !form.matricula.trim() || form.empresa_id === "") return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: payload(form) }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(payload(form), { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(c: Condutor) {
    setEditandoId(c.id);
    setForm({
      empresa_id: c.empresa_id,
      matricula: c.matricula,
      nome: c.nome,
      apelido: c.apelido ?? "",
      status: c.status,
      periodo: c.periodo,
      veiculo_preferencial_id: c.veiculo_preferencial_id ?? "",
    });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  function nomeEmpresa(id: number) {
    return empresas?.find((e) => e.id === id)?.nome ?? "-";
  }

  const veiculosDaEmpresa = (veiculos ?? []).filter((v) => v.empresa_id === form.empresa_id);

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar condutores.</div>}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Empresa</label>
          <select
            value={form.empresa_id}
            onChange={(e) => setForm({ ...form, empresa_id: e.target.value ? Number(e.target.value) : "", veiculo_preferencial_id: "" })}
          >
            <option value="">Selecione</option>
            {(empresas ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Matricula</label>
          <input value={form.matricula} onChange={(e) => setForm({ ...form, matricula: e.target.value })} />
        </div>
        <div className="campo">
          <label>Nome</label>
          <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
        </div>
        <div className="campo">
          <label>Apelido</label>
          <input value={form.apelido} onChange={(e) => setForm({ ...form, apelido: e.target.value })} />
        </div>
        <div className="campo">
          <label>Veiculo preferencial</label>
          <select
            value={form.veiculo_preferencial_id}
            onChange={(e) => setForm({ ...form, veiculo_preferencial_id: e.target.value ? Number(e.target.value) : "" })}
          >
            <option value="">Nenhum</option>
            {veiculosDaEmpresa.map((v) => (
              <option key={v.id} value={v.id}>
                {v.prefixo}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Status</label>
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as StatusCondutor })}>
            {STATUS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Periodo</label>
          <select value={form.periodo} onChange={(e) => setForm({ ...form, periodo: e.target.value as PeriodoCondutor })}>
            {PERIODOS.map((p) => (
              <option key={p} value={p}>
                {p}
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
            <th>Matricula</th>
            <th>Empresa</th>
            <th>Status</th>
            <th>Periodo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(condutores ?? []).map((c) => (
            <tr key={c.id}>
              <td>
                {c.nome} {c.apelido && <span className="tag">{c.apelido}</span>}
              </td>
              <td>{c.matricula}</td>
              <td>{nomeEmpresa(c.empresa_id)}</td>
              <td>
                <span className={`tag ${c.status === "Ativo" ? "tag-ativo" : c.status !== "Afastado" ? "tag-inativo" : ""}`}>{c.status}</span>
              </td>
              <td>{c.periodo}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(c)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => remover.mutate(c.id)}>
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
