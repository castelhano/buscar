import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Local, Regiao, UsuarioExcecao } from "../../api/types";

interface Props {
  usuarioId: number;
  excecoes: UsuarioExcecao[];
  regioes: Regiao[];
  locais: Local[];
}

interface FormState {
  data: string;
  suspenso: boolean;
  saida: string;
  retorno: string;
  origem: string;
  regiao_origem_id: number | "";
  destino_id: number | "";
  motivo: string;
}

const vazio: FormState = {
  data: "",
  suspenso: false,
  saida: "",
  retorno: "",
  origem: "",
  regiao_origem_id: "",
  destino_id: "",
  motivo: "",
};

export default function ExcecoesEditor({ usuarioId, excecoes, regioes, locais }: Props) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(vazio);
  const chaveDetalhe = ["usuario", usuarioId];

  async function adicionar() {
    if (!form.data) return;
    await api.post(`/usuarios/${usuarioId}/excecoes`, {
      data: form.data,
      suspenso: form.suspenso,
      saida: form.suspenso ? null : form.saida || null,
      retorno: form.suspenso ? null : form.retorno || null,
      origem: form.suspenso ? null : form.origem || null,
      regiao_origem_id: form.suspenso || form.regiao_origem_id === "" ? null : form.regiao_origem_id,
      destino_id: form.suspenso || form.destino_id === "" ? null : form.destino_id,
      motivo: form.motivo || null,
    });
    await queryClient.invalidateQueries({ queryKey: chaveDetalhe });
    setForm(vazio);
  }

  async function remover(id: number) {
    await api.delete(`/usuarios/${usuarioId}/excecoes/${id}`);
    await queryClient.invalidateQueries({ queryKey: chaveDetalhe });
  }

  return (
    <div>
      <h4>Excecoes pontuais</h4>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Para um dia especifico: suspender o atendimento ou trocar horario/local so naquela data.
      </p>
      <div className="linha-toolbar">
        <div className="campo">
          <label>Data</label>
          <input type="date" value={form.data} onChange={(e) => setForm({ ...form, data: e.target.value })} />
        </div>
        <label style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
          <input type="checkbox" checked={form.suspenso} onChange={(e) => setForm({ ...form, suspenso: e.target.checked })} />
          Suspender atendimento nesse dia
        </label>
        {!form.suspenso && (
          <>
            <input type="time" value={form.saida} onChange={(e) => setForm({ ...form, saida: e.target.value })} title="Saida" />
            <input type="time" value={form.retorno} onChange={(e) => setForm({ ...form, retorno: e.target.value })} title="Retorno" />
            <input placeholder="Origem" value={form.origem} onChange={(e) => setForm({ ...form, origem: e.target.value })} />
            <select
              value={form.regiao_origem_id}
              onChange={(e) => setForm({ ...form, regiao_origem_id: e.target.value ? Number(e.target.value) : "" })}
            >
              <option value="">Regiao origem</option>
              {regioes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome}
                </option>
              ))}
            </select>
            <select value={form.destino_id} onChange={(e) => setForm({ ...form, destino_id: e.target.value ? Number(e.target.value) : "" })}>
              <option value="">Destino</option>
              {locais.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          </>
        )}
        <input placeholder="Motivo" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
        <button className="btn btn-primario" onClick={adicionar}>
          Adicionar
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Situacao</th>
            <th>Motivo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {excecoes.map((e) => (
            <tr key={e.id}>
              <td>{e.data}</td>
              <td>{e.suspenso ? <span className="tag tag-inativo">Suspenso</span> : `${e.saida ?? "-"} / ${e.retorno ?? "-"}`}</td>
              <td>{e.motivo ?? "-"}</td>
              <td>
                <button className="btn btn-sm btn-perigo" onClick={() => remover(e.id)}>
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
