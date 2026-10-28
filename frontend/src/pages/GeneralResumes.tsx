import React, { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Plus, Search, X, ArrowUpDown, Download, Trash2, Copy, Gauge, ListChecks, FileText, Save, Wand2, RefreshCw,
  CheckCircle2, AlertTriangle, Info, Files, Check,
} from 'lucide-react';
import { generalResumeService, errorText, GeneralResume, ResumeFields, ResumeReview, FormSuggestions } from '../services/generalResumeService';
import { profileService } from '../services/profileService';

// General CVs: one per kind of job-board sign-up (not tied to a job). Same list look as Vagas.
type SortKey = 'updated' | 'score' | 'title';
const SORTS: { id: SortKey; label: string }[] = [
  { id: 'updated', label: 'Atualizados por último' }, { id: 'score', label: 'Melhor nota ATS' }, { id: 'title', label: 'Nome A–Z' },
];
const LANGS: Record<string, string> = { en: 'Inglês', pt: 'Português' };
type Tab = 'content' | 'review' | 'form';

const time = (d?: string | null) => (d ? new Date(d).getTime() : 0);
const ago = (d?: string | null) => {
  if (!d) return '';
  const days = Math.floor((Date.now() - time(d)) / 86400000);
  if (days <= 0) return 'hoje';
  if (days === 1) return 'ontem';
  if (days < 30) return `${days} d`;
  return new Date(d).toLocaleDateString();
};
const scoreColor = (s: number) => (s >= 80 ? '#00c853' : s >= 60 ? '#f5c542' : '#ff5c5c');
const SEVERITY = { high: { label: 'Alta', color: '#ff5c5c' }, medium: { label: 'Média', color: '#f5c542' }, low: { label: 'Baixa', color: '#8b85ff' } } as const;

const css = `
.gr-chip{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);font-size:.76rem;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .15s}
.gr-chip:hover{border-color:rgba(255,255,255,.18);color:#fff}
.gr-chip.on{background:rgba(108,99,255,.16);border-color:rgba(108,99,255,.55);color:#fff}
.gr-chip .n{font-size:.7rem;opacity:.7}
.gr-row{border-bottom:1px solid var(--border);cursor:pointer;transition:background .12s}
.gr-row:hover{background:rgba(255,255,255,.025)}
.gr-row .gr-acts{opacity:.35;transition:opacity .15s}
.gr-row:hover .gr-acts{opacity:1}
.gr-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);cursor:pointer;transition:all .15s}
.gr-icon:hover{color:#fff;border-color:rgba(255,255,255,.2);background:rgba(255,255,255,.07)}
.gr-icon.primary{background:linear-gradient(135deg,var(--accent),var(--accent-light));color:#fff;border-color:transparent}
.gr-icon.danger:hover{color:#ff5c5c;border-color:rgba(255,92,92,.4)}
.gr-icon:disabled{opacity:.5;cursor:default}
.gr-th{padding:.7rem 1rem;text-align:left;color:var(--text-muted);font-size:.68rem;font-weight:700;letter-spacing:.06em;white-space:nowrap}
.gr-td{padding:.75rem 1rem;vertical-align:middle}
.gr-select{height:32px;padding:0 30px 0 10px;width:auto;font-size:.76rem;border-radius:9px;appearance:none;-webkit-appearance:none;cursor:pointer;background:rgba(255,255,255,.04) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23a0a0c0' fill='none' stroke-width='1.5'/%3E%3C/svg%3E") no-repeat right 10px center}
.gr-score{display:inline-flex;align-items:center;justify-content:center;min-width:44px;height:26px;padding:0 9px;border-radius:999px;font-size:.74rem;font-weight:800}
.gr-card{border:1px solid var(--border);background:rgba(255,255,255,.02);border-radius:12px;padding:.85rem 1rem}
.gr-label{font-size:.68rem;font-weight:800;letter-spacing:.06em;color:var(--text-muted);text-transform:uppercase}
.gr-field{padding:.5rem .7rem;font-size:.82rem;border-radius:8px;background:#1a1a25;color:#fff;border:1px solid var(--border);width:100%}
.gr-kw{display:inline-flex;align-items:center;height:24px;padding:0 9px;border-radius:999px;font-size:.72rem;font-weight:600;margin:0 6px 6px 0}
.gr-copy{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:7px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);font-size:.7rem;font-weight:700;cursor:pointer}
.gr-copy:hover{color:#fff;border-color:rgba(255,255,255,.2)}
@media (max-width: 760px){.gr-hide-sm{display:none}}
`;

const ScorePill = ({ resume }: { resume: GeneralResume }) => {
  const s = resume.review?.score;
  if (s === undefined || s === null) return <span style={{ color: 'rgba(255,255,255,.25)', fontSize: '0.74rem', fontWeight: 700 }}>—</span>;
  const c = scoreColor(s);
  return <span className="gr-score" title={`Analisado ${ago(resume.review_at)}`} style={{ background: `${c}1f`, color: c }}>{s}</span>;
};

const CopyButton = ({ text }: { text: string }) => {
  const [done, setDone] = useState(false);
  return (
    <button className="gr-copy" title="Copiar" onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1200); }}>
      {done ? <Check size={11} /> : <Copy size={11} />} {done ? 'Copiado' : 'Copiar'}
    </button>
  );
};

const Modal = ({ children, onClose, maxWidth = 1100, height }: { children: React.ReactNode; onClose: () => void; maxWidth?: number; height?: string }) => {
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, [onClose]);
  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(5,5,10,.78)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(10px)', padding: 20 }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        width: '100%', maxWidth, height, maxHeight: '92vh', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden', marginBottom: 0,
        border: '1px solid rgba(108,99,255,.3)', boxShadow: '0 20px 50px rgba(0,0,0,.5)', background: 'var(--bg-card)',
      }}>{children}</div>
    </div>,
    document.body,
  );
};

// ── ATS review tab ──────────────────────────────────────────────────────────────────────────────────────────────
const ReviewView = ({ review }: { review: ResumeReview }) => {
  const c = scoreColor(review.score);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
      <div className="gr-card" style={{ display: 'flex', gap: '1.2rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ width: 92, height: 92, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: `conic-gradient(${c} ${review.score * 3.6}deg, rgba(255,255,255,.07) 0)` }}>
          <div style={{ width: 74, height: 74, borderRadius: '50%', background: '#14141f', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: '1.6rem', fontWeight: 800, color: c, lineHeight: 1 }}>{review.score}</span>
            <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>de 100</span>
          </div>
        </div>
        <div style={{ flex: '1 1 300px', minWidth: 0 }}>
          <div className="gr-label">Nota ATS</div>
          <p style={{ color: '#e8e8ee', fontSize: '0.88rem', margin: '4px 0 6px', lineHeight: 1.5 }}>{review.verdict}</p>
          {review.recruiter_view && <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: 0, lineHeight: 1.5 }}><b style={{ color: '#cfcfe0' }}>Leitura de 6 segundos:</b> {review.recruiter_view}</p>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.7rem' }}>
        {(review.categories || []).map(cat => {
          const pct = cat.max ? Math.round((cat.score / cat.max) * 100) : 0;
          const cc = scoreColor(pct);
          return (
            <div key={cat.id} className="gr-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontWeight: 700, color: '#fff', fontSize: '0.82rem' }}>{cat.name}</span>
                <span style={{ fontWeight: 800, color: cc, fontSize: '0.8rem' }}>{cat.score}/{cat.max}</span>
              </div>
              <div style={{ height: 5, borderRadius: 99, background: 'rgba(255,255,255,.07)', margin: '6px 0' }}>
                <div style={{ width: `${pct}%`, height: '100%', borderRadius: 99, background: cc }} />
              </div>
              {cat.notes && <p style={{ color: 'var(--text-muted)', fontSize: '0.76rem', margin: 0, lineHeight: 1.45 }}>{cat.notes}</p>}
            </div>
          );
        })}
      </div>

      {!!review.issues?.length && (
        <div className="gr-card" style={{ padding: 0 }}>
          <div className="gr-label" style={{ padding: '.8rem 1rem .4rem' }}>O que corrigir ({review.issues.length})</div>
          {review.issues.map((i, n) => {
            const sev = SEVERITY[i.severity] || SEVERITY.low;
            return (
              <div key={n} style={{ padding: '.7rem 1rem', borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>
                <span style={{ flexShrink: 0, alignSelf: 'flex-start', marginTop: 2, fontSize: '0.64rem', fontWeight: 800, padding: '2px 7px', borderRadius: 6, color: sev.color, background: `${sev.color}1f`, border: `1px solid ${sev.color}55` }}>{sev.label}</span>
                <div style={{ minWidth: 0, fontSize: '0.82rem', lineHeight: 1.5 }}>
                  <div style={{ color: '#fff', fontWeight: 600 }}>{i.section && <span style={{ color: 'var(--accent-light)' }}>{i.section} · </span>}{i.problem}</div>
                  {i.fix && <div style={{ color: 'var(--text-muted)' }}>{i.fix}</div>}
                  {i.example && (
                    <div style={{ marginTop: 5, padding: '6px 9px', borderRadius: 8, background: 'rgba(0,200,83,.06)', border: '1px solid rgba(0,200,83,.2)', color: '#cfe9d8', fontSize: '0.78rem', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <span style={{ flex: 1 }}>{i.example}</span><CopyButton text={i.example} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '0.7rem' }}>
        {!!review.strengths?.length && (
          <div className="gr-card">
            <div className="gr-label" style={{ marginBottom: 6 }}>Pontos fortes</div>
            {review.strengths.map((s, n) => (
              <div key={n} style={{ display: 'flex', gap: 7, fontSize: '0.8rem', color: '#d4d4dc', lineHeight: 1.45, marginBottom: 5 }}>
                <CheckCircle2 size={14} style={{ color: '#00c853', flexShrink: 0, marginTop: 2 }} /> {s}
              </div>
            ))}
          </div>
        )}
        {(review.keywords?.present?.length || review.keywords?.missing?.length) ? (
          <div className="gr-card">
            <div className="gr-label" style={{ marginBottom: 6 }}>Palavras-chave do cargo-alvo</div>
            {!!review.keywords?.missing?.length && <>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 5 }}>Faltando (acrescente só se for verdade):</div>
              <div>{review.keywords.missing.map(k => <span key={k} className="gr-kw" style={{ color: '#ff8a8a', background: 'rgba(255,92,92,.1)', border: '1px solid rgba(255,92,92,.3)' }}>{k}</span>)}</div>
            </>}
            {!!review.keywords?.present?.length && <>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', margin: '4px 0 5px' }}>Já presentes:</div>
              <div>{review.keywords.present.map(k => <span key={k} className="gr-kw" style={{ color: '#7ee2a8', background: 'rgba(0,200,83,.08)', border: '1px solid rgba(0,200,83,.25)' }}>{k}</span>)}</div>
            </>}
          </div>
        ) : null}
      </div>
    </div>
  );
};

// ── Sign-up form suggestions tab ────────────────────────────────────────────────────────────────────────────────
const FormView = ({ s }: { s: FormSuggestions }) => {
  const field = (label: string, value: string | undefined, why?: string, extra?: React.ReactNode) => value ? (
    <div className="gr-card" key={label}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span className="gr-label">{label}</span><CopyButton text={value} />
      </div>
      <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.9rem', margin: '5px 0 3px', whiteSpace: 'pre-wrap' }}>{value}</div>
      {extra}
      {why && <div style={{ color: 'var(--text-muted)', fontSize: '0.76rem', lineHeight: 1.45 }}>{why}</div>}
    </div>
  ) : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
      {!!s.target_job_titles?.length && (
        <div className="gr-card" style={{ padding: 0 }}>
          <div className="gr-label" style={{ padding: '.8rem 1rem .4rem' }}>Target job title — o primeiro é o recomendado</div>
          {s.target_job_titles.map((t, n) => (
            <div key={t.title} style={{ padding: '.6rem 1rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 20, color: 'var(--text-muted)', fontSize: '0.74rem', fontWeight: 700 }}>{n + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.86rem' }}>
                  {t.title}
                  {t.fit && <span style={{ marginLeft: 8, fontSize: '0.64rem', fontWeight: 800, padding: '1px 6px', borderRadius: 6,
                    color: t.fit === 'alta' ? '#00c853' : '#f5c542', background: t.fit === 'alta' ? 'rgba(0,200,83,.12)' : 'rgba(245,197,66,.12)' }}>aderência {t.fit}</span>}
                </div>
                {t.why && <div style={{ color: 'var(--text-muted)', fontSize: '0.76rem' }}>{t.why}</div>}
              </div>
              <CopyButton text={t.title} />
            </div>
          ))}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.7rem' }}>
        {field('Experience level', s.experience_level?.value, s.experience_level?.why,
          s.experience_level?.alternative ? <div style={{ fontSize: '0.74rem', color: 'var(--accent-light)', marginBottom: 3 }}>Alternativa: {s.experience_level.alternative}</div> : null)}
        {field('Job status', s.job_status?.value, s.job_status?.why)}
        {field('Preferred salary range', s.salary_range?.value, s.salary_range?.why,
          <>
            {s.salary_range?.minimum && <div style={{ fontSize: '0.74rem', color: 'var(--accent-light)', marginBottom: 3 }}>Mínimo a aceitar: {s.salary_range.minimum}</div>}
            {s.salary_range?.note && <div style={{ fontSize: '0.74rem', color: '#f5c542', marginBottom: 3, display: 'flex', gap: 5 }}><Info size={12} style={{ flexShrink: 0, marginTop: 2 }} /> {s.salary_range.note}</div>}
          </>)}
      </div>
      {!!s.other_fields?.length && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '0.7rem' }}>
          {s.other_fields.map(f => field(f.field, f.value, f.why))}
        </div>
      )}
    </div>
  );
};

// ── Detail window ───────────────────────────────────────────────────────────────────────────────────────────────
const Empty = ({ icon, text, action }: { icon: React.ReactNode; text: string; action: React.ReactNode }) => (
  <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
    {icon}<p style={{ maxWidth: 460, fontSize: '0.86rem', lineHeight: 1.5 }}>{text}</p>{action}
  </div>
);

const ResumeDetail = ({ resume: initial, initialTab = 'content', autoRun, onClose, onChanged }: {
  resume: GeneralResume; initialTab?: Tab; autoRun?: 'review' | 'form'; onClose: () => void; onChanged: (r: GeneralResume) => void;
}) => {
  const [resume, setResume] = useState(initial);
  const [draft, setDraft] = useState<ResumeFields>({ title: initial.title, lang: initial.lang, target_title: initial.target_title, used_on: initial.used_on, content_md: initial.content_md });
  const [tab, setTab] = useState<Tab>(initialTab);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);
  const [proposal, setProposal] = useState<{ resume_markdown: string; changes: string[] } | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);   // content before an accepted improvement (undo)

  const dirty = (['title', 'lang', 'target_title', 'used_on', 'content_md'] as const).some(k => (draft[k] ?? '') !== (resume[k] ?? ''));
  const apply = (r: GeneralResume) => { setResume(r); onChanged(r); };

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(b => ({ ...b, [key]: true })); setNotice(null);
    try { await fn(); } catch (e) { setNotice({ text: `Falhou: ${errorText(e)}`, ok: false }); }
    finally { setBusy(b => ({ ...b, [key]: false })); }
  };
  const save = () => run('save', async () => {
    const r = await generalResumeService.update(resume.id, draft);
    apply(r); setNotice({ text: 'Salvo', ok: true });
  });
  // review and suggestions read the saved CV: save pending edits first
  const saveIfDirty = async () => { if (dirty) apply(await generalResumeService.update(resume.id, draft)); };
  const review = () => run('review', async () => {
    await saveIfDirty(); setTab('review');
    apply(await generalResumeService.review(resume.id));
  });
  const suggest = () => run('form', async () => {
    await saveIfDirty(); setTab('form');
    apply(await generalResumeService.formSuggestions(resume.id));
  });
  const improve = () => run('improve', async () => {
    await saveIfDirty();
    setProposal(await generalResumeService.improve(resume.id));
    setTab('content');
  });
  const acceptProposal = () => run('save', async () => {
    if (!proposal) return;
    setPrevious(draft.content_md || '');
    const r = await generalResumeService.update(resume.id, { ...draft, content_md: proposal.resume_markdown });
    apply(r); setDraft(d => ({ ...d, content_md: proposal.resume_markdown })); setProposal(null);
    setNotice({ text: 'Versão melhorada salva. Rode a análise de novo para ver a nova nota.', ok: true });
  });
  const undo = () => run('save', async () => {
    if (previous === null) return;
    const r = await generalResumeService.update(resume.id, { content_md: previous });
    apply(r); setDraft(d => ({ ...d, content_md: previous })); setPrevious(null);
    setNotice({ text: 'Versão anterior restaurada', ok: true });
  });
  const pdf = () => run('pdf', async () => { await saveIfDirty(); await generalResumeService.downloadPDF({ ...resume, ...draft } as GeneralResume); });

  // list shortcuts: run once the window is open (StrictMode's first, cancelled pass clears its timer: one AI call)
  useEffect(() => {
    if (!autoRun) return;
    const t = setTimeout(autoRun === 'review' ? review : suggest, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = () => { if (!dirty || confirm('Há alterações não salvas. Fechar mesmo assim?')) onClose(); };
  const btn = (key: string, label: string, icon: React.ReactNode, onClick: () => void, primary = false, title = '') => (
    <button onClick={onClick} disabled={!!busy[key]} title={title} className={`btn ${primary ? 'btn-primary' : 'btn-secondary'}`}
      style={{ height: 34, padding: '0 12px', fontSize: '0.78rem', fontWeight: 700, gap: 6, whiteSpace: 'nowrap' }}>
      {busy[key] ? <RefreshCw size={14} className="animate-spin" /> : icon} {label}
    </button>
  );
  const loading = (text: string) => <Empty icon={<RefreshCw size={28} className="animate-spin" />} text={text} action={null} />;

  return (
    <Modal onClose={close} height="90vh">
      <div style={{ padding: '1rem 1.5rem 0.8rem', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,.02)', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', margin: 0 }}>{resume.title}</h2>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: 4, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              {resume.target_title && <span style={{ color: 'var(--accent-light)', fontWeight: 600 }}>{resume.target_title}</span>}
              <span>{LANGS[resume.lang] || resume.lang}</span>
              {resume.used_on && <span>Usado em: {resume.used_on}</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 }}>
            <ScorePill resume={resume} />
            <button onClick={close} className="btn btn-secondary" style={{ padding: 6, borderRadius: '50%' }} title="Fechar (Esc)"><X size={18} /></button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {btn('review', resume.review ? 'Analisar de novo' : 'Analisar (ATS)', <Gauge size={14} />, review, true, 'Nota e relatório no estilo dos verificadores de ATS dos sites de vagas')}
          {btn('improve', 'Melhorar com IA', <Wand2 size={14} />, improve, false, 'Reescreve o CV corrigindo o que a análise encontrou, só com fatos seus')}
          {btn('form', resume.form_suggestions ? 'Refazer sugestões' : 'Sugestões do formulário', <ListChecks size={14} />, suggest, false, 'O que responder no cadastro: cargo-alvo, nível, status, faixa salarial…')}
          {btn('pdf', 'Baixar PDF', <Download size={14} />, pdf)}
          {dirty && btn('save', 'Salvar', <Save size={14} />, save, true)}
          {notice && <span style={{ fontSize: '0.8rem', color: notice.ok ? '#10b981' : 'var(--error, #ff4d4d)' }}>{notice.text}</span>}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', padding: '0 1.5rem', borderBottom: '1px solid var(--border)' }}>
        {([['content', 'Conteúdo', <FileText size={15} />], ['review', 'Análise ATS', <Gauge size={15} />], ['form', 'Formulário do site', <ListChecks size={15} />]] as [Tab, string, React.ReactNode][]).map(([id, label, icon]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: '0.75rem 0', background: 'transparent', border: 'none', borderBottom: `2px solid ${tab === id ? 'var(--accent)' : 'transparent'}`,
            color: tab === id ? 'var(--accent)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem',
          }}>{icon} {label}</button>
        ))}
      </div>

      <div style={{ flex: 1, minHeight: 0, padding: '1rem 1.5rem', overflowY: 'auto' }}>
        {tab === 'content' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', height: '100%' }}>
            {proposal && (
              <div style={{ border: '1px solid rgba(0,200,83,.35)', background: 'rgba(0,200,83,.05)', borderRadius: 12, padding: '0.8rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Wand2 size={15} style={{ color: '#00c853' }} />
                  <b style={{ color: '#fff', fontSize: '0.86rem' }}>Versão melhorada pronta</b>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Confira abaixo antes de aceitar.</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                    <button className="btn btn-secondary" onClick={() => setProposal(null)} style={{ height: 30, padding: '0 10px', fontSize: '0.76rem' }}>Descartar</button>
                    <button className="btn btn-primary" onClick={acceptProposal} disabled={!!busy.save} style={{ height: 30, padding: '0 10px', fontSize: '0.76rem' }}>Aceitar e salvar</button>
                  </div>
                </div>
                {!!proposal.changes.length && (
                  <ul style={{ margin: '8px 0 0 18px', color: '#d4d4dc', fontSize: '0.78rem', lineHeight: 1.5 }}>
                    {proposal.changes.map((c, n) => <li key={n}>{c}</li>)}
                  </ul>
                )}
              </div>
            )}
            {previous !== null && !proposal && (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Versão anterior guardada até fechar a janela. <button onClick={undo} style={{ background: 'none', border: 'none', color: 'var(--accent-light)', cursor: 'pointer', fontWeight: 700 }}>Desfazer a melhoria</button>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="gr-label">Nome</span>
                <input className="gr-field" value={draft.title || ''} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="gr-label">Cargo-alvo</span>
                <input className="gr-field" value={draft.target_title || ''} placeholder="Ex.: Financial Modeling Analyst" onChange={e => setDraft({ ...draft, target_title: e.target.value })} /></label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="gr-label">Usado em</span>
                <input className="gr-field" value={draft.used_on || ''} placeholder="Ex.: We Work Remotely, Wellfound" onChange={e => setDraft({ ...draft, used_on: e.target.value })} /></label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="gr-label">Idioma</span>
                <select className="gr-field" value={draft.lang || 'en'} onChange={e => setDraft({ ...draft, lang: e.target.value })}>
                  {Object.entries(LANGS).map(([v, l]) => <option key={v} value={v} style={{ color: '#000' }}>{l}</option>)}
                </select></label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: proposal ? '1fr 1fr' : '1fr', gap: '0.6rem', flex: 1, minHeight: 360 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, minHeight: 0 }}>
                <span className="gr-label">{proposal ? 'Atual' : 'CV (markdown)'}</span>
                <textarea className="gr-field" value={draft.content_md || ''} onChange={e => setDraft({ ...draft, content_md: e.target.value })}
                  style={{ flex: 1, minHeight: 360, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.78rem', lineHeight: 1.5, resize: 'vertical' }} />
              </label>
              {proposal && (
                <label style={{ display: 'flex', flexDirection: 'column', gap: 4, minHeight: 0 }}>
                  <span className="gr-label" style={{ color: '#00c853' }}>Melhorada</span>
                  <textarea className="gr-field" value={proposal.resume_markdown} onChange={e => setProposal({ ...proposal, resume_markdown: e.target.value })}
                    style={{ flex: 1, minHeight: 360, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.78rem', lineHeight: 1.5, resize: 'vertical', borderColor: 'rgba(0,200,83,.35)' }} />
                </label>
              )}
            </div>
          </div>
        )}

        {tab === 'review' && (busy.review ? loading('Analisando o CV como um ATS e um recrutador…')
          : resume.review ? <>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                Analisado {ago(resume.review_at)}{resume.review_at && time(resume.updated_at) > time(resume.review_at) + 2000 ? ' · o CV mudou depois disso: analise de novo' : ''}
              </div>
              <ReviewView review={resume.review} />
            </>
          : <Empty icon={<Gauge size={30} />} text="Nota de 0 a 100 e relatório no estilo dos verificadores de ATS dos sites de vagas: leitura pelo sistema, palavras-chave do cargo-alvo, impacto, aderência, estrutura e clareza."
              action={btn('review', 'Analisar agora', <Gauge size={14} />, review, true)} />)}

        {tab === 'form' && (busy.form ? loading('Montando as respostas do formulário…')
          : resume.form_suggestions ? <>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 8 }}>Gerado {ago(resume.form_suggestions_at)} · valores em inglês, prontos para copiar</div>
              <FormView s={resume.form_suggestions} />
            </>
          : <Empty icon={<ListChecks size={30} />} text="Sugestões para os campos do cadastro nos sites de vagas: target job title, experience level, job status, preferred salary range, headline, bio curta, competências e mais."
              action={btn('form', 'Gerar sugestões', <ListChecks size={14} />, suggest, true)} />)}
      </div>
    </Modal>
  );
};

// ── New CV ──────────────────────────────────────────────────────────────────────────────────────────────────────
const NewResume = ({ resumes, onClose, onCreated }: { resumes: GeneralResume[]; onClose: () => void; onCreated: (r: GeneralResume) => void }) => {
  const [form, setForm] = useState({ title: '', target_title: '', used_on: '', lang: 'en', source: 'base-en' });
  const [saving, setSaving] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true);
    try {
      let content = '';
      if (form.source === 'base-en' || form.source === 'base-pt') content = (await profileService.getResume(form.source === 'base-pt' ? 'pt' : 'en')).content || '';
      else if (form.source.startsWith('copy-')) content = resumes.find(r => r.id === Number(form.source.slice(5)))?.content_md || '';
      const { title, target_title, used_on, lang } = form;
      onCreated(await generalResumeService.create({ title, target_title, used_on, lang, content_md: content }));
    } catch (err) { alert(`Falhou: ${errorText(err)}`); }
    finally { setSaving(false); }
  };
  return (
    <Modal onClose={onClose} maxWidth={460}>
      <form onSubmit={submit} style={{ padding: '1.4rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
        <h2 style={{ fontSize: '1.15rem', marginBottom: 4 }}>Novo CV geral</h2>
        <input required className="gr-field" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Nome (ex.: CV geral — FP&A remoto)" />
        <input className="gr-field" value={form.target_title} onChange={e => setForm({ ...form, target_title: e.target.value })} placeholder="Cargo-alvo (ex.: FP&A Manager)" />
        <input className="gr-field" value={form.used_on} onChange={e => setForm({ ...form, used_on: e.target.value })} placeholder="Onde vai usar (ex.: Wellfound)" />
        <select className="gr-field" value={form.lang} onChange={e => setForm({ ...form, lang: e.target.value })}>
          {Object.entries(LANGS).map(([v, l]) => <option key={v} value={v} style={{ color: '#000' }}>{l}</option>)}
        </select>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="gr-label">Começar de</span>
          <select className="gr-field" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}>
            <option value="base-en" style={{ color: '#000' }}>CV base em inglês (Dados e CVs)</option>
            <option value="base-pt" style={{ color: '#000' }}>CV base em português (Dados e CVs)</option>
            {resumes.map(r => <option key={r.id} value={`copy-${r.id}`} style={{ color: '#000' }}>Cópia de “{r.title}”</option>)}
            <option value="blank" style={{ color: '#000' }}>Em branco</option>
          </select>
        </label>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Criando…' : 'Criar'}</button>
        </div>
      </form>
    </Modal>
  );
};

// ── List ────────────────────────────────────────────────────────────────────────────────────────────────────────
const GeneralResumes = () => {
  const [resumes, setResumes] = useState<GeneralResume[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [lang, setLang] = useState('all');
  const [sort, setSort] = useState<SortKey>('updated');
  const [selected, setSelected] = useState<{ resume: GeneralResume; tab?: Tab; run?: 'review' | 'form' } | null>(null);
  const [creating, setCreating] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);

  useEffect(() => {
    generalResumeService.list().then(setResumes).catch(e => setError(errorText(e))).finally(() => setLoading(false));
  }, []);

  const upsert = (r: GeneralResume) => setResumes(prev => prev.some(x => x.id === r.id) ? prev.map(x => (x.id === r.id ? r : x)) : [r, ...prev]);
  const remove = async (r: GeneralResume) => {
    if (!confirm(`Excluir o CV "${r.title}"?`)) return;
    setResumes(prev => prev.filter(x => x.id !== r.id));
    try { await generalResumeService.remove(r.id); } catch { generalResumeService.list().then(setResumes); }
  };
  const duplicate = async (r: GeneralResume) => {
    try { upsert(await generalResumeService.create({ title: `${r.title} (cópia)`, lang: r.lang, target_title: r.target_title, used_on: r.used_on, content_md: r.content_md })); }
    catch (e) { alert(`Falhou: ${errorText(e)}`); }
  };
  const pdf = async (r: GeneralResume) => {
    setDownloading(r.id);
    try { await generalResumeService.downloadPDF(r); } catch (e) { alert(`Falha ao gerar o PDF: ${errorText(e)}`); }
    finally { setDownloading(null); }
  };

  const q = query.trim().toLowerCase();
  const base = useMemo(() => resumes.filter(r => !q || `${r.title} ${r.target_title} ${r.used_on}`.toLowerCase().includes(q)), [resumes, q]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: base.length };
    base.forEach(r => { c[r.lang] = (c[r.lang] || 0) + 1; });
    return c;
  }, [base]);
  const shown = useMemo(() => {
    const cmp: Record<SortKey, (a: GeneralResume, b: GeneralResume) => number> = {
      updated: (a, b) => time(b.updated_at) - time(a.updated_at),
      score: (a, b) => (b.review?.score ?? -1) - (a.review?.score ?? -1),
      title: (a, b) => a.title.localeCompare(b.title, 'pt'),
    };
    return base.filter(r => lang === 'all' || r.lang === lang).sort(cmp[sort]);
  }, [base, lang, sort]);
  const reviewed = resumes.filter(r => r.review);
  const best = reviewed.length ? Math.max(...reviewed.map(r => r.review!.score)) : null;

  const open = (resume: GeneralResume, tab?: Tab, run?: 'review' | 'form') => (e?: React.MouseEvent) => { e?.stopPropagation(); setSelected({ resume, tab, run }); };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', width: '100%', minWidth: 0 }}>
      <style>{css}</style>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
        <div style={{ marginRight: 'auto' }}>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', margin: 0 }}>CVs gerais</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: '2px 0 0' }}>
            Para cadastro em sites de vagas (We Work Remotely, Wellfound…) · {resumes.length} CV(s){best !== null ? ` · melhor nota ATS ${best}` : ''}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)} style={{ height: 34, padding: '0 14px', fontSize: '0.78rem', fontWeight: 700 }}>
          <Plus size={16} /> Novo CV
        </button>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 360 }}>
          <Search size={15} style={{ position: 'absolute', left: 11, top: 9, color: 'var(--text-muted)' }} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar nome, cargo-alvo ou site"
            style={{ height: 34, padding: '0 32px 0 34px', fontSize: '0.8rem', borderRadius: 10 }} />
          {query && <button onClick={() => setQuery('')} title="Limpar" style={{ position: 'absolute', right: 8, top: 8, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={15} /></button>}
        </div>
        {[{ id: 'all', label: 'Todos' }, ...Object.entries(LANGS).map(([id, label]) => ({ id, label }))].map(l => (
          <button key={l.id} className={`gr-chip${lang === l.id ? ' on' : ''}`} onClick={() => setLang(l.id)}>{l.label} <span className="n">{counts[l.id] || 0}</span></button>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
          <ArrowUpDown size={14} style={{ color: 'var(--text-muted)' }} />
          <select className="gr-select" value={sort} onChange={e => setSort(e.target.value as SortKey)} title="Ordenar">
            {SORTS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)', marginBottom: 0 }}>Carregando CVs…</div>
      ) : error ? (
        <div className="panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--error)', marginBottom: 0, display: 'flex', gap: 8, justifyContent: 'center' }}><AlertTriangle size={16} /> Não foi possível carregar: {error}</div>
      ) : (
        <div className="panel" style={{ padding: 0, marginBottom: 0, overflow: 'hidden' }}>
          <div style={{ overflow: 'auto', maxHeight: 'calc(100vh - 300px)', minHeight: 200 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, zIndex: 2, background: '#14141f', borderBottom: '1px solid var(--border)' }}>
                  <th className="gr-th">CV E CARGO-ALVO</th>
                  <th className="gr-th">NOTA ATS</th>
                  <th className="gr-th gr-hide-sm">FORMULÁRIO</th>
                  <th className="gr-th gr-hide-sm">IDIOMA</th>
                  <th className="gr-th gr-hide-sm">ATUALIZADO</th>
                  <th className="gr-th" style={{ textAlign: 'right' }}>AÇÕES</th>
                </tr>
              </thead>
              <tbody>
                {shown.map(r => (
                  <tr key={r.id} className="gr-row" onClick={open(r)}>
                    <td className="gr-td" style={{ maxWidth: 0, width: '100%' }}>
                      <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title}</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'flex', gap: 10, overflow: 'hidden', whiteSpace: 'nowrap' }}>
                        {r.target_title && <span style={{ color: 'var(--accent-light)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.target_title}</span>}
                        {r.used_on && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.used_on}</span>}
                      </div>
                    </td>
                    <td className="gr-td" onClick={open(r, 'review')}><ScorePill resume={r} /></td>
                    <td className="gr-td gr-hide-sm" style={{ fontSize: '0.7rem', fontWeight: 700, color: r.form_suggestions ? '#00c853' : 'rgba(255,255,255,.2)', whiteSpace: 'nowrap' }}
                      title={r.form_suggestions ? 'Sugestões geradas' : 'Sem sugestões'} onClick={open(r, 'form')}>Sugestões</td>
                    <td className="gr-td gr-hide-sm" style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{LANGS[r.lang] || r.lang}</td>
                    <td className="gr-td gr-hide-sm" style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{ago(r.updated_at)}</td>
                    <td className="gr-td" style={{ textAlign: 'right' }}>
                      <div className="gr-acts" style={{ display: 'inline-flex', gap: 6 }}>
                        <button className="gr-icon primary" title="Analisar como ATS (nota e relatório)" onClick={open(r, 'review', 'review')}><Gauge size={15} /></button>
                        <button className="gr-icon" title="Sugestões para o formulário do site" onClick={open(r, 'form', r.form_suggestions ? undefined : 'form')}><ListChecks size={15} /></button>
                        <button className="gr-icon" title="Baixar PDF" disabled={downloading === r.id} onClick={e => { e.stopPropagation(); pdf(r); }}>
                          {downloading === r.id ? <RefreshCw size={15} className="animate-spin" /> : <Download size={15} />}
                        </button>
                        <button className="gr-icon" title="Duplicar" onClick={e => { e.stopPropagation(); duplicate(r); }}><Files size={15} /></button>
                        <button className="gr-icon danger" title="Excluir" onClick={e => { e.stopPropagation(); remove(r); }}><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!shown.length && <p style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>{resumes.length ? 'Nenhum CV com estes filtros.' : 'Nenhum CV geral ainda. Crie um a partir do CV base.'}</p>}
          </div>
        </div>
      )}

      {creating && <NewResume resumes={resumes} onClose={() => setCreating(false)} onCreated={r => { upsert(r); setCreating(false); setSelected({ resume: r }); }} />}
      {selected && <ResumeDetail key={`${selected.resume.id}-${selected.run || selected.tab || ''}`} resume={selected.resume} initialTab={selected.tab} autoRun={selected.run}
        onClose={() => setSelected(null)} onChanged={upsert} />}
    </div>
  );
};

export default GeneralResumes;
