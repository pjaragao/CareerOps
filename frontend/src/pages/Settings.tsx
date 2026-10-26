import React, { useEffect, useState } from 'react';
import { settingsService, AppSettings } from '../services/settingsService';
import { Save, Key, Zap, Shield } from 'lucide-react';

const SettingsPage = () => {
  const [settings, setSettings] = useState<AppSettings>({
    gemini_api_key: '',
    linkedin_email: '',
    scrape_delay: 5,
    max_jobs: 50
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [availableModels, setAvailableModels] = useState<{id: string, name: string}[]>([]);

  useEffect(() => {
    loadSettings();
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

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem' }}>Loading settings...</div>;

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Configurações</h1>
          <p style={{ color: 'var(--text-muted)' }}>Chaves e modelos de IA. Com AI_PROVIDER=agy no .env, a IA roda pelo Antigravity e estes campos não são usados.</p>
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
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>LinkedIn Optimizer</label>
              <select 
                value={settings.ai_model_optimizer || ''}
                onChange={e => setSettings({...settings, ai_model_optimizer: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                <option value="">Default (Fast)</option>
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#aaa' }}>Interview Prep</label>
              <select 
                value={settings.ai_model_interview || ''}
                onChange={e => setSettings({...settings, ai_model_interview: e.target.value})}
                style={{ width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              >
                <option value="">Default (Chat-based)</option>
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
      </div>
    </div>
  );
};

export default SettingsPage;
