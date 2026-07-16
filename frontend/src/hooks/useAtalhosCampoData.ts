import { useEffect } from "react";

const setterNativoValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;

function paraIso(data: Date): string {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function dispararMudanca(input: HTMLInputElement, iso: string) {
  setterNativoValue.call(input, iso);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

/**
 * Atalhos de teclado para qualquer <input type="date"> da aplicacao:
 * "t" preenche com a data de hoje; "+"/"-" somam ou subtraem um dia
 * (a partir de hoje quando o campo estiver vazio).
 */
export function useAtalhosCampoData() {
  useEffect(() => {
    function aoTeclar(e: KeyboardEvent) {
      const alvo = e.target;
      if (!(alvo instanceof HTMLInputElement) || alvo.type !== "date") return;
      if (!["t", "+", "-"].includes(e.key)) return;

      e.preventDefault();
      const base = e.key !== "t" && alvo.value ? new Date(`${alvo.value}T00:00:00`) : new Date();
      if (e.key === "+") base.setDate(base.getDate() + 1);
      else if (e.key === "-") base.setDate(base.getDate() - 1);

      dispararMudanca(alvo, paraIso(base));
    }

    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, []);
}
