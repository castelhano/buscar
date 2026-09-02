import { exportarCsv } from "../../utils/csv";

interface Props {
  nomeArquivo: string;
  cabecalhos: string[];
  linhas: (string | number)[][];
}

export default function BotaoExportarCsv({ nomeArquivo, cabecalhos, linhas }: Props) {
  return (
    <button className="btn btn-sm" onClick={() => exportarCsv(nomeArquivo, cabecalhos, linhas)} disabled={linhas.length === 0}>
      Exportar CSV
    </button>
  );
}
