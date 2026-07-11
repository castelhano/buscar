import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Empresa, StatusVeiculo, Veiculo } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";

const STATUS: StatusVeiculo[] = ["Ativo", "Inativo", "Manutencao"];

interface FormState {
  empresa_id: number | "";
  prefixo: string;
  placa: string;
  status: StatusVeiculo;
  capacidade: number;
}

const vazio: FormState = { empresa_id: "", prefixo: "", placa: "", status: "Ativo", capacidade: 4 };

export default function VeiculosSection() {
  const { data: veiculos, error } = useList<Veiculo>("veiculos", "/veiculos");
  const { data: empresas } = useList<Empresa>("empresas", "/empresas");
  const criar = useCreate<Veiculo, FormState>("veiculos", "/veiculos");
  const atualizar = useUpdate<Veiculo, FormState>("veiculos", "/veiculos");
  const remover = useRemove("veiculos", "/veiculos");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);

  function salvar() {
    if (!form.prefixo.trim() || !form.placa.trim() || form.empresa_id === "") return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: form }, { onSuccess: cancelarEdicao });
    } else {
      criar.mutate(form, { onSuccess: () => setForm(vazio) });
    }
  }

  function editar(v: Veiculo) {
    setEditandoId(v.id);
    setForm({ empresa_id: v.empresa_id, prefixo: v.prefixo, placa: v.placa, status: v.status, capacidade: v.capacidade });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  function nomeEmpresa(id: number) {
    return empresas?.find((e) => e.id === id)?.nome ?? "-";
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar veiculos.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Empresa</label>
          <select value={form.empresa_id} onChange={(e) => setForm({ ...form, empresa_id: e.target.value ? Number(e.target.value) : "" })}>
            <option value="">Selecione</option>
            {(empresas ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Prefixo</label>
          <input value={form.prefixo} onChange={(e) => setForm({ ...form, prefixo: e.target.value })} placeholder="V01" />
        </div>
        <div className="campo">
          <label>Placa</label>
          <input value={form.placa} onChange={(e) => setForm({ ...form, placa: e.target.value })} placeholder="ABC1D23" />
        </div>
        <div className="campo">
          <label>Status</label>
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as StatusVeiculo })}>
            {STATUS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Capacidade</label>
          <input
            type="number"
            min={1}
            value={form.capacidade}
            onChange={(e) => setForm({ ...form, capacidade: Number(e.target.value) })}
          />
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
            <th>Prefixo</th>
            <th>Placa</th>
            <th>Empresa</th>
            <th>Status</th>
            <th>Capacidade</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(veiculos ?? []).map((v) => (
            <tr key={v.id}>
              <td>{v.prefixo}</td>
              <td>{v.placa}</td>
              <td>{nomeEmpresa(v.empresa_id)}</td>
              <td>
                <span className={`tag ${v.status === "Ativo" ? "tag-ativo" : v.status === "Inativo" ? "tag-inativo" : ""}`}>{v.status}</span>
              </td>
              <td>{v.capacidade}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(v)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(v.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover veiculo"
          mensagem="Remover este veiculo? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover veiculo");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
