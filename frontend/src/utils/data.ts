export function formatarData(data: string): string {
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano.slice(2)}`;
}

export function amanhaIso(): string {
  const data = new Date();
  data.setDate(data.getDate() + 1);
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

export function mesAtualIso(): string {
  const hoje = new Date();
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
}

export function limitesDoMes(mesIso: string): { inicio: string; fim: string } {
  const [anoStr, mesStr] = mesIso.split("-");
  const ano = Number(anoStr);
  const mes = Number(mesStr);
  const ultimoDia = new Date(ano, mes, 0).getDate();
  return { inicio: `${anoStr}-${mesStr}-01`, fim: `${anoStr}-${mesStr}-${String(ultimoDia).padStart(2, "0")}` };
}

export function calcularIdade(dataNascimento: string | null | undefined): number | null {
  if (!dataNascimento) return null;
  const [ano, mes, dia] = dataNascimento.split("-").map(Number);
  const hoje = new Date();
  let idade = hoje.getFullYear() - ano;
  if (hoje.getMonth() + 1 < mes || (hoje.getMonth() + 1 === mes && hoje.getDate() < dia)) idade--;
  return idade;
}

/** "(34)" ou "(--)" quando nao ha data de nascimento cadastrada. */
export function rotuloIdade(dataNascimento: string | null | undefined): string {
  const idade = calcularIdade(dataNascimento);
  return `(${idade ?? "--"})`;
}
