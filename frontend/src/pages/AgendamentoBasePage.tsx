import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useCreate, useList, useRemove } from "../api/hooks";
import type { AgendamentoBase, DiaTipo, Regiao, Sentido, Usuario, UsuarioAgendamentoBase } from "../api/types";

const DIA_TIPO_LABEL: Record<DiaTipo, string> = { U: "Util", S: "Sabado", D: "Domingo" };

interface FormBase {
  dia_tipo: DiaTipo;
  regiao_id: number | "";
  inicio: string;
  capacidade: number;
}

const formVazio: FormBase = { dia_tipo: "U", regiao_id: "", inicio: "", capacidade: 4 };

export default function AgendamentoBasePage() {
  const [diaTipo, setDiaTipo] = useState<DiaTipo>("U");
  const { data: bases, error } = useList<AgendamentoBase>("agendamento-base", "/agendamento-base", { dia_tipo: diaTipo });
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const criar = useCreate<AgendamentoBase, FormBase>("agendamento-base", "/agendamento-base");
  const remover = useRemove("agendamento-base", "/agendamento-base");

  const [form, setForm] = useState<FormBase>({ ...formVazio, dia_tipo: diaTipo });
  const [expandidoId, setExpandidoId] = useState<number | null>(null);

  function nomeRegiao(id: number) {
    return regioes?.find((r) => r.id === id)?.nome ?? "-";
  }

  function salvar() {
    if (form.regiao_id === "" || !form.inicio || form.capacidade <= 0) return;
    criar.mutate({ ...form, dia_tipo: diaTipo }, { onSuccess: () => setForm({ ...formVazio, dia_tipo: diaTipo }) });
  }

  return (
    <div>
      <h2>Agendamento base</h2>
      <div className="linha-toolbar">
        {(["U", "S", "D"] as DiaTipo[]).map((dt) => (
          <button
            key={dt}
            className={`btn ${dt === diaTipo ? "btn-primario" : ""}`}
            onClick={() => {
              setDiaTipo(dt);
              setForm({ ...formVazio, dia_tipo: dt });
            }}
          >
            {DIA_TIPO_LABEL[dt]}
          </button>
        ))}
      </div>

      <div className="painel">
        <h3>Novo carro base ({DIA_TIPO_LABEL[diaTipo]})</h3>
        <div className="linha-toolbar">
          <div className="campo">
            <label>Regiao</label>
            <select value={form.regiao_id} onChange={(e) => setForm({ ...form, regiao_id: e.target.value ? Number(e.target.value) : "" })}>
              <option value="">Selecione</option>
              {(regioes ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label>Horario de saida</label>
            <input type="time" value={form.inicio} onChange={(e) => setForm({ ...form, inicio: e.target.value })} />
          </div>
          <div className="campo">
            <label>Capacidade</label>
            <input type="number" min={1} value={form.capacidade} onChange={(e) => setForm({ ...form, capacidade: Number(e.target.value) })} />
          </div>
          <button className="btn btn-primario" onClick={salvar} disabled={criar.isPending}>
            Adicionar
          </button>
        </div>
      </div>

      {error && <div className="erro-box">Erro ao carregar agendamento base.</div>}

      {(bases ?? []).map((base) => (
        <div className="painel" key={base.id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>{nomeRegiao(base.regiao_id)}</strong> · saida {base.inicio} · capacidade {base.capacidade}
            </div>
            <div>
              <button className="btn btn-sm" onClick={() => setExpandidoId(expandidoId === base.id ? null : base.id)}>
                {expandidoId === base.id ? "Fechar" : "Usuarios vinculados"}
              </button>{" "}
              <button className="btn btn-sm btn-perigo" onClick={() => remover.mutate(base.id)}>
                Remover
              </button>
            </div>
          </div>
          {expandidoId === base.id && <VinculosBase baseId={base.id} />}
        </div>
      ))}
    </div>
  );
}

function VinculosBase({ baseId }: { baseId: number }) {
  const queryClient = useQueryClient();
  const { data: vinculos } = useQuery({
    queryKey: ["agendamento-base-vinculos", baseId],
    queryFn: () => api.get<UsuarioAgendamentoBase[]>(`/agendamento-base/${baseId}/usuarios`),
  });
  const { data: usuarios } = useList<Usuario>("usuarios", "/usuarios");

  const [usuarioId, setUsuarioId] = useState<number | "">("");
  const [sentido, setSentido] = useState<Sentido>("Ida");
  const [hora, setHora] = useState("");

  function nomeUsuario(id: number) {
    return usuarios?.find((u) => u.id === id)?.nome ?? "-";
  }

  async function adicionar() {
    if (usuarioId === "" || !hora) return;
    await api.post(`/agendamento-base/${baseId}/usuarios`, { agendamento_base_id: baseId, usuario_id: usuarioId, sentido, hora });
    await queryClient.invalidateQueries({ queryKey: ["agendamento-base-vinculos", baseId] });
    setUsuarioId("");
    setHora("");
  }

  async function remover(vinculoId: number) {
    await api.delete(`/agendamento-base/${baseId}/usuarios/${vinculoId}`);
    await queryClient.invalidateQueries({ queryKey: ["agendamento-base-vinculos", baseId] });
  }

  return (
    <div style={{ marginTop: "0.75rem", borderTop: "1px solid var(--cor-borda)", paddingTop: "0.75rem" }}>
      <div className="linha-toolbar">
        <select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Usuario (Fixo)</option>
          {(usuarios ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.nome}
            </option>
          ))}
        </select>
        <select value={sentido} onChange={(e) => setSentido(e.target.value as Sentido)}>
          <option value="Ida">Ida</option>
          <option value="Retorno">Retorno</option>
        </select>
        <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
        <button className="btn btn-sm btn-primario" onClick={adicionar}>
          Vincular
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Usuario</th>
            <th>Sentido</th>
            <th>Hora</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(vinculos ?? []).map((v) => (
            <tr key={v.id}>
              <td>{nomeUsuario(v.usuario_id)}</td>
              <td>{v.sentido}</td>
              <td>{v.hora}</td>
              <td>
                <button className="btn btn-sm btn-perigo" onClick={() => remover(v.id)}>
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
