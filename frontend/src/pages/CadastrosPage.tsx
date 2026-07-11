import { useState } from "react";
import RegioesSection from "./cadastros/RegioesSection";
import LocaisSection from "./cadastros/LocaisSection";
import LocalRecessoSection from "./cadastros/LocalRecessoSection";
import EmpresasSection from "./cadastros/EmpresasSection";
import VeiculosSection from "./cadastros/VeiculosSection";
import CondutoresSection from "./cadastros/CondutoresSection";
import FeriasSection from "./cadastros/FeriasSection";

const ABAS = [
  { chave: "regioes", label: "Regioes", Componente: RegioesSection },
  { chave: "locais", label: "Locais", Componente: LocaisSection },
  { chave: "recesso", label: "Recesso", Componente: LocalRecessoSection },
  { chave: "empresas", label: "Empresas", Componente: EmpresasSection },
  { chave: "veiculos", label: "Frota", Componente: VeiculosSection },
  { chave: "condutores", label: "Condutores", Componente: CondutoresSection },
  { chave: "ferias", label: "Ferias", Componente: FeriasSection },
] as const;

export default function CadastrosPage() {
  const [abaAtiva, setAbaAtiva] = useState<(typeof ABAS)[number]["chave"]>("regioes");
  const Ativa = ABAS.find((a) => a.chave === abaAtiva)!.Componente;

  return (
    <div>
      <h2>Cadastros</h2>
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
        <Ativa />
      </div>
    </div>
  );
}
