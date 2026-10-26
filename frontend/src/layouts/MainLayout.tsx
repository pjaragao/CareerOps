import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Home, UserCircle, Briefcase, Megaphone, Settings, Rocket, PanelLeftClose, PanelLeftOpen, Menu, X } from 'lucide-react';

const NAV = [
  { icon: <Home size={20} />, label: 'Início', path: '/' },
  { icon: <UserCircle size={20} />, label: 'Meu Perfil', path: '/perfil' },
  { icon: <Briefcase size={20} />, label: 'Vagas', path: '/vagas' },
  { icon: <Megaphone size={20} />, label: 'LinkedIn Copilot', path: '/linkedin-copilot' },
  { icon: <Settings size={20} />, label: 'Configurações', path: '/configuracoes' },
];

// Desktop: the sidebar collapses to icons (remembered per browser). Phone: it is a drawer opened from the top bar.
const Sidebar = ({ collapsed, onToggle, mobileOpen, onClose }: { collapsed: boolean; onToggle: () => void; mobileOpen: boolean; onClose: () => void }) => (
  <>
    {mobileOpen && <div className="sidebar-backdrop" onClick={onClose} />}
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' open' : ''}`}>
      <div className="logo-area">
        <Rocket className="logo-icon" />
        <span className="logo-text">CareerOps <span style={{ color: 'var(--accent)', fontSize: '0.8rem' }}>v2</span></span>
        <button className="sidebar-close" onClick={onClose} aria-label="Fechar menu"><X size={20} /></button>
      </div>
      <nav className="nav-menu">
        {NAV.map((item) => (
          <div key={item.path} className="nav-item">
            <NavLink to={item.path} end={item.path === '/'} title={collapsed ? item.label : undefined} onClick={onClose}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              {item.icon}
              <span className="nav-label">{item.label}</span>
            </NavLink>
          </div>
        ))}
      </nav>
      <button className="nav-link sidebar-toggle" onClick={onToggle} title={collapsed ? 'Expandir menu' : 'Recolher menu'}>
        {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
        <span className="nav-label">Recolher menu</span>
      </button>
    </aside>
  </>
);

const readCollapsed = () => {
  try { return localStorage.getItem('sidebarCollapsed') === '1'; } catch { return false; }
};

const MainLayout = () => {
  const [collapsed, setCollapsed] = React.useState(readCollapsed);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const toggle = () => setCollapsed(c => {
    try { localStorage.setItem('sidebarCollapsed', c ? '0' : '1'); } catch { /* storage blocked: only this visit */ }
    return !c;
  });
  return (
    <div className="app-container">
      <Sidebar collapsed={collapsed} onToggle={toggle} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <div className="mobile-topbar">
          <button onClick={() => setMobileOpen(true)} aria-label="Abrir menu"><Menu size={22} /></button>
          <Rocket size={18} className="logo-icon" />
          <span className="logo-text" style={{ fontSize: '1rem' }}>CareerOps</span>
        </div>
        <main className="main-content" style={{ flex: 1, minWidth: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
