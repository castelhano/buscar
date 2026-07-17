import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { agruparPorBloco, ancoraIdDoBloco } from "../../api/blocos";
import type { ViagemDia } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

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
  // Data cujos carros ja foram auto-marcados no carregamento -- sem isso,
  // desmarcar manualmente todos os carros faria o efeito abaixo remarcar
  // tudo de novo no proximo render (selecionados.size voltando a 0).
  const [dataAutoSelecionada, setDataAutoSelecionada] = useState<string | null>(null);

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

  // Marca todos os carros como selecionados assim que a lista do dia
  // escolhido termina de carregar (comportamento padrao: copia tudo).
  if (viagensOrigemQuery.isSuccess && dataOrigem !== "" && dataAutoSelecionada !== dataOrigem && blocos.length > 0) {
    setDataAutoSelecionada(dataOrigem);
    setSelecionados(new Set(blocos.map(ancoraIdDoBloco)));
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
