import { useState } from "react";
import type { Condutor, GrupoRevezamento } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";
import { corRevezamento } from "./coresRevezamento";

function labelCondutor(condutor: Condutor): string {
  return `${condutor.matricula} · ${condutor.apelido || condutor.nome}`;
}

interface Props {
  grupoRevezamento: GrupoRevezamento;
  numeroGrupo: number;
  todosGruposRevezamento: GrupoRevezamento[];
  condutores: Condutor[];
  onFechar: () => void;
  onSalvar: (condutorIds: number[]) => void;
}

export default function ModalCondutoresRevezamento({
  grupoRevezamento,
  numeroGrupo,
  todosGruposRevezamento,
  condutores,
  onFechar,
  onSalvar,
}: Props) {
  useLockBodyScroll();
  const [selecionados, setSelecionados] = useState<number[]>(
    grupoRevezamento.condutores.map((c) => c.condutor_id),
  );

  const cor = corRevezamento(grupoRevezamento.id);
  const condutoresAtivos = condutores.filter((c) => c.status === "Ativo");

  // Condutor ja escalado em OUTRO grupo de revezamento -- mostrado na cor
  // desse outro grupo pra deixar claro, ao montar um grupo novo, quem ja
  // esta comprometido noutra fila (mesmo condutor pode aparecer em varios
  // grupos por engano; isso so avisa, nao bloqueia a selecao).
  const grupoPorCondutor = new Map<number, { cor: string; numero: number }>();
  todosGruposRevezamento.forEach((grupo, indice) => {
    if (grupo.id === grupoRevezamento.id) return;
    for (const c of grupo.condutores) {
      grupoPorCondutor.set(c.condutor_id, { cor: corRevezamento(grupo.id), numero: indice + 1 });
    }
  });

  function alternar(id: number) {
    setSelecionados((atual) => (atual.includes(id) ? atual.filter((c) => c !== id) : [...atual, id]));
  }

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <h3>
          Condutores do Grupo {numeroGrupo} ({grupoRevezamento.carros.length} carro
          {grupoRevezamento.carros.length === 1 ? "" : "s"})
        </h3>
        <div className="meta" style={{ marginBottom: "0.5rem" }}>
          Clique nos condutores pra incluir/excluir da fila de revezamento -- a ordem de clique vira a ordem de
          revezamento (1º clicado assume a vaga 1 primeiro).
        </div>

        <div className="campo">
          <div className="badge-grade">
            {condutoresAtivos.map((c) => {
              const posicao = selecionados.indexOf(c.id);
              const selecionado = posicao !== -1;
              const outroGrupo = grupoPorCondutor.get(c.id);
              return (
                <button
                  key={c.id}
                  type="button"
                  className="badge-selecao"
                  title={outroGrupo ? `Ja esta no Grupo ${outroGrupo.numero}` : undefined}
                  style={{
                    background: selecionado ? cor : undefined,
                    borderColor: selecionado ? cor : outroGrupo?.cor ?? cor,
                    color: selecionado ? "#fff" : outroGrupo?.cor,
                    fontWeight: selecionado ? 600 : undefined,
                  }}
                  onClick={() => alternar(c.id)}
                >
                  {selecionado ? `${posicao + 1}. ` : ""}
                  {labelCondutor(c)}
                  {!selecionado && outroGrupo ? ` (G${outroGrupo.numero})` : ""}
                </button>
              );
            })}
          </div>
        </div>

        {grupoRevezamento.carros.length !== selecionados.length && (
          <div className="aviso-discreto" style={{ marginTop: "0.5rem" }}>
            {grupoRevezamento.carros.length} carro(s) mas {selecionados.length} condutor(es) selecionado(s) -- o
            rodizio fica desativado até as duas contagens serem iguais.
          </div>
        )}

        <div className="linha-toolbar" style={{ marginTop: "1.2rem" }}>
          <button className="btn btn-primario" onClick={() => onSalvar(selecionados)}>
            Salvar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
