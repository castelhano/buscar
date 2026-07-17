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
  condutores: Condutor[];
  onFechar: () => void;
  onSalvar: (condutorIds: number[]) => void;
}

export default function ModalCondutoresRevezamento({
  grupoRevezamento,
  numeroGrupo,
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
              return (
                <button
                  key={c.id}
                  type="button"
                  className="badge-selecao"
                  style={{
                    background: selecionado ? cor : undefined,
                    borderColor: cor,
                    color: selecionado ? "#fff" : undefined,
                    fontWeight: selecionado ? 600 : undefined,
                  }}
                  onClick={() => alternar(c.id)}
                >
                  {selecionado ? `${posicao + 1}. ` : ""}
                  {labelCondutor(c)}
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
