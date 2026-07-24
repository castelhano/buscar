import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { diaSemanaFromData, rotuloPonto, rotuloTrecho } from "../../api/types";
import type { Local, OperacaoExcecao, Regiao, TrechoInput, UsuarioAgendaSemanal, UsuarioExcecao } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";
import TrechoListEditor, { trechoParaInput, trechoVazio } from "../../components/usuarios/TrechoListEditor";
import { formatarData } from "../../utils/data";

interface Props {
  usuarioId: number;
  excecoes: UsuarioExcecao[];
  agendaSemanal: UsuarioAgendaSemanal[];
  regioes: Regiao[];
  locais: Local[];
  somenteLeitura?: boolean;
}

interface FormState {
  data_inicio: string;
  data_fim: string;
  operacao: OperacaoExcecao;
  trechos: TrechoInput[];
  motivo: string;
}

const rotulosOperacao: Record<OperacaoExcecao, string> = {
  Adicao: "Incluir",
  Modificacao: "Modificar",
  Suspensao: "Suspender",
};

const vazio = (): FormState => ({
  data_inicio: "",
  data_fim: "",
  operacao: "Modificacao",
  trechos: [trechoVazio(true)],
  motivo: "",
});

export default function ExcecoesEditor({ usuarioId, excecoes, agendaSemanal, regioes, locais, somenteLeitura = false }: Props) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(vazio());
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
      motivo: form.motivo || null,
      trechos: suspenso ? [] : form.trechos,
    };
  }

  const salvarMutation = useMutation({
    mutationFn: () =>
      editandoId !== null
        ? api.put(`/usuarios/${usuarioId}/excecoes/${editandoId}`, payload())
        : api.post(`/usuarios/${usuarioId}/excecoes`, payload()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      setForm(vazio());
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
      trechos: e.trechos.length ? e.trechos.map(trechoParaInput) : [trechoVazio(true)],
      motivo: e.motivo ?? "",
    });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio());
  }

  function clonarDoFixo() {
    if (!form.data_inicio) return;
    const dia = diaSemanaFromData(form.data_inicio);
    const fixo = agendaSemanal.find((a) => a.dia_semana === dia);
    if (!fixo || fixo.trechos.length === 0) {
      setErro("Nao ha atendimento Fixo cadastrado para o dia da semana dessa data");
      return;
    }
    setForm({ ...form, trechos: fixo.trechos.map(trechoParaInput) });
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

  function nomeLocal(id: number | null): string | undefined {
    return id ? locais.find((l) => l.id === id)?.nome : undefined;
  }

  return (
    <div>
      <h4>Exceções</h4>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Para um intervalo de datas (data fim vazia = mesma data do inicio): suspender o atendimento, substituir o
        itinerario do dia (MODIFICACAO substitui a lista de trechos inteira -- use "Clonar do Fixo" pra partir do
        itinerario recorrente e editar so o que muda), ou incluir um atendimento extra mantendo o Fixo original.
        Tambem serve pra um atendimento avulso (usuario sem agenda fixa nesse dia da semana): preenchendo os
        trechos aqui, a excecao sozinha ja garante a geracao nessas datas.
      </p>
      {!somenteLeitura && (
        <div className="painel" style={{ marginBottom: "1rem" }}>
          <div className="linha-toolbar" style={{ alignItems: "flex-end" }}>
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
            <div className="campo">
              <label>Motivo</label>
              <input placeholder="Motivo" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
            </div>
            <button className="btn btn-primario" onClick={adicionar} disabled={salvarMutation.isPending}>
              {editandoId !== null ? "Salvar" : "Adicionar"}
            </button>
            {editandoId !== null && (
              <button className="btn" onClick={cancelarEdicao} disabled={salvarMutation.isPending}>
                Cancelar
              </button>
            )}
          </div>
          {form.operacao !== "Suspensao" && (
            <div style={{ marginTop: "0.7rem" }}>
              <div style={{ marginBottom: "0.5rem" }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={clonarDoFixo}
                  disabled={!form.data_inicio}
                  title="Pre-popula com os trechos do Fixo do dia da semana dessa data"
                >
                  ⧉ Clonar do Fixo
                </button>
              </div>
              <TrechoListEditor
                trechos={form.trechos}
                onChange={(trechos) => setForm({ ...form, trechos })}
                regioes={regioes}
                locais={locais}
              />
            </div>
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
            <th>Itinerario</th>
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
              <td>
                {e.operacao === "Suspensao" ? (
                  <span className="tag tag-inativo">Suspenso</span>
                ) : (
                  e.trechos.map((t) => (
                    <div key={t.id} style={{ fontSize: "0.82rem" }}>
                      <span className="badge-rotulo" style={{ marginRight: "0.4rem" }}>
                        {rotuloTrecho(t.ordem)}
                      </span>
                      {t.hora} · {rotuloPonto(t.origem_tipo, nomeLocal(t.origem_id), t.origem_texto, undefined, "endereco do usuario")} →{" "}
                      {rotuloPonto(t.destino_tipo, nomeLocal(t.destino_id), t.destino_texto, undefined, "endereco do usuario")}
                    </div>
                  ))
                )}
              </td>
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
