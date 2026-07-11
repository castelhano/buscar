import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useCreate, useList, useUpdate } from "../api/hooks";
import type { Local, Regiao, StatusAtivoInativo, Usuario, UsuarioComAgenda } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import AgendaSemanalEditor from "./usuarios/AgendaSemanalEditor";
import ExcecoesEditor from "./usuarios/ExcecoesEditor";

interface FormState {
  nome: string;
  abbr: string;
  status: StatusAtivoInativo;
  detalhe: string;
}

const vazio: FormState = { nome: "", abbr: "", status: "Ativo", detalhe: "" };

export default function UsuariosPage() {
  const { isAdmin } = useAuth();
  const [filtroNome, setFiltroNome] = useState("");
  const [filtroFixo, setFiltroFixo] = useState(false);
  const [filtroStatus, setFiltroStatus] = useState<StatusAtivoInativo | "">("");

  const { data: usuarios, error } = useList<Usuario>("usuarios", "/usuarios", {
    nome: filtroNome || undefined,
    somente_fixo: filtroFixo || undefined,
    status: filtroStatus || undefined,
  });
  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: locais } = useList<Local>("locais", "/locais");
  const criar = useCreate<Usuario, unknown>("usuarios", "/usuarios");
  const atualizar = useUpdate<Usuario, unknown>("usuarios", "/usuarios");

  const [selecionadoId, setSelecionadoId] = useState<number | null>(null);
  const [novo, setNovo] = useState(false);
  const [form, setForm] = useState<FormState>(vazio);

  const detalhe = useQuery({
    queryKey: ["usuario", selecionadoId],
    queryFn: () => api.get<UsuarioComAgenda>(`/usuarios/${selecionadoId}`),
    enabled: selecionadoId !== null,
  });

  const [basico, setBasico] = useState<FormState>(vazio);
  const queryClient = useQueryClient();

  // So resincroniza o formulario quando o usuario selecionado MUDA, nao a
  // cada refetch de ["usuario", id] -- salvar a agenda semanal ou uma
  // excecao invalida essa mesma query e sobrescrevia edicoes pendentes aqui.
  const usuarioSincronizadoRef = useRef<number | null>(null);
  useEffect(() => {
    if (detalhe.data && usuarioSincronizadoRef.current !== detalhe.data.id) {
      usuarioSincronizadoRef.current = detalhe.data.id;
      setBasico({
        nome: detalhe.data.nome,
        abbr: detalhe.data.abbr,
        status: detalhe.data.status,
        detalhe: detalhe.data.detalhe ?? "",
      });
    }
  }, [detalhe.data]);

  function selecionar(id: number) {
    setSelecionadoId(id);
    setNovo(false);
  }

  function iniciarNovo() {
    setSelecionadoId(null);
    setNovo(true);
    setForm(vazio);
  }

  function salvarNovo() {
    if (!form.nome.trim() || !form.abbr.trim()) return;
    criar.mutate(
      { nome: form.nome, abbr: form.abbr, status: form.status, detalhe: form.detalhe || null },
      {
        onSuccess: (usuario) => {
          setNovo(false);
          setSelecionadoId(usuario.id);
        },
      },
    );
  }

  function salvarEdicaoBasica() {
    if (!detalhe.data) return;
    atualizar.mutate(
      {
        id: detalhe.data.id,
        body: { nome: basico.nome, abbr: basico.abbr, status: basico.status, detalhe: basico.detalhe || null },
      },
      { onSuccess: () => queryClient.invalidateQueries({ queryKey: ["usuario", detalhe.data!.id] }) },
    );
  }

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
      <div className="painel" style={{ width: 280, flexShrink: 0 }}>
        {isAdmin && (
          <div className="linha-toolbar">
            <button className="btn btn-primario" onClick={iniciarNovo}>
              Novo usuario
            </button>
          </div>
        )}
        <div className="campo" style={{ marginBottom: "0.5rem" }}>
          <input placeholder="Buscar por nome..." value={filtroNome} onChange={(e) => setFiltroNome(e.target.value)} />
        </div>
        <div className="campo" style={{ marginBottom: "0.5rem" }}>
          <select value={filtroStatus} onChange={(e) => setFiltroStatus(e.target.value as StatusAtivoInativo | "")}>
            <option value="">Todos os status</option>
            <option value="Ativo">Ativo</option>
            <option value="Inativo">Inativo</option>
          </select>
        </div>
        <label style={{ display: "flex", gap: "0.4rem", alignItems: "center", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
          <input type="checkbox" checked={filtroFixo} onChange={(e) => setFiltroFixo(e.target.checked)} />
          Somente com atendimento Fixo
        </label>
        {error && <div className="erro-box">Erro ao carregar usuarios.</div>}
        <div style={{ maxHeight: "70vh", overflowY: "auto" }}>
          {(usuarios ?? []).map((u) => (
            <div
              key={u.id}
              onClick={() => selecionar(u.id)}
              style={{
                padding: "0.5rem",
                borderRadius: 6,
                cursor: "pointer",
                background: u.id === selecionadoId ? "var(--cor-fundo)" : "transparent",
                marginBottom: "0.2rem",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{u.nome}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--cor-texto-suave)" }}>
                {u.abbr} · <span className={`tag ${u.status === "Ativo" ? "tag-ativo" : "tag-inativo"}`}>{u.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1 }}>
        {novo && (
          <div className="painel">
            <h3>Novo usuario</h3>
            <div className="linha-toolbar">
              <div className="campo">
                <label>Nome</label>
                <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
              </div>
              <div className="campo">
                <label>Abreviacao</label>
                <input value={form.abbr} onChange={(e) => setForm({ ...form, abbr: e.target.value })} />
              </div>
              <div className="campo">
                <label>Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as StatusAtivoInativo })}>
                  <option value="Ativo">Ativo</option>
                  <option value="Inativo">Inativo</option>
                </select>
              </div>
              <div className="campo" style={{ flex: 1 }}>
                <label>Detalhe</label>
                <input value={form.detalhe} onChange={(e) => setForm({ ...form, detalhe: e.target.value })} />
              </div>
              <button className="btn btn-primario" onClick={salvarNovo} disabled={criar.isPending}>
                Salvar
              </button>
            </div>
          </div>
        )}

        {!novo && selecionadoId !== null && detalhe.data && (
          <div>
            <div className="painel">
              <h3>{detalhe.data.nome}</h3>
              <div className="linha-toolbar">
                <div className="campo">
                  <label>Nome</label>
                  <input
                    value={basico.nome}
                    onChange={(e) => setBasico({ ...basico, nome: e.target.value })}
                    disabled={!isAdmin}
                  />
                </div>
                <div className="campo">
                  <label>Abreviacao</label>
                  <input
                    value={basico.abbr}
                    onChange={(e) => setBasico({ ...basico, abbr: e.target.value })}
                    disabled={!isAdmin}
                  />
                </div>
                <div className="campo">
                  <label>Status</label>
                  <select
                    value={basico.status}
                    onChange={(e) => setBasico({ ...basico, status: e.target.value as StatusAtivoInativo })}
                    disabled={!isAdmin}
                  >
                    <option value="Ativo">Ativo</option>
                    <option value="Inativo">Inativo</option>
                  </select>
                </div>
                <div className="campo" style={{ flex: 1 }}>
                  <label>Detalhe</label>
                  <input
                    value={basico.detalhe}
                    onChange={(e) => setBasico({ ...basico, detalhe: e.target.value })}
                    disabled={!isAdmin}
                  />
                </div>
                {isAdmin && (
                  <button className="btn btn-sm btn-primario" onClick={salvarEdicaoBasica} disabled={atualizar.isPending}>
                    Salvar dados basicos
                  </button>
                )}
              </div>
              <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)" }}>Cadastrado em {detalhe.data.data_cadastro}</p>
            </div>

            <div className="painel">
              <AgendaSemanalEditor
                usuarioId={detalhe.data.id}
                agenda={detalhe.data.agenda_semanal}
                regioes={regioes ?? []}
                locais={locais ?? []}
                somenteLeitura={!isAdmin}
              />
            </div>

            <div className="painel">
              <ExcecoesEditor
                usuarioId={detalhe.data.id}
                excecoes={detalhe.data.excecoes}
                regioes={regioes ?? []}
                locais={locais ?? []}
                somenteLeitura={!isAdmin}
              />
            </div>
          </div>
        )}

        {!novo && selecionadoId === null && <div className="painel">Selecione um usuario na lista ou crie um novo.</div>}
      </div>
    </div>
  );
}
