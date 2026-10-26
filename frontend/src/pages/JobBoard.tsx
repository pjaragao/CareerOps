import React, { useEffect, useState, useCallback, useRef } from 'react';
import { jobService, Job } from '../services/jobService';
import { 
  Plus, MapPin, Calendar, Trash2, Building2, 
  LayoutDashboard, List as ListIcon, MoreHorizontal, ExternalLink, Rocket, FileText, Mail, MessageSquare
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import JobDetail, { JobTab, JobAction } from '../components/JobDetail';

const JobBoard = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>(() => {
    return (localStorage.getItem('jobBoardViewMode') as 'table' | 'kanban') || 'table';
  });

  useEffect(() => {
    localStorage.setItem('jobBoardViewMode', viewMode);
  }, [viewMode]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selected, setSelected] = useState<{ job: Job; tab?: JobTab; action?: JobAction } | null>(null);
  const setSelectedJob = (job: Job) => setSelected({ job });

  // Shortcuts from the list: they open the job window and run the action there (progress and results visible)
  const QUICK: { action?: JobAction; tab?: JobTab; title: string; icon: React.ReactNode; primary?: boolean }[] = [
    { action: 'autoapply', title: 'Auto Apply: gera CV e carta se faltarem, abre a vaga e a extensão preenche a candidatura', icon: <Rocket size={15} />, primary: true },
    { action: 'resume', tab: 'docs', title: 'Gerar CV personalizado', icon: <FileText size={15} /> },
    { action: 'cover', tab: 'docs', title: 'Gerar cover letter', icon: <Mail size={15} /> },
    { tab: 'chat', title: 'Chat com a vaga', icon: <MessageSquare size={15} /> },
  ];
  const quickButtons = (job: Job, small = false) => QUICK.map(q => (
    <button key={q.title} title={q.title} className={`btn ${q.primary ? 'btn-primary' : 'btn-secondary'}`}
      onClick={(e) => { e.stopPropagation(); setSelected({ job, tab: q.tab, action: q.action }); }}
      style={{ padding: small ? '4px' : '6px', display: 'flex', alignItems: 'center' }}>
      {q.icon}
    </button>
  ));
  const [newJob, setNewJob] = useState({ job_title: '', company: '', location: '', url: '', description: '' });

  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);
  
  const jobsRef = useRef(jobs);
  useEffect(() => { jobsRef.current = jobs; }, [jobs]);

  const columns = [
    { id: 'scraped', title: 'Sourced', color: '#6c63ff' },
    { id: 'new', title: 'To Evaluate', color: '#ffd700' },
    { id: 'applied', title: 'Applied', color: '#00c853' },
    { id: 'interviewing', title: 'Interviewing', color: '#00b0ff' },
    { id: 'offer', title: 'Offer', color: '#aa00ff' },
    { id: 'rejected', title: 'Rejected', color: '#ff4d4d' }
  ];

  const loadJobs = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    try {
      const data = await jobService.getJobs(filter);
      setJobs(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("[JobBoard] Failed to load jobs", error);
      setJobs([]);
    } finally {
      if (isInitial) setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadJobs(true);
  }, [loadJobs]);

  const handleStatusUpdate = async (jobId: number, newStatus: string) => {
    const jobToUpdate = (jobsRef.current || []).find(j => j.id === jobId);
    if (!jobToUpdate || jobToUpdate.status === newStatus) return;
    setJobs(prev => (prev || []).map(j => j.id === jobId ? { ...j, status: newStatus } : j));
    try {
      await jobService.updateStatus(jobId, newStatus);
    } catch (error) {
      setJobs(prev => (prev || []).map(j => j.id === jobId ? { ...j, status: jobToUpdate.status } : j));
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateRows: 'auto auto 1fr', height: '100%', gap: '1rem', width: '100%', minWidth: 0, overflow: 'hidden' }}>
      
      {/* 1. Header Fixo e Inquebrável */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', paddingBottom: '0.8rem', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 900, color: '#fff', margin: 0 }}>Job Board</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: '2px 0 0 0' }}>Gerencie suas oportunidades.</p>
        </div>

        <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ background: '#1a1a25', padding: '3px', borderRadius: '8px', display: 'flex', border: '1px solid var(--border)' }}>
            <button 
              onClick={() => setViewMode('kanban')} 
              style={{ padding: '6px 14px', border: 'none', borderRadius: '6px', cursor: 'pointer', background: viewMode === 'kanban' ? 'var(--accent)' : 'transparent', color: viewMode === 'kanban' ? '#fff' : 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <LayoutDashboard size={14} /> Kanban
            </button>
            <button 
              onClick={() => setViewMode('table')} 
              style={{ padding: '6px 14px', border: 'none', borderRadius: '6px', cursor: 'pointer', background: viewMode === 'table' ? 'var(--accent)' : 'transparent', color: viewMode === 'table' ? '#fff' : 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <ListIcon size={14} /> Lista
            </button>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)} style={{ height: '34px', padding: '0 15px', fontSize: '0.75rem', fontWeight: 700 }}>
            <Plus size={16} /> Nova Vaga
          </button>
        </div>
      </div>

      {/* 2. Filtros */}
      <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', padding: '2px 0' }}>
        {['all', 'new', 'scraped', 'applied', 'interviewing', 'offer', 'rejected', 'archived'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`} style={{ textTransform: 'capitalize', fontSize: '0.7rem', height: '28px', padding: '0 10px', whiteSpace: 'nowrap' }}>
            {f}
          </button>
        ))}
      </div>

      {/* 3. Área de Conteúdo com Scroll Blindado */}
      <div style={{ width: '100%', height: '100%', overflow: 'hidden', position: 'relative' }}>
        {loading ? (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <p style={{ color: 'var(--text-muted)' }}>Carregando...</p>
          </div>
        ) : (
          <div style={{ height: '100%', width: '100%', overflowX: 'auto', overflowY: 'hidden' }}>
            <AnimatePresence mode="wait">
              {viewMode === 'table' ? (
                <motion.div key="table" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="panel" style={{ padding: 0, overflow: 'auto', height: '100%', minWidth: '800px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', position: 'sticky', top: 0, zIndex: 10 }}>
                        <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.85rem' }}>VAGA & EMPRESA</th>
                        <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.85rem' }}>STATUS</th>
                        <th style={{ padding: '1rem', textAlign: 'right', color: 'var(--text-muted)', fontSize: '0.85rem' }}>AÇÕES</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(jobs || []).map(job => (
                        <tr key={job.id} className="row-hover" style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setSelectedJob(job)}>
                          <td style={{ padding: '1rem' }}>
                            <div style={{ fontWeight: 700, color: '#fff' }}>{job.job_title}</div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{job.company}</div>
                          </td>
                          <td style={{ padding: '1rem' }}>
                            <span style={{ padding: '3px 10px', borderRadius: '15px', fontSize: '0.7rem', fontWeight: 700, background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{job.status}</span>
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'right' }}>
                            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                              {quickButtons(job)}
                              {job.url && (
                                <a href={job.url.startsWith('http') ? job.url : `https://${job.url}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="btn btn-secondary" style={{ padding: '6px', display: 'flex', alignItems: 'center' }} title="Acessar Vaga">
                                  <ExternalLink size={16} />
                                </a>
                              )}
                              <button onClick={(e) => { e.stopPropagation(); jobService.deleteJob(job.id).then(() => loadJobs()); }} className="btn btn-secondary" style={{ padding: '6px' }} title="Deletar"><Trash2 size={16} /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </motion.div>
              ) : (
                <div style={{ display: 'inline-flex', gap: '1rem', height: '100%', paddingBottom: '1rem' }}>
                  {columns.map(col => (
                    <div 
                      key={col.id} 
                      onDragOver={(e) => e.preventDefault()} 
                      onDrop={(e) => {
                        const id = e.dataTransfer.getData('jobId');
                        if (id) handleStatusUpdate(parseInt(id), col.id);
                      }}
                      style={{ 
                        width: '300px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.8rem',
                        background: 'rgba(255,255,255,0.01)', borderRadius: '16px', padding: '1rem', border: '1px solid var(--border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.5rem' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: col.color }} />
                        <h3 style={{ fontSize: '0.8rem', fontWeight: 800, textTransform: 'uppercase', color: '#fff' }}>{col.title}</h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                          {(jobs || []).filter(j => j.status === col.id).length}
                        </span>
                      </div>

                      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                        {(jobs || []).filter(j => j.status === col.id).map(job => (
                          <div 
                            key={job.id}
                            className="panel card-hover" 
                            style={{ padding: '1rem', marginBottom: 0, cursor: 'grab', background: 'rgba(30, 30, 40, 0.5)', border: '1px solid var(--border)' }} 
                            onDragStart={(e) => e.dataTransfer.setData('jobId', job.id.toString())}
                            draggable={true} 
                            onClick={() => setSelectedJob(job)}
                          >
                            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fff', marginBottom: '4px' }}>{job.job_title}</div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '8px' }}>{job.company}</div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}><MapPin size={12} /> {job.location || 'Remote'}</div>
                              <div style={{ display: 'flex', gap: 4 }} className="card-quick">{quickButtons(job, true)}</div>
                              {job.url && (
                                <a href={job.url.startsWith('http') ? job.url : `https://${job.url}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }} title="Acessar Vaga" className="card-hover-link">
                                  <ExternalLink size={14} />
                                </a>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', backdropFilter: 'blur(8px)' }}>
          <div className="panel" style={{ width: '100%', maxWidth: '400px' }}>
            <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem' }}>Nova Vaga</h2>
            <form onSubmit={async (e) => { e.preventDefault(); try { await jobService.addManualJob(newJob); setShowAddModal(false); loadJobs(true); } catch(err) { alert(err); } }} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <input required value={newJob.job_title} onChange={e => setNewJob({...newJob, job_title: e.target.value})} placeholder="Título" />
              <input required value={newJob.company} onChange={e => setNewJob({...newJob, company: e.target.value})} placeholder="Empresa" />
              <input value={newJob.url} onChange={e => setNewJob({...newJob, url: e.target.value})} placeholder="Link da Vaga (URL)" />
              <textarea required value={newJob.description} onChange={e => setNewJob({...newJob, description: e.target.value})} placeholder="Descrição" style={{ height: '100px' }} />
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary">Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {selected && <JobDetail key={`${selected.job.id}-${selected.action || selected.tab || ''}`} job={selected.job} initialTab={selected.tab} autoRun={selected.action}
        onClose={() => setSelected(null)} onChanged={() => loadJobs()} />}
    </div>
  );
};

export default JobBoard;
