import React, { useEffect, useState } from 'react';
import { jobService, Job } from '../services/jobService';
import { Plus, MapPin, Calendar, ExternalLink, Trash2, Building2, Globe } from 'lucide-react';
import JobDetail from '../components/JobDetail';

const JobBoard = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [newJob, setNewJob] = useState({ job_title: '', company: '', location: '', url: '', description: '' });

  useEffect(() => {
    loadJobs();
  }, [filter]);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const data = await jobService.getJobs(filter);
      setJobs(data);
    } catch (error) {
      console.error("Failed to load jobs", error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddJob = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await jobService.addManualJob(newJob);
      setShowModal(false);
      setNewJob({ job_title: '', company: '', location: '', url: '', description: '' });
      loadJobs();
    } catch (error) {
      alert("Failed to add job");
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this job?")) {
      try {
        await jobService.deleteJob(id);
        loadJobs();
      } catch (error) {
        alert("Failed to delete job");
      }
    }
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Job Board</h1>
          <p style={{ color: 'var(--text-muted)' }}>Manage and review your scraped opportunities.</p>
        </div>
        <button className="btn btn-primary" onClick={() => {
          setShowModal(true);
        }}>
          <Plus size={18} /> Add Manual Job
        </button>
      </div>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 9999, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto' }}>
          <div className="panel" style={{ width: '100%', maxWidth: '600px', margin: '0 auto', zIndex: 10000 }}>
            <h2 style={{ marginBottom: '1.5rem' }}>Add Manual Job</h2>
            <form onSubmit={handleAddJob}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <input placeholder="Job Title" required value={newJob.job_title} onChange={e => setNewJob({...newJob, job_title: e.target.value})} />
                <input placeholder="Company" required value={newJob.company} onChange={e => setNewJob({...newJob, company: e.target.value})} />
                <input placeholder="Location" value={newJob.location} onChange={e => setNewJob({...newJob, location: e.target.value})} />
                <input placeholder="URL" value={newJob.url} onChange={e => setNewJob({...newJob, url: e.target.value})} />
              </div>
              <textarea placeholder="Description" required value={newJob.description} onChange={e => setNewJob({...newJob, description: e.target.value})} style={{ height: '200px', marginBottom: '1.5rem' }} />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Job</button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="panel" style={{ padding: '0.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', padding: '0.5rem' }}>
          {['all', 'new', 'scraped', 'done', 'error'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`btn ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
              style={{ textTransform: 'capitalize', fontSize: '0.85rem' }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>Loading jobs...</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
                <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>Job & Company</th>
                <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>Location</th>
                <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '1rem', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>Added At</th>
                <th style={{ padding: '1rem', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(jobs || []).map(job => (
                <tr key={job.id} className="row-hover" style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.2s', cursor: 'pointer' }} onClick={() => {
                  setSelectedJob(job);
                }}>
                  <td style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ 
                        width: '36px', 
                        height: '36px', 
                        background: 'rgba(255,255,255,0.05)', 
                        borderRadius: '6px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        overflow: 'hidden',
                        flexShrink: 0
                      }}>
                        {job.logo_url ? (
                          <img src={job.logo_url} alt={job.company_name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        ) : (
                          <Building2 size={18} color="var(--text-muted)" />
                        )}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: '#fff' }}>{job.job_title}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {job.company_name || job.company}
                          {job.company_type && (
                            <span style={{ 
                              fontSize: '0.65rem', 
                              padding: '1px 6px', 
                              borderRadius: '4px', 
                              background: 'rgba(255,255,255,0.05)',
                              color: 'var(--text-muted)',
                              border: '1px solid rgba(255,255,255,0.1)'
                            }}>
                              {job.company_type.replace('_', ' ')}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <MapPin size={14} /> {job.location}
                    </div>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ 
                      padding: '4px 10px', 
                      borderRadius: '20px', 
                      fontSize: '0.75rem', 
                      background: job.status === 'new' ? 'rgba(108, 99, 255, 0.1)' : 'rgba(255,255,255,0.05)',
                      color: job.status === 'new' ? 'var(--accent)' : 'var(--text-muted)',
                      border: `1px solid ${job.status === 'new' ? 'rgba(108, 99, 255, 0.2)' : 'transparent'}`,
                      textTransform: 'uppercase'
                    }}>
                      {job.status}
                    </span>
                  </td>
                  <td style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Calendar size={14} /> {new Date(job.created_at).toLocaleDateString()}
                    </div>
                  </td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      {job.url && (
                        <a href={job.url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ padding: '6px' }} title="Anúncio Original" onClick={(e) => e.stopPropagation()}>
                          <ExternalLink size={16} />
                        </a>
                      )}
                      {job.career_site_url && (
                        <a href={job.career_site_url} target="_blank" rel="noreferrer" className="btn btn-primary" style={{ padding: '6px', background: 'rgba(108, 99, 255, 0.2)' }} title="Site de Carreira" onClick={(e) => e.stopPropagation()}>
                          <Globe size={16} />
                        </a>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(job.id); }} className="btn btn-secondary" style={{ padding: '6px', color: '#ff4d4d' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {jobs.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
            No jobs found for this filter.
          </div>
        )}
      </div>
      <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 2000 }}>
        {selectedJob && <div style={{ background: 'var(--success)', padding: '10px', borderRadius: '8px', fontSize: '0.8rem' }}>Opening: {selectedJob.job_title}</div>}
      </div>

      {selectedJob && (
        <JobDetail 
          job={selectedJob} 
          onClose={() => {
            console.log("Closing JobDetail");
            setSelectedJob(null);
          }} 
        />
      )}
    </div>
  );
};

export default JobBoard;
