const CHAVE_TOKEN = "buscar_token";

let onUnauthorized: (() => void) | null = null;

export function getToken(): string | null {
  return localStorage.getItem(CHAVE_TOKEN);
}

export function setToken(token: string): void {
  localStorage.setItem(CHAVE_TOKEN, token);
}

export function clearToken(): void {
  localStorage.removeItem(CHAVE_TOKEN);
}

export function setOnUnauthorized(handler: () => void): void {
  onUnauthorized = handler;
}

export function notifyUnauthorized(): void {
  onUnauthorized?.();
}
