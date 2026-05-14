import React, { useState, useEffect } from 'react';
import { Job, jobService } from '../services/jobService';
import { X, FileText, MessageSquare, Wand2, Zap, RefreshCw, Copy, Download, Send, CheckCircle2, Circle, ExternalLink } from 'lucide-react';
import api from '../services/api';

interface JobDetailProps {
  job: Job;
  onClose: () => void;
}

interface ActionStatus {
  id: string;
  label: string;
  status: 'idle' | 'running' | 'done' | 'error';
  selected: boolean;
}

const JobDetail: React.FC<JobDetailProps> = ({ job: initialJob, onClose }) => {
  if (!initialJob) return null;

  const [job, setJob] = useState<Job>(initialJob);
  const [activeTab, setActiveTab] = useState('info');
  const [chatMode, setChatMode] = useState<'assistant' | 'simulator'>('assistant');
  const [loading, setLoading] = useState(false);
  
  // AI Actions State
  const [actions, setActions] = useState<ActionStatus[]>([
    { id: 'resume', label: 'Tailor Resume', status: initialJob.resume_markdown ? 'done' : 'idle', selected: false },
    { id: 'cover', label: 'Cover Letter', status: initialJob.cover_letter ? 'done' : 'idle', selected: false },
    { id: 'dm', label: 'LinkedIn Outreach', status: initialJob.linkedin_dm_draft ? 'done' : 'idle', selected: false }
  ]);

  // Results Hub State (Expandable)
  const [expandedResults, setExpandedResults] = useState<Record<string, boolean>>({});

  // Form States
  const [chatMessage, setChatMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: string, text: string}[]>([]);
  const [tone, setTone] = useState('semi-formal');
  const [orientation, setOrientation] = useState('');
  const [employerQuestion, setEmployerQuestion] = useState('');

  const refreshJobData = async () => {
    try {
      const response = await api.get<Job>(`/jobs/${job.id}`);
      setJob(response.data);
      // Also update actions status if needed
      setActions(prev => prev.map(a => {
        if (a.id === 'resume' && response.data.resume_markdown) return { ...a, status: 'done' };
        if (a.id === 'cover' && response.data.cover_letter) return { ...a, status: 'done' };
        if (a.id === 'dm' && response.data.linkedin_dm_draft) return { ...a, status: 'done' };
        return a;
      }));
    } catch (e) {
      console.error("Failed to refresh job data", e);
    }
  };

  const toggleAction = (id: string) => {
    setActions(prev => prev.map(a => a.id === id ? { ...a, selected: !a.selected } : a));
  };

  const runSelectedActions = async () => {
    const selected = actions.filter(a => a.selected);
    if (selected.length === 0) return;

    setLoading(true);
    
    for (const action of selected) {
      setActions(prev => prev.map(a => a.id === action.id ? { ...a, status: 'running' } : a));
      
      try {
        if (action.id === 'resume') await jobService.generateResume(job.id, { tone, orientation });
        else if (action.id === 'cover') await jobService.generateCoverLetter(job.id, { tone, orientation });
        else if (action.id === 'dm') await jobService.outreach(job.id, 'dm', { tone, orientation });
        
        setActions(prev => prev.map(a => a.id === action.id ? { ...a, status: 'done', selected: false } : a));
      } catch (e) {
        setActions(prev => prev.map(a => a.id === action.id ? { ...a, status: 'error' } : a));
      }
    }
    
    await refreshJobData();
    setLoading(false);
    setActiveTab('result');
  };

  const handleSendChat = async () => {
    const msg = chatMode === 'assistant' ? employerQuestion : chatMessage;
    if (!msg.trim()) return;

    if (chatMode === 'simulator') {
      setChatMessage('');
      setChatHistory(prev => [...prev, { role: 'user', text: msg }]);
    }
    
    setLoading(true);
    try {
      const data = await jobService.chat(job.id, msg, { tone, orientation });
      if (chatMode === 'assistant') setChatHistory([{ role: 'ai', text: data.reply }]);
      else setChatHistory(prev => [...prev, { role: 'ai', text: data.reply }]);
    } catch (error) {
      alert("AI was unable to process your request.");
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async (content: string, type: string) => {
    try {
      const data = await jobService.downloadPDF(job.id, content);
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${type.toLowerCase()}_${job.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      alert("Failed to generate PDF");
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedResults(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      background: 'rgba(5, 5, 10, 0.8)', 
      zIndex: 9999, 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      backdropFilter: 'blur(10px)',
      padding: '20px'
    }}>
      <div className="panel animate-fade-in" style={{ 
        width: '100%', 
        maxWidth: '1000px', 
        maxHeight: '90vh', 
        display: 'flex', 
        flexDirection: 'column', 
        border: '1px solid rgba(108, 99, 255, 0.3)', 
        padding: 0, 
        overflow: 'hidden', 
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
        position: 'relative',
        background: 'var(--bg-card)'
      }}>
        
        {/* Compact Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.8rem 1.5rem', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1px' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>{job.job_title}</h2>
              {job.url && (
                <a href={job.url.startsWith('http') ? job.url : `https://${job.url}`} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center' }} title="Acessar Vaga">
                  <ExternalLink size={16} />
                </a>
              )}
            </div>
            <p style={{ color: 'var(--accent)', fontSize: '0.8rem', fontWeight: 600, margin: 0 }}>{job.company} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>• {job.location}</span></p>
          </div>
          <button onClick={onClose} className="btn btn-secondary" style={{ padding: '5px', borderRadius: '50%' }}><X size={18} /></button>
        </div>

        {/* Shrunken Tabs */}
        <div style={{ display: 'flex', gap: '1.5rem', padding: '0 1.5rem', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.01)' }}>
          {[
            { id: 'info', label: 'Job Detail', icon: <FileText size={15} /> },
            { id: 'actions', label: 'AI Flow', icon: <Zap size={15} /> },
            { id: 'chat', label: 'Career Chat', icon: <MessageSquare size={15} /> },
            { id: 'result', label: 'Results Hub', icon: <Wand2 size={15} /> }
          ].map(tab => (
            <button 
              key={tab.id} 
              onClick={() => setActiveTab(tab.id)}
              className={`nav-link ${activeTab === tab.id ? 'active' : ''}`}
              style={{ 
                padding: '0.8rem 0', background: 'transparent', border: 'none', borderBottom: `2px solid ${activeTab === tab.id ? 'var(--accent)' : 'transparent'}`,
                color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem'
              }}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div style={{ flex: 1, padding: '1rem 1.5rem', overflowY: 'auto' }}>
          
          {activeTab === 'info' && (
            <div className="animate-fade-in" style={{ height: '450px', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border)', overflowY: 'auto', whiteSpace: 'pre-wrap', color: '#ccc', lineHeight: '1.5', fontSize: '0.9rem' }}>
              {job.description || "No description provided."}
            </div>
          )}

          {activeTab === 'actions' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', background: 'rgba(108, 99, 255, 0.05)', padding: '0.8rem', borderRadius: '10px', border: '1px solid rgba(108, 99, 255, 0.2)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--accent)' }}>TONE</label>
                  <select value={tone} onChange={e => setTone(e.target.value)} style={{ padding: '3px 6px', fontSize: '0.75rem', borderRadius: '4px', background: '#1a1a25', color: '#fff', border: '1px solid var(--border)' }}>
                    <option value="semi-formal">Semi-Formal</option>
                    <option value="formal">Formal</option>
                    <option value="informal">Casual</option>
                  </select>
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <label style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--accent)' }}>AI ORIENTATION</label>
                  <input 
                    type="text" 
                    value={orientation}
                    onChange={e => setOrientation(e.target.value)}
                    placeholder="Focus on my AWS and Python skills..."
                    style={{ padding: '5px 10px', fontSize: '0.8rem', borderRadius: '6px', background: '#1a1a25', color: '#fff', border: '1px solid var(--border)' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {actions.map(act => (
                  <div key={act.id} onClick={() => toggleAction(act.id)} className="panel card-hover" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.8rem 1rem', cursor: 'pointer', background: act.selected ? 'rgba(108, 99, 255, 0.1)' : 'rgba(255,255,255,0.02)', border: act.selected ? '1px solid var(--accent)' : '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      {act.selected ? <CheckCircle2 size={18} color="var(--accent)" /> : <Circle size={18} color="#444" />}
                      <div>
                        <h4 style={{ fontSize: '0.9rem', color: '#fff' }}>{act.label}</h4>
                      </div>
                    </div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', color: act.status === 'done' ? '#10b981' : act.status === 'running' ? 'var(--accent)' : '#666' }}>
                      {act.status === 'running' ? <RefreshCw className="animate-spin" size={14} /> : act.status}
                    </div>
                  </div>
                ))}
              </div>

              <button 
                onClick={runSelectedActions} 
                disabled={loading || actions.filter(a => a.selected).length === 0}
                className="btn btn-primary" 
                style={{ marginTop: '1rem', padding: '0.8rem', width: '100%', justifyContent: 'center', gap: '10px' }}
              >
                {loading ? <RefreshCw className="animate-spin" size={18} /> : <Zap size={18} />}
                {loading ? 'Running AI Magic...' : 'Run Selected Actions'}
              </button>
            </div>
          )}

          {activeTab === 'chat' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.8rem', background: 'rgba(255,255,255,0.03)', padding: '3px', borderRadius: '8px', width: 'fit-content', margin: '0 auto' }}>
                <button onClick={() => setChatMode('assistant')} style={{ padding: '5px 12px', borderRadius: '6px', border: 'none', background: chatMode === 'assistant' ? 'var(--accent)' : 'transparent', color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: '0.75rem' }}>Employer Answer</button>
                <button onClick={() => setChatMode('simulator')} style={{ padding: '5px 12px', borderRadius: '6px', border: 'none', background: chatMode === 'simulator' ? 'var(--accent)' : 'transparent', color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: '0.75rem' }}>Free Chat</button>
              </div>

              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                {chatMode === 'assistant' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                    <div className="form-group">
                      <label style={{ fontSize: '0.7rem', color: '#888' }}>Employer Question</label>
                      <textarea 
                        value={employerQuestion} 
                        onChange={e => setEmployerQuestion(e.target.value)}
                        placeholder="Paste the question here..."
                        style={{ height: '100px', background: '#1a1a25', border: '1px solid var(--border)', color: '#fff', padding: '0.8rem', borderRadius: '10px', fontSize: '0.85rem' }}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                       <div style={{ flex: 1 }}>
                          <label style={{ fontSize: '0.7rem', color: '#888' }}>Tone</label>
                          <select value={tone} onChange={e => setTone(e.target.value)} style={{ width: '100%', padding: '0.5rem', background: '#1a1a25', border: '1px solid var(--border)', color: '#fff', borderRadius: '6px' }}>
                            <option value="semi-formal">Semi-Formal</option>
                            <option value="formal">Formal</option>
                            <option value="informal">Casual</option>
                          </select>
                       </div>
                       <div style={{ flex: 2 }}>
                          <label style={{ fontSize: '0.7rem', color: '#888' }}>Orientation</label>
                          <input value={orientation} onChange={e => setOrientation(e.target.value)} placeholder="Ex: Focus on soft skills..." style={{ width: '100%', padding: '0.5rem', background: '#1a1a25', border: '1px solid var(--border)', color: '#fff', borderRadius: '6px' }} />
                       </div>
                    </div>
                    <button className="btn btn-primary" onClick={handleSendChat} disabled={loading} style={{ padding: '0.8rem' }}>
                      {loading ? <RefreshCw className="animate-spin" size={16} /> : <Wand2 size={16} />} Generate Answer
                    </button>
                    {chatHistory.length > 0 && (
                      <div className="panel" style={{ background: 'rgba(108, 99, 255, 0.05)', padding: '1rem', border: '1px solid var(--border)' }}>
                        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: '#fff', fontFamily: 'inherit' }}>{chatHistory[0].text}</pre>
                        <button onClick={() => navigator.clipboard.writeText(chatHistory[0].text)} className="btn btn-secondary" style={{ marginTop: '0.5rem', fontSize: '0.7rem' }}><Copy size={12} /> Copy</button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', minHeight: '250px' }}>
                      {chatHistory.map((msg, i) => (
                        <div key={i} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', background: msg.role === 'user' ? 'var(--accent)' : 'rgba(255,255,255,0.08)', padding: '0.6rem 1rem', borderRadius: '12px', maxWidth: '85%', fontSize: '0.85rem' }}>{msg.text}</div>
                      ))}
                    </div>
                    <div style={{ display: 'flex', gap: '0.6rem' }}>
                      <input value={chatMessage} onChange={e => setChatMessage(e.target.value)} onKeyPress={e => e.key === 'Enter' && handleSendChat()} placeholder="Type message..." style={{ flex: 1, background: '#1a1a25', border: '1px solid var(--border)', color: '#fff', padding: '0.7rem', borderRadius: '10px' }} />
                      <button onClick={handleSendChat} className="btn btn-primary" style={{ padding: '0.7rem' }}><Send size={16} /></button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'result' && (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              {[
                { id: 'resume', label: 'Custom Resume', content: job.resume_markdown },
                { id: 'cover', label: 'Cover Letter', content: job.cover_letter },
                { id: 'dm', label: 'LinkedIn Outreach', content: job.linkedin_dm_draft }
              ].map(res => (
                <div key={res.id} className="panel" style={{ background: 'rgba(255,255,255,0.01)', padding: 0, border: '1px solid var(--border)', overflow: 'hidden' }}>
                  <div onClick={() => res.content && toggleExpand(res.id)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.8rem 1.2rem', cursor: res.content ? 'pointer' : 'default', background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: res.content ? '#10b981' : '#444' }}></div>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: res.content ? '#fff' : '#666' }}>{res.label}</span>
                    </div>
                    {res.content && (
                      <div style={{ display: 'flex', gap: '0.6rem' }}>
                        <button onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(res.content!); alert("Copied!"); }} className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '0.7rem' }}><Copy size={12} /></button>
                        {(res.id === 'resume' || res.id === 'cover') && (
                          <button onClick={(e) => { e.stopPropagation(); downloadPDF(res.content!, res.label); }} className="btn btn-primary" style={{ padding: '4px 8px', fontSize: '0.7rem' }}><Download size={12} /></button>
                        )}
                        <span style={{ fontSize: '0.7rem', color: 'var(--accent)' }}>{expandedResults[res.id] ? 'Collapse' : 'Expand'}</span>
                      </div>
                    )}
                  </div>
                  {expandedResults[res.id] && res.content && (
                    <div style={{ padding: '1rem', background: '#0a0a0f', borderTop: '1px solid var(--border)', maxHeight: '300px', overflowY: 'auto' }}>
                      <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.75rem', color: '#ccc', lineHeight: '1.5' }}>{res.content}</pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default JobDetail;
