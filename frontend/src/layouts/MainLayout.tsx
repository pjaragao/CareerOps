import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { 
  LayoutDashboard, 
  UserCircle, 
  Target, 
  Briefcase, 
  GitPullRequest, 
  MessageSquare, 
  Settings,
  Rocket,
  Shield,
  Building2,
  FileText,
  Layout
} from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/' },
    { icon: <UserCircle size={20} />, label: 'User Profile', path: '/profile' },
    { icon: <FileText size={20} />, label: 'Document Repository', path: '/onboarding' },
    { icon: <Target size={20} />, label: 'Search Strategies', path: '/strategies' },
    { icon: <Layout size={20} />, label: 'Job Board', path: '/jobs' },
    { icon: <Building2 size={20} />, label: 'Empresas', path: '/companies' },
    { icon: <GitPullRequest size={20} />, label: 'Pipeline', path: '/pipeline' },
    { icon: <MessageSquare size={20} />, label: 'Interview Prep', path: '/interview' },
    { icon: <Shield size={20} />, label: 'LinkedIn Optimizer', path: '/linkedin-optimizer' },
    { icon: <Settings size={20} />, label: 'Settings', path: '/settings' },
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
  const [status, setStatus] = React.useState({ linkedin: false, ai: true });

  React.useEffect(() => {
    const checkStatus = async () => {
       try {
         const res = await fetch('/api/auth/status');
         const data = await res.json();
         setStatus(prev => ({ ...prev, linkedin: data.active }));
       } catch (e) {}
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '1rem 2rem', gap: '1.5rem', background: 'rgba(0,0,0,0.2)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem' }}>
        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: status.linkedin ? '#00d4aa' : '#ff6b6b' }}></div>
        <span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span>
        <span style={{ color: '#fff' }}>{status.linkedin ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem' }}>
        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: status.ai ? '#00d4aa' : '#ff6b6b' }}></div>
        <span style={{ color: 'var(--text-muted)' }}>AI Services:</span>
        <span style={{ color: '#fff' }}>{status.ai ? 'Ready' : 'Error'}</span>
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
