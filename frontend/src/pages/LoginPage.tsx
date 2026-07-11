import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export default function LoginPage() {
  const { login } = useAuth();
  const [loginValue, setLoginValue] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!loginValue.trim() || !senha) return;
    setEnviando(true);
    setErro(null);
    try {
      await login(loginValue.trim(), senha);
    } catch (e: unknown) {
      setErro(e instanceof ApiError ? String(e.detail) : "Nao foi possivel entrar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={handleSubmit} className="painel" style={{ width: 320 }}>
        <h2 style={{ marginTop: 0 }}>Buscar</h2>
        {erro && <div className="erro-box">{erro}</div>}
        <div className="campo" style={{ marginBottom: "0.75rem" }}>
          <label>Login</label>
          <input value={loginValue} onChange={(e) => setLoginValue(e.target.value)} autoFocus />
        </div>
        <div className="campo" style={{ marginBottom: "1rem" }}>
          <label>Senha</label>
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primario" disabled={enviando} style={{ width: "100%" }}>
          Entrar
        </button>
      </form>
    </div>
  );
}
