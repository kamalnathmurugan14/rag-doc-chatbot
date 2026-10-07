import { NavLink, Route, Routes } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { ChatPage } from "./pages/ChatPage";
import { EvalPage } from "./pages/EvalPage";
import { IndexPage } from "./pages/IndexPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  const [theme, toggle] = useTheme();
  return (
    <div className="layout">
      <nav className="sidebar" aria-label="Main">
        <h1>💬 Doc Chat</h1>
        <NavLink to="/" end>
          Chat
        </NavLink>
        <NavLink to="/index">Index</NavLink>
        <NavLink to="/eval">Evaluation</NavLink>
        <NavLink to="/settings">Settings</NavLink>
        <span className="spacer" />
        <button type="button" onClick={toggle} aria-label="Toggle theme">
          {theme === "dark" ? "☀ Light" : "🌙 Dark"}
        </button>
      </nav>
      <main className="main wide">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/index" element={<IndexPage />} />
          <Route path="/eval" element={<EvalPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
