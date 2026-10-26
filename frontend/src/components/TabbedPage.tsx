import React from 'react';
import { useSearchParams } from 'react-router-dom';

export interface TabDef {
  id: string;
  label: string;
  icon?: React.ReactNode;
  render: () => React.ReactNode;
}

// Page with tabs; the active tab lives in ?tab= so links (e.g. from Início) can open a specific tab.
const TabbedPage = ({ title, subtitle, tabs }: { title?: string; subtitle?: string; tabs: TabDef[] }) => {
  const [params, setParams] = useSearchParams();
  const active = tabs.find(t => t.id === params.get('tab')) ?? tabs[0];
  return (
    <div className="animate-fade-in">
      {title && (
        <div style={{ marginBottom: '1.2rem' }}>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.4rem' }}>{title}</h1>
          {subtitle && <p style={{ color: 'var(--text-muted)' }}>{subtitle}</p>}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.id} className={`btn ${t.id === active.id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setParams({ tab: t.id }, { replace: true })}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>
      <div key={active.id}>{active.render()}</div>
    </div>
  );
};

export default TabbedPage;
