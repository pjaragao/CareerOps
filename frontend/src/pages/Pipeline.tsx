import React, { useEffect, useState } from 'react';
import { pipelineService, PipelineUrl } from '../services/pipelineService';
import { GitPullRequest, Plus, Trash2, ExternalLink, Clock } from 'lucide-react';

const PipelinePage = () => {
  const [urls, setUrls] = useState<PipelineUrl[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState('');

  useEffect(() => {
    loadUrls();
  }, []);

  const loadUrls = async () => {
    setLoading(true);
    try {
      const data = await pipelineService.getUrls();
      setUrls(data);
    } catch (error) {
      console.error("Failed to load pipeline", error);
    } finally {
      setLoading(false);
    }
  };

  const [adding, setAdding] = useState(false);

  const handleAdd = async () => {
    if (!newUrl.trim()) return;
    setAdding(true);
    try {
      await pipelineService.addUrl(newUrl);
      setNewUrl('');
      await loadUrls();
    } catch (error) {
      alert("Failed to add URL. Check if it already exists or if the server is offline.");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    await pipelineService.deleteUrl(id);
    loadUrls();
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Pipeline</h1>
          <p style={{ color: 'var(--text-muted)' }}>URLs waiting to be scraped and processed.</p>
        </div>
      </div>

      <div className="panel" style={{ display: 'flex', gap: '1rem' }}>
        <input 
          type="text" 
          value={newUrl}
          onChange={e => setNewUrl(e.target.value)}
          placeholder="Paste LinkedIn Job URL here..."
          style={{ flex: 1, padding: '0.8rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
        />
        <button className="btn btn-primary" onClick={handleAdd} disabled={adding}>
          <Plus size={18} /> {adding ? 'Adding...' : 'Add URL'}
        </button>
      </div>

      <div className="panel" style={{ padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: '1.2rem', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>Source</th>
              <th style={{ textAlign: 'left', padding: '1.2rem', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>URL</th>
              <th style={{ textAlign: 'left', padding: '1.2rem', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>Added At</th>
              <th style={{ textAlign: 'right', padding: '1.2rem', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>Loading pipeline...</td></tr>
            ) : urls.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>No pending URLs in pipeline.</td></tr>
            ) : (
              urls.map(item => (
                <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '1.2rem' }}>
                    <span style={{ 
                      fontSize: '0.75rem', 
                      padding: '4px 8px', 
                      borderRadius: '6px', 
                      background: 'rgba(255,255,255,0.05)', 
                      color: 'var(--text-main)',
                      fontWeight: 600
                    }}>
                      {item.source}
                    </span>
                  </td>
                  <td style={{ padding: '1.2rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={item.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>{item.url}</a>
                    </div>
                  </td>
                  <td style={{ padding: '1.2rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Clock size={14} /> {new Date(item.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td style={{ padding: '1.2rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <a href={item.url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ padding: '6px' }}>
                        <ExternalLink size={16} />
                      </a>
                      <button onClick={() => handleDelete(item.id)} className="btn btn-secondary" style={{ padding: '6px', color: 'var(--error)' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PipelinePage;
