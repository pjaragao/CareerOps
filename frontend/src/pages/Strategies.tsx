import React, { useEffect, useState } from 'react';
import { strategyService, Strategy } from '../services/strategyService';
import { Target, Plus, Play, Trash2, Globe, MapPin, Search } from 'lucide-react';

const StrategiesPage = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newStrat, setNewStrat] = useState({
    title: '',
    keywords: '',
    locations: '',
    remote_only: true
  });

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    const data = await strategyService.getStrategies();
    setStrategies(data);
  };

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!newStrat.title || !newStrat.keywords) return;
    setSaving(true);
    try {
      await strategyService.saveStrategy({
        title: newStrat.title,
        keywords: newStrat.keywords.split(',').map(k => k.trim()).filter(k => k),
        locations: newStrat.locations.split(',').map(l => l.trim()).filter(l => l),
        remote_only: newStrat.remote_only
      });
      setNewStrat({ title: '', keywords: '', locations: '', remote_only: true });
      setShowAdd(false);
      await loadStrategies();
    } catch (error) {
      alert("Failed to save strategy. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async (id: number) => {
    await strategyService.runStrategy(id);
    alert("Search started in background.");
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Search Strategies</h1>
          <p style={{ color: 'var(--text-muted)' }}>Define automated search parameters for LinkedIn.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
          <Plus size={18} /> New Strategy
        </button>
      </div>

      {showAdd && (
        <div className="panel" style={{ border: '1px solid var(--accent)' }}>
          <h3 style={{ marginBottom: '1.5rem' }}>Create New Strategy</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}>Strategy Title</label>
              <input 
                type="text" 
                value={newStrat.title}
                onChange={e => setNewStrat({...newStrat, title: e.target.value})}
                placeholder="Ex: AI Engineer Roles"
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}>Keywords (comma separated)</label>
              <input 
                type="text" 
                value={newStrat.keywords}
                onChange={e => setNewStrat({...newStrat, keywords: e.target.value})}
                placeholder="Python, React, FastAPI..."
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}>Locations (comma separated)</label>
              <input 
                type="text" 
                value={newStrat.locations}
                onChange={e => setNewStrat({...newStrat, locations: e.target.value})}
                placeholder="Remote, São Paulo, Europe..."
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
          </div>
          <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input 
              type="checkbox" 
              checked={newStrat.remote_only}
              onChange={e => setNewStrat({...newStrat, remote_only: e.target.checked})}
              id="remote-only"
            />
            <label htmlFor="remote-only">Remote Only</label>
          </div>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Strategy'}
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {strategies.map(strat => (
          <div key={strat.id} className="panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 600 }}>{strat.title}</h3>
                <div style={{ display: 'flex', gap: '12px', marginTop: '8px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Search size={14} /> {strat.keywords.length} keywords</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><MapPin size={14} /> {strat.locations.length} locations</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => handleRun(strat.id)} className="btn btn-primary" style={{ padding: '8px 12px' }}>
                  <Play size={16} fill="currentColor" /> Run
                </button>
                <button onClick={async () => {
                  if(confirm("Delete strategy?")) {
                    await strategyService.deleteStrategy(strat.id);
                    loadStrategies();
                  }
                }} className="btn btn-secondary" style={{ padding: '8px', color: 'var(--error)' }}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
            
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', marginTop: '1.5rem' }}>
              <div style={{ marginBottom: '0.8rem' }}>
                <strong style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Keywords</strong>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                  {strat.keywords.map(k => <span key={k} style={{ padding: '2px 8px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', fontSize: '0.8rem' }}>{k}</span>)}
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: strat.remote_only ? 'var(--success)' : 'var(--text-muted)', fontSize: '0.85rem' }}>
                  <Globe size={14} /> {strat.remote_only ? 'Remote Only' : 'On-site / Hybrid'}
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Created: {new Date(strat.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StrategiesPage;
