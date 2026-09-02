const BOM_UTF8 = "﻿";

function escaparCampoCsv(valor: string | number): string {
  const texto = String(valor);
  if (/[;"\n]/.test(texto)) {
    return `"${texto.replace(/"/g, '""')}"`;
  }
  return texto;
}

/** Separador ";" (padrao do Excel em pt-BR) e BOM UTF-8 (evita acento
 * quebrado ao abrir no Excel) -- mesma convencao do backend (ver
 * services/exportacao.py: delimiter=";" + encode("utf-8-sig")). */
export function exportarCsv(nomeArquivo: string, cabecalhos: string[], linhas: (string | number)[][]): void {
  const conteudo = [cabecalhos, ...linhas].map((linha) => linha.map(escaparCampoCsv).join(";")).join("\r\n");
  const blob = new Blob([BOM_UTF8 + conteudo], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
