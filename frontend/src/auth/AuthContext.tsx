import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { Conta, LoginResponse } from "../api/types";
import { clearToken, setOnUnauthorized, setToken } from "./token";

const CHAVE_CONTA = "buscar_conta";

interface AuthState {
  conta: Conta | null;
  isAdmin: boolean;
  login: (login: string, senha: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function lerContaSalva(): Conta | null {
  const bruto = localStorage.getItem(CHAVE_CONTA);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as Conta;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [conta, setConta] = useState<Conta | null>(() => lerContaSalva());

  useEffect(() => {
    setOnUnauthorized(() => {
      clearToken();
      localStorage.removeItem(CHAVE_CONTA);
      setConta(null);
    });
  }, []);

  async function login(loginValue: string, senha: string) {
    const resposta = await api.post<LoginResponse>("/auth/login", { login: loginValue, senha });
    setToken(resposta.access_token);
    localStorage.setItem(CHAVE_CONTA, JSON.stringify(resposta.conta));
    setConta(resposta.conta);
  }

  function logout() {
    clearToken();
    localStorage.removeItem(CHAVE_CONTA);
    setConta(null);
  }

  return (
    <AuthContext.Provider value={{ conta, isAdmin: conta?.papel === "Admin", login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
