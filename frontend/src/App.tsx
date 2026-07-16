import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import CadastrosPage from "./pages/CadastrosPage";
import UsuariosPage from "./pages/UsuariosPage";
import AgendamentoDiaPage from "./pages/AgendamentoDiaPage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./auth/AuthContext";
import { useAtalhosCampoData } from "./hooks/useAtalhosCampoData";

const CHAVE_NAV_COLAPSADA = "buscar_nav_colapsada";

const ITENS_MENU = [
  { to: "/", fim: true, label: "Agendamento do dia", Icone: IconeAgenda },
  { to: "/usuarios", fim: false, label: "Usuarios", Icone: IconeUsuarios },
  { to: "/cadastros", fim: false, label: "Cadastros", Icone: IconeCadastros },
];

function iniciais(nome: string) {
  const partes = nome.trim().split(/\s+/);
  return partes.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

function App() {
  const { conta, logout } = useAuth();
  useAtalhosCampoData();
  const [colapsada, setColapsada] = useState(() => {
    try {
      return localStorage.getItem(CHAVE_NAV_COLAPSADA) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE_NAV_COLAPSADA, colapsada ? "1" : "0");
    } catch {
      // armazenamento indisponivel, ignora
    }
  }, [colapsada]);

  if (!conta) {
    return <LoginPage />;
  }

  return (
    <div className="app-layout">
      <nav className={`app-nav${colapsada ? " app-nav-colapsada" : ""}`}>
        <div className="app-nav-topo">
          <span className="app-nav-logo">B</span>
          {!colapsada && <h1>Buscar</h1>}
          <button
            type="button"
            className="app-nav-toggle"
            onClick={() => setColapsada((v) => !v)}
            title={colapsada ? "Expandir menu" : "Recolher menu"}
          >
            <IconeChevron invertido={colapsada} />
          </button>
        </div>

        <div className="app-nav-links">
          {ITENS_MENU.map(({ to, fim, label, Icone }) => (
            <NavLink key={to} to={to} end={fim} className="app-nav-link" title={colapsada ? label : undefined}>
              <Icone />
              {!colapsada && <span>{label}</span>}
            </NavLink>
          ))}
        </div>

        <div className="app-nav-usuario">
          <div className="app-nav-usuario-info">
            <span className="app-nav-avatar">{iniciais(conta.nome)}</span>
            {!colapsada && (
              <div className="app-nav-usuario-texto">
                <span className="app-nav-usuario-nome">{conta.nome}</span>
                <span className="app-nav-usuario-papel">{conta.papel}</span>
              </div>
            )}
          </div>
          <button type="button" className="app-nav-sair" onClick={logout} title="Sair">
            <IconeSair />
            {!colapsada && <span>Sair</span>}
          </button>
        </div>
      </nav>
      <main className="app-content">
        <Routes>
          <Route path="/" element={<AgendamentoDiaPage />} />
          <Route path="/usuarios" element={<UsuariosPage />} />
          <Route path="/cadastros" element={<CadastrosPage />} />
        </Routes>
      </main>
    </div>
  );
}

function IconeAgenda() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4.5" width="18" height="16" rx="2" />
      <path d="M3 9.5h18" />
      <path d="M8 2.5v4M16 2.5v4" />
    </svg>
  );
}

function IconeUsuarios() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" />
      <circle cx="17.5" cy="8.5" r="2.6" />
      <path d="M15.7 14.3c2.9.4 4.8 2.5 4.8 5.7" />
    </svg>
  );
}

function IconeCadastros() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="3.5" width="14" height="17" rx="2" />
      <rect x="9" y="1.5" width="6" height="3" rx="1" />
      <path d="M8.5 10.5h7M8.5 14h7M8.5 17.5h4.5" />
    </svg>
  );
}

function IconeChevron({ invertido }: { invertido?: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transform: invertido ? "rotate(180deg)" : undefined, transition: "transform 0.2s" }}
    >
      <path d="M15 6l-6 6 6 6" />
    </svg>
  );
}

function IconeSair() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" />
      <path d="M15 16l4-4-4-4" />
      <path d="M19 12H9" />
    </svg>
  );
}

export default App;
