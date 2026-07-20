import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  pointerWithin,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
} from "@dnd-kit/core";
import { api } from "../api/client";
import { agruparPorBloco, ancoraIdDoBloco } from "../api/blocos";
import { useList } from "../api/hooks";
import { CORTE_TARDE_MINUTOS, minutosDaHora, periodoDaViagem } from "../api/periodo";
import { DIAS_SEMANA, DIAS_SEMANA_LABEL, diaSemanaFromData } from "../api/types";
import type {
  Condutor,
  CondutorFerias,
  DiaSemana,
  EstruturaBase,
  Empresa,
  GrupoBase,
  GrupoRevezamento,
  Local,
  Regiao,
  Sentido,
  Sobras,
  UsuarioDesconsiderado,
  Veiculo,
  ViagemBase,
  ViagemDia,
  ViagemDiaPassageiro,
} from "../api/types";
import CarroCard from "../components/board/CarroCard";
import CarroBaseCard from "../components/board/CarroBaseCard";
import GruposRevezamentoBar from "../components/board/GruposRevezamentoBar";
import ModalCondutoresRevezamento from "../components/board/ModalCondutoresRevezamento";
import NaoClassificadosBasePanel from "../components/board/NaoClassificadosBasePanel";
import SobrasPanel from "../components/board/SobrasPanel";
import DesconsideradosPanel from "../components/board/DesconsideradosPanel";
import CancelamentosPanel from "../components/board/CancelamentosPanel";
import SemVagaPanel from "../components/board/SemVagaPanel";
import AdicionarPassageiroModal from "../components/board/AdicionarPassageiroModal";
import AtribuirModal from "../components/board/AtribuirModal";
import AbrirCarroModal from "../components/board/AbrirCarroModal";
import ExportarEscalasModal from "../components/board/ExportarEscalasModal";
import ExportarAgendamentosModal from "../components/board/ExportarAgendamentosModal";
import OcupacaoBaseModal from "../components/board/OcupacaoBaseModal";
import CancelarPassageiroModal from "../components/board/CancelarPassageiroModal";
import ConfirmarModal from "../components/board/ConfirmarModal";
import ReordenarPosicaoModal from "../components/board/ReordenarPosicaoModal";
import CopiarDiaModal from "../components/board/CopiarDiaModal";

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

function periodoDaViagemBase(viagem: ViagemBase): "Manha" | "Tarde" {
  return minutosDaHora(viagem.hora) >= CORTE_TARDE_MINUTOS ? "Tarde" : "Manha";
}

// pointerWithin acerta o droppable que o cursor esta literalmente sobre
// (respeita o aninhamento carro > viagem > passageiro); closestCenter entra
// so de fallback quando o ponteiro sai de toda area droppable (ex: fora do
// board) -- sem isso, um carro vazio/pequeno perde pra vizinhos maiores
// mesmo com o cursor em cima dele.
const collisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args);
  return pointerCollisions.length > 0 ? pointerCollisions : closestCenter(args);
};

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
  const { data: ferias } = useList<CondutorFerias>("ferias", "/ferias");

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
  const travamentoQuery = useQuery({
    queryKey: ["travamento", data],
    queryFn: () => api.get<{ data: string; travado: boolean; travado_em: string | null }>("/viagens/travamento", { data }),
  });
  const travado = travamentoQuery.data?.travado ?? false;

  const estruturaBaseQuery = useQuery({
    queryKey: ["estrutura-base", diaSemanaBase],
    queryFn: () => api.get<EstruturaBase>(`/base/${diaSemanaBase}`),
  });

  function atualizarEstruturaBase(dados: EstruturaBase) {
    queryClient.setQueryData(["estrutura-base", diaSemanaBase], dados);
  }

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
  const tirarPassageiroDoCarro = useMutation({
    mutationFn: (id: number) => api.patch(`/viagens/passageiros/${id}/tirar-do-carro`),
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
  const moverPassageiroBloco = useMutation({
    mutationFn: ({ id, bloco_id }: { id: number; bloco_id: number }) =>
      api.patch(`/viagens/passageiros/${id}/mover-bloco`, { bloco_id }),
    onSuccess: invalidarDia,
  });
  const criarGrupoBase = useMutation({
    mutationFn: () => api.post<EstruturaBase>(`/base/${diaSemanaBase}/grupos`),
    onSuccess: atualizarEstruturaBase,
  });
  const removerGrupoBase = useMutation({
    mutationFn: (grupoId: number) => api.delete<EstruturaBase>(`/base/grupos/${grupoId}`),
    onSuccess: atualizarEstruturaBase,
  });
  const criarViagemBase = useMutation({
    mutationFn: ({ grupoId, sentido, hora }: { grupoId: number; sentido: Sentido; hora: string }) =>
      api.post<EstruturaBase>(`/base/grupos/${grupoId}/viagens`, { sentido, hora }),
    onSuccess: atualizarEstruturaBase,
  });
  const removerViagemBase = useMutation({
    mutationFn: (viagemId: number) => api.delete<EstruturaBase>(`/base/viagens/${viagemId}`),
    onSuccess: atualizarEstruturaBase,
  });
  const removerMembroBase = useMutation({
    mutationFn: (membroId: number) => api.delete<EstruturaBase>(`/base/membros/${membroId}`),
    onSuccess: atualizarEstruturaBase,
  });
  const alterarHoraViagemBase = useMutation({
    mutationFn: ({ viagemId, hora }: { viagemId: number; hora: string }) =>
      api.patch<EstruturaBase>(`/base/viagens/${viagemId}/hora`, { hora }),
    onSuccess: atualizarEstruturaBase,
  });
  const moverMembroBase = useMutation({
    mutationFn: ({
      agendaId,
      sentido,
      grupoBaseId,
      hora,
      ordem,
    }: {
      agendaId: number;
      sentido: Sentido;
      grupoBaseId: number;
      hora: string;
      ordem?: number;
    }) => api.patch<EstruturaBase>(`/base/membros/${agendaId}/mover`, { sentido, grupo_base_id: grupoBaseId, hora, ordem }),
    onSuccess: atualizarEstruturaBase,
  });
  const criarRevezamento = useMutation({
    mutationFn: () => api.post<EstruturaBase>(`/base/${diaSemanaBase}/revezamentos`, {}),
    onSuccess: atualizarEstruturaBase,
  });
  const removerRevezamento = useMutation({
    mutationFn: (grupoRevezamentoId: number) => api.delete<EstruturaBase>(`/base/revezamentos/${grupoRevezamentoId}`),
    onSuccess: atualizarEstruturaBase,
  });
  const definirCarrosRevezamento = useMutation({
    mutationFn: ({ grupoRevezamentoId, grupoBaseIds }: { grupoRevezamentoId: number; grupoBaseIds: number[] }) =>
      api.put<EstruturaBase>(`/base/revezamentos/${grupoRevezamentoId}/carros`, { grupo_base_ids: grupoBaseIds }),
    onSuccess: atualizarEstruturaBase,
  });
  const definirCondutoresRevezamento = useMutation({
    mutationFn: ({ grupoRevezamentoId, condutorIds }: { grupoRevezamentoId: number; condutorIds: number[] }) =>
      api.put<EstruturaBase>(`/base/revezamentos/${grupoRevezamentoId}/condutores`, { condutor_ids: condutorIds }),
    onSuccess: atualizarEstruturaBase,
  });
  const girarRevezamento = useMutation({
    mutationFn: (grupoRevezamentoId: number) => api.post<EstruturaBase>(`/base/revezamentos/${grupoRevezamentoId}/girar`, {}),
    onSuccess: atualizarEstruturaBase,
  });
  const atribuir = useMutation({
    mutationFn: (dados: { viagemIds: number[]; condutor_id: number | null; veiculo_id: number | null }) =>
      api.patch("/viagens/atribuir-bloco", {
        viagem_ids: dados.viagemIds,
        condutor_id: dados.condutor_id,
        veiculo_id: dados.veiculo_id,
      }),
    onSuccess: invalidarDia,
  });
  const reordenarBlocos = useMutation({
    mutationFn: (ancoraIds: number[]) => api.patch("/viagens/reordenar-blocos", { data, ancora_ids: ancoraIds }),
    onSuccess: invalidarDia,
  });
  const limparCondutorVeiculo = useMutation({
    mutationFn: async (viagemIds: number[]) => {
      for (const viagemId of viagemIds) {
        await api.patch(`/viagens/${viagemId}/atribuir`, { limpar: true });
      }
    },
    onSuccess: invalidarDia,
  });
  const removerViagem = useMutation({
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
  const travarDia = useMutation({
    mutationFn: () => api.post("/viagens/travar", undefined, { data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["travamento", data] }),
  });
  const destravarDia = useMutation({
    mutationFn: () => api.post("/viagens/destravar", undefined, { data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["travamento", data] }),
  });
  const copiarDia = useMutation({
    mutationFn: ({ dataOrigem, ancoraIds }: { dataOrigem: string; ancoraIds: number[] }) =>
      api.post<ViagemDia[]>("/viagens/copiar", { data_origem: dataOrigem, data_destino: data, ancora_ids: ancoraIds }),
    onSuccess: invalidarDia,
  });

  function mensagemErro(e: unknown, fallback: string): string {
    return e instanceof Error ? e.message : fallback;
  }

  function outrosAtendimentosDoDia(passageiroId: number): ViagemDiaPassageiro[] {
    const viagens = viagensQuery.data ?? [];
    let atual: ViagemDiaPassageiro | null = null;
    for (const v of viagens) {
      const p = v.passageiros.find((p) => p.id === passageiroId);
      if (p) {
        atual = p;
        break;
      }
    }
    if (!atual) return [];
    const outros: ViagemDiaPassageiro[] = [];
    for (const v of viagens) {
      for (const p of v.passageiros) {
        if (p.id !== passageiroId && p.usuario_id === atual.usuario_id && p.status !== "Cancelado") {
          outros.push(p);
        }
      }
    }
    return outros;
  }

  const [modalAdicionar, setModalAdicionar] = useState<number | null>(null);
  const [modalAtribuir, setModalAtribuir] = useState<{
    viagemIds: number[];
    condutorAtualId: number | null;
    veiculoAtualId: number | null;
  } | null>(null);
  const [modalAbrirCarro, setModalAbrirCarro] = useState(false);
  const [modalEscalas, setModalEscalas] = useState(false);
  const [modalAgendamentos, setModalAgendamentos] = useState(false);
  const [modalOcupacao, setModalOcupacao] = useState(false);
  const [modalCancelar, setModalCancelar] = useState<number | null>(null);
  const [modalRemoverPassageiro, setModalRemoverPassageiro] = useState<number | null>(null);
  const [modalEditarPassageiro, setModalEditarPassageiro] = useState<ViagemDiaPassageiro | null>(null);
  const [modalCopiarDia, setModalCopiarDia] = useState(false);
  const [modalLimparDia, setModalLimparDia] = useState(false);
  const [modalDestravarDia, setModalDestravarDia] = useState(false);
  const [modalRemoverRevezamentoId, setModalRemoverRevezamentoId] = useState<number | null>(null);
  const [modalOrdemIndice, setModalOrdemIndice] = useState<number | null>(null);
  const [modalCondutoresRevezamentoId, setModalCondutoresRevezamentoId] = useState<number | null>(null);
  const [carrosSelecionadosRevezamento, setCarrosSelecionadosRevezamento] = useState<Set<number>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const erroBoxRef = useRef<HTMLDivElement>(null);

  // A pagina e longa (carros, grupos, sobras ficam bem abaixo) -- sem isso,
  // um erro disparado la embaixo aparece so no topo, fora da tela, e parece
  // que "nada aconteceu".
  useEffect(() => {
    if (erro) {
      erroBoxRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [erro]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  // So chamado quando o destino e a MESMA leg em que o passageiro ja esta --
  // move-troca-de-carro/horario vai por handleDragEnd -> moverPassageiroBloco.
  // Aqui e so reordenacao (ordem) dentro da propria leg.
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

  type ItemBase =
    | { tipo: "membro-base"; agendaId: number; viagemBaseId: number; grupoBaseId: number; sentido: Sentido; hora: string }
    | { tipo: "nao-classificado"; agendaId: number; sentido: Sentido; hora: string };
  type AlvoBase =
    | { tipo: "viagem-base"; viagemBaseId: number; grupoBaseId: number; sentido: Sentido; hora: string }
    | { tipo: "membro-base"; agendaId: number; viagemBaseId: number; grupoBaseId: number; sentido: Sentido; hora: string }
    | { tipo: "grupo-base"; grupoBaseId: number };

  function handleDragEndBase(activeData: ItemBase, overData: AlvoBase) {
    const estrutura = estruturaBaseQuery.data;
    if (!estrutura) return;

    // sentido/horario SEMPRE vem de quem esta sendo arrastado -- nunca do
    // alvo do drop. O horario real da pessoa e fixo (vem da agenda semanal
    // dela), soltar em cima de uma viagem de outro horario nao muda isso;
    // so decide em qual carro ela entra, criando a viagem certa on-the-fly
    // se o carro ainda nao tiver uma pro horario dela.
    const grupoBaseId = overData.grupoBaseId;
    const sentidoAlvo = activeData.sentido;
    const horaAlvo = activeData.hora;

    const grupo = estrutura.grupos.find((g) => g.id === grupoBaseId);
    const viagemAlvo = grupo?.viagens.find((v) => v.sentido === sentidoAlvo && v.hora === horaAlvo);
    const membrosAlvo = viagemAlvo?.membros ?? [];

    // a posicao dentro da lista (over em cima de um membro especifico) so
    // faz sentido quando o alvo do drop e de fato a MESMA viagem (sentido e
    // horario) de quem foi arrastado -- soltar em cima de alguem de outro
    // horario so importa pra saber o carro, nao a posicao.
    const overMembroAgendaId =
      overData.tipo === "membro-base" && overData.viagemBaseId === viagemAlvo?.id ? overData.agendaId : undefined;

    if (activeData.tipo === "membro-base" && activeData.agendaId === overMembroAgendaId) return; // solto em cima de si mesmo

    const semAtivo = membrosAlvo.filter((m) => m.agenda_id !== activeData.agendaId);
    let ordem = semAtivo.length;
    if (overMembroAgendaId !== undefined) {
      const idx = semAtivo.findIndex((m) => m.agenda_id === overMembroAgendaId);
      if (idx >= 0) ordem = idx;
    }

    moverMembroBase.mutate(
      { agendaId: activeData.agendaId, sentido: sentidoAlvo, grupoBaseId, hora: horaAlvo, ordem },
      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao mover no molde")) },
    );
  }

  function handleDragEnd(evento: DragEndEvent) {
    const { active, over } = evento;
    if (!over) return;

    if (modo === "dia" && travado) return;

    if (modo === "base") {
      const activeData = active.data.current as ItemBase | undefined;
      const overData = over.data.current as AlvoBase | undefined;
      if (!activeData || !overData) return;
      handleDragEndBase(activeData, overData);
      return;
    }

    const activeData = active.data.current as { viagemId: number; passageiroId: number } | undefined;
    if (!activeData) return;

    // Solto no bloco (carro) inteiro, fora de qualquer leg especifica -- o
    // horario/sentido do proprio passageiro decide a leg de destino dentro
    // desse carro, criando-a se ainda nao existir (igual ao modo Base).
    const overBloco = over.data.current as { blocoId: number } | undefined;
    if (overBloco?.blocoId !== undefined) {
      moverPassageiroBloco.mutate(
        { id: activeData.passageiroId, bloco_id: overBloco.blocoId },
        { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao mover passageiro")) },
      );
      return;
    }

    const overData = over.data.current as { viagemId: number; passageiroId?: number } | undefined;
    const destinoId = overData?.viagemId ?? Number(String(over.id).replace("carro-", ""));
    if (!destinoId || Number.isNaN(destinoId)) return;

    if (destinoId !== activeData.viagemId) {
      // Solto numa viagem diferente da propria (outro carro, ou outro
      // horario do mesmo carro) -- igual ao solto no bloco inteiro e ao modo
      // Base: o horario/sentido de quem esta sendo arrastado e quem manda,
      // decidindo a leg de destino e criando-a on-the-fly se o carro de
      // destino ainda nao tiver uma pro horario dele.
      moverPassageiroBloco.mutate(
        { id: activeData.passageiroId, bloco_id: destinoId },
        { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao mover passageiro")) },
      );
      return;
    }

    handleDragEndDia(activeData, overData, destinoId);
  }

  // Escopo estrito de periodo (so pernas cuja hora bate com o periodo aberto)
  // -- usado pra saber quem esta "escalado" no periodo no modal de
  // condutor/veiculo, independente do bloco aparecer ou nao na tela.
  const viagensDoPeriodo = (viagensQuery.data ?? []).filter((v) => periodoDaViagem(v) === periodo);

  // Blocos exibidos: agrupa TODAS as pernas do dia (nao so as do periodo
  // aberto) e mostra o bloco inteiro se qualquer perna dele bater com o
  // periodo -- carro com pernas em periodos diferentes (ida de manha, volta
  // a tarde) nao fica mais escondido, so aparece com destaque visual na perna
  // fora do periodo (ver LegBlock).
  const todosOsBlocos = agruparPorBloco(viagensQuery.data ?? []);
  const gruposBloco = todosOsBlocos.filter((grupo) => grupo.some((v) => periodoDaViagem(v) === periodo));

  function moverBloco(indiceAtual: number, novoIndice: number) {
    const total = gruposBloco.length;
    const alvo = Math.max(0, Math.min(novoIndice, total - 1));
    if (alvo === indiceAtual) return;
    const ids = gruposBloco.map(ancoraIdDoBloco);
    const [id] = ids.splice(indiceAtual, 1);
    ids.splice(alvo, 0, id);
    reordenarBlocos.mutate(ids, {
      onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao reordenar carro")),
    });
  }

  const condutoresFeriasIds = new Set(
    (ferias ?? []).filter((f) => f.data_inicio <= data && f.data_fim >= data).map((f) => f.condutor_id),
  );

  const condutoresEscaladosNoDia = (() => {
    const idsEscalados = new Set(
      (viagensQuery.data ?? []).filter((v) => v.condutor_id !== null).map((v) => v.condutor_id as number),
    );
    return (condutores ?? [])
      .filter((c) => idsEscalados.has(c.id))
      .sort((a, b) => (a.apelido || a.nome).localeCompare(b.apelido || b.nome));
  })();

  // Carros sem condutor escalado nao tem nome pra exibir no select de
  // exportacao -- entram como "Indefinido_N", numerados na mesma ordem em
  // que aparecem no board (ordem definida em agruparPorBloco).
  const blocosSemCondutorNoDia = todosOsBlocos.filter((grupo) => grupo.every((v) => v.condutor_id === null));

  const opcoesExportacao: { valor: string; label: string }[] = [
    ...condutoresEscaladosNoDia.map((c) => ({ valor: `c-${c.id}`, label: c.apelido || c.nome })),
    ...blocosSemCondutorNoDia.map((grupo, indice) => ({
      valor: `b-${ancoraIdDoBloco(grupo)}`,
      label: `Indefinido_${indice + 1}`,
    })),
  ];

  // "Gerado" pro dia = existe algo persistido pela geracao: carros (ViagemDia)
  // ou passageiros orfaos sem vaga (viagem_dia_id NULL). Sobras e
  // desconsiderados NAO servem de sinal aqui -- sao calculados on-the-fly a
  // partir da agenda semanal, independente de ter gerado ou nao (sobras
  // sempre lista os condutores ociosos do dia, gerado ou nao).
  const diaTemAlgumRegistro = (viagensQuery.data ?? []).length > 0 || (semVagaQuery.data ?? []).length > 0;

  const gruposBaseDoPeriodo: { grupo: GrupoBase; viagensExibir: ViagemBase[] }[] = (estruturaBaseQuery.data?.grupos ?? [])
    .map((grupo) => ({ grupo, viagensExibir: grupo.viagens.filter((v) => periodoDaViagemBase(v) === periodo) }))
    .filter(({ grupo, viagensExibir }) => viagensExibir.length > 0 || grupo.viagens.length === 0);

  const revezamentoPorGrupoBase = new Map<number, { grupo: GrupoRevezamento; numeroGrupo: number; ordem: number }>();
  (estruturaBaseQuery.data?.grupos_revezamento ?? []).forEach((revezamento, indice) => {
    for (const carro of revezamento.carros) {
      revezamentoPorGrupoBase.set(carro.grupo_base_id, { grupo: revezamento, numeroGrupo: indice + 1, ordem: carro.ordem });
    }
  });

  // Numeracao global (pra bater com o "Grupo N" mostrado no card do carro),
  // mas so exibe na barra os grupos que tem pelo menos um carro no periodo
  // aberto (Manha/Tarde) -- grupo de manha nao deve aparecer olhando a tarde.
  const gruposBaseIdsDoPeriodo = new Set(gruposBaseDoPeriodo.map(({ grupo }) => grupo.id));
  const gruposRevezamentoDoPeriodo = (estruturaBaseQuery.data?.grupos_revezamento ?? [])
    .map((grupo, indice) => ({ grupo, numeroGrupo: indice + 1 }))
    .filter(({ grupo }) => grupo.carros.some((c) => gruposBaseIdsDoPeriodo.has(c.grupo_base_id)));

  return (
    <div>
      <h2>Agendamento do dia</h2>

      {erro && (
        <div ref={erroBoxRef} className="erro-box" onClick={() => setErro(null)} style={{ cursor: "pointer" }}>
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

      {modo === "base" && estruturaBaseQuery.error && (
        <div className="erro-box">Erro ao carregar o molde: {mensagemErro(estruturaBaseQuery.error, "erro desconhecido")}</div>
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

        {modo === "dia" && diaTemAlgumRegistro && !travado && (
          <button
            className="btn"
            onClick={() => travarDia.mutate(undefined, { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao travar o dia")) })}
            disabled={travarDia.isPending}
            title="Trava o agendamento desse dia, impedindo edicao nao intencional"
          >
            Travar
          </button>
        )}
        {modo === "dia" && travado && (
          <button className="btn btn-primario" onClick={() => setModalDestravarDia(true)} disabled={destravarDia.isPending}>
            Destravar
          </button>
        )}
        {modo === "dia" && diaTemAlgumRegistro && !travado && (
          <button className="btn btn-perigo" onClick={() => setModalLimparDia(true)} disabled={limparDia.isPending}>
            Limpar
          </button>
        )}
        {modo === "dia" && !diaTemAlgumRegistro && !viagensQuery.isLoading && (
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
        {modo === "dia" && !diaTemAlgumRegistro && !viagensQuery.isLoading && (
          <button className="btn" onClick={() => setModalCopiarDia(true)}>
            Copiar de outro dia
          </button>
        )}
        {modo === "base" && (
          <button
            className="btn btn-primario"
            onClick={() =>
              criarGrupoBase.mutate(undefined, {
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao criar carro")),
              })
            }
            disabled={criarGrupoBase.isPending}
          >
            + Novo carro
          </button>
        )}
        {modo === "base" && (
          <button className="btn" onClick={() => setModalOcupacao(true)}>
            Ocupacao
          </button>
        )}
        {modo === "base" && (
          <button
            className="btn"
            onClick={() =>
              api
                .download(`/base/${diaSemanaBase}/revezamentos/csv`)
                .catch((e: unknown) => setErro(mensagemErro(e, "Erro ao baixar grupos")))
            }
          >
            Grupos
          </button>
        )}
        {modo === "dia" && !travado && (
          <button className="btn" onClick={() => setModalAbrirCarro(true)}>
            + Abrir carro
          </button>
        )}
        {modo === "dia" && (
          <button className="btn" onClick={() => setModalAgendamentos(true)}>
            Agendamentos
          </button>
        )}
        {modo === "dia" && (
          <button className="btn" onClick={() => setModalEscalas(true)}>
            Exportar escalas
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
      {modo === "base" && estruturaBaseQuery.isLoading && <p>Carregando molde...</p>}

      <DndContext sensors={sensors} collisionDetection={collisionDetection} onDragEnd={handleDragEnd}>
        {modo === "dia" ? (
          <div className="board-layout">
            <div className="board">
              {gruposBloco.map((grupo, indice) => (
                <CarroCard
                  key={ancoraIdDoBloco(grupo)}
                  viagens={grupo}
                  empresas={empresas ?? []}
                  veiculos={veiculos ?? []}
                  condutores={condutores ?? []}
                  locais={locais ?? []}
                  regioes={regioes ?? []}
                  tituloSemVeiculo="Carro sem veiculo"
                  periodoAtual={periodo}
                  posicao={indice + 1}
                  totalNoPeriodo={gruposBloco.length}
                  onMoverEsquerda={() => moverBloco(indice, indice - 1)}
                  onMoverDireita={() => moverBloco(indice, indice + 1)}
                  onEditarPosicao={() => setModalOrdemIndice(indice)}
                  onAdicionarPassageiro={travado ? undefined : setModalAdicionar}
                  onRemoverPassageiro={
                    travado
                      ? undefined
                      : (id) =>
                          tirarPassageiroDoCarro.mutate(id, {
                            onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover atendimento do carro")),
                          })
                  }
                  onCancelarPassageiro={travado ? undefined : setModalCancelar}
                  onEditarPassageiro={setModalEditarPassageiro}
                  onAtribuir={travado ? undefined : setModalAtribuir}
                  onLimparCondutorVeiculo={
                    travado
                      ? undefined
                      : (viagemIds) =>
                          limparCondutorVeiculo.mutate(viagemIds, {
                            onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao limpar condutor/veiculo")),
                          })
                  }
                  onRemoverViagem={
                    travado
                      ? undefined
                      : (id) =>
                          removerViagem.mutate(id, {
                            onError: (e: unknown) => setErro(mensagemErro(e, "Nao foi possivel remover a viagem")),
                          })
                  }
                  bloqueado={travado}
                />
              ))}
            </div>

            {semVagaQuery.data && (
              <SemVagaPanel
                passageiros={semVagaQuery.data}
                locais={locais ?? []}
                regioes={regioes ?? []}
                onRemover={travado ? undefined : setModalRemoverPassageiro}
                onCancelar={travado ? undefined : setModalCancelar}
                onEditar={setModalEditarPassageiro}
              />
            )}
          </div>
        ) : (
          <>
            <GruposRevezamentoBar
              gruposRevezamento={gruposRevezamentoDoPeriodo}
              carrosSelecionadosCount={carrosSelecionadosRevezamento.size}
              onAbrirModalCondutores={(grupoRevezamentoId) => setModalCondutoresRevezamentoId(grupoRevezamentoId)}
              onRemoverGrupo={(grupoRevezamentoId) => setModalRemoverRevezamentoId(grupoRevezamentoId)}
              onGirarGrupo={(grupoRevezamentoId) =>
                girarRevezamento.mutate(grupoRevezamentoId, {
                  onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao girar o rodizio do grupo")),
                })
              }
              onCriarGrupo={() => {
                const carroIds = [...carrosSelecionadosRevezamento];
                criarRevezamento.mutate(undefined, {
                  onSuccess: (estrutura) => {
                    const novoId = Math.max(...estrutura.grupos_revezamento.map((g) => g.id));
                    definirCarrosRevezamento.mutate(
                      { grupoRevezamentoId: novoId, grupoBaseIds: carroIds },
                      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao salvar carros do grupo")) },
                    );
                  },
                  onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao criar grupo de revezamento")),
                });
                setCarrosSelecionadosRevezamento(new Set());
              }}
              onAdicionarAoGrupo={(grupoRevezamentoId) => {
                const grupoRevezamento = estruturaBaseQuery.data?.grupos_revezamento.find((g) => g.id === grupoRevezamentoId);
                const carrosAtuais = grupoRevezamento?.carros.map((c) => c.grupo_base_id) ?? [];
                const novosCarros = [...carrosAtuais, ...carrosSelecionadosRevezamento];
                definirCarrosRevezamento.mutate(
                  { grupoRevezamentoId, grupoBaseIds: novosCarros },
                  { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao adicionar carros ao grupo")) },
                );
                setCarrosSelecionadosRevezamento(new Set());
              }}
              onLimparSelecao={() => setCarrosSelecionadosRevezamento(new Set())}
            />
            <div className="board-layout">
            <div className="board">
              {gruposBaseDoPeriodo.map(({ grupo, viagensExibir }, indice) => (
                <CarroBaseCard
                  key={grupo.id}
                  grupo={grupo}
                  viagensExibir={viagensExibir}
                  indice={indice}
                  periodo={periodo}
                  locais={locais ?? []}
                  regioes={regioes ?? []}
                  revezamento={revezamentoPorGrupoBase.get(grupo.id) ?? null}
                  selecionadoPraRevezamento={carrosSelecionadosRevezamento.has(grupo.id)}
                  onToggleSelecaoRevezamento={(grupoId, marcado) =>
                    setCarrosSelecionadosRevezamento((atual) => {
                      const nova = new Set(atual);
                      if (marcado) nova.add(grupoId);
                      else nova.delete(grupoId);
                      return nova;
                    })
                  }
                  onSairDoGrupoRevezamento={(grupoRevezamentoId) => {
                    const grupoRevezamento = estruturaBaseQuery.data?.grupos_revezamento.find((g) => g.id === grupoRevezamentoId);
                    const carrosRestantes = (grupoRevezamento?.carros ?? [])
                      .map((c) => c.grupo_base_id)
                      .filter((id) => id !== grupo.id);
                    definirCarrosRevezamento.mutate(
                      { grupoRevezamentoId, grupoBaseIds: carrosRestantes },
                      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao sair do grupo de revezamento")) },
                    );
                  }}
                  onNovaViagem={(grupoId, sentido, hora) =>
                    criarViagemBase.mutate(
                      { grupoId, sentido, hora: `${hora}:00` },
                      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao criar viagem")) },
                    )
                  }
                  onRemoverGrupo={(grupoId) =>
                    removerGrupoBase.mutate(grupoId, {
                      onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover carro")),
                    })
                  }
                  onRemoverViagem={(viagemId) =>
                    removerViagemBase.mutate(viagemId, {
                      onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover viagem")),
                    })
                  }
                  onRemoverMembro={(membroId) =>
                    removerMembroBase.mutate(membroId, {
                      onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao tirar do carro")),
                    })
                  }
                  onAlterarHoraViagem={(viagemId, hora) =>
                    alterarHoraViagemBase.mutate(
                      { viagemId, hora: `${hora}:00` },
                      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao alterar horario da viagem")) },
                    )
                  }
                />
              ))}
            </div>

            <NaoClassificadosBasePanel
              membros={estruturaBaseQuery.data?.nao_classificados ?? []}
              locais={locais ?? []}
              regioes={regioes ?? []}
            />
            </div>
          </>
        )}

        {modo === "dia" && sobrasQuery.data && (
          <SobrasPanel
            sobras={sobrasQuery.data}
            onMarcarFolga={(ids) =>
              marcarFolga.mutate(ids, { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao marcar folga")) })
            }
            aplicando={marcarFolga.isPending}
          />
        )}

        {modo === "dia" && ((desconsideradosQuery.data?.length ?? 0) > 0 || (viagensQuery.data?.length ?? 0) > 0) && (
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            {desconsideradosQuery.data && desconsideradosQuery.data.length > 0 && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <DesconsideradosPanel desconsiderados={desconsideradosQuery.data} />
              </div>
            )}
            {viagensQuery.data && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <CancelamentosPanel viagens={viagensQuery.data} />
              </div>
            )}
          </div>
        )}
      </DndContext>

      {modalAdicionar !== null && (
        <AdicionarPassageiroModal
          diaSemana={diaSemanaFromData(data)}
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
          empresas={empresas ?? []}
          condutorAtualId={modalAtribuir.condutorAtualId}
          veiculoAtualId={modalAtribuir.veiculoAtualId}
          periodo={periodo}
          veiculosEscaladosIds={
            new Set(
              viagensDoPeriodo
                .filter((v) => !modalAtribuir.viagemIds.includes(v.id) && v.veiculo_id !== null)
                .map((v) => v.veiculo_id as number),
            )
          }
          condutoresEscaladosIds={
            new Set(
              (viagensQuery.data ?? [])
                .filter((v) => !modalAtribuir.viagemIds.includes(v.id) && v.condutor_id !== null)
                .map((v) => v.condutor_id as number),
            )
          }
          condutoresFeriasIds={condutoresFeriasIds}
          onFechar={() => setModalAtribuir(null)}
          onConfirmar={(dados) =>
            atribuir.mutate(
              { viagemIds: modalAtribuir.viagemIds, ...dados },
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
      {modalAgendamentos && (
        <ExportarAgendamentosModal
          data={data}
          opcoes={opcoesExportacao}
          onFechar={() => setModalAgendamentos(false)}
          onErro={(mensagem) => setErro(mensagem)}
        />
      )}
      {modalOcupacao && (
        <OcupacaoBaseModal diaSemanaInicial={diaSemanaBase} locais={locais ?? []} onFechar={() => setModalOcupacao(false)} />
      )}

      {modalCancelar !== null && (
        <CancelarPassageiroModal
          onFechar={() => setModalCancelar(null)}
          temOutrosAtendimentos={outrosAtendimentosDoDia(modalCancelar).length > 0}
          onConfirmar={(motivo, cancelarTodos) => {
            const outros = cancelarTodos ? outrosAtendimentosDoDia(modalCancelar) : [];
            cancelarPassageiro.mutate(
              { id: modalCancelar, motivo },
              {
                onSuccess: () => {
                  setModalCancelar(null);
                  for (const p of outros) {
                    cancelarPassageiro.mutate(
                      { id: p.id, motivo },
                      { onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao cancelar outros atendimentos do passageiro")) },
                    );
                  }
                },
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao cancelar passageiro")),
              },
            );
          }}
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

      {modalDestravarDia && (
        <ConfirmarModal
          titulo="Destravar agendamento do dia"
          mensagem="Destravar esse dia permite editar novamente o agendamento (mover passageiros, trocar condutor/veiculo, reordenar carros etc). Confirma?"
          onFechar={() => setModalDestravarDia(false)}
          onConfirmar={() =>
            destravarDia.mutate(undefined, {
              onSuccess: () => setModalDestravarDia(false),
              onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao destravar o dia")),
            })
          }
        />
      )}

      {modalRemoverRevezamentoId !== null && (
        <ConfirmarModal
          titulo="Remover grupo de revezamento"
          mensagem={`Remover o grupo ${
            (estruturaBaseQuery.data?.grupos_revezamento ?? []).findIndex((g) => g.id === modalRemoverRevezamentoId) + 1
          }? Os carros ficam livres pra outro grupo.`}
          onFechar={() => setModalRemoverRevezamentoId(null)}
          onConfirmar={() =>
            removerRevezamento.mutate(modalRemoverRevezamentoId, {
              onSuccess: () => setModalRemoverRevezamentoId(null),
              onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao remover grupo de revezamento")),
            })
          }
        />
      )}

      {modalCopiarDia && (
        <CopiarDiaModal
          dataDestino={data}
          enviando={copiarDia.isPending}
          onFechar={() => setModalCopiarDia(false)}
          onConfirmar={(dataOrigem, ancoraIds) =>
            copiarDia.mutate(
              { dataOrigem, ancoraIds },
              {
                onSuccess: () => setModalCopiarDia(false),
                onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao copiar agendamento do dia")),
              },
            )
          }
        />
      )}

      {modalCondutoresRevezamentoId !== null &&
        (() => {
          const grupoRevezamento = estruturaBaseQuery.data?.grupos_revezamento.find((g) => g.id === modalCondutoresRevezamentoId);
          if (!grupoRevezamento) return null;
          const numeroGrupo = (estruturaBaseQuery.data?.grupos_revezamento ?? []).findIndex((g) => g.id === modalCondutoresRevezamentoId) + 1;
          return (
            <ModalCondutoresRevezamento
              grupoRevezamento={grupoRevezamento}
              numeroGrupo={numeroGrupo}
              todosGruposRevezamento={estruturaBaseQuery.data?.grupos_revezamento ?? []}
              condutores={condutores ?? []}
              empresas={empresas ?? []}
              onFechar={() => setModalCondutoresRevezamentoId(null)}
              onSalvar={(condutorIds) =>
                definirCondutoresRevezamento.mutate(
                  { grupoRevezamentoId: grupoRevezamento.id, condutorIds },
                  {
                    onSuccess: (estrutura) => {
                      atualizarEstruturaBase(estrutura);
                      setModalCondutoresRevezamentoId(null);
                    },
                    onError: (e: unknown) => setErro(mensagemErro(e, "Erro ao salvar condutores do grupo")),
                  },
                )
              }
            />
          );
        })()}

      {modalOrdemIndice !== null && (
        <ReordenarPosicaoModal
          posicaoAtual={modalOrdemIndice + 1}
          total={gruposBloco.length}
          onFechar={() => setModalOrdemIndice(null)}
          onConfirmar={(novaPosicao) => {
            moverBloco(modalOrdemIndice, novaPosicao - 1);
            setModalOrdemIndice(null);
          }}
        />
      )}

      {modalRemoverPassageiro !== null && (
        <ConfirmarModal
          titulo="Remover atendimento"
          mensagem="Remover esse atendimento? Ao contrario de Cancelar, isso apaga o registro sem deixar historico."
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
          titulo={travado ? "Detalhes do atendimento" : "Editar atendimento"}
          textoConfirmar="Salvar edicao"
          somenteLeitura={travado}
          diaSemana={diaSemanaFromData(data)}
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
