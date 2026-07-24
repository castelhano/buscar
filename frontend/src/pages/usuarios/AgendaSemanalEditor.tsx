import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL, rotuloPonto, rotuloTrecho } from "../../api/types";
import type { DiaSemana, Local, Regiao, TipoAtendimento, TrechoInput, UsuarioAgendaSemanal } from "../../api/types";
import TrechoListEditor, { trechoParaInput, trechoVazio } from "../../components/usuarios/TrechoListEditor";
import ReplicarModal from "./ReplicarModal";

interface Props {
  usuarioId: number;
  agenda: UsuarioAgendaSemanal[];
  regioes: Regiao[];
  locais: Local[];
  somenteLeitura?: boolean;
}

interface FormState {
  tipo: TipoAtendimento;
  ativo: boolean;
  trechos: TrechoInput[];
}

const formVazio = (): FormState => ({ tipo: "Fixo", ativo: true, trechos: [trechoVazio(true)] });

// Um dia pode ter mais de um atendimento (ex: terapia de manha, escola a
// noite). entradaId null = criando um atendimento novo pro dia; caso
// contrario, edicao de um atendimento existente (por id, nao por dia).
interface Edicao {
  dia: DiaSemana;
  entradaId: number | null;
}

export default function AgendaSemanalEditor({ usuarioId, agenda, regioes, locais, somenteLeitura = false }: Props) {
  const queryClient = useQueryClient();
  const [edicao, setEdicao] = useState<Edicao | null>(null);
  const [form, setForm] = useState<FormState>(formVazio());
  const [erro, setErro] = useState<string | null>(null);
  const [replicando, setReplicando] = useState<UsuarioAgendaSemanal | null>(null);

  const chaveDetalhe = ["usuario", usuarioId];

  function mensagemErro(e: unknown, fallback: string): string {
    return e instanceof Error ? e.message : fallback;
  }

  function nomeLocal(id: number | null): string | undefined {
    return id ? locais.find((l) => l.id === id)?.nome : undefined;
  }

  const porDia = new Map<DiaSemana, UsuarioAgendaSemanal[]>();
  for (const dia of DIAS_SEMANA) porDia.set(dia, []);
  for (const a of agenda) porDia.get(a.dia_semana)?.push(a);

  function abrirEdicao(dia: DiaSemana, existente: UsuarioAgendaSemanal | null) {
    setEdicao({ dia, entradaId: existente?.id ?? null });
    setForm(
      existente
        ? {
            tipo: existente.tipo,
            ativo: existente.ativo,
            trechos: existente.trechos.length ? existente.trechos.map(trechoParaInput) : [trechoVazio(true)],
          }
        : formVazio(),
    );
  }

  function payload(dia: DiaSemana) {
    return {
      dia_semana: dia,
      tipo: form.tipo,
      ativo: form.ativo,
      trechos: form.trechos,
    };
  }

  const salvarMutation = useMutation({
    mutationFn: () => {
      if (!edicao) return Promise.resolve();
      return edicao.entradaId !== null
        ? api.put(`/usuarios/${usuarioId}/agenda-semanal/${edicao.entradaId}`, payload(edicao.dia))
        : api.post(`/usuarios/${usuarioId}/agenda-semanal`, payload(edicao.dia));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      setEdicao(null);
      setErro(null);
    },
    onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao salvar atendimento")),
  });

  function payloadDeEntrada(existente: UsuarioAgendaSemanal, dia: DiaSemana) {
    return {
      dia_semana: dia,
      tipo: existente.tipo,
      ativo: existente.ativo,
      trechos: existente.trechos.map(trechoParaInput),
    };
  }

  const replicarMutation = useMutation({
    mutationFn: async (dias: DiaSemana[]) => {
      if (!replicando) return;
      await Promise.all(dias.map((dia) => api.post(`/usuarios/${usuarioId}/agenda-semanal`, payloadDeEntrada(replicando, dia))));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      setReplicando(null);
      setErro(null);
    },
    onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao replicar atendimento")),
  });

  const removerMutation = useMutation({
    mutationFn: (entradaId: number) => api.delete(`/usuarios/${usuarioId}/agenda-semanal/${entradaId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chaveDetalhe });
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      setErro(null);
    },
    onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover atendimento")),
  });

  function linhaFormulario(dia: DiaSemana, key: string) {
    return (
      <tr key={key}>
        <td colSpan={5}>
          <div style={{ margin: 0 }}>
            <div className="linha-toolbar">
              <strong>{DIAS_SEMANA_LABEL[dia]}</strong>
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoAtendimento })}>
                <option value="Fixo">Fixo</option>
                <option value="Eventual">Eventual</option>
              </select>
              <label style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}>
                <input type="checkbox" checked={form.ativo} onChange={(e) => setForm({ ...form, ativo: e.target.checked })} />
                Ativo
              </label>
            </div>
            <TrechoListEditor
              trechos={form.trechos}
              onChange={(trechos) => setForm({ ...form, trechos })}
              regioes={regioes}
              locais={locais}
            />
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.6rem" }}>
              <button className="btn btn-primario btn-sm" onClick={() => salvarMutation.mutate()} disabled={salvarMutation.isPending}>
                Salvar
              </button>
              <button className="btn btn-sm" onClick={() => setEdicao(null)}>
                Cancelar
              </button>
            </div>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <div>
      <h4>Agenda semanal</h4>
      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Dia</th>
            <th>Tipo</th>
            <th>Itinerario</th>
            <th>Ativo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {DIAS_SEMANA.flatMap((dia) => {
            const entradas = porDia.get(dia) ?? [];
            const linhas: ReactNode[] = [];
            const criandoNestedia = edicao?.dia === dia && edicao.entradaId === null;

            entradas.forEach((existente, i) => {
              if (edicao?.entradaId === existente.id) {
                linhas.push(linhaFormulario(dia, `${dia}-${existente.id}-form`));
                return;
              }
              const ehUltima = i === entradas.length - 1;
              linhas.push(
                <tr key={existente.id} className={!existente.ativo ? "linha-inativa" : undefined}>
                  <td>{i === 0 ? DIAS_SEMANA_LABEL[dia] : ""}</td>
                  <td>
                    <span className="tag">{existente.tipo}</span>
                  </td>
                  <td>
                    {existente.trechos.map((t) => (
                      <div key={t.id} style={{ fontSize: "0.82rem" }}>
                        <span className="badge-rotulo" style={{ marginRight: "0.4rem" }}>
                          {rotuloTrecho(t.ordem)}
                        </span>
                        {t.hora} · {rotuloPonto(t.origem_tipo, nomeLocal(t.origem_id), t.origem_texto, undefined, "endereco do usuario")} →{" "}
                        {rotuloPonto(t.destino_tipo, nomeLocal(t.destino_id), t.destino_texto, undefined, "endereco do usuario")}
                        {t.acompanhante && <span className="tag-acompanhante" style={{ marginLeft: "0.3rem" }}>+ acomp</span>}
                      </div>
                    ))}
                  </td>
                  <td>{existente.ativo ? "Sim" : "Nao"}</td>
                  <td>
                    {!somenteLeitura && (
                      <>
                        <button className="btn btn-sm" onClick={() => abrirEdicao(dia, existente)}>
                          Editar
                        </button>{" "}
                        <button
                          className="btn btn-sm btn-perigo"
                          onClick={() => removerMutation.mutate(existente.id)}
                          disabled={removerMutation.isPending}
                        >
                          Remover
                        </button>{" "}
                        <button className="btn btn-sm" onClick={() => setReplicando(existente)}>
                          Replicar
                        </button>
                        {ehUltima && !criandoNestedia && (
                          <>
                            {" "}
                            <button
                              className="btn btn-sm"
                              title="Adicionar outro horario nesse dia"
                              onClick={() => abrirEdicao(dia, null)}
                            >
                              +
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </td>
                </tr>,
              );
            });

            if (criandoNestedia) {
              linhas.push(linhaFormulario(dia, `${dia}-novo-form`));
            } else if (entradas.length === 0) {
              linhas.push(
                <tr key={dia}>
                  <td>{DIAS_SEMANA_LABEL[dia]}</td>
                  <td colSpan={3}>-</td>
                  <td>
                    {!somenteLeitura && (
                      <button className="btn btn-sm" onClick={() => abrirEdicao(dia, null)}>
                        Adicionar
                      </button>
                    )}
                  </td>
                </tr>,
              );
            }

            return linhas;
          })}
        </tbody>
      </table>
      {replicando && (
        <ReplicarModal
          diaAtual={replicando.dia_semana}
          onFechar={() => setReplicando(null)}
          onConfirmar={(dias) => replicarMutation.mutate(dias)}
          enviando={replicarMutation.isPending}
        />
      )}
    </div>
  );
}
