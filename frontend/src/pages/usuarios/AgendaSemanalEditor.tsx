import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana, Local, Modalidade, Regiao, TipoAtendimento, UsuarioAgendaSemanal } from "../../api/types";
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
  modalidade: Modalidade;
  acompanhante: boolean;
  saida: string;
  retorno: string;
  origem: string;
  regiao_origem_id: number | "";
  destino_id: number | "";
  ativo: boolean;
}

const formVazio: FormState = {
  tipo: "Fixo",
  modalidade: "Ida e Volta",
  acompanhante: false,
  saida: "",
  retorno: "",
  origem: "",
  regiao_origem_id: "",
  destino_id: "",
  ativo: true,
};

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
  const [form, setForm] = useState<FormState>(formVazio);
  const [erro, setErro] = useState<string | null>(null);
  const [replicando, setReplicando] = useState<UsuarioAgendaSemanal | null>(null);

  const chaveDetalhe = ["usuario", usuarioId];

  function mensagemErro(e: unknown, fallback: string): string {
    return e instanceof Error ? e.message : fallback;
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
            modalidade: existente.modalidade,
            acompanhante: existente.acompanhante,
            saida: existente.saida ?? "",
            retorno: existente.retorno ?? "",
            origem: existente.origem ?? "",
            regiao_origem_id: existente.regiao_origem_id ?? "",
            destino_id: existente.destino_id ?? "",
            ativo: existente.ativo,
          }
        : formVazio,
    );
  }

  function payload(dia: DiaSemana) {
    return {
      dia_semana: dia,
      tipo: form.tipo,
      modalidade: form.modalidade,
      acompanhante: form.acompanhante,
      saida: form.saida || null,
      retorno: form.retorno || null,
      origem: form.origem || null,
      regiao_origem_id: form.regiao_origem_id === "" ? null : form.regiao_origem_id,
      destino_id: form.destino_id === "" ? null : form.destino_id,
      ativo: form.ativo,
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
      modalidade: existente.modalidade,
      acompanhante: existente.acompanhante,
      saida: existente.saida,
      retorno: existente.retorno,
      origem: existente.origem,
      regiao_origem_id: existente.regiao_origem_id,
      destino_id: existente.destino_id,
      ativo: existente.ativo,
    };
  }

  const replicarMutation = useMutation({
    mutationFn: (dias: DiaSemana[]) => {
      if (!replicando) return Promise.resolve();
      return Promise.all(dias.map((dia) => api.post(`/usuarios/${usuarioId}/agenda-semanal`, payloadDeEntrada(replicando, dia))));
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
        <td colSpan={9}>
          <div className="linha-toolbar" style={{ margin: 0 }}>
            <strong>{DIAS_SEMANA_LABEL[dia]}</strong>
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoAtendimento })}>
              <option value="Fixo">Fixo</option>
              <option value="Eventual">Eventual</option>
            </select>
            <input type="time" value={form.saida} onChange={(e) => setForm({ ...form, saida: e.target.value })} title="Saida" />
            <input type="time" value={form.retorno} onChange={(e) => setForm({ ...form, retorno: e.target.value })} title="Retorno" />
            <input
              placeholder="Origem (endereco)"
              value={form.origem}
              onChange={(e) => setForm({ ...form, origem: e.target.value })}
            />
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
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexBasis: "100%" }}>
              <select
                value={form.modalidade}
                onChange={(e) => setForm({ ...form, modalidade: e.target.value as Modalidade })}
              >
                <option value="Somente Ida">Somente Ida</option>
                <option value="Ida e Volta">Ida e Volta</option>
              </select>
              <label style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}>
                <input
                  type="checkbox"
                  checked={form.acompanhante}
                  onChange={(e) => setForm({ ...form, acompanhante: e.target.checked })}
                />
                Acompanhante
              </label>
              <label style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}>
                <input type="checkbox" checked={form.ativo} onChange={(e) => setForm({ ...form, ativo: e.target.checked })} />
                Ativo
              </label>
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
            <th>Saida</th>
            <th>Retorno</th>
            <th>Regiao</th>
            <th>Destino</th>
            <th>Modal</th>
            <th>Acomp</th>
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
                  <td>{existente.saida ?? "-"}</td>
                  <td>{existente.retorno ?? "-"}</td>
                  <td>{existente.regiao_origem_id ? regioes.find((r) => r.id === existente.regiao_origem_id)?.nome ?? "-" : "-"}</td>
                  <td>{existente.destino_id ? locais.find((l) => l.id === existente.destino_id)?.nome ?? "-" : "-"}</td>
                  <td>
                    <span className="tag">{existente.modalidade}</span>
                  </td>
                  <td>{existente.acompanhante ? "Sim" : "Nao"}</td>
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
                  <td colSpan={7}>-</td>
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
