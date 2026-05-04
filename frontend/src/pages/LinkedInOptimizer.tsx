import React, { useState, useEffect } from 'react';
import { profileService } from '../services/profileService';
import { strategyService, Strategy } from '../services/strategyService';
import { jobService, Job } from '../services/jobService';
import { 
  Wand2, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw, 
  Layout, 
  Type, 
  ListChecks, 
  FileText,
  Target,
  TrendingUp,
  Award,
  Zap,
  MoreHorizontal,
  ChevronRight,
  Clipboard,
  Eye,
  ShieldCheck,
  MessageSquare,
  Users,
  Search,
  Plus
} from 'lucide-react';

const LinkedInOptimizer = () => {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [profile, setProfile] = useState<any>({
    personal: {},
    experience: [],
    education: [],
    skills: [],
    about: ''
  });
  const [results, setResults] = useState<any>(null);
  const [lang, setLang] = useState<'pt' | 'en'>('pt');
  const [atsJobDesc, setAtsJobDesc] = useState('');
  const [atsMatchResult, setAtsMatchResult] = useState<any>(null);
  const [skillsResult, setSkillsResult] = useState<any>(null);
  const [expResult, setExpResult] = useState<any>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [savedJobs, setSavedJobs] = useState<Job[]>([]);
  const [strategyContext, setStrategyContext] = useState<{type: string, id: number, label: string, keywords: string[]}|null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [profileData, strats, jobs, latestAnalysis, latestExp, latestSkills] = await Promise.all([
        profileService.getProfile(),
        strategyService.getStrategies(),
        jobService.getJobs(),
        profileService.getLatestAnalysis('full_audit').catch(() => null),
        profileService.getLatestAnalysis('experience').catch(() => null),
        profileService.getLatestAnalysis('skills').catch(() => null)
      ]);
      setProfile(profileData);
      setStrategies(strats || []);
      setSavedJobs(jobs || []);
      
      if (latestAnalysis) {
        setResults(latestAnalysis.results);
        setStrategyContext(latestAnalysis.strategy_context);
        setLang(latestAnalysis.lang || 'pt');
      }
      if (latestExp && latestExp.results) {
        setExpResult(latestExp.results.results || latestExp.results);
      }
      if (latestSkills) {
        setSkillsResult(latestSkills.results);
      }
    } catch (error) {
      console.error("Failed to load data", error);
    }
  };

  const checkCompleteness = (p: any) => {
    if (!p.personal?.name || !p.experience?.length || !p.skills?.length) {
      return false;
    }
    return true;
  };

  const runFullAnalysis = async () => {
    const p = await profileService.getProfile();
    if (!checkCompleteness(p)) {
      alert("⚠️ Profile is incomplete. Please ensure you have a Name, Experience, and Skills in the Profile page before running optimization.");
      return;
    }

    setLoading(true);
    try {
      setProfile(p);
      const res = await profileService.runFullAudit(lang, strategyContext);
      setResults(res);
      setActiveTab('overview');
    } catch (error) {
      alert("Failed to run optimization.");
    } finally {
      setLoading(false);
    }
  };

  const handleATSMatch = async () => {
    if (!atsJobDesc) return;
    setLoading(true);
    try {
      const res = await profileService.atsMatch(atsJobDesc, lang, strategyContext);
      setAtsMatchResult(res);
    } catch (error) {
      alert("ATS Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleSkillsAnalysis = async () => {
    setLoading(true);
    try {
      const target = strategyContext?.label || profile.preferences?.target_role || 'Software Engineer';
      const res = await profileService.analyzeSkills(target, lang, strategyContext);
      setSkillsResult(res);
    } catch (error) {
      alert("Skills analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleExpOptimization = async () => {
    setLoading(true);
    try {
      const res = await profileService.optimizeExperience(lang, strategyContext);
      setExpResult(res.results);
    } catch (error) {
      alert("Experience optimization failed.");
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () => {
    if (!results) return null;
    return (
      <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        <div className="panel" style={{ marginBottom: 0 }}>
          <h3 className="panel-title"><Award color="var(--accent)" /> Profile Strength</h3>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '16px', marginTop: '1rem' }}>
             <div style={{ position: 'relative', width: '160px', height: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="160" height="160" style={{ transform: 'rotate(-90deg)' }}>
                  <circle cx="80" cy="80" r="70" stroke="rgba(255,255,255,0.05)" strokeWidth="10" fill="transparent" />
                  <circle cx="80" cy="80" r="70" stroke="var(--accent)" strokeWidth="10" fill="transparent" 
                    strokeDasharray={440} strokeDashoffset={440 - (440 * results.score.score) / 100} 
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 1.5s ease-in-out' }}
                  />
                </svg>
                <div style={{ position: 'absolute', fontSize: '2.5rem', fontWeight: 800 }}>{results.score.score}<span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>%</span></div>
             </div>
             <p style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{results.score.reason}</p>
          </div>
        </div>

        <div className="panel" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column' }}>
          <h3 className="panel-title"><ListChecks color="var(--accent)" /> All-Star Checklist</h3>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.8rem', marginTop: '1rem' }}>
            {[
              { label: 'Professional Headline', checked: !!profile.personal?.headline },
              { label: 'Detailed About Section', checked: (profile.about?.length > 100) },
              { label: 'Work Experience (2+ roles)', checked: (profile.experience?.length >= 2) },
              { label: 'Skills (5+ listed)', checked: (profile.skills?.length >= 5) },
              { label: 'Education Details', checked: (profile.education?.length >= 1) },
              { label: 'Contact Information', checked: !!profile.personal?.email },
            ].map((item, i) => (
              <div key={i} style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px', 
                padding: '0.8rem 1rem', 
                borderRadius: '12px', 
                background: item.checked ? 'rgba(0, 200, 83, 0.05)' : 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255,255,255,0.02)'
              }}>
                {item.checked ? <CheckCircle color="var(--success)" size={18} /> : <div style={{ width: '18px', height: '18px', borderRadius: '50%', border: '2px dashed var(--text-muted)', opacity: 0.3 }} />}
                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: item.checked ? '#fff' : 'var(--text-muted)' }}>{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel" style={{ gridColumn: '1 / -1', marginBottom: 0 }}>
           <h3 className="panel-title"><TrendingUp color="var(--accent)" /> SSI Score Simulator</h3>
           <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
              {[results.ssi.brand, results.ssi.people, results.ssi.insights, results.ssi.relationships].map((pillar, i) => (
                <div key={i} style={{ 
                  background: 'rgba(255,255,255,0.03)', 
                  padding: '1.2rem', 
                  borderRadius: '16px', 
                  border: '1px solid var(--border)',
                  position: 'relative'
                }}>
                  <div style={{ fontSize: '1.8rem', fontWeight: 900, color: 'var(--accent)', marginBottom: '4px' }}>{pillar.score}<span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}>/25</span></div>
                  <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', color: 'rgba(255,255,255,0.7)' }}>{pillar.label}</div>
                  
                  <div style={{ width: '100%', background: 'rgba(255,255,255,0.05)', height: '4px', borderRadius: '2px', marginTop: '12px', overflow: 'hidden' }}>
                    <div style={{ background: 'var(--accent)', height: '100%', width: `${(pillar.score/25)*100}%` }}></div>
                  </div>
                </div>
              ))}
           </div>
           <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(108, 99, 255, 0.05)', border: '1px solid rgba(108, 99, 255, 0.1)', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Zap size={20} color="var(--accent)" />
              <p style={{ fontSize: '0.85rem' }}><strong>Weekly Plan:</strong> {results.ssi.weekly_plan[0]}</p>
           </div>
        </div>
      </div>
    );
  };

  const renderHeadline = () => {
    if (!results?.headlines) return null;
    return (
      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
             <h3 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}><Type color="var(--accent)" /> AI Headline Variants</h3>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {results.headlines.variants.map((variant: any, i: number) => (
                  <div key={i} className="panel" style={{ 
                    padding: '1.5rem', 
                    marginBottom: 0,
                    border: i === results.headlines.best_pick ? '2px solid var(--accent)' : '1px solid var(--border)',
                    background: i === results.headlines.best_pick ? 'rgba(108, 99, 255, 0.05)' : 'var(--bg-panel)',
                    cursor: 'pointer'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
                      <span style={{ fontSize: '10px', textTransform: 'uppercase', fontWeight: 800, padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', color: 'var(--text-muted)' }}>Focus: {variant.focus}</span>
                      <span style={{ fontSize: '10px', fontWeight: 600, color: variant.chars > 220 ? 'var(--error)' : 'var(--success)' }}>{variant.chars}/220</span>
                    </div>
                    <p style={{ fontSize: '1.1rem', fontWeight: 600, lineHeight: 1.4, marginBottom: '1.5rem' }}>{variant.text}</p>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '12px' }} onClick={() => navigator.clipboard.writeText(variant.text)}>Copy</button>
                    </div>
                  </div>
                ))}
             </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}><Eye color="var(--accent)" /> LinkedIn Preview</h3>
            <div style={{ background: '#fff', borderRadius: '24px', padding: '2rem', color: '#000', boxShadow: '0 20px 50px rgba(0,0,0,0.5)', position: 'relative', overflow: 'hidden' }}>
               <div style={{ height: '80px', background: '#e1e9ee', position: 'absolute', top: 0, left: 0, right: 0 }}></div>
               <div style={{ position: 'relative', marginTop: '40px' }}>
                  <div style={{ width: '120px', height: '120px', borderRadius: '50%', border: '4px solid #fff', background: '#cfd8dc', marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    <Users size={60} color="#90a4ae" />
                  </div>
                  <div>
                     <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: profile.personal?.name ? '#000' : '#d32f2f' }}>{profile.personal?.name || '⚠️ Name not set'}</h2>
                     <p style={{ fontSize: '1rem', lineHeight: 1.3, color: '#333', marginTop: '4px' }}>
                       {results.headlines.variants[results.headlines.best_pick].text}
                     </p>
                     <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '8px' }}>{profile.personal?.location || 'Location not set'} • <span style={{ color: '#0a66c2', fontWeight: 700 }}>500+ connections</span></p>
                  </div>
                  <div style={{ marginTop: '1rem', display: 'flex', gap: '8px' }}>
                    <button style={{ background: '#0a66c2', color: '#fff', border: 'none', padding: '0.4rem 1rem', borderRadius: '20px', fontWeight: 700, fontSize: '0.85rem' }}>Open to</button>
                    <button style={{ background: 'transparent', color: '#0a66c2', border: '1px solid #0a66c2', padding: '0.4rem 1rem', borderRadius: '20px', fontWeight: 700, fontSize: '0.85rem' }}>Add section</button>
                    <button style={{ background: 'transparent', color: '#666', border: '1px solid #666', padding: '0.4rem 1rem', borderRadius: '20px', fontWeight: 700, fontSize: '0.85rem' }}>More</button>
                  </div>
               </div>
            </div>
            <div className="panel" style={{ background: 'rgba(255, 193, 7, 0.05)', border: '1px solid rgba(255, 193, 7, 0.2)' }}>
               <div style={{ display: 'flex', gap: '12px' }}>
                 <AlertCircle size={20} color="#ffc107" />
                 <div>
                    <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ffc107', margin: 0 }}>Pro Tip</p>
                    <p style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.8)', marginTop: '4px', lineHeight: 1.4 }}>{results.headlines.tips[0]}</p>
                 </div>
               </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderAbout = () => {
    if (!results?.about) return null;
    return (
      <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '2rem' }}>
         <div className="panel" style={{ marginBottom: 0 }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '1rem', letterSpacing: '1px' }}>Current Summary</h3>
            <div style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '16px', color: '#fff', fontSize: '0.9rem', whiteSpace: 'pre-wrap', minHeight: '300px', lineHeight: 1.6 }}>
              {results.about.original || "No original summary found in profile."}
            </div>
         </div>
         <div className="panel" style={{ marginBottom: 0, background: 'rgba(108, 99, 255, 0.05)', border: '1px solid rgba(108, 99, 255, 0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '1px', margin: 0 }}>AI Optimized</h3>
              <button className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '11px' }} onClick={() => navigator.clipboard.writeText(results.about.optimized)}>
                <Clipboard size={14} /> Copy
              </button>
            </div>
            <div style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.3)', borderRadius: '16px', color: '#fff', fontSize: '0.95rem', whiteSpace: 'pre-wrap', minHeight: '300px', lineHeight: 1.7, border: '1px solid rgba(255,255,255,0.05)' }}>
              {results.about.optimized}
            </div>
         </div>
      </div>
    );
  };

  const renderExperience = () => {
    return (
      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}><Award color="var(--accent)" /> Professional Impact</h3>
          <button className="btn btn-primary" onClick={handleExpOptimization} disabled={loading}>
            {loading ? <RefreshCw className="animate-spin" size={16} /> : <Zap size={16} />} 
            Optimize All
          </button>
        </div>

        {expResult ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {expResult.map((exp: any, i: number) => (
              <div key={i} className="panel" style={{ padding: 0, overflow: 'hidden', marginBottom: 0 }}>
                <div style={{ padding: '1rem 1.5rem', background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                   <div style={{ fontWeight: 700 }}>
                     <span style={{ color: '#fff' }}>{exp.role}</span>
                     <span style={{ color: 'var(--text-muted)', margin: '0 8px' }}>@</span>
                     <span style={{ color: 'var(--accent)' }}>{exp.company}</span>
                   </div>
                   <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <div style={{ fontSize: '11px', fontWeight: 600 }}>
                        <span style={{ color: 'var(--text-muted)' }}>Score: </span>
                        <span style={{ color: 'var(--accent)' }}>{exp.impact_score}/10</span>
                      </div>
                      {exp.has_metrics && <span style={{ fontSize: '9px', fontWeight: 800, background: 'rgba(0,200,83,0.1)', color: 'var(--success)', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>Metrics</span>}
                   </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
                   <div style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.01)', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5, borderRight: '1px solid var(--border)' }}>
                      <p style={{ fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', marginBottom: '1rem', opacity: 0.3 }}>Original</p>
                      {exp.original}
                   </div>
                   <div style={{ padding: '1.5rem', background: 'rgba(108, 99, 255, 0.03)', fontSize: '0.9rem', color: '#fff', lineHeight: 1.6 }}>
                      <p style={{ fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', marginBottom: '1rem', color: 'var(--accent)' }}>AI Optimized</p>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{exp.optimized}</div>
                   </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="panel" style={{ padding: '4rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <ShieldCheck size={48} color="var(--text-muted)" style={{ opacity: 0.2, marginBottom: '1.5rem' }} />
            <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>Analyze your experiences to add metrics and high-impact action verbs.</p>
            <button className="btn btn-secondary" onClick={handleExpOptimization}>Analyze Experiences</button>
          </div>
        )}
      </div>
    );
  };

  const renderSkills = () => {
    return (
      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}><Zap color="var(--accent)" /> Skills Gap</h3>
          <button className="btn btn-primary" onClick={handleSkillsAnalysis} disabled={loading}>
            {loading ? <RefreshCw className="animate-spin" size={16} /> : <Target size={16} />} 
            Analyze Gap
          </button>
        </div>

        {skillsResult ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
            <div className="panel" style={{ borderTop: '4px solid var(--success)', marginBottom: 0 }}>
               <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success)', fontWeight: 800, fontSize: '0.75rem', textTransform: 'uppercase', marginBottom: '1.5rem' }}>
                 <CheckCircle size={14} /> Keep & Pin
               </h4>
               <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                 {skillsResult.keep_and_pin.map((s: any, i: number) => (
                   <div key={i} style={{ padding: '1rem', background: 'rgba(0,200,83,0.05)', borderRadius: '12px', border: '1px solid rgba(0,200,83,0.1)' }}>
                     <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{s.skill}</div>
                     <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>{s.reason}</div>
                   </div>
                 ))}
               </div>
            </div>

            <div className="panel" style={{ borderTop: '4px solid var(--accent)', marginBottom: 0 }}>
               <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontWeight: 800, fontSize: '0.75rem', textTransform: 'uppercase', marginBottom: '1.5rem' }}>
                 <Plus size={14} /> High Priority Missing
               </h4>
               <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                 {skillsResult.add.filter((s: any) => s.priority === 'high').map((s: any, i: number) => (
                   <div key={i} style={{ padding: '1rem', background: 'rgba(108, 99, 255, 0.05)', borderRadius: '12px', border: '1px solid rgba(108, 99, 255, 0.1)' }}>
                     <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{s.skill}</div>
                     <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>{s.reason}</div>
                   </div>
                 ))}
               </div>
            </div>

            <div className="panel" style={{ borderTop: '4px solid #666', marginBottom: 0, opacity: 0.6 }}>
               <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontWeight: 800, fontSize: '0.75rem', textTransform: 'uppercase', marginBottom: '1.5rem' }}>
                 <AlertCircle size={14} /> Remove / Deprecate
               </h4>
               <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                 {skillsResult.remove.map((s: any, i: number) => (
                   <div key={i} style={{ padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '12px' }}>
                     <div style={{ fontWeight: 700, fontSize: '0.9rem', textDecoration: 'line-through' }}>{s.skill}</div>
                     <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px', fontStyle: 'italic' }}>{s.reason}</div>
                   </div>
                 ))}
               </div>
            </div>
          </div>
        ) : (
          <div className="panel" style={{ padding: '4rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Users size={48} color="var(--text-muted)" style={{ opacity: 0.2, marginBottom: '1.5rem' }} />
            <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>Compare your skills with the market to find gaps and relevant assessments.</p>
            <button className="btn btn-secondary" onClick={handleSkillsAnalysis}>Analyze Skill Gaps</button>
          </div>
        )}
      </div>
    );
  };

  const renderATS = () => {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
         <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}><Target color="var(--accent)" /> ATS Match</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Paste a job description to test your profile.</p>
            <textarea 
              style={{ height: '350px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', color: '#fff', fontSize: '0.9rem', outline: 'none', transition: 'all 0.3s' }}
              placeholder="Paste job description here..."
              value={atsJobDesc}
              onChange={(e) => setAtsJobDesc(e.target.value)}
            />
            <button className="btn btn-primary" style={{ padding: '1rem', width: '100%' }} onClick={handleATSMatch} disabled={loading || !atsJobDesc}>
              {loading ? <RefreshCw className="animate-spin" size={18} /> : <Search size={18} />} 
              Check Compatibility
            </button>
         </div>

         <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {atsMatchResult ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                 <div className="panel" style={{ background: 'rgba(108, 99, 255, 0.05)', border: '1px solid rgba(108, 99, 255, 0.2)', display: 'flex', alignItems: 'center', gap: '2rem', padding: '2rem', marginBottom: 0 }}>
                    <div style={{ position: 'relative', width: '100px', height: '100px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                       <svg width="100" height="100" style={{ transform: 'rotate(-90deg)' }}>
                         <circle cx="50" cy="50" r="45" stroke="rgba(255,255,255,0.05)" strokeWidth="6" fill="transparent" />
                         <circle cx="50" cy="50" r="45" stroke="var(--accent)" strokeWidth="6" fill="transparent" 
                           strokeDasharray={283} strokeDashoffset={283 - (283 * atsMatchResult.match_score) / 100} 
                           strokeLinecap="round"
                         />
                       </svg>
                       <div style={{ position: 'absolute', fontSize: '1.5rem', fontWeight: 900 }}>{atsMatchResult.match_score}%</div>
                    </div>
                    <div>
                       <h4 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '8px' }}>Match Score</h4>
                       <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', lineHeight: 1.5 }}>{atsMatchResult.recommendation}</p>
                    </div>
                 </div>

                 <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                    <div className="panel" style={{ marginBottom: 0 }}>
                       <h5 style={{ color: 'var(--success)', fontWeight: 800, fontSize: '0.75rem', marginBottom: '1rem', textTransform: 'uppercase' }}>Strengths</h5>
                       <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {atsMatchResult.strengths.map((s: string, i: number) => (
                            <li key={i} style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.8)', display: 'flex', gap: '8px' }}>
                              <span style={{ color: 'var(--success)' }}>•</span> {s}
                            </li>
                          ))}
                       </ul>
                    </div>
                    <div className="panel" style={{ marginBottom: 0 }}>
                       <h5 style={{ color: 'var(--accent)', fontWeight: 800, fontSize: '0.75rem', marginBottom: '1rem', textTransform: 'uppercase' }}>Gaps</h5>
                       <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {atsMatchResult.gaps.map((s: string, i: number) => (
                            <li key={i} style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.8)', display: 'flex', gap: '8px' }}>
                              <span style={{ color: 'var(--accent)' }}>•</span> {s}
                            </li>
                          ))}
                       </ul>
                    </div>
                 </div>
              </div>
            ) : (
              <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.3, minHeight: '400px', marginBottom: 0 }}>
                 <Target size={64} color="var(--text-muted)" />
                 <p style={{ marginTop: '1.5rem', fontStyle: 'italic' }}>Awaiting analysis...</p>
              </div>
            )}
         </div>
      </div>
    );
  };

  const renderContextSelector = () => (
    <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
      <label style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 600 }}>Optimize for:</label>
      <select 
        style={{ 
          background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: '8px', 
          color: '#fff', padding: '0.5rem 1rem', outline: 'none' 
        }}
        value={strategyContext ? `${strategyContext.type}-${strategyContext.id}` : ''}
        onChange={(e) => {
          const val = e.target.value;
          if (!val) {
            setStrategyContext(null);
            return;
          }
          const [type, idStr] = val.split('-');
          const id = parseInt(idStr);
          if (type === 'strategy') {
            const s = strategies.find(x => x.id === id);
            if (s) setStrategyContext({ type: 'strategy', id, label: s.title, keywords: s.keywords });
          } else if (type === 'job') {
            const j = savedJobs.find(x => x.id === id);
            if (j) setStrategyContext({ type: 'job', id, label: `${j.job_title} at ${j.company}`, keywords: [j.job_title, j.company] });
          }
        }}
      >
        <option value="">General (No specific target)</option>
        <optgroup label="Search Strategies">
          {strategies.map(s => <option key={`strategy-${s.id}`} value={`strategy-${s.id}`}>{s.title}</option>)}
        </optgroup>
        <optgroup label="Saved Jobs">
          {savedJobs.map(j => <option key={`job-${j.id}`} value={`job-${j.id}`}>{j.job_title} @ {j.company}</option>)}
        </optgroup>
      </select>
      
      {strategyContext && (
         <div style={{ padding: '4px 10px', background: 'rgba(108, 99, 255, 0.1)', border: '1px solid rgba(108, 99, 255, 0.3)', borderRadius: '12px', fontSize: '11px', color: 'var(--accent)', fontWeight: 700 }}>
           Targeting: {strategyContext.label}
         </div>
      )}
    </div>
  );

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.5rem' }}>
             <div style={{ padding: '2px 8px', background: 'rgba(108, 99, 255, 0.1)', border: '1px solid rgba(108, 99, 255, 0.2)', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold', color: 'var(--accent)', letterSpacing: '1px' }}>BETA</div>
             <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>AI Career Suite 2.0</div>
          </div>
          <h1 style={{ fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-1px', color: '#fff', margin: 0 }}>
            LinkedIn Optimizer
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem', fontSize: '1.1rem' }}>Smart optimization for the modern recruiter ecosystem.</p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', background: 'rgba(255, 255, 255, 0.05)', padding: '4px', borderRadius: '12px', border: '1px solid var(--border)' }}>
            <button 
              onClick={() => setLang('pt')} 
              style={{ 
                padding: '0.5rem 1rem', 
                borderRadius: '8px', 
                fontSize: '12px', 
                fontWeight: 'bold', 
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.3s',
                background: lang === 'pt' ? 'var(--accent)' : 'transparent',
                color: lang === 'pt' ? '#fff' : 'var(--text-muted)'
              }}
            >
              PT
            </button>
            <button 
              onClick={() => setLang('en')} 
              style={{ 
                padding: '0.5rem 1rem', 
                borderRadius: '8px', 
                fontSize: '12px', 
                fontWeight: 'bold', 
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.3s',
                background: lang === 'en' ? 'var(--accent)' : 'transparent',
                color: lang === 'en' ? '#fff' : 'var(--text-muted)'
              }}
            >
              EN
            </button>
          </div>
          <button 
            className="btn btn-primary"
            onClick={runFullAnalysis} 
            disabled={loading} 
            style={{ padding: '0.8rem 1.5rem', fontSize: '0.9rem' }}
          >
            {loading ? <RefreshCw className="animate-spin" size={18} /> : <Wand2 size={18} />}
            {loading ? 'Processing...' : 'Run Profile Audit'}
          </button>
        </div>
      </div>
      
      {renderContextSelector()}

      {!results && !loading && (
        <div className="panel" style={{ position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 2rem', textAlign: 'center', minHeight: '400px' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '200px', height: '200px', background: 'rgba(108, 99, 255, 0.05)', borderRadius: '50%', filter: 'blur(60px)', transform: 'translate(-50%, -50%)' }}></div>
          
          <div style={{ position: 'relative', zIndex: 1, maxWidth: '600px', width: '100%' }}>
            <div style={{ width: '80px', height: '80px', background: 'rgba(108, 99, 255, 0.1)', borderRadius: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '2rem', marginLeft: 'auto', marginRight: 'auto', transform: 'rotate(6deg)', border: '1px solid rgba(108, 99, 255, 0.2)' }}>
              <Zap size={40} color="var(--accent)" fill="var(--accent)" />
            </div>
            <h2 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '1rem', color: '#fff' }}>Master Your Professional Brand</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '2.5rem', fontSize: '1rem', lineHeight: 1.6 }}>
              We use advanced LLMs to audit your profile across 8 professional dimensions, ensuring you stand out to both AI filters and human recruiters.
            </p>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '3rem' }}>
               {[
                 { icon: <Search size={18} />, label: 'SEO/ATS Optimization' },
                 { icon: <TrendingUp size={18} />, label: 'SSI Score Growth' },
                 { icon: <MessageSquare size={18} />, label: 'Impactful Copy' }
               ].map((f, i) => (
                 <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '16px', border: '1px solid var(--border)', textAlign: 'left' }}>
                   <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'rgba(108, 99, 255, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                     <span style={{ color: 'var(--accent)' }}>{f.icon}</span>
                   </div>
                   <span style={{ fontSize: '12px', fontWeight: 600, color: '#fff', lineHeight: 1.2 }}>{f.label}</span>
                 </div>
               ))}
            </div>
            
            <button 
              onClick={runFullAnalysis} 
              className="btn btn-primary"
              style={{ padding: '1.2rem 2.5rem', fontSize: '1.1rem', borderRadius: '16px' }}
            >
              Start AI Deep Scan <ChevronRight size={20} />
            </button>
          </div>
        </div>
      )}

      {loading && !results && (
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '6rem 2rem', textAlign: 'center' }}>
          <div style={{ position: 'relative', width: '100px', height: '100px', marginBottom: '2rem' }}>
            <RefreshCw className="animate-spin" size={80} color="var(--accent)" style={{ opacity: 0.2 }} />
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Zap size={40} color="var(--accent)" className="animate-pulse" />
            </div>
          </div>
          <h3 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '0.5rem', fontStyle: 'italic' }}>Analyzing Career Trajectory...</h3>
          <p style={{ color: 'var(--text-muted)' }}>Extracting professional entities and calculating semantic scores.</p>
        </div>
      )}

      {results && (
        <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '2rem', alignItems: 'start' }}>
          <div style={{ position: 'sticky', top: '2rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {[
              { id: 'overview', icon: <Layout size={20} />, label: 'Dashboard' },
              { id: 'headline', icon: <Type size={20} />, label: 'Headline Builder' },
              { id: 'about', icon: <FileText size={20} />, label: 'Bio / Summary' },
              { id: 'experience', icon: <Award size={20} />, label: 'Experiences' },
              { id: 'skills', icon: <Zap size={20} />, label: 'Skills Analysis' },
              { id: 'ats', icon: <Search size={20} />, label: 'ATS Match' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`nav-link ${activeTab === tab.id ? 'active' : ''}`}
                style={{ 
                  width: '100%', 
                  border: 'none', 
                  cursor: 'pointer',
                  justifyContent: 'flex-start',
                  background: activeTab === tab.id ? 'linear-gradient(135deg, rgba(108, 99, 255, 0.2), rgba(108, 99, 255, 0.05))' : 'transparent',
                  color: activeTab === tab.id ? '#fff' : 'var(--text-muted)',
                  borderLeft: activeTab === tab.id ? '3px solid var(--accent)' : '3px solid transparent'
                }}
              >
                {tab.icon}
                <span style={{ fontWeight: 600 }}>{tab.label}</span>
              </button>
            ))}
          </div>

          <div style={{ minHeight: '700px', position: 'relative' }}>
             {loading && results && (
               <div style={{ position: 'absolute', inset: 0, zIndex: 50, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '20px' }}>
                  <RefreshCw className="animate-spin text-accent" size={48} color="var(--accent)" />
               </div>
             )}
             
             {activeTab === 'overview' && renderOverview()}
             {activeTab === 'headline' && renderHeadline()}
             {activeTab === 'about' && renderAbout()}
             {activeTab === 'experience' && renderExperience()}
             {activeTab === 'skills' && renderSkills()}
             {activeTab === 'ats' && renderATS()}
          </div>
        </div>
      )}
    </div>
  );
};

export default LinkedInOptimizer;
