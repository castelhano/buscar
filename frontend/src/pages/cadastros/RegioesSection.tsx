import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { Regiao } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";

export default function RegioesSection() {
  const { data: regioes, error } = useList<Regiao>("regioes", "/regioes");
  const criar = useCreate<Regiao, { nome: string }>("regioes", "/regioes");
  const atualizar = useUpdate<Regiao, { nome: string }>("regioes", "/regioes");
  const remover = useRemove("regioes", "/regioes");

  const [nome, setNome] = useState("");
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [removendoId, setRemovendoId] = useState<number | null>(null);
  const [erroRemocao, setErroRemocao] = useState<string | null>(null);

  function salvar() {
    if (!nome.trim()) return;
    if (editandoId !== null) {
      atualizar.mutate({ id: editandoId, body: { nome } }, { onSuccess: () => cancelarEdicao() });
    } else {
      criar.mutate({ nome }, { onSuccess: () => setNome("") });
    }
  }

  function editar(regiao: Regiao) {
    setEditandoId(regiao.id);
    setNome(regiao.nome);
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setNome("");
  }

  return (
    <div>
      {error && <div className="erro-box">Erro ao carregar regioes.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Nome da regiao</label>
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: Coxipo" />
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
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(regioes ?? []).map((r) => (
            <tr key={r.id}>
              <td>{r.nome}</td>
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
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover regiao"
          mensagem="Remover esta regiao? Essa acao nao pode ser desfeita."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover regiao");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
