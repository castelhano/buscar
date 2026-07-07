interface Props {
  titulo: string;
  mensagem: string;
  onFechar: () => void;
  onConfirmar: () => void;
}

export default function ConfirmarModal({ titulo, mensagem, onFechar, onConfirmar }: Props) {
  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <p>{mensagem}</p>
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn btn-perigo" onClick={onConfirmar}>
            Confirmar
          </button>
          <button className="btn" onClick={onFechar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
