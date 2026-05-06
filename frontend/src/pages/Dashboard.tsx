import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { dashboardService, DashboardStats } from '../services/dashboardService';
import { 
  Briefcase, 
  GitPullRequest, 
  MessageSquare, 
  CheckCircle2, 
  Zap,
  TrendingUp,
  Clock
} from 'lucide-react';

const DashboardCard = ({ title, value, icon, color }: any) => (
  <div className="panel" style={{ marginBottom: 0 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '4px' }}>{title}</p>
        <h2 style={{ fontSize: '1.8rem', fontWeight: 700 }}>{value}</h2>
      </div>
      <div style={{ 
        padding: '10px', 
        borderRadius: '12px', 
        background: `rgba(${color}, 0.1)`, 
        color: `rgb(${color})` 
      }}>
        {icon}
      </div>
    </div>
    <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--success)' }}>
      <TrendingUp size={14} />
      <span>+12% this week</span>
    </div>
  </div>
);

const Dashboard = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [gaps, setGaps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [statsData, gapsData] = await Promise.all([
        dashboardService.getStats(),
        dashboardService.getSkillGaps()
      ]);
      setStats(statsData);
      setGaps(gapsData);
    } catch (error) {
      console.error("Failed to load dashboard data", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem' }}>Loading dashboard...</div>;

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '2.5rem' }}>
        <h1 style={{ fontSize: '2.2rem', fontWeight: 800, marginBottom: '0.5rem' }}>Welcome back, Paulo</h1>
        <p style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Clock size={16} /> Your career automation is running smoothly.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        <DashboardCard 
          title="Jobs Scraped" 
          value={stats?.total_jobs} 
          icon={<Briefcase size={24} />} 
          color="108, 99, 255" 
        />
        <DashboardCard 
          title="Pipeline Pending" 
          value={stats?.pipeline_pending} 
          icon={<GitPullRequest size={24} />} 
          color="255, 171, 0" 
        />
        <DashboardCard 
          title="Applications" 
          value={stats?.apps_count} 
          icon={<CheckCircle2 size={24} />} 
          color="0, 200, 83" 
        />
        <DashboardCard 
          title="STAR Cases" 
          value={stats?.stories_count} 
          icon={<MessageSquare size={24} />} 
          color="0, 184, 212" 
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Zap size={20} color="var(--accent)" /> Quick Actions</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <button className="btn btn-secondary" style={{ padding: '1.5rem', flexDirection: 'column', gap: '12px' }} onClick={async () => {
              try {
                await api.post('/pipeline/process');
                alert("Pipeline processing started!");
              } catch(e) { alert("Failed to start pipeline"); }
            }}>
              <GitPullRequest size={24} />
              <span>Process Pipeline</span>
            </button>
            <button className="btn btn-secondary" style={{ padding: '1.5rem', flexDirection: 'column', gap: '12px' }} onClick={async () => {
              try {
                await api.post('/strategies/run-all');
                alert("All strategies search started!");
              } catch(e) { alert("Failed to start strategies"); }
            }}>
              <Zap size={24} />
              <span>Run Strategies</span>
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Skill Gaps Analysis</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {gaps && gaps.length > 0 ? gaps.map((gap, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.9rem', color: '#fff' }}>{gap.skill}</span>
                <span style={{ 
                  fontSize: '0.75rem', 
                  padding: '2px 8px', 
                  borderRadius: '10px',
                  background: gap.priority === 'high' ? 'rgba(255, 77, 77, 0.1)' : 'rgba(255,255,255,0.05)',
                  color: gap.priority === 'high' ? '#ff4d4d' : 'var(--text-muted)'
                }}>
                  {gap.frequency}x
                </span>
              </div>
            )) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No gaps identified yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
