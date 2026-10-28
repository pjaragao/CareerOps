import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { Link2, Wand2, RefreshCw, ClipboardPaste, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { jobService, JobFromLink } from '../services/jobService';

// "Nova vaga": paste the link and everything is filled in (like the extension's universal import); the pasted text of
// the ad when the site can't be read. You review before saving; saving runs the eligibility check, CV and cover letter.
const STATUS_LABEL: Record<string, string> = {
  new: 'Avaliar', scraped: 'Captada', applied: 'Candidatado', interviewing: 'Entrevista', offer: 'Proposta', rejected: 'Recusada', archived: 'Arquivada',
};
const EMPTY = { job_title: '', company: '', location: '', url: '', description: '' };
const field: React.CSSProperties = { padding: '0.55rem 0.75rem', fontSize: '0.84rem', borderRadius: 9 };
const label: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.68rem', fontWeight: 800, letterSpacing: '.06em', color: 'var(--text-muted)' };
const errorText = (e: unknown) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (e as Error)?.message || 'erro desconhecido';

const NewJobModal = ({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) => {
  const [job, setJob] = useState(EMPTY);
  const [read, setRead] = useState<JobFromLink | null>(null);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState('');
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasted, setPasted] = useState('');
  const [saving, setSaving] = useState(false);
  const [readUrl, setReadUrl] = useState('');   // the link the fields were filled from

  const fill = async (url: string, text?: string) => {
    if (!url.trim() && !text?.trim()) return;
    setReading(true); setError(''); setReadUrl(url.trim());
    try {
      const r = await jobService.fromLink(url.trim(), text);
      setRead(r);
      setJob({ job_title: r.title, company: r.company, location: r.location, url: r.url || url.trim(), description: r.description });
      setPasteOpen(false);
    } catch (e) {
      setError(errorText(e));
      if (!text) setPasteOpen(true);
    } finally { setReading(false); }
  };
  // a pasted link is read right away
  const onUrlPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const v = e.clipboardData.getData('text').trim();
    if (/^(https?:\/\/|www\.)\S+$/i.test(v)) { e.preventDefault(); setJob(j => ({ ...j, url: v })); fill(v); }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true);
    try { await jobService.addManualJob(job); onSaved(); }
    catch (err) { setError(errorText(err)); }
    finally { setSaving(false); }
  };

  const facts = read ? [read.employment_type, read.seniority, read.workplace, read.salary, read.posted && `publicada em ${String(read.posted).slice(0, 10)}`].filter(Boolean) : [];
  const filled = !!(job.job_title || job.description);

  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(5,5,10,.75)', zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, backdropFilter: 'blur(8px)' }}>
      <div className="panel" onClick={e => e.stopPropagation()} style={{ width: '100%', maxWidth: 760, maxHeight: '92vh', marginBottom: 0, padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '1.1rem 1.4rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <h2 style={{ fontSize: '1.15rem', margin: 0, marginRight: 'auto' }}>Nova vaga</h2>
          <button onClick={onClose} className="btn btn-secondary" style={{ padding: 6, borderRadius: '50%' }} title="Fechar"><X size={16} /></button>
        </div>

        <form onSubmit={save} style={{ padding: '1.1rem 1.4rem', display: 'flex', flexDirection: 'column', gap: '0.85rem', overflowY: 'auto' }}>
          {/* Link first: it fills everything else */}
          <div style={{ background: 'rgba(108,99,255,.06)', border: '1px solid rgba(108,99,255,.25)', borderRadius: 12, padding: '0.85rem' }}>
            <label style={label}>LINK DA VAGA
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <Link2 size={15} style={{ position: 'absolute', left: 11, top: 11, color: 'var(--text-muted)' }} />
                  <input autoFocus value={job.url} onChange={e => setJob({ ...job, url: e.target.value })} onPaste={onUrlPaste}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); fill(job.url); } }}
                    placeholder="Cole o link: LinkedIn, We Work Remotely, Greenhouse, Lever, Workday, site da empresa…" style={{ ...field, paddingLeft: 34 }} />
                </div>
                <button type="button" className="btn btn-primary" onClick={() => fill(job.url)} disabled={reading || !job.url.trim()} style={{ height: 38, padding: '0 14px', fontSize: '0.8rem', fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {reading ? <RefreshCw size={15} className="animate-spin" /> : <Wand2 size={15} />} {read && readUrl === job.url.trim() ? 'Ler de novo' : 'Preencher'}
                </button>
              </div>
            </label>
            {reading && <p style={{ margin: '8px 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>Lendo a vaga… sites que só abrem com JavaScript levam até 30 s.</p>}
            {error && !reading && (
              <p style={{ margin: '8px 0 0', fontSize: '0.8rem', color: '#ff8a8a', display: 'flex', gap: 6 }}><AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} /> Não deu: {error}</p>
            )}
            {read && !reading && !error && (
              <div style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                <CheckCircle2 size={14} style={{ color: '#00c853' }} /> Preenchido a partir de: {read.source}. Revise antes de salvar.
                {facts.map(f => <span key={f} style={{ padding: '1px 8px', borderRadius: 999, background: 'rgba(255,255,255,.06)', color: '#d4d4dc' }}>{f}</span>)}
              </div>
            )}
            {read?.existing && !reading && (
              <p style={{ margin: '8px 0 0', fontSize: '0.8rem', color: '#f5c542', display: 'flex', gap: 6 }}>
                <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                Esta vaga já está no CareerOps ({read.existing.job_title} · {STATUS_LABEL[read.existing.status] || read.existing.status}). Salvar atualiza os dados dela.
              </p>
            )}
            <button type="button" onClick={() => setPasteOpen(o => !o)} style={{ marginTop: 8, background: 'none', border: 'none', padding: 0, color: 'var(--accent-light)', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
              <ClipboardPaste size={13} /> {pasteOpen ? 'Fechar' : 'Sem link, ou o site não abre? Cole o texto da vaga'}
            </button>
            {pasteOpen && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <textarea value={pasted} onChange={e => setPasted(e.target.value)} placeholder="Selecione tudo na página da vaga (Ctrl+A), copie e cole aqui"
                  style={{ ...field, height: 120, resize: 'vertical' }} />
                <button type="button" className="btn btn-secondary" onClick={() => fill(job.url, pasted)} disabled={reading || pasted.trim().length < 80}
                  style={{ alignSelf: 'flex-end', height: 32, padding: '0 12px', fontSize: '0.78rem', fontWeight: 700 }}>
                  <Wand2 size={14} /> Preencher pelo texto
                </button>
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.7rem', opacity: reading ? 0.5 : 1 }}>
            <label style={label}>CARGO<input required value={job.job_title} onChange={e => setJob({ ...job, job_title: e.target.value })} style={field} /></label>
            <label style={label}>EMPRESA<input required value={job.company} onChange={e => setJob({ ...job, company: e.target.value })} style={field} /></label>
            <label style={label}>LOCAL<input value={job.location} onChange={e => setJob({ ...job, location: e.target.value })} placeholder="Ex.: Remote (LATAM)" style={field} /></label>
          </div>
          <label style={{ ...label, opacity: reading ? 0.5 : 1 }}>DESCRIÇÃO
            <textarea required value={job.description} onChange={e => setJob({ ...job, description: e.target.value })}
              placeholder="Preenchida pelo link; ou escreva/cole aqui" style={{ ...field, height: filled ? 260 : 110, resize: 'vertical', lineHeight: 1.5 }} />
          </label>
          <p style={{ margin: 0, fontSize: '0.74rem', color: 'var(--text-muted)' }}>Ao salvar, a vaga passa pela checagem de residência/visto e ganha CV e carta automaticamente.</p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving || reading}>{saving ? 'Salvando…' : read?.existing ? 'Atualizar vaga' : 'Salvar vaga'}</button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
};

export default NewJobModal;
