import { useState } from "react";
import { useCreate, useList, useRemove, useUpdate } from "../../api/hooks";
import type { GrupoFamiliarComUsuarios } from "../../api/types";
import ConfirmarModal from "../../components/board/ConfirmarModal";
import { corGrupoFamiliar } from "../../components/board/coresGrupoFamiliar";

export default function GruposFamiliaresSection() {
  const { data: grupos, error } = useList<GrupoFamiliarComUsuarios>("grupos-familiares", "/grupos-familiares");
  const criar = useCreate<GrupoFamiliarComUsuarios, { nome: string }>("grupos-familiares", "/grupos-familiares");
  const atualizar = useUpdate<GrupoFamiliarComUsuarios, { nome: string }>("grupos-familiares", "/grupos-familiares");
  const remover = useRemove("grupos-familiares", "/grupos-familiares");

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

  function editar(grupo: GrupoFamiliarComUsuarios) {
    setEditandoId(grupo.id);
    setNome(grupo.nome);
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setNome("");
  }

  return (
    <div>
      <p style={{ fontSize: "0.8rem", color: "var(--cor-texto-suave)", marginTop: 0 }}>
        Usuarios que devem viajar juntos dentro do possivel (ex: irmaos). Crie o grupo aqui e associe cada usuario a
        ele na tela de Usuarios -- o molde Base passa a mostrar os dois com a mesma cor e a tentar move-los juntos.
      </p>
      {error && <div className="erro-box">Erro ao carregar grupos familiares.</div>}
      {erroRemocao && (
        <div className="erro-box" onClick={() => setErroRemocao(null)} style={{ cursor: "pointer" }}>
          {erroRemocao} (clique para fechar)
        </div>
      )}
      <div className="linha-toolbar">
        <div className="campo">
          <label>Nome do grupo</label>
          <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: Familia Silva" />
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
            <th>Usuarios</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(grupos ?? []).map((g) => (
            <tr key={g.id}>
              <td>
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: corGrupoFamiliar(g.id),
                    marginRight: "0.4rem",
                  }}
                />
                {g.nome}
              </td>
              <td>{g.usuarios.length > 0 ? g.usuarios.map((u) => u.abbr || u.nome).join(", ") : "-"}</td>
              <td>
                <button className="btn btn-sm" onClick={() => editar(g)}>
                  Editar
                </button>{" "}
                <button className="btn btn-sm btn-perigo" onClick={() => setRemovendoId(g.id)}>
                  Remover
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {removendoId !== null && (
        <ConfirmarModal
          titulo="Remover grupo familiar"
          mensagem="Remover este grupo? Os usuarios associados ficam sem grupo (nao sao removidos)."
          onFechar={() => setRemovendoId(null)}
          onConfirmar={() =>
            remover.mutate(removendoId, {
              onSuccess: () => setRemovendoId(null),
              onError: (err: unknown) => {
                setErroRemocao(err instanceof Error ? err.message : "Erro ao remover grupo familiar");
                setRemovendoId(null);
              },
            })
          }
        />
      )}
    </div>
  );
}
