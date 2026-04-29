import React, { useEffect, useState } from 'react';
import { settingsService, AppSettings } from '../services/settingsService';
import { authService } from '../services/authService';
import { Settings as SettingsIcon, Save, Key, Mail, Shield, Zap, Globe, LogIn } from 'lucide-react';

const SettingsPage = () => {
  const [settings, setSettings] = useState<AppSettings>({
    gemini_api_key: '',
    linkedin_email: '',
    scrape_delay: 5,
    max_jobs: 50
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<{ exists: boolean, last_updated: number } | null>(null);
  const [availableModels, setAvailableModels] = useState<{id: string, name: string}[]>([]);

  useEffect(() => {
    loadSettings();
    loadSessionStatus();
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      const models = await settingsService.getAvailableModels();
      setAvailableModels(models);
    } catch (e) {
      console.error("Failed to load models");
    }
  };

  const loadSessionStatus = async () => {
    try {
      const status = await settingsService.getSessionStatus();
      setSessionStatus(status);
    } catch (e) {
      console.error("Failed to load session status");
    }
  };

  const loadSettings = async () => {
    try {
      const data = await settingsService.getSettings();
      setSettings(data);
    } catch (error) {
      console.error("Failed to load settings", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await settingsService.updateSettings(settings);
      alert("Settings saved successfully!");
    } catch (error) {
      console.error(error);
      alert("Failed to save settings. Check if the server is running.");
    } finally {
      setSaving(false);
    }
  };

  const sessionRef = React.useRef<HTMLTextAreaElement>(null);

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem' }}>Loading settings...</div>;

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>System Settings</h1>
          <p style={{ color: 'var(--text-muted)' }}>Configure your API keys and scraper behavior.</p>
        </div>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          <Save size={18} /> {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '2rem' }}>
        {/* AI Configuration */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Key size={20} color="var(--accent)" /> AI Credentials</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Google Gemini API Key</label>
              <input 
                type="password" 
                value={settings.gemini_api_key}
                onChange={e => setSettings({...settings, gemini_api_key: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
                placeholder="AIza..."
              />
            </div>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.2rem' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>OpenAI compatible Base URL (Optional)</label>
              <input 
                type="text" 
                value={settings.openai_base_url || ''}
                onChange={e => setSettings({...settings, openai_base_url: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>OpenAI compatible API Key</label>
              <input 
                type="password" 
                value={settings.openai_api_key || ''}
                onChange={e => setSettings({...settings, openai_api_key: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
                placeholder="sk-..."
              />
            </div>
          </div>
        </div>

        {/* Model Selection */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Zap size={20} color="var(--accent)" /> Model Selection</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.2rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Resume Tailoring</label>
              <select 
                value={settings.ai_model_resume}
                onChange={e => setSettings({...settings, ai_model_resume: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Cover Letter</label>
              <select 
                value={settings.ai_model_cover}
                onChange={e => setSettings({...settings, ai_model_cover: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Career Chat</label>
              <select 
                value={settings.ai_model_chat}
                onChange={e => setSettings({...settings, ai_model_chat: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>LinkedIn Profile Import</label>
              <select 
                value={settings.ai_model_import || ''}
                onChange={e => setSettings({...settings, ai_model_import: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                <option value="">Default (Fast & Stable)</option>
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Outreach (DM/Email)</label>
              <select 
                value={settings.ai_model_outreach}
                onChange={e => setSettings({...settings, ai_model_outreach: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.2rem', marginTop: '0.5rem' }}>
                <Shield size={14} style={{ verticalAlign: 'middle', marginRight: '5px' }} /> 
                Fallback Model (Used if primary model fails or doesn't support JSON)
              </label>
              <select 
                value={settings.ai_model_fallback || 'gemini-1.5-flash'}
                onChange={e => setSettings({...settings, ai_model_fallback: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* LinkedIn Configuration */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Mail size={20} color="var(--accent)" /> LinkedIn Account</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>Account Email</label>
              <input 
                type="email" 
                value={settings.linkedin_email}
                onChange={e => setSettings({...settings, linkedin_email: e.target.value})}
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button className="btn btn-secondary" onClick={async () => {
                try {
                  const res = await authService.startLogin();
                  if (res.error) {
                    alert(`Login Error: ${res.error}`);
                  } else {
                    alert("Browser opened! Log in to LinkedIn on your desktop and then click 'Save & Finish Session'.");
                  }
                } catch (e: any) {
                  const msg = e.response?.data?.detail || e.message || "Unknown error";
                  alert(`Failed to connect to backend: ${msg}`);
                }
              }}>
                <LogIn size={18} /> Start Login
              </button>
              <button className="btn btn-primary" onClick={async () => {
                try {
                  const res = await authService.finishLogin();
                  if (res.error) {
                    alert(`Save Error: ${res.error}\n\nThis usually happens if the login browser didn't start correctly. Use 'Manual Session Import' below instead.`);
                  } else {
                    alert(res.message);
                    loadSessionStatus();
                  }
                } catch (e: any) {
                  alert("Failed to save session. Connection error.");
                }
              }}>
                <Save size={18} /> Save & Finish Session
              </button>
            </div>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem', marginTop: '1.5rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input 
                    type="file" 
                    accept=".json"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = async (event) => {
                        try {
                          const json = JSON.parse(event.target?.result as string);
                          const res = await authService.uploadSession(json);
                          alert(res.message || "Session uploaded successfully!");
                          loadSessionStatus();
                          e.target.value = "";
                        } catch (err: any) {
                          alert(`Error reading file: ${err.message}`);
                        }
                      };
                      reader.readAsText(file);
                    }}
                    style={{ fontSize: '0.85rem' }}
                  />
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>or paste below</span>
                </div>
                
                <textarea 
                  ref={sessionRef}
                  placeholder='Paste your storageState.json content here...'
                  style={{ width: '100%', height: '100px', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff', fontSize: '0.8rem', fontFamily: 'monospace' }}
                />
                <button 
                  className="btn btn-primary" 
                  style={{ width: 'fit-content' }}
                  onClick={async () => {
                    const value = sessionRef.current?.value;
                    if (!value) return alert("Please paste the JSON first.");
                    
                    try {
                      const json = JSON.parse(value.trim());
                      const res = await authService.uploadSession(json);
                      alert(res.message || "Session uploaded successfully!");
                      loadSessionStatus();
                      if (sessionRef.current) sessionRef.current.value = "";
                    } catch (err: any) {
                      alert(`JSON Error: ${err.message}. Please make sure you copied the entire content from the file.`);
                      console.error("Parse error:", err);
                    }
                  }}
                >
                  <Save size={18} /> Import Session
                </button>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '5px' }}>
                If "Start Login" fails (e.g. no display), paste your LinkedIn session JSON here and click Import.
              </p>
            </div>
          </div>
        </div>

        {/* Scraper Configuration */}
        <div className="panel" style={{ gridColumn: 'span 1' }}>
          <div className="panel-header">
            <h3 className="panel-title"><Zap size={20} color="var(--accent)" /> Scraper Behavior</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>Delay between requests (s)</label>
              <input 
                type="number" 
                value={settings.scrape_delay}
                onChange={e => setSettings({...settings, scrape_delay: parseInt(e.target.value)})}
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>Max jobs per search</label>
              <input 
                type="number" 
                value={settings.max_jobs}
                onChange={e => setSettings({...settings, max_jobs: parseInt(e.target.value)})}
                style={{ width: '100%', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '10px', color: '#fff' }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
