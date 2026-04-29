import React, { useState } from 'react';
import { profileService } from '../services/profileService';
import api from '../services/api';
import { Wand2, CheckCircle, AlertCircle, RefreshCw, Layout, Type, ListChecks, FileText } from 'lucide-react';

const LinkedInOptimizer = () => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [lang, setLang] = useState<'pt' | 'en'>('pt');

  const runOptimization = async () => {
    setLoading(true);
    try {
      // Scrape specific language version
      await api.post('/profile/import-linkedin', { lang });
      const profile = await profileService.getProfile();
      
      // Optimization requests based on language
      const promptLang = lang === 'pt' ? 'Portuguese' : 'English';
      const headlineOpt = await profileService.optimizeSection(`LinkedIn Headline in ${promptLang}`, profile.personal?.headline || '');
      const aboutOpt = await profileService.optimizeSection(`LinkedIn About/Summary in ${promptLang}`, profile.experience?.[0]?.description || '');
      
      setResults({
        headline: {
          original: profile.personal?.headline,
          optimized: headlineOpt
        },
        about: {
          original: "Based on your latest experiences...",
          optimized: aboutOpt
        },
        tips: [
          "Use a professional background photo related to your field.",
          "Add your top 5 skills to the headline for better searchability.",
          "Request at least 2 recommendations from former colleagues."
        ]
      });
    } catch (error) {
      alert("Failed to run optimization. Make sure your profile has data.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>LinkedIn Profile Optimizer</h1>
          <p style={{ color: 'var(--text-muted)' }}>Use AI to boost your profile visibility and ranking.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', padding: '4px', borderRadius: '8px' }}>
            <button 
              className={`btn ${lang === 'pt' ? 'btn-primary' : ''}`} 
              style={{ padding: '8px 16px', fontSize: '0.8rem', border: 'none' }}
              onClick={() => setLang('pt')}
            >🇧🇷 PT</button>
            <button 
              className={`btn ${lang === 'en' ? 'btn-primary' : ''}`} 
              style={{ padding: '8px 16px', fontSize: '0.8rem', border: 'none' }}
              onClick={() => setLang('en')}
            >🇺🇸 EN</button>
          </div>
          <button className="btn btn-primary" onClick={runOptimization} disabled={loading}>
            {loading ? <RefreshCw className="animate-spin" size={18} /> : <Wand2 size={18} />}
            {loading ? 'Analyzing...' : 'Run AI Analysis'}
          </button>
        </div>
      </div>

      {!results && !loading && (
        <div className="panel" style={{ textAlign: 'center', padding: '5rem 2rem' }}>
          <Layout size={48} color="var(--accent)" style={{ marginBottom: '1.5rem', opacity: 0.5 }} />
          <h2 style={{ marginBottom: '1rem' }}>Ready to optimize?</h2>
          <p style={{ color: 'var(--text-muted)', maxWidth: '500px', margin: '0 auto 2rem' }}>
            Our AI will analyze your current profile data and suggest high-impact changes for your Headline, About section, and Work Experience.
          </p>
          <button className="btn btn-primary" onClick={runOptimization}>Get Started</button>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '5rem' }}>
          <RefreshCw className="animate-spin" size={48} color="var(--accent)" style={{ marginBottom: '1.5rem' }} />
          <h3>AI is analyzing your professional DNA...</h3>
          <p style={{ color: 'var(--text-muted)' }}>This may take a few seconds.</p>
        </div>
      )}

      {results && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {/* Headline Section */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title"><Type size={20} color="var(--accent)" /> Suggested Headline</h3>
              </div>
              <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', marginBottom: '1rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ORIGINAL</span>
                <p style={{ marginTop: '0.5rem', opacity: 0.7 }}>{results.headline.original || 'No headline found'}</p>
              </div>
              <div style={{ padding: '1.5rem', background: 'rgba(108, 99, 255, 0.1)', border: '1px solid var(--accent)', borderRadius: '12px' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--accent)', fontWeight: 'bold' }}>AI OPTIMIZED</span>
                <p style={{ marginTop: '0.5rem', fontSize: '1.1rem', fontWeight: 600 }}>{results.headline.optimized}</p>
                <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={() => navigator.clipboard.writeText(results.headline.optimized)}>Copy to Clipboard</button>
              </div>
            </div>

            {/* About Section */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title"><FileText size={20} color="var(--accent)" /> About / Summary</h3>
              </div>
              <textarea 
                readOnly 
                value={results.about.optimized}
                style={{ width: '100%', height: '300px', background: 'rgba(108, 99, 255, 0.05)', border: '1px solid var(--accent)', borderRadius: '12px', padding: '1.5rem', lineHeight: 1.6 }}
              />
              <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={() => navigator.clipboard.writeText(results.about.optimized)}>Copy Optimized Summary</button>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title"><ListChecks size={20} color="var(--accent)" /> Quick Wins</h3>
              </div>
              <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {results.tips.map((tip: string, i: number) => (
                  <li key={i} style={{ display: 'flex', gap: '12px', fontSize: '0.9rem' }}>
                    <CheckCircle size={18} color="var(--success)" style={{ flexShrink: 0 }} />
                    {tip}
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel" style={{ background: 'rgba(255, 171, 0, 0.1)', border: '1px solid #ffab00' }}>
              <div style={{ display: 'flex', gap: '12px' }}>
                <AlertCircle color="#ffab00" size={24} style={{ flexShrink: 0 }} />
                <div>
                  <h4 style={{ color: '#ffab00', marginBottom: '0.5rem' }}>Important Note</h4>
                  <p style={{ fontSize: '0.8rem', opacity: 0.9 }}>
                    LinkedIn's algorithm favors profiles with high engagement. After updating your text, try to interact with 5 relevant posts in your feed.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LinkedInOptimizer;
