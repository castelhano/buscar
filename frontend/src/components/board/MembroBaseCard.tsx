import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { MembroBase } from "../../api/types";
import { rotuloPonto, rotuloTrecho } from "../../api/types";
import { rotuloIdade } from "../../utils/data";
import { corGrupoFamiliar } from "./coresGrupoFamiliar";

interface Props {
  viagemBaseId: number;
  grupoBaseId: number;
  hora: string;
  membro: MembroBase;
  origemLocalNome?: string;
  destinoLocalNome?: string;
  onRemover: (membroId: number) => void;
}

export default function MembroBaseCard({
  viagemBaseId,
  grupoBaseId,
  hora,
  membro,
  origemLocalNome,
  destinoLocalNome,
  onRemover,
}: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `membro-${membro.id}`,
    data: { tipo: "membro-base", agendaTrechoId: membro.agenda_trecho_id, viagemBaseId, grupoBaseId, hora },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const usuarioInativo = !membro.usuario_ativo;
  const atendimentoInativo = !membro.atendimento_ativo;
  const horarioDivergente = membro.hora_agenda !== hora;

  const titulo = [
    usuarioInativo && "Usuario inativo -- nao conta na ocupacao do veiculo",
    !usuarioInativo && atendimentoInativo && "Atendimento inativo -- nao conta na ocupacao do veiculo",
    horarioDivergente &&
      `Horario do cadastro (${membro.hora_agenda.slice(0, 5)}) diferente do horario dessa viagem (${hora.slice(
        0,
        5,
      )}) -- na geracao real essa pessoa fica de fora desse carro ate ser corrigido`,
  ]
    .filter(Boolean)
    .join(" · ") || undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`passageiro-card ${membro.acompanhante ? "com-acompanhante" : ""} ${usuarioInativo ? "usuario-inativo" : ""} ${
        atendimentoInativo ? "atendimento-inativo" : ""
      } ${horarioDivergente ? "horario-divergente" : ""}`}
      title={titulo}
      {...attributes}
      {...listeners}
    >
      <button
        className="remover"
        title="Tirar do carro (volta pra nao classificados)"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          onRemover(membro.id);
        }}
      >
        ✕
      </button>
      <div className="linha-1">
        <span>
          {membro.usuario_grupo_familiar_id !== null && (
            <span
              className="dot-grupo-familiar"
              title={`Grupo familiar: ${membro.usuario_grupo_familiar_nome ?? ""}`}
              style={{ background: corGrupoFamiliar(membro.usuario_grupo_familiar_id) }}
            />
          )}
          {membro.usuario_abbr || membro.usuario_nome}{" "}
          <span style={{ color: "var(--cor-texto-suave)" }}>{rotuloIdade(membro.usuario_data_nascimento)}</span>
        </span>
        <span className="badge-rotulo" style={{ marginLeft: "0.4rem" }}>
          {rotuloTrecho(membro.ordem_trecho)}
        </span>
        {usuarioInativo && <span className="tag tag-inativo" style={{ marginLeft: "0.4rem" }}>Inativo</span>}
        {!usuarioInativo && atendimentoInativo && (
          <span className="tag tag-inativo" style={{ marginLeft: "0.4rem" }}>
            Atendimento inativo
          </span>
        )}
        {horarioDivergente && (
          <span className="tag tag-alerta" style={{ marginLeft: "0.4rem" }}>
            ⚠ Cadastro {membro.hora_agenda.slice(0, 5)}
          </span>
        )}
      </div>
      {membro.acompanhante && (
        <div className="tag-acompanhante" title="Usuario leva acompanhante: ocupa 2 lugares no veiculo">
          Com acompanhante · 2 lugares
        </div>
      )}
      <div className="linha-2 linha-origem-destino">
        <span>
          {rotuloPonto(membro.origem_tipo, origemLocalNome, membro.origem_texto, membro.usuario_abbr, membro.usuario_nome)}
        </span>
        <span>
          {rotuloPonto(membro.destino_tipo, destinoLocalNome, membro.destino_texto, membro.usuario_abbr, membro.usuario_nome)}
        </span>
      </div>
    </div>
  );
}
