import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useList } from "../api/hooks";
import type { Empresa } from "../api/types";
import { mesAtualIso } from "../utils/data";
import RodagemView from "./resumos/RodagemView";
import AtendimentosView from "./resumos/AtendimentosView";
import OutrosView from "./resumos/OutrosView";
import ExportarXlsxModal from "./resumos/ExportarXlsxModal";

const ABAS = [
  { chave: "rodagem", label: "Rodagem", Componente: RodagemView },
  { chave: "atendimentos", label: "Atendimentos", Componente: AtendimentosView },
  { chave: "outros", label: "Outros", Componente: OutrosView },
] as const;

export default function ResumosPage() {
  const [mesAno, setMesAno] = useState(mesAtualIso());
  const [empresaId, setEmpresaId] = useState<number | "">("");
  const [abaAtiva, setAbaAtiva] = useState<(typeof ABAS)[number]["chave"]>("rodagem");
  const [gerandoRelatorio, setGerandoRelatorio] = useState<"pdf" | "xlsx" | null>(null);
  const [erroRelatorio, setErroRelatorio] = useState<string | null>(null);
  const [modalXlsxAberto, setModalXlsxAberto] = useState(false);

  const { data: empresas } = useList<Empresa>("empresas", "/empresas");

  const [anoStr, mesStr] = mesAno.split("-");
  const ano = Number(anoStr);
  const mes = Number(mesStr);

  const Ativa = (ABAS.find((a) => a.chave === abaAtiva) ?? ABAS[0]).Componente;

  function gerarRelatorio(formato: "pdf" | "xlsx", incluirCanceladosEmpresa?: boolean) {
    setErroRelatorio(null);
    setGerandoRelatorio(formato);
    const caminho = formato === "pdf" ? "/resumos/relatorio" : "/resumos/relatorio-xlsx";
    api
      .download(caminho, {
        ano,
        mes,
        empresa_id: empresaId === "" ? undefined : empresaId,
        incluir_cancelados_empresa: incluirCanceladosEmpresa,
      })
      .catch((e: unknown) => setErroRelatorio(e instanceof ApiError ? String(e.detail) : "Erro ao gerar relatorio"))
      .finally(() => setGerandoRelatorio(null));
  }

  return (
    <div>
      <h2>Resumos</h2>
      {erroRelatorio && (
        <div className="erro-box" onClick={() => setErroRelatorio(null)} style={{ cursor: "pointer" }}>
          {erroRelatorio} (clique para fechar)
        </div>
      )}
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
        <button
          className="btn"
          onClick={() => gerarRelatorio("pdf")}
          disabled={gerandoRelatorio !== null}
          style={{ alignSelf: "flex-end" }}
        >
          {gerandoRelatorio === "pdf" ? "Gerando..." : "PDF"}
        </button>
        <button
          className="btn"
          onClick={() => setModalXlsxAberto(true)}
          disabled={gerandoRelatorio !== null}
          style={{ alignSelf: "flex-end" }}
        >
          {gerandoRelatorio === "xlsx" ? "Gerando..." : "XLSX"}
        </button>
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
      {modalXlsxAberto && (
        <ExportarXlsxModal
          onFechar={() => setModalXlsxAberto(false)}
          onExportar={(incluir) => {
            setModalXlsxAberto(false);
            gerarRelatorio("xlsx", incluir);
          }}
        />
      )}
    </div>
  );
}
