import { useState } from "react";
import { useList } from "../api/hooks";
import type { Empresa } from "../api/types";
import { mesAtualIso } from "../utils/data";
import RodagemView from "./resumos/RodagemView";
import AtendimentosView from "./resumos/AtendimentosView";
import OutrosView from "./resumos/OutrosView";

const ABAS = [
  { chave: "rodagem", label: "Rodagem", Componente: RodagemView },
  { chave: "atendimentos", label: "Atendimentos", Componente: AtendimentosView },
  { chave: "outros", label: "Outros", Componente: OutrosView },
] as const;

export default function ResumosPage() {
  const [mesAno, setMesAno] = useState(mesAtualIso());
  const [empresaId, setEmpresaId] = useState<number | "">("");
  const [abaAtiva, setAbaAtiva] = useState<(typeof ABAS)[number]["chave"]>("rodagem");

  const { data: empresas } = useList<Empresa>("empresas", "/empresas");

  const [anoStr, mesStr] = mesAno.split("-");
  const ano = Number(anoStr);
  const mes = Number(mesStr);

  const Ativa = (ABAS.find((a) => a.chave === abaAtiva) ?? ABAS[0]).Componente;

  return (
    <div>
      <h2>Resumos</h2>
      <div className="linha-toolbar">
        <div className="campo">
          <label>Mes</label>
          <input type="month" value={mesAno} onChange={(e) => setMesAno(e.target.value)} />
        </div>
        <div className="campo">
          <label>Empresa</label>
          <select value={empresaId} onChange={(e) => setEmpresaId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Todas</option>
            {(empresas ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="linha-toolbar">
        {ABAS.map((aba) => (
          <button
            key={aba.chave}
            className={`btn ${aba.chave === abaAtiva ? "btn-primario" : ""}`}
            onClick={() => setAbaAtiva(aba.chave)}
          >
            {aba.label}
          </button>
        ))}
      </div>
      <div className="painel">
        <Ativa ano={ano} mes={mes} empresaId={empresaId === "" ? undefined : empresaId} />
      </div>
    </div>
  );
}
