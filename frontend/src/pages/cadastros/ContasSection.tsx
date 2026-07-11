import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Conta, PapelConta, StatusAtivoInativo } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ConfirmarModal from "../../components/board/ConfirmarModal";

interface FormState {
  nome: string;
  login: string;
  senha: string;
  papel: PapelConta;
  status: StatusAtivoInativo;
}

const vazio: FormState = { nome: "", login: "", senha: "", papel: "Operador", status: "Ativo" };

export default function ContasSection() {
  const { conta: contaAtual } = useAuth();
  const { data: contas, error } = useList<Conta>("contas", "/contas");
  const criar = useCreate<Conta, FormState>("contas", "/contas");
  const atualizar = useUpdate<Conta, Omit<FormState, "senha"> & { senha: string | null }>("contas", "/contas");
  const remover = useRemove("contas", "/contas");

  const [form, setForm] = useState<FormState>(vazio);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  function salvar() {
    if (!form.nome.trim() || !form.login.trim()) return;
    if (editandoId !== null) {
      atualizar.mutate(
        { id: editandoId, body: { ...form, senha: form.senha || null } },
        {
          onSuccess: cancelarEdicao,
          onError: (e: unknown) => setErro(e instanceof Error ? e.message : "Erro ao salvar conta"),
        },
      );
    } else {
      if (!form.senha) return;
      criar.mutate(form, {
        onSuccess: () => setForm(vazio),
        onError: (e: unknown) => setErro(e instanceof Error ? e.message : "Erro ao criar conta"),
      });
    }
  }

  function editar(c: Conta) {
    setEditandoId(c.id);
    setForm({ nome: c.nome, login: c.login, senha: "", papel: c.papel, status: c.status });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm(vazio);
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar contas.</div>}
      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar" style={{ alignItems: "flex-start" }}>
        <div className="campo">
          <label>Nome</label>
          <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
        </div>
        <div className="campo">
          <label>Login</label>
          <input value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} />
        </div>
        <div className="campo">
          <label>{editandoId !== null ? "Nova senha (opcional)" : "Senha"}</label>
          <input type="password" value={form.senha} onChange={(e) => setForm({ ...form, senha: e.target.value })} />
        </div>
        <div className="campo">
          <label>Papel</label>
          <select value={form.papel} onChange={(e) => setForm({ ...form, papel: e.target.value as PapelConta })}>
            <option value="Operador">Operador</option>
            <option value="Admin">Admin</option>
          </select>
        </div>
        <div className="campo">
          <label>Status</label>
          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as StatusAtivoInativo })}>
            <option value="Ativo">Ativo</option>
            <option value="Inativo">Inativo</option>
          </select>
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
            <th>Nome</th>
            <th>Login</th>
            <th>Papel</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(contas ?? []).map((c) => (
            <tr key={c.id}>
              <td>{c.nome}</td>
              <td>{c.login}</td>
              <td>
                <span className="tag">{c.papel}</span>
              </td>
              <td>
                <span className={`tag ${c.status === "Ativo" ? "tag-ativo" : "tag-inativo"}`}>{c.status}</span>
              </td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(c)}>
                  Editar
                </button>{" "}
                <button
                  className="btn btn-sm btn-perigo"
                  onClick={() => setRemovendoId(c.id)}
                  disabled={c.id === contaAtual?.id}
                  title={c.id === contaAtual?.id ? "Nao e possivel remover a propria conta" : undefined}
                >
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover conta"
          mensagem="Remover esta conta? A pessoa perde acesso ao sistema imediatamente."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (e: unknown) => {
                setErro(e instanceof Error ? e.message : "Erro ao remover conta");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
