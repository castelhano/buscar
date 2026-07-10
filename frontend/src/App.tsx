import { NavLink, Route, Routes } from "react-router-dom";
import CadastrosPage from "./pages/CadastrosPage";
import UsuariosPage from "./pages/UsuariosPage";
import AgendamentoDiaPage from "./pages/AgendamentoDiaPage";

function App() {
  return (
    <div className="app-layout">
      <nav className="app-nav">
        <h1>Buscar</h1>
        <NavLink to="/" end>
          Agendamento do dia
        </NavLink>
        <NavLink to="/usuarios">Usuarios</NavLink>
        <NavLink to="/cadastros">Cadastros</NavLink>
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
