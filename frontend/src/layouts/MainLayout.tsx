import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Home, UserCircle, Briefcase, Megaphone, Settings, Rocket } from 'lucide-react';
import { linkedinCopilotService } from '../services/linkedinCopilotService';

const Sidebar = () => {
  const navItems = [
    { icon: <Home size={20} />, label: 'Início', path: '/' },
    { icon: <UserCircle size={20} />, label: 'Meu Perfil', path: '/perfil' },
    { icon: <Briefcase size={20} />, label: 'Vagas', path: '/vagas' },
    { icon: <Megaphone size={20} />, label: 'LinkedIn Copilot', path: '/linkedin-copilot' },
    { icon: <Settings size={20} />, label: 'Configurações', path: '/configuracoes' },
  ];

  return (
    <aside className="sidebar">
      <div className="logo-area">
        <Rocket className="logo-icon" />
        <span className="logo-text">CareerOps <span style={{color: 'var(--accent)', fontSize: '0.8rem'}}>v2</span></span>
      </div>
      <nav className="nav-menu">
        {navItems.map((item) => (
          <div key={item.path} className="nav-item">
            <NavLink 
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          </div>
        ))}
      </nav>
    </aside>
  );
};

const TopBar = () => {
  // Publishing through the official LinkedIn API (LinkedIn Copilot); without it, posts are copied and pasted by hand.
  const [connected, setConnected] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    linkedinCopilotService.status().then(st => setConnected(st.connected)).catch(() => setConnected(null));
  }, []);

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '1rem 2rem', gap: '1.5rem', background: 'rgba(0,0,0,0.2)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem' }}>
        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: connected ? '#00d4aa' : '#ffb020' }}></div>
        <span style={{ color: 'var(--text-muted)' }}>Publicação no LinkedIn:</span>
        <span style={{ color: '#fff' }}>{connected === null ? '—' : connected ? 'API conectada' : 'manual (copiar e colar)'}</span>
      </div>
    </div>
  );
};

const MainLayout = () => {
  return (
    <div className="app-container">
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <TopBar />
        <main className="main-content" style={{ flex: 1, minWidth: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
