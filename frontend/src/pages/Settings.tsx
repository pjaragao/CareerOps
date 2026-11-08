import React, { useCallback, useEffect, useState } from 'react';
import { settingsService, AppSettings } from '../services/settingsService';
import api, { getAccessToken, setAccessToken } from '../services/api';
import { Save, Key, Zap, Shield, Lock, Bookmark } from 'lucide-react';
import { automationService, SavedImportSettings, SavedImportRun } from '../services/automationService';

const field = { padding: '0.5rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' };
const hours = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i);
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

// Your saved jobs on LinkedIn, read by the server browser: when (hours of the day and of the night) and the last reads
const SavedImportPanel = () => {
  const [value, setValue] = useState<SavedImportSettings | null>(null);
  const [runs, setRuns] = useState<SavedImportRun[]>([]);
  const [note, setNote] = useState('');
  const load = () => automationService.savedImport().then((r) => { setValue(r.settings); setRuns(r.runs); }).catch(() => setNote('Precisa do token de aprovador (acima).'));
  useEffect(() => { load(); }, []);
  if (!value) return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{note || 'Carregando…'}</p>;
  const set = (patch: Partial<SavedImportSettings>) => { setValue({ ...value, ...patch }); setNote(''); };
  const save = async () => {
    try { setValue(await automationService.setSavedImport(value)); setNote('✓ Salvo'); } catch { setNote('Não foi possível salvar'); }
  };
  const runNow = async () => {
    try {
      const r = await automationService.runSavedImport();
      setNote(r.mode === 'off' ? 'Na fila, mas a automação está desligada (Automação → Buscas e limites)' : r.already ? `Já estava na fila (#${r.id}): vai agora` : `Na fila (#${r.id}): começa em instantes`);
      load();
    } catch { setNote('Não foi possível pedir agora'); }
  };
  const result = (r: SavedImportRun) => {
    if (r.status === 'done') {
      const n = (r.result.added || 0) + (r.result.promoted || 0);
      return `${r.result.cards ?? 0} na lista · ${n} nova(s)`;
    }
    return r.error_text || r.status;
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', fontSize: '0.9rem' }}>
      <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input type="checkbox" checked={value.enabled} onChange={(e) => set({ enabled: e.target.checked })} /> Importar automaticamente
      </label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
        Das <select style={field} value={value.day_start} onChange={(e) => set({ day_start: +e.target.value })}>{hours(0, 23).map((h) => <option key={h} value={h}>{h}h</option>)}</select>
        às <select style={field} value={value.day_end} onChange={(e) => set({ day_end: +e.target.value })}>{hours(1, 24).map((h) => <option key={h} value={h}>{h}h</option>)}</select>
        a cada <select style={field} value={value.day_every} onChange={(e) => set({ day_every: +e.target.value })}>{hours(1, 12).map((h) => <option key={h} value={h}>{h}h</option>)}</select>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
        Fora desse horário <select style={field} value={value.night_every} onChange={(e) => set({ night_every: +e.target.value })}>
          <option value={0}>não importar</option>{hours(1, 12).map((h) => <option key={h} value={h}>a cada {h}h</option>)}
        </select>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={save}>Salvar horários</button>
        <button className="btn" onClick={runNow}>Importar agora</button>
      </div>
      {note && <p style={{ fontSize: '0.85rem', margin: 0 }}>{note}</p>}
      <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: 0 }}>
        Só lê a lista e o anúncio de cada vaga nova; elas entram em Vagas como novas e vão para a lista de aprovação. Vale também
        fora da janela das outras ações. No WhatsApp: “importar vagas salvas”.
      </p>
      {runs.length > 0 && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {runs.map((r) => <div key={r.id}>#{r.id} · {when(r.finished_at || r.created_at)}{r.run_now ? ' · pedido' : ''} · {result(r)}</div>)}
        </div>
      )}
    </div>
  );
};

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
  const [token, setToken] = useState(getAccessToken);
  const [tokenStatus, setTokenStatus] = useState('');

  const loadModels = useCallback(async () => {
    try {
      setAvailableModels(await settingsService.getAvailableModels());
    } catch {
      console.error("Failed to load models");
    }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      setSettings(await settingsService.getSettings());
    } catch (error) {
      console.error("Failed to load settings", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(() => { loadSettings(); loadModels(); }, 0);
    return () => clearTimeout(first);
  }, [loadSettings, loadModels]);

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

  const handleToken = async () => {
    setAccessToken(token.trim());
    try {
      const { data } = await api.get<{ role: string }>('/automation/status');
      setTokenStatus(data.role === 'approver' ? '✓ Token de aprovador válido' : 'Este token não é o de aprovador');
    } catch {
      setTokenStatus('Token recusado pelo servidor');
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(400px, 100%), 1fr))', gap: '2rem' }}>
        {/* Access */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Lock size={20} color="var(--accent)" /> Acesso</h3>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.8rem' }}>
            Aprovar e publicar exigem o token de aprovador (<code>CAREEROPS_APPROVER_TOKEN</code> no servidor). Fica só neste navegador.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="password"
              value={token}
              onChange={e => { setToken(e.target.value); setTokenStatus(''); }}
              style={{ flex: 1, minWidth: 0, padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              placeholder="Token de aprovador"
            />
            <button className="btn btn-primary" onClick={handleToken}>Salvar e testar</button>
          </div>
          {tokenStatus && <p style={{ fontSize: '0.85rem', marginTop: '0.6rem' }}>{tokenStatus}</p>}
        </div>

        {/* Saved jobs */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title"><Bookmark size={20} color="var(--accent)" /> Vagas salvas no LinkedIn</h3>
          </div>
          <SavedImportPanel />
        </div>

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
