import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { api } from "../api/client";
import { useList } from "../api/hooks";
import type { Condutor, Empresa, Regiao, Sentido, Sobras, Veiculo, ViagemDia, ViagemDiaPassageiro } from "../api/types";
import CarroCard from "../components/board/CarroCard";
import SobrasPanel from "../components/board/SobrasPanel";
import AdicionarPassageiroModal from "../components/board/AdicionarPassageiroModal";
import AtribuirModal from "../components/board/AtribuirModal";
import AbrirCarroModal from "../components/board/AbrirCarroModal";
import ExportarEscalasModal from "../components/board/ExportarEscalasModal";
import FeriasModal from "../components/board/FeriasModal";
import CancelarPassageiroModal from "../components/board/CancelarPassageiroModal";
import ConfirmarModal from "../components/board/ConfirmarModal";

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

export default function AgendamentoDiaPage() {
  const [data, setData] = useState(hoje());
  const queryClient = useQueryClient();

  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: empresas } = useList<Empresa>("empresas", "/empresas");
  const { data: veiculos } = useList<Veiculo>("veiculos", "/veiculos");
  const { data: condutores } = useList<Condutor>("condutores", "/condutores");

  const viagensQuery = useQuery({
    queryKey: ["viagens", data],
    queryFn: () => api.get<ViagemDia[]>("/viagens", { data }),
  });
  const sobrasQuery = useQuery({
    queryKey: ["sobras", data],
    queryFn: () => api.get<Sobras>("/viagens/sobras", { data }),
  });

  function invalidarDia() {
    queryClient.invalidateQueries({ queryKey: ["viagens", data] });
    queryClient.invalidateQueries({ queryKey: ["sobras", data] });
  }

  const gerar = useMutation({
    mutationFn: () => api.post<ViagemDia[]>("/viagens/gerar", undefined, { data }),
    onSuccess: invalidarDia,
  });

  const adicionarPassageiro = useMutation({
    mutationFn: ({ viagemId, body }: { viagemId: number; body: unknown }) => api.post(`/viagens/${viagemId}/passageiros`, body),
    onSuccess: invalidarDia,
  });
  const removerPassageiro = useMutation({
    mutationFn: (id: number) => api.delete(`/viagens/passageiros/${id}`),
    onSuccess: invalidarDia,
  });
  const cancelarPassageiro = useMutation({
    mutationFn: ({ id, motivo }: { id: number; motivo: string }) =>
      api.patch(`/viagens/passageiros/${id}/status`, undefined, { status: "Cancelado", observacoes: motivo || undefined }),
    onSuccess: invalidarDia,
  });
  const editarPassageiro = useMutation({
    mutationFn: ({ id, body }: { id: number; body: unknown }) => api.patch(`/viagens/passageiros/${id}`, body),
    onSuccess: invalidarDia,
  });
  const moverPassageiro = useMutation({
    mutationFn: ({ id, viagem_dia_destino_id, ordem }: { id: number; viagem_dia_destino_id: number; ordem: number }) =>
      api.patch(`/viagens/passageiros/${id}/mover`, { viagem_dia_destino_id, ordem }),
    onSuccess: invalidarDia,
  });
  const atribuir = useMutation({
    mutationFn: ({ viagemId, body }: { viagemId: number; body: unknown }) => api.patch(`/viagens/${viagemId}/atribuir`, body),
    onSuccess: invalidarDia,
  });
  const removerCarro = useMutation({
    mutationFn: (viagemId: number) => api.delete(`/viagens/${viagemId}`),
    onSuccess: invalidarDia,
  });
  const abrirCarro = useMutation({
    mutationFn: (body: { regiao_id: number; horario_saida: string; capacidade: number }) =>
      api.post("/viagens/abrir", { ...body, data }),
    onSuccess: invalidarDia,
  });
  const marcarFolga = useMutation({
    mutationFn: async (condutorIds: number[]) => {
      for (const id of condutorIds) {
        await api.post(`/viagens/sobras/condutor/${id}/folga`, undefined, { data });
      }
    },
    onSuccess: invalidarDia,
  });

  const [modalAdicionar, setModalAdicionar] = useState<number | null>(null);
  const [modalAtribuir, setModalAtribuir] = useState<number | null>(null);
  const [modalAbrirCarro, setModalAbrirCarro] = useState(false);
  const [modalEscalas, setModalEscalas] = useState(false);
  const [modalFerias, setModalFerias] = useState(false);
  const [modalCancelar, setModalCancelar] = useState<number | null>(null);
  const [modalRemoverPassageiro, setModalRemoverPassageiro] = useState<number | null>(null);
  const [modalEditarPassageiro, setModalEditarPassageiro] = useState<ViagemDiaPassageiro | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEnd(evento: DragEndEvent) {
    const { active, over } = evento;
    if (!over) return;
    const viagens = viagensQuery.data ?? [];

    const activeData = active.data.current as { viagemId: number; passageiroId: number } | undefined;
    if (!activeData) return;

    const overData = over.data.current as { viagemId: number; passageiroId?: number } | undefined;
    const destinoViagemId = overData?.viagemId ?? Number(String(over.id).replace("carro-", ""));
    if (!destinoViagemId || Number.isNaN(destinoViagemId)) return;

    const carroDestino = viagens.find((v) => v.id === destinoViagemId);
    if (!carroDestino) return;

    let novaOrdem = carroDestino.passageiros.length;
    if (overData?.passageiroId !== undefined) {
      const idx = carroDestino.passageiros.findIndex((p) => p.id === overData.passageiroId);
      if (idx >= 0) novaOrdem = idx;
    }

    if (destinoViagemId === activeData.viagemId && novaOrdem === carroDestino.passageiros.findIndex((p) => p.id === activeData.passageiroId)) {
      return; // sem mudanca real
    }

    moverPassageiro.mutate(
      { id: activeData.passageiroId, viagem_dia_destino_id: destinoViagemId, ordem: novaOrdem },
      {
        onError: (e: unknown) => setErro(e instanceof Error ? e.message : "Erro ao mover passageiro"),
      },
    );
  }

  const viagens = viagensQuery.data ?? [];

  return (
    <div>
      <h2>Agendamento do dia</h2>

      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}

      <div className="linha-toolbar">
        <div className="campo">
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
        </div>
        {viagens.length === 0 && !viagensQuery.isLoading && (
          <button className="btn btn-primario" onClick={() => gerar.mutate()} disabled={gerar.isPending}>
            Gerar agendamento do dia
          </button>
        )}
        <button className="btn" onClick={() => setModalAbrirCarro(true)}>
          + Abrir carro
        </button>
        <a
          className="btn"
          href={api.downloadUrl("/viagens/agendamentos/zip", { data })}
          target="_blank"
          rel="noreferrer"
          style={{ textDecoration: "none" }}
        >
          Agendamentos (zip)
        </a>
        <button className="btn" onClick={() => setModalEscalas(true)}>
          Exportar escalas
        </button>
        <button className="btn" onClick={() => setModalFerias(true)}>
          Ferias
        </button>
      </div>

      {viagensQuery.isLoading && <p>Carregando...</p>}

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="board">
          {viagens.map((viagem) => (
            <CarroCard
              key={viagem.id}
              viagem={viagem}
              empresas={empresas ?? []}
              veiculos={veiculos ?? []}
              condutores={condutores ?? []}
              onAdicionarPassageiro={setModalAdicionar}
              onRemoverPassageiro={setModalRemoverPassageiro}
              onCancelarPassageiro={setModalCancelar}
              onEditarPassageiro={setModalEditarPassageiro}
              onAtribuir={setModalAtribuir}
              onRemoverCarro={(id) =>
                removerCarro.mutate(id, {
                  onError: (e: unknown) => setErro(e instanceof Error ? e.message : "Nao foi possivel remover o carro"),
                })
              }
            />
          ))}
        </div>
      </DndContext>

      {sobrasQuery.data && (
        <SobrasPanel sobras={sobrasQuery.data} onMarcarFolga={(ids) => marcarFolga.mutate(ids)} aplicando={marcarFolga.isPending} />
      )}

      {modalAdicionar !== null && (
        <AdicionarPassageiroModal
          onFechar={() => setModalAdicionar(null)}
          onConfirmar={(dados) => {
            adicionarPassageiro.mutate(
              { viagemId: modalAdicionar, body: { ...dados, sentido: dados.sentido as Sentido } },
              { onSuccess: () => setModalAdicionar(null) },
            );
          }}
        />
      )}

      {modalAtribuir !== null && (
        <AtribuirModal
          condutores={(condutores ?? []).filter((c) => c.status === "Ativo")}
          veiculos={(veiculos ?? []).filter((v) => v.status === "Ativo")}
          onFechar={() => setModalAtribuir(null)}
          onConfirmar={(dados) => atribuir.mutate({ viagemId: modalAtribuir, body: dados }, { onSuccess: () => setModalAtribuir(null) })}
        />
      )}

      {modalAbrirCarro && (
        <AbrirCarroModal
          regioes={regioes ?? []}
          onFechar={() => setModalAbrirCarro(false)}
          onConfirmar={(dados) => abrirCarro.mutate(dados, { onSuccess: () => setModalAbrirCarro(false) })}
        />
      )}

      {modalEscalas && <ExportarEscalasModal onFechar={() => setModalEscalas(false)} />}
      {modalFerias && <FeriasModal onFechar={() => setModalFerias(false)} />}

      {modalCancelar !== null && (
        <CancelarPassageiroModal
          onFechar={() => setModalCancelar(null)}
          onConfirmar={(motivo) =>
            cancelarPassageiro.mutate({ id: modalCancelar, motivo }, { onSuccess: () => setModalCancelar(null) })
          }
        />
      )}

      {modalRemoverPassageiro !== null && (
        <ConfirmarModal
          titulo="Remover passageiro"
          mensagem="Remover esse atendimento do carro? Ao contrario de Cancelar, isso apaga o registro sem deixar historico."
          onFechar={() => setModalRemoverPassageiro(null)}
          onConfirmar={() =>
            removerPassageiro.mutate(modalRemoverPassageiro, { onSuccess: () => setModalRemoverPassageiro(null) })
          }
        />
      )}

      {modalEditarPassageiro !== null && (
        <AdicionarPassageiroModal
          titulo="Editar atendimento"
          textoConfirmar="Salvar edicao"
          usuarioFixo={{ id: modalEditarPassageiro.usuario_id, nome: modalEditarPassageiro.usuario.nome }}
          valoresIniciais={{
            sentido: modalEditarPassageiro.sentido,
            hora: modalEditarPassageiro.hora.slice(0, 5),
            origem: modalEditarPassageiro.origem ?? "",
            regiao_origem_id: modalEditarPassageiro.regiao_origem_id ?? "",
            destino_id: modalEditarPassageiro.destino_id ?? "",
          }}
          onFechar={() => setModalEditarPassageiro(null)}
          onConfirmar={(dados) =>
            editarPassageiro.mutate(
              {
                id: modalEditarPassageiro.id,
                body: {
                  sentido: dados.sentido,
                  hora: dados.hora,
                  origem: dados.origem,
                  regiao_origem_id: dados.regiao_origem_id,
                  destino_id: dados.destino_id,
                  regiao_destino_id: dados.regiao_destino_id,
                },
              },
              { onSuccess: () => setModalEditarPassageiro(null) },
            )
          }
        />
      )}
    </div>
  );
}
