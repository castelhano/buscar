import { NavLink, Route, Routes } from "react-router-dom";
import CadastrosPage from "./pages/CadastrosPage";
import UsuariosPage from "./pages/UsuariosPage";
import AgendamentoDiaPage from "./pages/AgendamentoDiaPage";
import LoginPage from "./pages/LoginPage";
import { useAuth } from "./auth/AuthContext";

function App() {
  const { conta, logout } = useAuth();

  if (!conta) {
    return <LoginPage />;
  }

  return (
    <div className="app-layout">
      <nav className="app-nav">
        <h1>Buscar</h1>
        <NavLink to="/" end>
          Agendamento do dia
        </NavLink>
        <NavLink to="/usuarios">Usuarios</NavLink>
        <NavLink to="/cadastros">Cadastros</NavLink>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span style={{ fontSize: "0.85rem" }}>
            {conta.nome} ({conta.papel})
          </span>
          <button className="btn btn-sm" onClick={logout}>
            Sair
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

export default App;
