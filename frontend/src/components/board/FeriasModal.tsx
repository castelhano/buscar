import FeriasSection from "../../pages/cadastros/FeriasSection";

interface Props {
  onFechar: () => void;
}

export default function FeriasModal({ onFechar }: Props) {
  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" style={{ width: "min(90vw, 900px)" }} onClick={(e) => e.stopPropagation()}>
        <h3>Ferias dos condutores</h3>
        <FeriasSection />
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
