import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { RegistroKm, Veiculo } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";
import BotaoExportarCsv from "../../components/board/BotaoExportarCsv";
import { formatarData, limitesDoMes, mesAtualIso } from "../../utils/data";
import { formatarMilhar } from "../../utils/numero";

interface FormState {
  veiculo_id: number | "";
  data_inicio: string;
  data_fim: string;
  km_inicial: number | "";
  km_final: number | "";
  observacoes: string;
}

function formVazio(mesIso: string): FormState {
  const { inicio, fim } = limitesDoMes(mesIso);
  return { veiculo_id: "", data_inicio: inicio, data_fim: fim, km_inicial: "", km_final: "", observacoes: "" };
}

export default function RegistrosKmSection() {
  const { data: registros, error } = useList<RegistroKm>("registros-km", "/registros-km");
  const { data: veiculos } = useList<Veiculo>("veiculos", "/veiculos");
  const criar = useCreate<RegistroKm, unknown>("registros-km", "/registros-km");
  const atualizar = useUpdate<RegistroKm, unknown>("registros-km", "/registros-km");
  const remover = useRemove("registros-km", "/registros-km");

  const [mesFiltro, setMesFiltro] = useState(mesAtualIso());
  const [form, setForm] = useState<FormState>(() => formVazio(mesAtualIso()));
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroSalvar, setErroSalvar] = useState<string | null>(null);
  const kmInicialRef = useRef<HTMLInputElement>(null);
  const kmFinalRef = useRef<HTMLInputElement>(null);
  const botaoSalvarRef = useRef<HTMLButtonElement>(null);

  const registrosFiltrados = (registros ?? []).filter((r) => r.data_inicio.slice(0, 7) === mesFiltro);
  const totalKmRodado = registrosFiltrados.reduce((s, r) => s + (r.km_final !== null ? r.km_final - r.km_inicial : 0), 0);

  function selecionarMes(novoMes: string) {
    setMesFiltro(novoMes);
    const { inicio, fim } = limitesDoMes(novoMes);
    setForm((f) => ({ ...f, data_inicio: inicio, data_fim: fim }));
  }

  /** Proximo veiculo da lista (em ordem de prefixo) sem lancamento no mes filtrado,
   * pulando quem ja tem registro -- circula pro comeco ao chegar no fim.
   * `extraFeitoId` cobre o veiculo que acabou de ser salvo (a lista em cache
   * ainda nao reflete o registro recem-criado no momento do onSuccess). */
  function proximoVeiculoId(atualId: number, extraFeitoId: number): number | "" {
    const lista = veiculos ?? [];
    if (lista.length === 0) return "";
    const idx = lista.findIndex((v) => v.id === atualId);
    const feitos = new Set(registrosFiltrados.map((r) => r.veiculo_id));
    feitos.add(extraFeitoId);
    for (let passo = 1; passo <= lista.length; passo++) {
      const proximo = lista[(idx + passo) % lista.length];
      if (!feitos.has(proximo.id)) return proximo.id;
    }
    return "";
  }

  function payload() {
    return {
      veiculo_id: form.veiculo_id,
      data_inicio: form.data_inicio,
      data_fim: form.data_fim,
      km_inicial: form.km_inicial,
      km_final: form.km_final === "" ? null : form.km_final,
      observacoes: form.observacoes || null,
    };
  }

  function salvar() {
    if (form.veiculo_id === "" || !form.data_inicio || !form.data_fim || form.km_inicial === "") return;
    setErroSalvar(null);
    const aoErrar = (err: unknown) => setErroSalvar(err instanceof Error ? err.message : "Erro ao salvar registro de km");

    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: payload() }, { onSuccess: cancelarEdicao, onError: aoErrar });
      return;
    }

    const veiculoSalvo = form.veiculo_id;
    criar.mutate(payload(), {
      onSuccess: () => {
        setForm((f) => ({ ...f, veiculo_id: proximoVeiculoId(veiculoSalvo, veiculoSalvo), km_inicial: "", km_final: "" }));
        kmInicialRef.current?.focus();
      },
      onError: aoErrar,
    });
  }

  function editar(r: RegistroKm) {
    setEditandoId(r.id);
    setForm({
      veiculo_id: r.veiculo_id,
      data_inicio: r.data_inicio,
      data_fim: r.data_fim,
      km_inicial: r.km_inicial,
      km_final: r.km_final ?? "",
      observacoes: r.observacoes ?? "",
    });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(formVazio(mesFiltro));
  }

  function veiculoLabel(id: number) {
    const v = veiculos?.find((v) => v.id === id);
    return v ? `${v.prefixo} - ${v.placa}` : "-";
  }

  function aoPressionarEnter(e: KeyboardEvent<HTMLInputElement>, proximo: () => void) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    proximo();
  }

  const kmRodadoPreview = form.km_inicial !== "" && form.km_final !== "" ? form.km_final - form.km_inicial : null;

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar registros de km.</div>}
      {erroSalvar && (
        <div className="erro-box" onClick={() => setErroSalvar(null)} style={{ cursor: "pointer" }}>
          {erroSalvar} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Mes</label>
          <input type="month" value={mesFiltro} onChange={(e) => selecionarMes(e.target.value)} />
        </div>
      </div>
      <div className="linha-toolbar" style={{ alignItems: "flex-end" }}>
        <div className="campo">
          <label>Veiculo</label>
          <select value={form.veiculo_id} onChange={(e) => setForm({ ...form, veiculo_id: e.target.value ? Number(e.target.value) : "" })}>
            <option value="">Selecione</option>
            {(veiculos ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.prefixo} - {v.placa}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label>Inicio</label>
          <input type="date" value={form.data_inicio} onChange={(e) => setForm({ ...form, data_inicio: e.target.value })} />
        </div>
        <div className="campo">
          <label>Fim</label>
          <input type="date" value={form.data_fim} onChange={(e) => setForm({ ...form, data_fim: e.target.value })} />
        </div>
        <div className="campo">
          <label>Km inicial</label>
          <input
            ref={kmInicialRef}
            type="number"
            min={0}
            value={form.km_inicial}
            onChange={(e) => setForm({ ...form, km_inicial: e.target.value ? Number(e.target.value) : "" })}
            onKeyDown={(e) => aoPressionarEnter(e, () => kmFinalRef.current?.focus())}
            style={{ width: "6rem", textAlign: "right" }}
          />
        </div>
        <div className="campo">
          <label>Km final</label>
          <input
            ref={kmFinalRef}
            type="number"
            min={0}
            value={form.km_final}
            onChange={(e) => setForm({ ...form, km_final: e.target.value ? Number(e.target.value) : "" })}
            onKeyDown={(e) => aoPressionarEnter(e, () => botaoSalvarRef.current?.focus())}
            style={{ width: "6rem", textAlign: "right" }}
          />
        </div>
        <div className="campo">
          <label>Km rodado</label>
          <input
            readOnly
            tabIndex={-1}
            value={kmRodadoPreview === null ? "" : formatarMilhar(kmRodadoPreview)}
            style={{
              width: "6rem",
              textAlign: "right",
              background: "var(--cor-fundo)",
              color: kmRodadoPreview !== null && kmRodadoPreview < 0 ? "var(--cor-perigo)" : undefined,
            }}
          />
        </div>
        <div className="campo">
          <label>Observacoes</label>
          <input value={form.observacoes} onChange={(e) => setForm({ ...form, observacoes: e.target.value })} />
        </div>
        <button ref={botaoSalvarRef} className="btn btn-primario" onClick={salvar} disabled={criar.isPending || atualizar.isPending}>
          {editandoId !== null ? "Salvar edicao" : "Adicionar"}
        </button>
        {editandoId !== null && (
          <button className="btn" onClick={cancelarEdicao}>
            Cancelar
          </button>
        )}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.5rem" }}>
        <BotaoExportarCsv
          nomeArquivo={`registros-km-${mesFiltro}.csv`}
          cabecalhos={["Veiculo", "Inicio", "Fim", "Km inicial", "Km final", "Km rodado", "Observacoes"]}
          linhas={[
            ...registrosFiltrados.map((r) => [
              veiculoLabel(r.veiculo_id),
              formatarData(r.data_inicio),
              formatarData(r.data_fim),
              r.km_inicial,
              r.km_final ?? "",
              r.km_final !== null ? r.km_final - r.km_inicial : "",
              r.observacoes ?? "",
            ]),
            ["Total", "", "", "", "", totalKmRodado, ""],
          ]}
        />
      </div>
      <table>
        <thead>
          <tr>
            <th>Veiculo</th>
            <th>Inicio</th>
            <th>Fim</th>
            <th className="col-num">Km inicial</th>
            <th className="col-num">Km final</th>
            <th className="col-num">Km rodado</th>
            <th>Observacoes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {registrosFiltrados.map((r) => (
            <tr key={r.id}>
              <td>{veiculoLabel(r.veiculo_id)}</td>
              <td>{formatarData(r.data_inicio)}</td>
              <td>{formatarData(r.data_fim)}</td>
              <td className="col-num">{formatarMilhar(r.km_inicial)}</td>
              <td className="col-num">{r.km_final !== null ? formatarMilhar(r.km_final) : "-"}</td>
              <td className="col-num">{r.km_final !== null ? formatarMilhar(r.km_final - r.km_inicial) : "-"}</td>
              <td>{r.observacoes ?? "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(r)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(r.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>
              <strong>Total</strong>
            </td>
            <td className="col-num"></td>
            <td className="col-num"></td>
            <td className="col-num">
              <strong>{formatarMilhar(totalKmRodado)}</strong>
            </td>
            <td></td>
            <td></td>
          </tr>
        </tfoot>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover registro de km"
          mensagem="Remover este registro de km? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroSalvar(err instanceof Error ? err.message : "Erro ao remover registro de km");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
