import type { Local, Regiao, Trecho, TrechoInput } from "../../api/types";
import { rotuloTrecho } from "../../api/types";

interface Props {
  trechos: TrechoInput[];
  onChange: (novos: TrechoInput[]) => void;
  regioes: Regiao[];
  locais: Local[];
  somenteLeitura?: boolean;
  /** false trava a lista no tamanho atual (usado ao editar um unico trecho
   * ja lancado, onde adicionar/remover mudaria outro registro). */
  permitirAdicionarRemover?: boolean;
}

/** Trecho vazio pronto pra inserir na lista. `primeiro=true` (index 0, nao
 * ha trecho anterior de onde herdar) forca uma origem propria -- o padrao
 * mais comum e sair de casa, entao comeca em "Usuario". Os demais indices
 * comecam herdando a origem do trecho anterior (`origem_tipo: null`). */
export function trechoVazio(primeiro: boolean): TrechoInput {
  return {
    hora: "",
    origem_tipo: primeiro ? "Usuario" : null,
    origem_id: null,
    origem_texto: null,
    origem_detalhe: null,
    regiao_origem_id: null,
    destino_tipo: "Local",
    destino_id: null,
    destino_texto: null,
    destino_detalhe: null,
    regiao_destino_id: null,
    acompanhante: false,
  };
}

export function trechoParaInput(t: Trecho): TrechoInput {
  return {
    hora: t.hora,
    origem_tipo: t.origem_tipo,
    origem_id: t.origem_id,
    origem_texto: t.origem_texto,
    origem_detalhe: t.origem_detalhe,
    regiao_origem_id: t.regiao_origem_id,
    destino_tipo: t.destino_tipo,
    destino_id: t.destino_id,
    destino_texto: t.destino_texto,
    destino_detalhe: t.destino_detalhe,
    regiao_destino_id: t.regiao_destino_id,
    acompanhante: t.acompanhante,
  };
}

interface PontoFields {
  tipo: "Local" | "Usuario" | "Avulso" | null;
  id: number | null;
  texto: string | null;
  detalhe: string | null;
  regiaoId: number | null;
}

function lerOrigem(t: TrechoInput): PontoFields {
  return { tipo: t.origem_tipo, id: t.origem_id, texto: t.origem_texto, detalhe: t.origem_detalhe, regiaoId: t.regiao_origem_id };
}

function lerDestino(t: TrechoInput): PontoFields {
  return { tipo: t.destino_tipo, id: t.destino_id, texto: t.destino_texto, detalhe: t.destino_detalhe, regiaoId: t.regiao_destino_id };
}

function patchOrigem(p: Partial<PontoFields>): Partial<TrechoInput> {
  const patch: Partial<TrechoInput> = {};
  if ("tipo" in p) patch.origem_tipo = p.tipo as TrechoInput["origem_tipo"];
  if ("id" in p) patch.origem_id = p.id ?? null;
  if ("texto" in p) patch.origem_texto = p.texto ?? null;
  if ("detalhe" in p) patch.origem_detalhe = p.detalhe ?? null;
  if ("regiaoId" in p) patch.regiao_origem_id = p.regiaoId ?? null;
  return patch;
}

function patchDestino(p: Partial<PontoFields>): Partial<TrechoInput> {
  const patch: Partial<TrechoInput> = {};
  if ("tipo" in p) patch.destino_tipo = p.tipo as TrechoInput["destino_tipo"];
  if ("id" in p) patch.destino_id = p.id ?? null;
  if ("texto" in p) patch.destino_texto = p.texto ?? null;
  if ("detalhe" in p) patch.destino_detalhe = p.detalhe ?? null;
  if ("regiaoId" in p) patch.regiao_destino_id = p.regiaoId ?? null;
  return patch;
}

/** Editor de um lado (origem OU destino) de um trecho: escolha de tipo
 * (Local/Usuario/Avulso) + os campos especificos de cada um. `permitirHerdar`
 * (so na origem, quando o trecho nao e o primeiro do itinerario) acrescenta
 * a opcao de deixar em branco pra herdar o destino do trecho anterior. */
function PontoEditor({
  rotulo,
  ponto,
  aplicar,
  regioes,
  locais,
  somenteLeitura,
  permitirHerdar,
}: {
  rotulo: string;
  ponto: PontoFields;
  aplicar: (patch: Partial<PontoFields>) => void;
  regioes: Regiao[];
  locais: Local[];
  somenteLeitura: boolean;
  permitirHerdar: boolean;
}) {
  const herdando = permitirHerdar && ponto.tipo === null;

  return (
    <div className="campo campo-ponto">
      <span>{rotulo}</span>
      {permitirHerdar && (
        <label className="campo-herdar">
          <input
            type="checkbox"
            checked={herdando}
            disabled={somenteLeitura}
            onChange={(e) =>
              aplicar(
                e.target.checked
                  ? { tipo: null, id: null, texto: null, detalhe: null, regiaoId: null }
                  : { tipo: "Usuario", id: null, texto: null, detalhe: null, regiaoId: null },
              )
            }
          />
          Herdar do trecho anterior
        </label>
      )}
      {!herdando && (
        <>
          <div className="destino-toggle">
            <button
              type="button"
              className={ponto.tipo === "Local" ? "ativo" : ""}
              disabled={somenteLeitura}
              onClick={() => aplicar({ tipo: "Local", texto: null, detalhe: null, regiaoId: null })}
            >
              Local cadastrado
            </button>
            <button
              type="button"
              className={ponto.tipo === "Usuario" ? "ativo" : ""}
              disabled={somenteLeitura}
              onClick={() => aplicar({ tipo: "Usuario", id: null, texto: null, detalhe: null, regiaoId: null })}
            >
              Endereco do usuario
            </button>
            <button
              type="button"
              className={ponto.tipo === "Avulso" ? "ativo" : ""}
              disabled={somenteLeitura}
              onClick={() => aplicar({ tipo: "Avulso", id: null, texto: ponto.texto ?? "" })}
            >
              Avulso
            </button>
          </div>
          {ponto.tipo === "Local" && (
            <select
              value={ponto.id ?? ""}
              disabled={somenteLeitura}
              onChange={(e) => aplicar({ id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Selecionar local...</option>
              {locais.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.nome}
                </option>
              ))}
            </select>
          )}
          {ponto.tipo === "Usuario" && (
            <p className="campo-nota">Usa o endereco e a regiao cadastrados no usuario -- sem repetir aqui.</p>
          )}
          {ponto.tipo === "Avulso" && (
            <>
              <input
                placeholder="Rotulo (exibido no card)"
                value={ponto.texto ?? ""}
                disabled={somenteLeitura}
                onChange={(e) => aplicar({ texto: e.target.value })}
              />
              <input
                placeholder="Endereco completo (opcional, aparece na exportacao)"
                value={ponto.detalhe ?? ""}
                disabled={somenteLeitura}
                onChange={(e) => aplicar({ detalhe: e.target.value })}
              />
              <select
                value={ponto.regiaoId ?? ""}
                disabled={somenteLeitura}
                onChange={(e) => aplicar({ regiaoId: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">Regiao...</option>
                {regioes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.nome}
                  </option>
                ))}
              </select>
            </>
          )}
        </>
      )}
    </div>
  );
}

/** Editor de lista de trechos (itinerario do dia) -- reaproveitado na Agenda
 * Semanal, nas Excecoes e no modal de passageiro avulso. Ida-e-volta
 * convencional e so uma lista de 2 trechos, sem tratamento especial.
 * Totalmente controlado: quem chama e dono do estado e decide quando
 * persistir (o atendimento inteiro, com todos os seus trechos, e salvo
 * numa unica chamada pelo componente pai). */
export default function TrechoListEditor({
  trechos,
  onChange,
  regioes,
  locais,
  somenteLeitura = false,
  permitirAdicionarRemover = true,
}: Props) {
  function atualizar(indice: number, patch: Partial<TrechoInput>) {
    onChange(trechos.map((t, i) => (i === indice ? { ...t, ...patch } : t)));
  }

  function mover(indice: number, direcao: -1 | 1) {
    const alvo = indice + direcao;
    if (alvo < 0 || alvo >= trechos.length) return;
    const novos = [...trechos];
    [novos[indice], novos[alvo]] = [novos[alvo], novos[indice]];
    onChange(novos);
  }

  function remover(indice: number) {
    if (trechos.length <= 1) return;
    onChange(trechos.filter((_, i) => i !== indice));
  }

  function adicionar() {
    onChange([...trechos, trechoVazio(false)]);
  }

  return (
    <div className="trecho-lista">
      {trechos.map((trecho, indice) => (
        <div className="trecho-row" key={indice}>
          <div className="trecho-row-badge">
            <span className="badge-rotulo">{rotuloTrecho(indice)}</span>
          </div>
          <div className="trecho-row-fields">
            <label className="campo campo-hora">
              <span>Horario</span>
              <input
                type="time"
                value={trecho.hora}
                disabled={somenteLeitura}
                onChange={(e) => atualizar(indice, { hora: e.target.value })}
              />
            </label>
            <PontoEditor
              rotulo="Origem"
              ponto={lerOrigem(trecho)}
              aplicar={(patch) => atualizar(indice, patchOrigem(patch))}
              regioes={regioes}
              locais={locais}
              somenteLeitura={somenteLeitura}
              permitirHerdar={indice > 0}
            />
            <PontoEditor
              rotulo="Destino"
              ponto={lerDestino(trecho)}
              aplicar={(patch) => atualizar(indice, patchDestino(patch))}
              regioes={regioes}
              locais={locais}
              somenteLeitura={somenteLeitura}
              permitirHerdar={false}
            />
            <label className="campo campo-acompanhante">
              <input
                type="checkbox"
                checked={trecho.acompanhante}
                disabled={somenteLeitura}
                onChange={(e) => atualizar(indice, { acompanhante: e.target.checked })}
              />
              <span>Acompanhante</span>
            </label>
          </div>
          {!somenteLeitura && permitirAdicionarRemover && (
            <div className="trecho-row-actions">
              <button type="button" onClick={() => mover(indice, -1)} disabled={indice === 0} title="Mover para cima">
                ↑
              </button>
              <button
                type="button"
                onClick={() => mover(indice, 1)}
                disabled={indice === trechos.length - 1}
                title="Mover para baixo"
              >
                ↓
              </button>
              <button type="button" className="rm" onClick={() => remover(indice)} title="Remover trecho">
                ✕
              </button>
            </div>
          )}
        </div>
      ))}
      {!somenteLeitura && permitirAdicionarRemover && (
        <button type="button" className="trecho-add" onClick={adicionar}>
          + Adicionar trecho
        </button>
      )}
    </div>
  );
}
