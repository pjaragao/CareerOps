import React, { useEffect, useState } from 'react';
import { Save, Wand2, Eye, RotateCcw, Cpu } from 'lucide-react';
import api from '../services/api';

interface StyleEntry {
  preset: string;
  tone?: string;
  formality?: string;
  length: string;
  emojis: string;
  hashtags: number;
  custom: string;
}
interface Preset { label: string; tone: string; formality: string }
interface SettingsData {
  provider: string;
  kinds: Record<string, string>;
  presets: Record<string, Preset>;
  lengths: Record<string, Record<string, [number, number]>>;
  style: Record<string, StyleEntry>;
  default_style: Record<string, StyleEntry>;
  tasks: Record<string, string>;
  models: Record<string, string>;
  default_models: Record<string, string>;
  available_models: string[];
}

const field: React.CSSProperties = {
  width: '100%', padding: '0.55rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
  borderRadius: '8px', color: '#fff', fontFamily: 'inherit', fontSize: '0.88rem',
};
const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.82rem' };
const lbl: React.CSSProperties = { display: 'block', ...muted, marginBottom: 4 };
const errMsg = (e: unknown) => (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
  || (e as { message?: string })?.message || 'Erro';

const KindCard = ({ kind, label, data, value, onChange }: {
  kind: string; label: string; data: SettingsData; value: StyleEntry; onChange: (v: StyleEntry) => void;
}) => {
  const [preview, setPreview] = useState<string | null>(null);
  const [instruction, setInstruction] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  const [explanation, setExplanation] = useState('');
  const preset = data.presets[value.preset];
  const set = (k: keyof StyleEntry, v: string | number) => onChange({ ...value, [k]: v });
  const range = (len: string) => { const r = data.lengths[kind]?.[len]; return r ? `${r[0]}–${r[1]} car.` : ''; };

  const adjust = async () => {
    if (!instruction.trim()) return;
    setAdjusting(true);
    try {
      const r = await api.post<{ style: StyleEntry; explanation: string }>('/ai-settings/style/adjust', { kind, instruction, current: value });
      onChange(r.data.style);
      setExplanation(r.data.explanation ? `${r.data.explanation} (ainda não salvo)` : 'Ajuste aplicado ao formulário (ainda não salvo).');
      setInstruction('');
    } catch (e) { alert(errMsg(e)); } finally { setAdjusting(false); }
  };

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>{label}</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-secondary" style={{ padding: '4px 10px' }} title="Voltar ao padrão"
            onClick={() => onChange({ ...data.default_style[kind] })}><RotateCcw size={14} /></button>
          <button className="btn btn-secondary" style={{ padding: '4px 10px' }}
            onClick={async () => setPreview(preview ? null : (await api.get<{ text: string }>(`/ai-settings/preview/${kind}`)).data.text)}>
            <Eye size={14} /> {preview ? 'Fechar' : 'Ver o que a IA recebe'}
          </button>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.7rem' }}>
        <div>
          <span style={lbl}>Predefinição</span>
          <select value={value.preset} onChange={e => set('preset', e.target.value)} style={field}>
            {Object.entries(data.presets).map(([id, p]) => <option key={id} value={id} style={{ color: '#000' }}>{p.label}</option>)}
          </select>
        </div>
        <div>
          <span style={lbl}>Tamanho</span>
          <select value={value.length} onChange={e => set('length', e.target.value)} style={field}>
            {['short', 'medium', 'long'].map(l => <option key={l} value={l} style={{ color: '#000' }}>
              {{ short: 'Curto', medium: 'Médio', long: 'Longo' }[l]} ({range(l)})</option>)}
          </select>
        </div>
        <div>
          <span style={lbl}>Formalidade</span>
          <select value={value.formality || ''} onChange={e => set('formality', e.target.value)} style={field}>
            <option value="" style={{ color: '#000' }}>Da predefinição ({preset?.formality})</option>
            {['formal', 'neutral', 'casual'].map(f => <option key={f} value={f} style={{ color: '#000' }}>
              {{ formal: 'Formal', neutral: 'Neutra', casual: 'Informal' }[f]}</option>)}
          </select>
        </div>
        <div>
          <span style={lbl}>Emojis</span>
          <select value={value.emojis} onChange={e => set('emojis', e.target.value)} style={field}>
            <option value="none" style={{ color: '#000' }}>Nenhum</option>
            <option value="minimal" style={{ color: '#000' }}>No máximo um</option>
            <option value="some" style={{ color: '#000' }}>Alguns</option>
          </select>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: kind === 'post' ? '3fr 1fr' : '1fr', gap: '0.7rem' }}>
        <div>
          <span style={lbl}>Tom (vazio = o da predefinição)</span>
          <input value={value.tone || ''} onChange={e => set('tone', e.target.value)} placeholder={preset?.tone} style={field} />
        </div>
        {kind === 'post' && (
          <div>
            <span style={lbl}>Hashtags</span>
            <input type="number" min={0} max={5} value={value.hashtags} onChange={e => set('hashtags', Number(e.target.value))} style={field} />
          </div>
        )}
      </div>
      <div>
        <span style={lbl}>Instruções extras</span>
        <textarea value={value.custom} onChange={e => set('custom', e.target.value)} rows={2} style={{ ...field, resize: 'vertical' }}
          placeholder="Ex.: sempre traga um exemplo de obra ou de orçamento; evite começar com pergunta." />
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input value={instruction} onChange={e => setInstruction(e.target.value)} onKeyDown={e => e.key === 'Enter' && adjust()}
          placeholder="Ajustar com IA: descreva a mudança (ex.: mais curto e mais técnico, menos formal)" style={field} />
        <button className="btn btn-primary" disabled={adjusting} onClick={adjust} style={{ whiteSpace: 'nowrap' }}>
          <Wand2 size={15} /> {adjusting ? 'Ajustando…' : 'Ajustar com IA'}
        </button>
      </div>
      {explanation && <div style={{ ...muted, color: '#ffb020' }}>{explanation}</div>}
      {preview && <pre style={{ whiteSpace: 'pre-wrap', ...muted, background: 'rgba(0,0,0,0.25)', padding: '0.7rem', borderRadius: 8 }}>{preview}</pre>}
    </div>
  );
};

const AISettings = () => {
  const [data, setData] = useState<SettingsData | null>(null);
  const [style, setStyle] = useState<Record<string, StyleEntry>>({});
  const [models, setModels] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api.get<SettingsData>('/ai-settings').then(r => { setData(r.data); setStyle(r.data.style); setModels(r.data.models); });
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/ai-settings/style', style);
      await api.put('/ai-settings/models', models);
      alert('Estilo e modelos salvos. Valem para a próxima geração.');
    } catch (e) { alert(errMsg(e)); } finally { setSaving(false); }
  };

  if (!data) return <p style={muted}>Carregando…</p>;
  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.4rem' }}>Estilo e modelos da IA</h1>
          <p style={muted}>Vale para tudo que a IA escreve: posts, comentários, convites, Easy Apply, CV, carta e mensagens.
            O idioma segue o conteúdo (post em inglês → comentário em inglês; mercado Brasil → português).</p>
        </div>
        <button className="btn btn-primary" onClick={save} disabled={saving}><Save size={16} /> {saving ? 'Salvando…' : 'Salvar'}</button>
      </div>

      {Object.entries(data.kinds).map(([kind, label]) => style[kind] && (
        <KindCard key={kind} kind={kind} label={label} data={data} value={style[kind]}
          onChange={v => setStyle(prev => ({ ...prev, [kind]: v }))} />
      ))}

      <div className="panel">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.6rem' }}><Cpu size={18} /> Modelo por tarefa</h3>
        {data.provider !== 'agy' && (
          <p style={{ ...muted, marginBottom: '0.6rem' }}>A escolha por tarefa vale com AI_PROVIDER=agy (Antigravity). Provedor atual: {data.provider}.</p>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem' }}>
          {Object.entries(data.tasks).map(([task, label]) => (
            <div key={task}>
              <span style={lbl}>{label}</span>
              <select value={models[task] || ''} onChange={e => setModels(prev => ({ ...prev, [task]: e.target.value }))} style={field}>
                {[...new Set([models[task], ...data.available_models])].filter(Boolean).map(m => (
                  <option key={m} value={m} style={{ color: '#000' }}>{m}{m === data.default_models[task] ? ' (padrão)' : ''}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AISettings;
