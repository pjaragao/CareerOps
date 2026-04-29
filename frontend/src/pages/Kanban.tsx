import React, { useEffect, useState } from 'react';
import { jobService, Job } from '../services/jobService';
import { MoreHorizontal, Plus } from 'lucide-react';
import JobDetail from '../components/JobDetail';

const Kanban = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const columns = [
    { id: 'scraped', title: 'Sourced / Scraped', color: '#6c63ff' },
    { id: 'new', title: 'To Evaluate', color: '#ffd700' },
    { id: 'applied', title: 'Applied', color: '#00c853' },
    { id: 'interviewing', title: 'Interviewing', color: '#00b0ff' },
    { id: 'offer', title: 'Offer / Accepted', color: '#aa00ff' },
    { id: 'rejected', title: 'Rejected', color: '#ff4d4d' }
  ];

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const data = await jobService.getJobs('all');
      setJobs(data);
    } catch (error) {
      console.error("Failed to load jobs", error);
      alert("Failed to load Kanban board. Check server connection.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading Kanban...</div>;

  return (
    <div className="animate-fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Kanban Board</h1>
        <p style={{ color: 'var(--text-muted)' }}>Track your applications through the recruitment funnel.</p>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', overflowX: 'auto', paddingBottom: '1rem', flex: 1 }}>
        {columns.map(col => (
          <div key={col.id} style={{ minWidth: '300px', flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: col.color }} />
                <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{col.title}</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '10px' }}>
                  {(jobs || []).filter(j => j.status === col.id).length}
                </span>
              </div>
              <Plus size={18} style={{ color: 'var(--text-muted)', cursor: 'pointer' }} />
            </div>

            <div style={{ flex: 1, background: 'rgba(255,255,255,0.02)', borderRadius: '12px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {(jobs || []).filter(j => j.status === col.id).map(job => (
                <div key={job.id} className="panel card-hover" style={{ padding: '1rem', marginBottom: 0, cursor: 'pointer' }} onClick={() => setSelectedJob(job)}>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.4rem' }}>{job.job_title}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{job.company}</div>
                  <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <MoreHorizontal size={16} style={{ color: 'var(--text-muted)' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 2000 }}>
        {selectedJob && <div style={{ background: 'var(--success)', padding: '10px', borderRadius: '8px', fontSize: '0.8rem' }}>Opening: {selectedJob.job_title}</div>}
      </div>

      {selectedJob && (
        <JobDetail 
          job={selectedJob} 
          onClose={() => {
            console.log("Closing Kanban JobDetail");
            setSelectedJob(null);
          }} 
        />
      )}
    </div>
  );
};

export default Kanban;
