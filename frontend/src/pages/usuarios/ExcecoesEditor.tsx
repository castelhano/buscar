import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Local, OperacaoExcecao, Regiao, UsuarioExcecao } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";
import { formatarData } from "../../utils/data";

interface Props {
  usuarioId: number;
  excecoes: UsuarioExcecao[];
  regioes: Regiao[];
  locais: Local[];
  somenteLeitura?: boolean;
}

interface FormState {
  data_inicio: string;
  data_fim: string;
  operacao: OperacaoExcecao;
  saida: string;
  retorno: string;
  origem: string;
  regiao_origem_id: number | "";
  destino_id: number | "";
  acompanhante: boolean;
  motivo: string;
}

const rotulosOperacao: Record<OperacaoExcecao, string> = {
  Adicao: "Incluir atendimento extra",
  Modificacao: "Alterar atendimento",
  Suspensao: "Suspender atendimento",
};

const vazio: FormState = {
  data_inicio: "",
  data_fim: "",
  operacao: "Modificacao",
  saida: "",
  retorno: "",
  origem: "",
  regiao_origem_id: "",
  destino_id: "",
  acompanhante: false,
  motivo: "",
};

export default function ExcecoesEditor({ usuarioId, excecoes, regioes, locais, somenteLeitura = false }: Props) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(vazio);
  const [erro, setErro] = useState<string | null>(null);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendo, setRemovendo] = useState<UsuarioExcecao | null>(null);
  const chaveDetalhe = ["usuario", usuarioId];

  function mensagemErro(e: unknown, fallback: string): string {
    return e instanceof Error ? e.message : fallback;
  }

  function payload() {
    const suspenso = form.operacao === "Suspensao";
    return {
      data_inicio: form.data_inicio,
      data_fim: form.data_fim || form.data_inicio,
      operacao: form.operacao,
      tipo: "Eventual",
      saida: suspenso ? null : form.saida || null,
      retorno: suspenso ? null : form.retorno || null,
      origem: suspenso ? null : form.origem || null,
      regiao_origem_id: suspenso || form.regiao_origem_id === "" ? null : form.regiao_origem_id,
      destino_id: suspenso || form.destino_id === "" ? null : form.destino_id,
      acompanhante: suspenso ? null : form.acompanhante,
      motivo: form.motivo || null,
    };
  }

  const salvarMutation = useMutation({
    mutationFn: () =>
      editandoId !== null
        ? api.put(`/usuarios/${usuarioId}/excecoes/${editandoId}`, payload())
        : api.post(`/usuarios/${usuarioId}/excecoes`, payload()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      setForm(vazio);
      setEditandoId(null);
      setErro(null);
    },
    onError: (e: unknown) => setErro(mensagemErro(e, editandoId !== null ? "Erro ao salvar excecao" : "Erro ao adicionar excecao")),
  });

  function adicionar() {
    if (!form.data_inicio) return;
    salvarMutation.mutate();
  }

  function editar(e: UsuarioExcecao) {
    setEditandoId(e.id);
    setForm({
      data_inicio: e.data_inicio,
      data_fim: e.data_fim,
      operacao: e.operacao,
      saida: e.saida ?? "",
      retorno: e.retorno ?? "",
      origem: e.origem ?? "",
      regiao_origem_id: e.regiao_origem_id ?? "",
      destino_id: e.destino_id ?? "",
      acompanhante: e.acompanhante ?? false,
      motivo: e.motivo ?? "",
    });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  const removerMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/usuarios/${usuarioId}/excecoes/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      setRemovendo(null);
      setErro(null);
    },
    onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover excecao")),
  });

  return (
    <div>
      <h4>Exceções</h4>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Para um intervalo de datas (data fim vazia = mesma data do inicio): suspender o atendimento, alterar
        horario/local do atendimento atual, ou incluir um atendimento extra mantendo o Fixo original. Tambem serve
        pra um atendimento avulso (usuario sem agenda fixa nesse dia da semana): preenchendo horario/local aqui, a
        excecao sozinha ja garante a geracao nessas datas, sem precisar cadastrar agenda semanal pra isso.
      </p>
      {!somenteLeitura && (
        <div className="linha-toolbar">
          <div className="campo">
            <label>Data inicio</label>
            <input
              type="date"
              value={form.data_inicio}
              onChange={(e) => setForm({ ...form, data_inicio: e.target.value })}
            />
          </div>
          <div className="campo">
            <label>Data fim</label>
            <input
              type="date"
              value={form.data_fim}
              placeholder={form.data_inicio}
              onChange={(e) => setForm({ ...form, data_fim: e.target.value })}
            />
          </div>
          <div className="campo">
            <label>Operacao</label>
            <select
              value={form.operacao}
              onChange={(e) => setForm({ ...form, operacao: e.target.value as OperacaoExcecao })}
            >
              {(Object.keys(rotulosOperacao) as OperacaoExcecao[]).map((op) => (
                <option key={op} value={op}>
                  {rotulosOperacao[op]}
                </option>
              ))}
            </select>
          </div>
          {form.operacao !== "Suspensao" && (
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
              <label style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={form.acompanhante}
                  onChange={(e) => setForm({ ...form, acompanhante: e.target.checked })}
                />
                Acompanhante
              </label>
            </>
          )}
          <input placeholder="Motivo" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
          <button className="btn btn-primario" onClick={adicionar} disabled={salvarMutation.isPending}>
            {editandoId !== null ? "Salvar" : "Adicionar"}
          </button>
          {editandoId !== null && (
            <button className="btn" onClick={cancelarEdicao} disabled={salvarMutation.isPending}>
              Cancelar
            </button>
          )}
        </div>
      )}
      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Operacao</th>
            <th>Situacao</th>
            <th>Destino</th>
            <th>Motivo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {excecoes.map((e) => (
            <tr key={e.id}>
              <td>
                {formatarData(e.data_inicio)}
                {e.data_fim !== e.data_inicio ? ` a ${formatarData(e.data_fim)}` : ""}
              </td>
              <td>{rotulosOperacao[e.operacao]}</td>
              <td>{e.operacao === "Suspensao" ? <span className="tag tag-inativo">Suspenso</span> : `${e.saida ?? "-"} / ${e.retorno ?? "-"}`}</td>
              <td>{e.destino_id ? locais.find((l) => l.id === e.destino_id)?.nome ?? "-" : "-"}</td>
              <td>{e.motivo ?? "-"}</td>
              <td>
                {!somenteLeitura && (
                  <>
                    <button className="btn btn-sm" onClick={() => editar(e)}>
                      Editar
                    </button>{" "}
                    <button className="btn btn-sm btn-perigo" onClick={() => setRemovendo(e)} disabled={removerMutation.isPending}>
                      Remover
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendo && (
        <ConfirmarModal
          titulo="Remover excecao"
          mensagem={`Deseja realmente remover a excecao de ${formatarData(removendo.data_inicio)}?`}
          onFechar={() => setRemovendo(null)}
          onConfirmar={() => removerMutation.mutate(removendo.id)}
        />
      )}
    </div>
  );
}
