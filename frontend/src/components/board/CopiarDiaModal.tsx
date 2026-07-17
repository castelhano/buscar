import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { ViagemDia } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

function primeiraHora(viagem: ViagemDia): string {
  const horas = viagem.passageiros.map((p) => p.hora).sort();
  return horas[0] ?? viagem.horario_saida;
}

function agruparPorBloco(viagens: ViagemDia[]): ViagemDia[][] {
  const grupos = new Map<number, ViagemDia[]>();
  for (const viagem of viagens) {
    const chave = viagem.grupo_viagem_id ?? viagem.id;
    const grupo = grupos.get(chave);
    if (grupo) grupo.push(viagem);
    else grupos.set(chave, [viagem]);
  }
  const lista = [...grupos.values()];
  const ordemDoBloco = (grupo: ViagemDia[]) => grupo.find((v) => v.grupo_viagem_id === null)?.ordem_exibicao ?? null;
  lista.sort((a, b) => {
    const ordemA = ordemDoBloco(a);
    const ordemB = ordemDoBloco(b);
    if (ordemA !== null && ordemB !== null) return ordemA - ordemB;
    if (ordemA !== null) return -1;
    if (ordemB !== null) return 1;
    return primeiraHora(a[0]).localeCompare(primeiraHora(b[0]));
  });
  return lista;
}

function ancoraIdDoBloco(grupo: ViagemDia[]): number {
  return grupo.find((v) => v.grupo_viagem_id === null)?.id ?? grupo[0].id;
}

interface Props {
  dataDestino: string;
  onFechar: () => void;
  onConfirmar: (dataOrigem: string, ancoraIds: number[]) => void;
  enviando?: boolean;
}

export default function CopiarDiaModal({ dataDestino, onFechar, onConfirmar, enviando }: Props) {
  useLockBodyScroll();
  const [dataOrigem, setDataOrigem] = useState("");
  const [selecionados, setSelecionados] = useState<Set<number>>(new Set());

  const viagensOrigemQuery = useQuery({
    queryKey: ["viagens", dataOrigem],
    queryFn: () => api.get<ViagemDia[]>("/viagens", { data: dataOrigem }),
    enabled: dataOrigem !== "",
  });

  const blocos = agruparPorBloco(viagensOrigemQuery.data ?? []);

  function selecionarData(novaData: string) {
    setDataOrigem(novaData);
    setSelecionados(new Set());
  }

  function marcarTodosAposCarregar(gruposCarregados: ViagemDia[][]) {
    setSelecionados(new Set(gruposCarregados.map(ancoraIdDoBloco)));
  }

  // Marca todos os carros como selecionados assim que a lista do dia
  // escolhido termina de carregar (comportamento padrao: copia tudo).
  if (viagensOrigemQuery.isSuccess && selecionados.size === 0 && blocos.length > 0 && dataOrigem !== "") {
    marcarTodosAposCarregar(blocos);
  }

  function alternar(ancoraId: number) {
    setSelecionados((atual) => {
      const novo = new Set(atual);
      if (novo.has(ancoraId)) novo.delete(ancoraId);
      else novo.add(ancoraId);
      return novo;
    });
  }

  const podeGravar = dataOrigem !== "" && dataOrigem !== dataDestino && selecionados.size > 0;

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Copiar agendamento de outro dia</h3>

        <div className="campo">
          <label>Copiar da data</label>
          <input type="date" value={dataOrigem} onChange={(e) => selecionarData(e.target.value)} />
        </div>
        {dataOrigem === dataDestino && dataOrigem !== "" && (
          <p className="erro-box">A data de origem deve ser diferente da data de destino</p>
        )}

        {dataOrigem !== "" && viagensOrigemQuery.isLoading && <p>Carregando carros do dia...</p>}
        {dataOrigem !== "" && viagensOrigemQuery.isSuccess && blocos.length === 0 && (
          <p>Nenhum carro encontrado nessa data.</p>
        )}

        {blocos.length > 0 && (
          <div className="campo">
            <label>Carros a copiar</label>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "16rem", overflowY: "auto" }}>
              {blocos.map((grupo, indice) => {
                const ancoraId = ancoraIdDoBloco(grupo);
                return (
                  <label key={ancoraId} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <input type="checkbox" checked={selecionados.has(ancoraId)} onChange={() => alternar(ancoraId)} />
                    Carro {indice + 1}/{blocos.length}
                  </label>
                );
              })}
            </div>
          </div>
        )}

        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primario"
            disabled={!podeGravar || enviando}
            onClick={() => onConfirmar(dataOrigem, [...selecionados])}
          >
            Gravar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
