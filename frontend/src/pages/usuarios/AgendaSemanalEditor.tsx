import { useState } from "react";
import { api } from "../../api/client";
import { useQueryClient } from "@tanstack/react-query";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../../api/types";
import type { DiaSemana, Local, Modalidade, Regiao, TipoAtendimento, UsuarioAgendaSemanal } from "../../api/types";

interface Props {
  usuarioId: number;
  agenda: UsuarioAgendaSemanal[];
  regioes: Regiao[];
  locais: Local[];
}

interface FormState {
  tipo: TipoAtendimento;
  modalidade: Modalidade;
  acompanhante: boolean;
  ordem: number;
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
  ordem: 0,
  saida: "",
  retorno: "",
  origem: "",
  regiao_origem_id: "",
  destino_id: "",
  ativo: true,
};

export default function AgendaSemanalEditor({ usuarioId, agenda, regioes, locais }: Props) {
  const queryClient = useQueryClient();
  const [diaEmEdicao, setDiaEmEdicao] = useState<DiaSemana | null>(null);
  const [form, setForm] = useState<FormState>(formVazio);

  const chaveDetalhe = ["usuario", usuarioId];

  function abrirEdicao(dia: DiaSemana) {
    const existente = agenda.find((a) => a.dia_semana === dia);
    setDiaEmEdicao(dia);
    setForm(
      existente
        ? {
            tipo: existente.tipo,
            modalidade: existente.modalidade,
            acompanhante: existente.acompanhante,
            ordem: existente.ordem,
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

  function payload() {
    return {
      dia_semana: diaEmEdicao,
      tipo: form.tipo,
      modalidade: form.modalidade,
      acompanhante: form.acompanhante,
      ordem: form.ordem,
      saida: form.saida || null,
      retorno: form.retorno || null,
      origem: form.origem || null,
      regiao_origem_id: form.regiao_origem_id === "" ? null : form.regiao_origem_id,
      destino_id: form.destino_id === "" ? null : form.destino_id,
      ativo: form.ativo,
    };
  }

  async function salvar() {
    if (!diaEmEdicao) return;
    const existente = agenda.find((a) => a.dia_semana === diaEmEdicao);
    if (existente) {
      await api.put(`/usuarios/${usuarioId}/agenda-semanal/${existente.id}`, payload());
    } else {
      await api.post(`/usuarios/${usuarioId}/agenda-semanal`, payload());
    }
    await queryClient.invalidateQueries({ queryKey: chaveDetalhe });
    setDiaEmEdicao(null);
  }

  async function remover(dia: DiaSemana) {
    const existente = agenda.find((a) => a.dia_semana === dia);
    if (!existente) return;
    await api.delete(`/usuarios/${usuarioId}/agenda-semanal/${existente.id}`);
    await queryClient.invalidateQueries({ queryKey: chaveDetalhe });
  }

  return (
    <div>
      <h4>Agenda semanal</h4>
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
          {DIAS_SEMANA.map((dia) => {
            const existente = agenda.find((a) => a.dia_semana === dia);
            if (diaEmEdicao === dia) {
              return (
                <tr key={dia}>
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
                        <label
                          style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}
                          title="Ordem de preenchimento dos carros na geracao do dia -- usada para manter juntos quem mora perto"
                        >
                          Ordem
                          <input
                            type="number"
                            style={{ width: "4rem" }}
                            value={form.ordem}
                            onChange={(e) => setForm({ ...form, ordem: Number(e.target.value) })}
                          />
                        </label>
                        <label style={{ display: "flex", gap: "0.25rem", alignItems: "center", fontWeight: "normal" }}>
                          <input type="checkbox" checked={form.ativo} onChange={(e) => setForm({ ...form, ativo: e.target.checked })} />
                          Ativo
                        </label>
                        <button className="btn btn-primario btn-sm" onClick={salvar}>
                          Salvar
                        </button>
                        <button className="btn btn-sm" onClick={() => setDiaEmEdicao(null)}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              );
            }
            return (
              <tr key={dia} className={existente && !existente.ativo ? "linha-inativa" : undefined}>
                <td>{DIAS_SEMANA_LABEL[dia]}</td>
                <td>{existente ? <span className="tag">{existente.tipo}</span> : "-"}</td>
                <td>{existente?.saida ?? "-"}</td>
                <td>{existente?.retorno ?? "-"}</td>
                <td>{existente?.regiao_origem_id ? regioes.find((r) => r.id === existente.regiao_origem_id)?.nome ?? "-" : "-"}</td>
                <td>{existente?.destino_id ? locais.find((l) => l.id === existente.destino_id)?.nome ?? "-" : "-"}</td>
                <td>{existente ? <span className="tag">{existente.modalidade}</span> : "-"}</td>
                <td>{existente ? (existente.acompanhante ? "Sim" : "Nao") : "-"}</td>
                <td>
                  <button className="btn btn-sm" onClick={() => abrirEdicao(dia)}>
                    {existente ? "Editar" : "Adicionar"}
                  </button>{" "}
                  {existente && (
                    <button className="btn btn-sm btn-perigo" onClick={() => remover(dia)}>
                      Remover
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
