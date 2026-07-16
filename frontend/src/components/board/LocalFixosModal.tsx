import { useList } from "../../api/hooks";
import type { Local, LocalFixoUsuario } from "../../api/types";
import { DIAS_SEMANA_ABREV } from "../../api/types";
import { useLockBodyScroll } from "../../hooks/useLockBodyScroll";

interface Props {
  local: Local;
  onFechar: () => void;
}

export default function LocalFixosModal({ local, onFechar }: Props) {
  useLockBodyScroll();
  const { data: fixos, error } = useList<LocalFixoUsuario>("locais-fixos", `/locais/${local.id}/fixos`);

  return (
    <div className="modal-fundo" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Fixos - {local.nome}</h3>
        {error && <div className="erro-box">Erro ao carregar usuarios fixos.</div>}
        {!error && (fixos ?? []).length === 0 && <p>Nenhum usuario com atendimento fixo neste local.</p>}
        {(fixos ?? []).length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Dias</th>
              </tr>
            </thead>
            <tbody>
              {(fixos ?? []).map((f) => (
                <tr key={f.usuario_id}>
                  <td>{f.abbr}</td>
                  <td>{f.dias.map((d) => DIAS_SEMANA_ABREV[d]).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="linha-toolbar" style={{ marginTop: "1rem" }}>
          <button className="btn" onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
