import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { api } from "../api/client";
import { useList } from "../api/hooks";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL } from "../api/types";
import type {
  Condutor,
  DiaSemana,
  Empresa,
  Local,
  Regiao,
  Sentido,
  Sobras,
  UsuarioDesconsiderado,
  Veiculo,
  ViagemDia,
  ViagemDiaPassageiro,
  ViagemPreview,
} from "../api/types";
import CarroCard from "../components/board/CarroCard";
import SobrasPanel from "../components/board/SobrasPanel";
import DesconsideradosPanel from "../components/board/DesconsideradosPanel";
import SemVagaPanel from "../components/board/SemVagaPanel";
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

const CORTE_TARDE_MINUTOS = 14 * 60;

function minutosDaHora(hora: string): number {
  const [h, m] = hora.split(":").map(Number);
  return h * 60 + m;
}

function primeiraHora(viagem: ViagemDia): string {
  const horas = viagem.passageiros.map((p) => p.hora).sort();
  return horas[0] ?? viagem.horario_saida;
}

function periodoDaViagem(viagem: ViagemDia): "Manha" | "Tarde" {
  return minutosDaHora(primeiraHora(viagem)) >= CORTE_TARDE_MINUTOS ? "Tarde" : "Manha";
}

function agruparPorCondutor(viagens: ViagemDia[]): ViagemDia[][] {
  const grupos = new Map<string, ViagemDia[]>();
  for (const viagem of viagens) {
    const chave = viagem.condutor_id !== null ? `c${viagem.condutor_id}` : `v${viagem.id}`;
    const grupo = grupos.get(chave);
    if (grupo) grupo.push(viagem);
    else grupos.set(chave, [viagem]);
  }
  const lista = [...grupos.values()];
  for (const grupo of lista) {
    grupo.sort((a, b) => primeiraHora(a).localeCompare(primeiraHora(b)));
  }
  lista.sort((a, b) => primeiraHora(a[0]).localeCompare(primeiraHora(b[0])));
  return lista;
}

export default function AgendamentoDiaPage() {
  const [data, setData] = useState(hoje());
  const [periodo, setPeriodo] = useState<"Manha" | "Tarde">("Manha");
  const [modo, setModo] = useState<"dia" | "base">("dia");
  const [diaSemanaBase, setDiaSemanaBase] = useState<DiaSemana>("SEG");
  const queryClient = useQueryClient();

  const { data: regioes } = useList<Regiao>("regioes", "/regioes");
  const { data: empresas } = useList<Empresa>("empresas", "/empresas");
  const { data: veiculos } = useList<Veiculo>("veiculos", "/veiculos");
  const { data: condutores } = useList<Condutor>("condutores", "/condutores");
  const { data: locais } = useList<Local>("locais", "/locais");

  const viagensQuery = useQuery({
    queryKey: ["viagens", data],
    queryFn: () => api.get<ViagemDia[]>("/viagens", { data }),
  });
  const sobrasQuery = useQuery({
    queryKey: ["sobras", data],
    queryFn: () => api.get<Sobras>("/viagens/sobras", { data }),
  });
  const desconsideradosQuery = useQuery({
    queryKey: ["desconsiderados", data],
    queryFn: () => api.get<UsuarioDesconsiderado[]>("/viagens/desconsiderados", { data }),
  });
  const semVagaQuery = useQuery({
    queryKey: ["sem-vaga", data],
    queryFn: () => api.get<ViagemDiaPassageiro[]>("/viagens/sem-vaga", { data }),
  });

  const previewQuery = useQuery({
    queryKey: ["preview-semana", diaSemanaBase],
    queryFn: () => api.get<ViagemPreview[]>("/viagens/preview-semana", { dia_semana: diaSemanaBase }),
    enabled: false,
  });

  function invalidarDia() {
    queryClient.invalidateQueries({ queryKey: ["viagens", data] });
    queryClient.invalidateQueries({ queryKey: ["sobras", data] });
    queryClient.invalidateQueries({ queryKey: ["desconsiderados", data] });
    queryClient.invalidateQueries({ queryKey: ["sem-vaga", data] });
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
  const gerarPreviewBase = useMutation({
    mutationFn: () => api.post<ViagemPreview[]>("/viagens/preview-semana/gerar", undefined, { dia_semana: diaSemanaBase }),
    onSuccess: (dados) => {
      queryClient.setQueryData(["preview-semana", diaSemanaBase], dados);
    },
  });
  const moverPassageiroBase = useMutation({
    mutationFn: ({ agendaId, sentido, ordem }: { agendaId: number; sentido: Sentido; ordem: number }) =>
      api.patch<ViagemPreview[]>(`/viagens/preview-semana/passageiros/${agendaId}/mover`, {
        dia_semana: diaSemanaBase,
        sentido,
        ordem,
      }),
    onSuccess: (dados) => {
      queryClient.setQueryData(["preview-semana", diaSemanaBase], dados);
    },
  });
  const atribuir = useMutation({
    mutationFn: async ({ viagemIds, body }: { viagemIds: number[]; body: unknown }) => {
      for (const viagemId of viagemIds) {
        await api.patch(`/viagens/${viagemId}/atribuir`, body);
      }
    },
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
  const limparDia = useMutation({
    mutationFn: () => api.delete("/viagens/limpar", { data }),
    onSuccess: invalidarDia,
  });

  function mensagemErro(e: unknown, fallback: string): string {
    return e instanceof Error ? e.message : fallback;
  }

  const [modalAdicionar, setModalAdicionar] = useState<number | null>(null);
  const [modalAtribuir, setModalAtribuir] = useState<{
    viagemIds: number[];
    condutorAtualId: number | null;
    veiculoAtualId: number | null;
  } | null>(null);
  const [modalAbrirCarro, setModalAbrirCarro] = useState(false);
  const [modalEscalas, setModalEscalas] = useState(false);
  const [modalFerias, setModalFerias] = useState(false);
  const [modalCancelar, setModalCancelar] = useState<number | null>(null);
  const [modalRemoverPassageiro, setModalRemoverPassageiro] = useState<number | null>(null);
  const [modalEditarPassageiro, setModalEditarPassageiro] = useState<ViagemDiaPassageiro | null>(null);
  const [modalLimparDia, setModalLimparDia] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEndDia(activeData: { viagemId: number; passageiroId: number }, overData: { viagemId: number; passageiroId?: number } | undefined, destinoId: number) {
    const viagens = viagensQuery.data ?? [];
    const carroDestino = viagens.find((v) => v.id === destinoId);
    if (!carroDestino) return;
    if (activeData.passageiroId === overData?.passageiroId) return; // solto em cima de si mesmo

    // posicao alvo calculada sobre a lista SEM o passageiro ativo, pra bater
    // certinho com o reindex que o backend faz (evita off-by-one quando
    // reordena dentro da mesma leva, empurrando o ativo pra frente)
    const semAtivo = carroDestino.passageiros.filter((p) => p.id !== activeData.passageiroId);
    let novaOrdem = semAtivo.length;
    if (overData?.passageiroId !== undefined) {
      const idx = semAtivo.findIndex((p) => p.id === overData.passageiroId);
      if (idx >= 0) novaOrdem = idx;
    }

    moverPassageiro.mutate(
      { id: activeData.passageiroId, viagem_dia_destino_id: destinoId, ordem: novaOrdem },
      {
        onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao mover passageiro")),
      },
    );
  }

  function handleDragEndBase(activeData: { viagemId: number; passageiroId: number }, overData: { viagemId: number; passageiroId?: number } | undefined, destinoId: number) {
    const grupos = previewQuery.data ?? [];
    const grupoOrigem = grupos.find((g) => g.passageiros.some((p) => p.id === activeData.passageiroId));
    const grupoDestino = grupos.find((g) => g.id === destinoId);
    const passageiroAtivo = grupoOrigem?.passageiros.find((p) => p.id === activeData.passageiroId);
    if (!grupoOrigem || !grupoDestino || !passageiroAtivo) return;
    if (activeData.passageiroId === overData?.passageiroId) return; // solto em cima de si mesmo

    // no modo Base so faz sentido reordenar dentro do mesmo "bucket" (regiao
    // + sentido + horario) -- arrastar pra um sentido/horario diferente
    // mudaria a agenda semanal da pessoa, nao so a ordem, e isso nao e feito
    // por drag aqui
    const referencia = grupoDestino.passageiros.find((p) => p.id !== activeData.passageiroId);
    const mesmoBucket =
      grupoDestino.regiao_id === grupoOrigem.regiao_id &&
      (!referencia || (referencia.sentido === passageiroAtivo.sentido && referencia.hora === passageiroAtivo.hora));
    if (!mesmoBucket) return;

    const bucket = grupos.filter(
      (g) =>
        g.regiao_id === grupoOrigem.regiao_id &&
        g.passageiros[0]?.sentido === passageiroAtivo.sentido &&
        g.passageiros[0]?.hora === passageiroAtivo.hora,
    );

    const destinoSemAtivo = grupoDestino.passageiros.filter((p) => p.id !== activeData.passageiroId);
    let posicaoNoGrupoDestino = destinoSemAtivo.length;
    if (overData?.passageiroId !== undefined) {
      const idx = destinoSemAtivo.findIndex((p) => p.id === overData.passageiroId);
      if (idx >= 0) posicaoNoGrupoDestino = idx;
    }

    // ordem_ida/ordem_retorno e um criterio global dentro do bucket inteiro
    // (nao "dentro de um carro"), entao o indice enviado ao backend soma
    // quantos ficam antes do carro de destino nos outros carros do bucket
    let antesDoDestino = 0;
    for (const g of bucket) {
      if (g.id === grupoDestino.id) break;
      antesDoDestino += g.id === grupoOrigem.id ? g.passageiros.length - 1 : g.passageiros.length;
    }

    moverPassageiroBase.mutate(
      { agendaId: passageiroAtivo.agenda_id, sentido: passageiroAtivo.sentido, ordem: antesDoDestino + posicaoNoGrupoDestino },
      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao reordenar no molde")) },
    );
  }

  function handleDragEnd(evento: DragEndEvent) {
    const { active, over } = evento;
    if (!over) return;

    const activeData = active.data.current as { viagemId: number; passageiroId: number } | undefined;
    if (!activeData) return;

    const overData = over.data.current as { viagemId: number; passageiroId?: number } | undefined;
    const destinoId = overData?.viagemId ?? Number(String(over.id).replace("carro-", ""));
    if (!destinoId || Number.isNaN(destinoId)) return;

    if (modo === "base") handleDragEndBase(activeData, overData, destinoId);
    else handleDragEndDia(activeData, overData, destinoId);
  }

  const viagens = modo === "dia" ? viagensQuery.data ?? [] : previewQuery.data ?? [];
  const viagensDoPeriodo = viagens.filter((v) => periodoDaViagem(v) === periodo);
  const gruposCondutor = agruparPorCondutor(viagensDoPeriodo);

  return (
    <div>
      <h2>Agendamento do dia</h2>

      {erro && (
        <div className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
          {erro} (clique para fechar)
        </div>
      )}

      {modo === "dia" &&
        (viagensQuery.error || sobrasQuery.error || desconsideradosQuery.error || semVagaQuery.error) && (
          <div className="erro-box">
            Erro ao carregar dados do dia:{" "}
            {mensagemErro(
              viagensQuery.error ?? sobrasQuery.error ?? desconsideradosQuery.error ?? semVagaQuery.error,
              "erro desconhecido",
            )}
          </div>
        )}

      {modo === "base" && previewQuery.error && (
        <div className="erro-box">Erro ao carregar previa do molde: {mensagemErro(previewQuery.error, "erro desconhecido")}</div>
      )}

      <div className="linha-toolbar">
        <div className="btn-group">
          <button className={`btn btn-sm ${modo === "dia" ? "btn-group-ativo" : ""}`} onClick={() => setModo("dia")}>
            Dia
          </button>
          <button className={`btn btn-sm ${modo === "base" ? "btn-group-ativo" : ""}`} onClick={() => setModo("base")}>
            Base
          </button>
        </div>

        {modo === "dia" ? (
          <div className="campo">
            <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
          </div>
        ) : (
          <div className="campo">
            <select value={diaSemanaBase} onChange={(e) => setDiaSemanaBase(e.target.value as DiaSemana)}>
              {DIAS_SEMANA.map((dia) => (
                <option key={dia} value={dia}>
                  {DIAS_SEMANA_LABEL[dia]}
                </option>
              ))}
            </select>
          </div>
        )}

        {modo === "dia" && viagens.length > 0 && (
          <button className="btn btn-perigo" onClick={() => setModalLimparDia(true)} disabled={limparDia.isPending}>
            Limpar
          </button>
        )}
        {modo === "dia" && viagens.length === 0 && !viagensQuery.isLoading && (
          <button
            className="btn btn-primario"
            onClick={() =>
              gerar.mutate(undefined, { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao gerar agendamento do dia")) })
            }
            disabled={gerar.isPending}
          >
            Gerar agendamento do dia
          </button>
        )}
        {modo === "base" && (
          <button
            className="btn btn-primario"
            onClick={() =>
              gerarPreviewBase.mutate(undefined, {
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao gerar previa do molde")),
              })
            }
            disabled={gerarPreviewBase.isPending}
          >
            Gerar previa
          </button>
        )}
        {modo === "dia" && (
          <button className="btn" onClick={() => setModalAbrirCarro(true)}>
            + Abrir carro
          </button>
        )}
        {modo === "dia" && (
          <button
            className="btn"
            onClick={() =>
              api
                .download("/viagens/agendamentos/zip", { data })
                .catch((e: unknown) => setErro(mensagemErro(e, "Erro ao baixar agendamentos")))
            }
          >
            Agendamentos (zip)
          </button>
        )}
        {modo === "dia" && (
          <button className="btn" onClick={() => setModalEscalas(true)}>
            Exportar escalas
          </button>
        )}
        {modo === "dia" && (
          <button className="btn" onClick={() => setModalFerias(true)}>
            Ferias
          </button>
        )}
        {modo === "dia" && (
          <button
            className="btn"
            onClick={() =>
              api
                .download("/viagens/agendamentos/resumo", { data })
                .catch((e: unknown) => setErro(mensagemErro(e, "Erro ao baixar resumo")))
            }
          >
            Resumo
          </button>
        )}

        <div className="btn-group" style={{ marginLeft: "auto" }}>
          <button
            className={`btn btn-sm ${periodo === "Manha" ? "btn-group-ativo" : ""}`}
            onClick={() => setPeriodo("Manha")}
          >
            Manha
          </button>
          <button
            className={`btn btn-sm ${periodo === "Tarde" ? "btn-group-ativo" : ""}`}
            onClick={() => setPeriodo("Tarde")}
          >
            Tarde
          </button>
        </div>
      </div>

      {modo === "dia" && viagensQuery.isLoading && <p>Carregando...</p>}
      {modo === "base" && gerarPreviewBase.isPending && <p>Gerando previa...</p>}

      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="board-layout">
          <div className="board">
            {gruposCondutor.map((grupo, indice) => (
              <CarroCard
                key={grupo[0].condutor_id !== null ? `c${grupo[0].condutor_id}` : `v${grupo[0].id}`}
                viagens={grupo}
                empresas={empresas ?? []}
                veiculos={veiculos ?? []}
                condutores={condutores ?? []}
                locais={locais ?? []}
                regioes={regioes ?? []}
                tituloSemVeiculo={
                  modo === "base" ? (grupo[0].capacidade === 0 ? "Sem vaga" : `Grupo ${indice + 1}`) : "Carro sem veiculo"
                }
                onAdicionarPassageiro={modo === "dia" ? setModalAdicionar : undefined}
                onRemoverPassageiro={modo === "dia" ? setModalRemoverPassageiro : undefined}
                onCancelarPassageiro={modo === "dia" ? setModalCancelar : undefined}
                onEditarPassageiro={modo === "dia" ? setModalEditarPassageiro : undefined}
                onAtribuir={modo === "dia" ? setModalAtribuir : undefined}
                onRemoverCarro={
                  modo === "dia"
                    ? (id) =>
                        removerCarro.mutate(id, {
                          onError: (e: unknown) => setErro(mensagemErro(e, "Nao foi possivel remover o carro")),
                        })
                    : undefined
                }
              />
            ))}
          </div>

          {modo === "dia" && semVagaQuery.data && (
            <SemVagaPanel
              passageiros={semVagaQuery.data}
              locais={locais ?? []}
              onRemover={setModalRemoverPassageiro}
              onCancelar={setModalCancelar}
              onEditar={setModalEditarPassageiro}
            />
          )}

        </div>

        {modo === "dia" && sobrasQuery.data && (
          <SobrasPanel
            sobras={sobrasQuery.data}
            onMarcarFolga={(ids) =>
              marcarFolga.mutate(ids, { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao marcar folga")) })
            }
            aplicando={marcarFolga.isPending}
          />
        )}

        {modo === "dia" && desconsideradosQuery.data && <DesconsideradosPanel desconsiderados={desconsideradosQuery.data} />}
      </DndContext>

      {modalAdicionar !== null && (
        <AdicionarPassageiroModal
          onFechar={() => setModalAdicionar(null)}
          onConfirmar={(dados) => {
            adicionarPassageiro.mutate(
              { viagemId: modalAdicionar, body: { ...dados, sentido: dados.sentido as Sentido } },
              {
                onSuccess: () => setModalAdicionar(null),
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao adicionar passageiro")),
              },
            );
          }}
        />
      )}

      {modalAtribuir !== null && (
        <AtribuirModal
          condutores={(condutores ?? []).filter((c) => c.status === "Ativo")}
          veiculos={(veiculos ?? []).filter((v) => v.status === "Ativo")}
          condutorAtualId={modalAtribuir.condutorAtualId}
          veiculoAtualId={modalAtribuir.veiculoAtualId}
          onFechar={() => setModalAtribuir(null)}
          onConfirmar={(dados) =>
            atribuir.mutate(
              { viagemIds: modalAtribuir.viagemIds, body: dados },
              {
                onSuccess: () => setModalAtribuir(null),
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao atribuir condutor/veiculo")),
              },
            )
          }
        />
      )}

      {modalAbrirCarro && (
        <AbrirCarroModal
          regioes={regioes ?? []}
          onFechar={() => setModalAbrirCarro(false)}
          onConfirmar={(dados) =>
            abrirCarro.mutate(dados, {
              onSuccess: () => setModalAbrirCarro(false),
              onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao abrir carro")),
            })
          }
        />
      )}

      {modalEscalas && <ExportarEscalasModal onFechar={() => setModalEscalas(false)} />}
      {modalFerias && <FeriasModal onFechar={() => setModalFerias(false)} />}

      {modalCancelar !== null && (
        <CancelarPassageiroModal
          onFechar={() => setModalCancelar(null)}
          onConfirmar={(motivo) =>
            cancelarPassageiro.mutate(
              { id: modalCancelar, motivo },
              {
                onSuccess: () => setModalCancelar(null),
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao cancelar passageiro")),
              },
            )
          }
        />
      )}

      {modalLimparDia && (
        <ConfirmarModal
          titulo="Limpar agendamento do dia"
          mensagem="Apagar TODO o agendamento desse dia (todos os carros e passageiros gerados/lancados)? Essa acao nao pode ser desfeita."
          onFechar={() => setModalLimparDia(false)}
          onConfirmar={() =>
            limparDia.mutate(undefined, {
              onSuccess: () => setModalLimparDia(false),
              onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao limpar o dia")),
            })
          }
        />
      )}

      {modalRemoverPassageiro !== null && (
        <ConfirmarModal
          titulo="Remover passageiro"
          mensagem="Remover esse atendimento do carro? Ao contrario de Cancelar, isso apaga o registro sem deixar historico."
          onFechar={() => setModalRemoverPassageiro(null)}
          onConfirmar={() =>
            removerPassageiro.mutate(modalRemoverPassageiro, {
              onSuccess: () => setModalRemoverPassageiro(null),
              onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover passageiro")),
            })
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
            acompanhante: modalEditarPassageiro.acompanhante,
            observacoes: modalEditarPassageiro.observacoes ?? "",
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
                  acompanhante: dados.acompanhante,
                  observacoes: dados.observacoes,
                },
              },
              {
                onSuccess: () => setModalEditarPassageiro(null),
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao editar passageiro")),
              },
            )
          }
        />
      )}
    </div>
  );
}
