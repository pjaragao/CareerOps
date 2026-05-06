import React, { useEffect, useState, useCallback, useRef } from 'react';
import { jobService, Job } from '../services/jobService';
import { 
  Plus, MapPin, Calendar, Trash2, Building2, 
  LayoutDashboard, List as ListIcon, MoreHorizontal
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import JobDetail from '../components/JobDetail';

const JobBoard = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('kanban');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
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
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0, height: '100%' }}>
      
      {/* Header Section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '0.8rem', flexShrink: 0 }}>
        <div>
          <h1 style={{ fontSize: '1.2rem', fontWeight: 900, color: '#fff', margin: 0 }}>Job Board</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', margin: '2px 0 0 0' }}>Gerencie suas oportunidades.</p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <div style={{ background: '#1a1a25', padding: '3px', borderRadius: '8px', display: 'flex', border: '1px solid var(--border)' }}>
            <button 
              onClick={() => setViewMode('kanban')} 
              style={{ padding: '4px 12px', border: 'none', borderRadius: '6px', cursor: 'pointer', background: viewMode === 'kanban' ? 'var(--accent)' : 'transparent', color: viewMode === 'kanban' ? '#fff' : 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <LayoutDashboard size={14} /> Kanban
            </button>
            <button 
              onClick={() => setViewMode('table')} 
              style={{ padding: '4px 12px', border: 'none', borderRadius: '6px', cursor: 'pointer', background: viewMode === 'table' ? 'var(--accent)' : 'transparent', color: viewMode === 'table' ? '#fff' : 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <ListIcon size={14} /> Lista
            </button>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)} style={{ height: '30px', padding: '0 12px', fontSize: '0.75rem' }}>
            <Plus size={16} /> Nova Vaga
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', padding: '2px 0', flexShrink: 0 }}>
        {['all', 'new', 'scraped', 'applied', 'interviewing', 'offer', 'rejected'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`} style={{ textTransform: 'capitalize', fontSize: '0.7rem', height: '26px', padding: '0 8px', whiteSpace: 'nowrap' }}>
            {f}
          </button>
        ))}
      </div>

      {/* Main Content Scroll Area */}
      <div style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden', minHeight: 0 }}>
        {loading ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <p style={{ color: 'var(--text-muted)' }}>Carregando...</p>
          </div>
        ) : (
          <div style={{ height: '100%', display: 'flex', gap: '1rem', paddingBottom: '1rem' }}>
            <AnimatePresence mode="wait">
              {viewMode === 'table' ? (
                <motion.div key="table" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="panel" style={{ padding: 0, overflow: 'auto', height: '100%', flex: 1, minWidth: '100%' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', position: 'sticky', top: 0, zIndex: 10 }}>
                        <th style={{ padding: '0.8rem', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.8rem' }}>VAGA</th>
                        <th style={{ padding: '0.8rem', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.8rem' }}>STATUS</th>
                        <th style={{ padding: '0.8rem', textAlign: 'right', color: 'var(--text-muted)', fontSize: '0.8rem' }}>AÇÕES</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(jobs || []).map(job => (
                        <tr key={job.id} className="row-hover" style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setSelectedJob(job)}>
                          <td style={{ padding: '0.8rem' }}>
                            <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.85rem' }}>{job.job_title}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{job.company}</div>
                          </td>
                          <td style={{ padding: '0.8rem' }}>
                            <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.65rem', fontWeight: 700, background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{job.status}</span>
                          </td>
                          <td style={{ padding: '0.8rem', textAlign: 'right' }}>
                            <button onClick={(e) => { e.stopPropagation(); jobService.deleteJob(job.id).then(() => loadJobs()); }} className="btn btn-secondary" style={{ padding: '4px' }}><Trash2 size={16} /></button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </motion.div>
              ) : (
                <motion.div 
                  key="kanban" 
                  initial={{ opacity: 0 }} 
                  animate={{ opacity: 1 }} 
                  exit={{ opacity: 0 }} 
                  style={{ display: 'flex', gap: '1rem', height: '100%' }}
                >
                  {columns.map(col => (
                    <div 
                      key={col.id} 
                      onDragOver={(e) => { e.preventDefault(); setDragOverColumn(col.id); }} 
                      onDrop={(e) => {
                        e.preventDefault();
                        const jobIdStr = e.dataTransfer.getData('text/plain');
                        if (jobIdStr) handleStatusUpdate(parseInt(jobIdStr), col.id);
                        setDragOverColumn(null);
                      }} 
                      onDragLeave={() => setDragOverColumn(null)}
                      style={{ 
                        width: '280px', 
                        flexShrink: 0, 
                        display: 'flex', 
                        flexDirection: 'column', 
                        gap: '0.8rem',
                        background: dragOverColumn === col.id ? 'rgba(108, 99, 255, 0.05)' : 'rgba(255,255,255,0.01)',
                        borderRadius: '16px', 
                        padding: '0.8rem', 
                        border: `1px solid ${dragOverColumn === col.id ? 'var(--accent)' : 'var(--border)'}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: col.color }} />
                        <h3 style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: '#fff' }}>{col.title}</h3>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                          {(jobs || []).filter(j => j.status === col.id).length}
                        </span>
                      </div>

                      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                        <AnimatePresence>
                          {(jobs || []).filter(j => j.status === col.id).map(job => (
                            <motion.div key={job.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                              <div 
                                className="panel card-hover" 
                                style={{ padding: '0.8rem', marginBottom: 0, cursor: 'grab', background: 'rgba(30, 30, 40, 0.5)', border: '1px solid var(--border)' }} 
                                onDragStart={(e) => { e.dataTransfer.setData('text/plain', job.id.toString()); e.dataTransfer.effectAllowed = 'move'; }} 
                                draggable={true} 
                                onClick={() => setSelectedJob(job)}
                              >
                                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fff', marginBottom: '2px' }}>{job.job_title}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px' }}>{job.company}</div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}><MapPin size={12} /> {job.location || 'Remote'}</div>
                              </div>
                            </motion.div>
                          ))}
                        </AnimatePresence>
                      </div>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', backdropFilter: 'blur(8px)' }}>
          <div className="panel" style={{ width: '100%', maxWidth: '380px' }}>
            <h2 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Nova Vaga</h2>
            <form onSubmit={async (e) => { e.preventDefault(); try { await jobService.addManualJob(newJob); setShowAddModal(false); loadJobs(true); } catch(err) { alert(err); } }}>
               <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                <input required value={newJob.job_title} onChange={e => setNewJob({...newJob, job_title: e.target.value})} placeholder="Título" />
                <input required value={newJob.company} onChange={e => setNewJob({...newJob, company: e.target.value})} placeholder="Empresa" />
                <textarea required value={newJob.description} onChange={e => setNewJob({...newJob, description: e.target.value})} placeholder="Descrição" style={{ height: '80px' }} />
                <div style={{ display: 'flex', gap: '0.8rem', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowAddModal(false)}>Cancelar</button>
                  <button type="submit" className="btn btn-primary">Salvar</button>
                </div>
               </div>
            </form>
          </div>
        </div>
      )}

      {selectedJob && <JobDetail job={selectedJob} onClose={() => setSelectedJob(null)} />}
    </div>
  );
};

export default JobBoard;
