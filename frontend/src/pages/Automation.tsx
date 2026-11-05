/* eslint-disable @typescript-eslint/no-explicit-any -- JSON bags, as the backend sends them */
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Check, CircleStop, Zap, ExternalLink, FileText, Inbox as InboxIcon, ListChecks, Mail, Monitor, Play, RefreshCw, Settings2, UserRound, X } from 'lucide-react';
import TabbedPage from '../components/TabbedPage';
import { EligibilityBadge, css as listCss } from './JobBoard';
import { jobService } from '../services/jobService';
import { automationService as auto, Action, AutomationStatus, EmailEvent, FoundJob, FunnelRow, Inbox, Limit, Question, SearchRow } from '../services/automationService';

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.88rem' };
const stack: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: '0.8rem' };
const row: React.CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' };
const input: React.CSSProperties = { width: '100%', padding: '0.6rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#fff', font: 'inherit' };
const badge = (color: string): React.CSSProperties => ({ fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', borderRadius: 999, background: `${color}22`, color, whiteSpace: 'nowrap' });
const checkLabel: React.CSSProperties = { ...muted, display: 'flex', gap: 8, alignItems: 'flex-start' };
const checkbox: React.CSSProperties = { width: 'auto', flex: '0 0 auto', marginTop: 3 };
const GREEN = '#00b894';
const YELLOW = '#fdcb6e';
const RED = '#ff7675';
const GRAY = '#9aa0a6';

const errorText = (e: any): string => {
  if (e?.response?.status === 401) return 'Token recusado: confira em Configurações → Chaves de IA → Acesso.';
  return e?.response?.data?.detail || e?.message || 'Falhou';
};

const ago = (iso?: string | null): string => {
  if (!iso) return '';
  const hours = (Date.now() - new Date(iso).getTime()) / 3600000;
  if (hours < 1) return 'há menos de 1 h';
  if (hours < 48) return `há ${Math.floor(hours)} h`;
  return `há ${Math.floor(hours / 24)} dias`;
};
const isRecent = (iso?: string | null) => !!iso && Date.now() - new Date(iso).getTime() < 48 * 3600000;
const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '');

const KIND_LABEL: Record<string, string> = { apply: 'Candidatura', comment: 'Comentário', connect: 'Conexão', follow: 'Seguir', search: 'Busca', check: 'Verificação', feed_scan: 'Leitura do feed', follow_scan: 'Sugestões para seguir', saved_import: 'Vagas salvas' };
const STATUS_LABEL: Record<string, string> = {
  approved: 'Gerando documentos', review_docs: 'Aguarda você ler o CV', queued: 'Na fila', running_ext: 'Executando', verifying: 'Conferindo na página', awaiting_confirm: 'Aguarda seu envio',
  unknown_outcome: 'Vai conferir antes de repetir', escalated: 'Aguarda rotina Claude', running_claude: 'Rotina Claude', needs_user: 'Precisa de você', done: 'Feito', discarded: 'Descartada', failed: 'Falhou', expired: 'Expirou', cancelled: 'Cancelada',
};
const CODE_LABEL: Record<string, string> = {
  unknown_required_question: 'Pergunta sem resposta', captcha: 'Captcha no site', account_required: 'O site exige conta ou login', email_verification: 'O site pede verificação de e-mail',
  invite_needs_email: 'O LinkedIn pediu o e-mail da pessoa', content_blocked: 'Barrado pela trava de NDA', documents_failed: 'Documentos não gerados', external_manual: 'Candidatura no site da empresa',
  verify_failed: 'Não deu para confirmar na página', claude_stopped: 'A rotina Claude parou', claude_audit: 'A rotina Claude saiu do alvo', payload_changed: 'O conteúdo mudou após a aprovação', confirm_timeout: 'Sem confirmação a tempo',
};

// Loads on mount and every few seconds; refresh() after an action of yours
function useLive<T>(load: () => Promise<T>, everyMs = 15000): { data: T | null; error: string; refresh: () => void } {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState('');
  const refresh = useCallback(() => { load().then((v) => { setValue(v); setError(''); }).catch((e) => setError(errorText(e))); }, [load]);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, everyMs);
    return () => clearInterval(timer);
  }, [refresh, everyMs]);
  return { data: value, error, refresh };
}

const Failure = ({ text }: { text: string }) => (text ? <p style={{ ...muted, color: RED }}>{text}</p> : null);

// ── Always on screen: the state and the stop button ──────────────────────
const MODE_LABEL = { off: 'Desligada', dry_run: 'Ensaio (sem o clique final)', live: 'Ligada' };

const StatusBar = () => {
  const { data: s, error, refresh } = useLive<AutomationStatus>(auto.status, 10000);
  if (!s) return <div className="panel" style={{ marginBottom: '1rem' }}>{error ? <Failure text={error} /> : <span style={muted}>Carregando…</span>}</div>;
  const { state } = s;
  const halted = state.halted_lanes.length > 0;
  return (
    <div className="panel" style={{ marginBottom: '1rem', borderColor: halted ? RED : undefined }}>
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <div style={row}>
          <span style={badge(state.mode === 'live' ? GREEN : state.mode === 'dry_run' ? YELLOW : GRAY)}>{MODE_LABEL[state.mode]}</span>
          <span style={badge(state.account_kind === 'main' ? GREEN : YELLOW)}>{state.account_kind === 'main' ? 'Conta principal' : 'Conta de teste'}</span>
          <span style={badge(s.worker_online ? GREEN : RED)}>{s.worker_online ? 'Navegador no ar' : 'Navegador fora do ar'}</span>
          <span style={badge(state.session_status === 'logged_in' ? GREEN : YELLOW)}>{state.session_status === 'logged_in' ? 'LinkedIn conectado' : 'Faça login no LinkedIn'}</span>
        </div>
        <div style={row}>
          <a className="btn btn-secondary" style={{ textDecoration: 'none' }} href={s.novnc_url} target="_blank" rel="noreferrer"><Monitor size={15} /> Ver navegador</a>
          {halted
            ? <button className="btn btn-primary" onClick={() => auto.resume().then(refresh)}><Play size={15} /> Religar</button>
            : <button className="btn btn-primary" style={{ background: '#d63031', borderColor: '#d63031' }} onClick={() => auto.halt().then(refresh)}><CircleStop size={15} /> Parar tudo</button>}
        </div>
      </div>
      {halted && <p style={{ marginTop: '0.7rem', color: RED, fontSize: '0.9rem' }}>Parado: {state.halted_reason}. Nada roda até você religar. O que estava em andamento é conferido na página antes de qualquer repetição.</p>}
      {state.invites_paused_until && new Date(state.invites_paused_until) > new Date() && <p style={{ ...muted, marginTop: '0.5rem' }}>Convites pausados até {when(state.invites_paused_until)} (limite semanal do LinkedIn).</p>}
      <Failure text={error} />
    </div>
  );
};

// ── Approve: one compact list, like Vagas ────────────────────────────────
type WriteKind = 'apply' | 'comment' | 'connect' | 'follow';
const KINDS: { id: WriteKind; label: string; plural: string; color: string }[] = [
  { id: 'apply', label: 'Vaga', plural: 'Vagas', color: '#8b85ff' }, { id: 'comment', label: 'Comentário', plural: 'Comentários', color: GREEN },
  { id: 'connect', label: 'Conexão', plural: 'Conexões', color: '#00b0ff' }, { id: 'follow', label: 'Seguir', plural: 'Seguir', color: GRAY },
];
const kindOf = (k: string) => KINDS.find((x) => x.id === k) || { id: k, label: k, plural: k, color: GRAY };
// when the automation works on its own; "executar agora" does not wait for it
const WINDOW = '8h–20h';
const fitColor = (n: number) => (n >= 85 ? GREEN : n >= 70 ? YELLOW : GRAY);
const ellipsis: React.CSSProperties = { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' };
// on a phone the kind moves next to the title, so the title keeps the width
const approveCss = '.ap-sm{display:none}@media (max-width: 760px){.ap-sm{display:inline-flex}}';
const KindPill = ({ kind, className }: { kind: string; className?: string }) => {
  const k = kindOf(kind);
  return <span className={`jb-pill ${className || ''}`} style={{ background: `${k.color}1f`, color: k.color, cursor: 'inherit' }}><span className="jb-dot" style={{ background: k.color }} />{k.label}</span>;
};

// the job triage, the person's fit or the post's relevance: always 0-100 against your profile
const FitBadge = ({ fit }: { fit?: number | null }) => (fit == null
  ? <span style={{ ...muted, fontSize: '0.76rem' }}>—</span>
  : <span title="Fit com o seu perfil (0–100)" style={{ ...badge(fitColor(fit)), fontVariantNumeric: 'tabular-nums' }}>{fit}</span>);

const what = (a: Action): { title: string; sub: string } => {
  const p = a.payload || {};
  if (a.kind === 'apply') return { title: a.job_title || p.title || a.title || 'Vaga', sub: [a.company || p.company, a.location].filter(Boolean).join(' · ') };
  if (a.kind === 'comment') return { title: `Post de ${p.author || a.title || '—'}`, sub: p.text || '' };
  return { title: p.name || a.title || '—', sub: p.headline || p.why || p.reason || '' };
};

const chip: React.CSSProperties = { background: 'rgba(255,255,255,.06)', color: 'var(--text-muted)', border: 'none', cursor: 'pointer' };
// The kinds of comment the AI drafts all at once (backend COMMENT_ANGLES): picking one only swaps the text, no new AI call
const VERSIONS: [string, string][] = [
  ['tecnico', 'Técnico'], ['elogio', 'Elogio + problema'], ['pergunta', 'Pergunta'],
  ['contraponto', 'Contraponto'], ['complemento', 'Complemento'], ['experiencia', 'Minha experiência'],
];
// Like the extension's comment card: edit it yourself, or tell the AI what to change; either way it waits for your ✓
const CommentEditor = ({ action, text, setText, onRevised }: { action: Action; text: string; setText: (t: string) => void; onRevised: () => void }) => {
  const [mode, setMode] = useState<'edit' | 'ai'>('edit');
  const [ask, setAsk] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const revise = (instruction: string) => {
    if (!instruction.trim()) return;
    setBusy(true); setError(''); setNote('');
    auto.revise(action.id, instruction.trim(), text !== action.payload.text ? text : undefined)
      .then((a) => { setText(a.payload.text || ''); setNote(`Revisado com o pedido “${instruction.trim()}”. Aprove pelo ✓ quando estiver bom.`); setAsk(''); onRevised(); })
      .catch((e) => setError(errorText(e)))
      .finally(() => setBusy(false));
  };
  const tab = (id: 'edit' | 'ai', label: string) => (
    <button type="button" className={`jb-pill${mode === id ? ' active' : ''}`} style={mode === id ? { ...chip, background: `${GREEN}22`, color: GREEN } : chip} onClick={() => setMode(id)}>{label}</button>
  );
  const variants: Record<string, string> = action.payload.variants || {};
  const versions = VERSIONS.filter(([k]) => variants[k]);
  return <>
    {versions.length > 1 && <div style={row}>
      {versions.map(([k, label]) => {
        const on = text === variants[k];
        return <button key={k} type="button" className={`jb-pill${on ? ' active' : ''}`} title={variants[k]}
          style={on ? { ...chip, background: `${GREEN}22`, color: GREEN } : chip} disabled={busy} onClick={() => setText(variants[k])}>{label}</button>;
      })}
    </div>}
    <div style={row}>{tab('edit', '✏️ Editar')}{tab('ai', '✨ Pedir à IA')}</div>
    <textarea style={{ ...input, minHeight: 90, opacity: busy ? 0.5 : 1 }} value={text} readOnly={busy} onChange={(e) => setText(e.target.value)} aria-label="Comentário" />
    {mode === 'edit'
      ? <span style={muted}>Escolheu outra versão ou editou? Aprove por esta linha (✓ ou ⚡): a aprovação em lote usa o texto original.</span>
      : <>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input style={{ ...input, flex: 1, minWidth: 0 }} value={ask} disabled={busy} placeholder="Ex.: mais curto, discorde com educação, cite a experiência com concessões"
            onChange={(e) => setAsk(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); revise(ask); } }} aria-label="Pedido para a IA" />
          <button className="btn btn-primary" style={{ whiteSpace: 'nowrap' }} disabled={busy || !ask.trim()} onClick={() => revise(ask)}>{busy ? 'Gerando…' : '✨ Revisar'}</button>
        </div>
        <div style={row}>
          {['Mais curto', 'Mais técnico', 'Termine com uma pergunta'].map((q) => <button key={q} type="button" className="jb-pill" style={chip} disabled={busy} onClick={() => revise(q)}>{q}</button>)}
          <button type="button" className="jb-pill" style={chip} disabled={busy} onClick={() => revise('Escreva um comentário diferente.')}>🔄 Gerar outro</button>
        </div>
        <span style={muted}>A IA parte do texto acima (com a sua edição, se houver). O novo texto não é publicado: continua aqui esperando o seu ✓.</span>
      </>}
    {note && <span style={{ ...muted, color: GREEN }}>{note}</span>}
    <Failure text={error} />
  </>;
};

// The ad as it was read, opened right here: no new tab, nothing leaves the screen
const JobText = ({ jobId }: { jobId: number }) => {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState('');
  const toggle = () => {
    setOpen(!open);
    if (text === null && !open) jobService.getJob(jobId).then((j) => setText(j.description || '')).catch((e) => setError(errorText(e)));
  };
  return (
    <div>
      <button type="button" style={{ ...muted, background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline' }} onClick={toggle}>
        <FileText size={12} /> {open ? 'Ocultar texto da vaga' : 'Ver texto da vaga'}
      </button>
      {open && (
        <div style={{ ...muted, whiteSpace: 'pre-wrap', maxHeight: 360, overflow: 'auto', marginTop: 6, padding: '0.6rem 0.75rem', border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(255,255,255,.02)' }}>
          {error ? <Failure text={error} /> : text === null ? 'Carregando…' : (text.trim() || 'Sem texto salvo para esta vaga.')}
        </div>
      )}
    </div>
  );
};

const ProposalDetail = ({ action, text, setText, onRevised }: { action: Action; text: string; setText: (t: string) => void; onRevised: () => void }) => {
  const p = action.payload;
  return (
    <div style={{ ...stack, gap: '0.5rem' }}>
      {action.kind === 'apply' && <>
        <div style={row}>
          {action.posted_at && <span style={badge(isRecent(action.posted_at) ? GREEN : GRAY)}>Publicada {ago(action.posted_at)}</span>}
          <span style={badge(action.easy_apply ? GREEN : YELLOW)}>{action.easy_apply ? 'Easy Apply' : 'Site da empresa'}</span>
        </div>
        {action.triage_reason && <p style={muted}>{action.triage_reason}</p>}
        {action.salary_flag && <p style={{ ...muted, color: YELLOW }}>{action.salary_flag}</p>}
        {(action.eligibility_issues || []).map((i, n) => (
          <p key={n} style={{ ...muted, color: action.eligibility_status === 'blocked' ? RED : YELLOW }}>“{i.quote}”{i.reason ? ` — ${i.reason}` : ''}</p>
        ))}
        {action.target_id != null && <JobText jobId={action.target_id} />}
      </>}
      {action.kind === 'comment' && <>
        {p.reason && <p style={muted}>{p.reason}</p>}
        {(p.post_full || p.post_head) && <p style={{ ...muted, whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto' }}>{p.post_full || p.post_head}</p>}
        <CommentEditor action={action} text={text} setText={setText} onRevised={onRevised} />
      </>}
      {(action.kind === 'connect' || action.kind === 'follow') && <>
        {p.headline && <div style={muted}>{p.headline}</div>}
        {p.reason && <p style={muted}>{p.reason}</p>}
        {p.why && <p style={muted}>{p.why}</p>}
      </>}
    </div>
  );
};

const ProposalRow = ({ action, picked, onPick, onDone, setError }: { action: Action; picked: boolean; onPick: (on: boolean) => void; onDone: () => void; setError: (e: string) => void }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState<string>(action.payload.text || '');
  const decide = (call: Promise<unknown>) => {
    setBusy(true);
    call.then(onDone).catch((e) => setError(errorText(e))).finally(() => setBusy(false));
  };
  const w = what(action);
  return (
    <>
      <tr className="jb-row" onClick={() => setOpen(!open)}>
        <td className="jb-td jb-hide-sm" style={{ width: 1, paddingRight: 0 }} onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" style={checkbox} checked={picked} onChange={(e) => onPick(e.target.checked)} aria-label="Selecionar" />
        </td>
        <td className="jb-td jb-hide-sm" style={{ width: 1, paddingRight: 0 }}><KindPill kind={action.kind} /></td>
        <td className="jb-td" style={{ maxWidth: 0, width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <span style={{ fontWeight: 700, color: '#fff', fontSize: '0.88rem', ...ellipsis }}>{w.title}</span>
            {action.kind === 'apply' && <EligibilityBadge job={action} />}
            {action.salary_flag && <span title={action.salary_flag} style={{ ...badge(YELLOW), fontSize: '0.66rem', padding: '1px 6px' }}>Salário</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <KindPill kind={action.kind} className="ap-sm" />
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', ...ellipsis }}>{w.sub}</span>
          </div>
        </td>
        <td className="jb-td" style={{ textAlign: 'center' }}><FitBadge fit={action.fit} /></td>
        <td className="jb-td jb-hide-sm" style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{ago(action.posted_at || action.sort_at || action.created_at)}</td>
        <td className="jb-td" style={{ textAlign: 'right', paddingLeft: 0, whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: 'inline-flex', flexWrap: 'nowrap', gap: 6 }}>
            <button className="jb-icon primary" title={`Aprovar: vai no próximo horário (${WINDOW})`} disabled={busy} onClick={() => decide(auto.approve(action.id, action.kind === 'comment' ? text : undefined))}><Check size={15} /></button>
            <button className="jb-icon" title="Aprovar e executar agora, mesmo fora do horário" style={{ color: YELLOW }} disabled={busy} onClick={() => decide(auto.approve(action.id, action.kind === 'comment' ? text : undefined, true))}><Zap size={15} /></button>
            <button className="jb-icon danger" title="Rejeitar" disabled={busy} onClick={() => decide(auto.reject(action.id))}><X size={15} /></button>
            {action.target_url && <a className="jb-icon jb-hide-sm" title="Abrir no LinkedIn" href={action.target_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /></a>}
          </div>
        </td>
      </tr>
      {open && (
        <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,.015)' }}>
          <td colSpan={6} className="jb-td">
            <ProposalDetail action={action} text={text} setText={setText} onRevised={onDone} />
            {action.target_url && <a style={{ ...muted, display: 'inline-block', marginTop: 6 }} href={action.target_url} target="_blank" rel="noreferrer">Abrir no LinkedIn <ExternalLink size={12} /></a>}
          </td>
        </tr>
      )}
    </>
  );
};

const FoundList = ({ title, hint, jobs, action }: { title: string; hint: string; jobs: FoundJob[]; action?: (job: FoundJob) => React.ReactNode }) => (
  <details className="panel" style={{ marginTop: '1rem' }}>
    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title} ({jobs.length})</summary>
    <p style={{ ...muted, margin: '0.6rem 0' }}>{hint}</p>
    <div style={stack}>
      {jobs.map((j) => (
        <div key={j.id} style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
          <div style={{ ...row, justifyContent: 'space-between' }}>
            <a href={j.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', fontWeight: 600 }}>{j.job_title} <ExternalLink size={12} /></a>
            {j.posted_at && <span style={badge(isRecent(j.posted_at) ? GREEN : GRAY)}>{ago(j.posted_at)}</span>}
          </div>
          <div style={muted}>{j.company}{j.triage_score != null ? ` · fit ${j.triage_score}` : ''}</div>
          {j.triage_reason && <p style={muted}>{j.triage_reason}</p>}
          <JobText jobId={j.id} />
          {action && action(j)}
        </div>
      ))}
    </div>
  </details>
);

const ApproveTab = () => {
  const { data: box, error, refresh } = useLive<Inbox>(auto.inbox, 30000);
  // ?tipo= comes from Lolo's link, so the list opens on what the message was about
  const [params, setParams] = useSearchParams();
  const kind = (KINDS.some((k) => k.id === params.get('tipo')) ? params.get('tipo') : 'all') as WriteKind | 'all';
  const [sort, setSort] = useState<'recent' | 'fit'>('recent');
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState('');
  if (!box) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  const setKind = (k: WriteKind | 'all') => {
    const next = new URLSearchParams(params);
    if (k === 'all') next.delete('tipo'); else next.set('tipo', k);
    setParams(next, { replace: true });
    setPicked(new Set());
  };
  const all = box.items || [];
  const filtered = all.filter((a) => kind === 'all' || a.kind === kind);
  const shown = sort === 'fit' ? [...filtered].sort((a, b) => (b.fit ?? -1) - (a.fit ?? -1)) : filtered;
  const selected = shown.filter((a) => picked.has(a.id));
  const pick = (id: number, on: boolean) => setPicked((prev) => { const next = new Set(prev); if (on) next.add(id); else next.delete(id); return next; });
  const done = () => { setPicked(new Set()); refresh(); };
  const approveMany = (items: Action[], runNow = false) => {
    const how = runNow ? ' e executar agora' : '';
    if (!selected.length && items.length > 1 && !confirm(`Aprovar${how} as ${items.length} da lista?`)) return;
    const missing = items.filter((a) => a.kind === 'comment' && !a.payload.text);
    auto.approveBatch(items.filter((a) => !missing.includes(a)).map((a) => a.id), runNow)
      .then((r) => { if (r.refused.length) setActionError(`${r.refused.length} não aprovado(s): revise um a um.`); done(); })
      .catch((e) => setActionError(errorText(e)));
  };
  const rejectMany = (items: Action[]) => Promise.all(items.map((a) => auto.reject(a.id))).then(done).catch((e) => setActionError(errorText(e)));
  return (
    <div style={stack}>
      <style>{listCss + approveCss}</style>
      <Failure text={actionError || error} />
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 2 }}>
        {[{ id: 'all' as const, plural: 'Todas', color: '' }, ...KINDS].map((k) => (
          <button key={k.id} className={`jb-chip${kind === k.id ? ' on' : ''}`} onClick={() => setKind(k.id)}>
            {k.color && <span className="jb-dot" style={{ background: k.color }} />}
            {k.plural} <span className="n">{k.id === 'all' ? all.length : all.filter((a) => a.kind === k.id).length}</span>
          </button>
        ))}
      </div>
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <span style={muted}>{selected.length ? `${selected.length} selecionada(s)` : `${shown.length} para aprovar · toque na linha para ver detalhes`} · ✓ vai no horário ({WINDOW}), ⚡ executa agora</span>
        <div style={row}>
          <select className="jb-select" value={sort} onChange={(e) => setSort(e.target.value as 'recent' | 'fit')} title="Ordenar">
            <option value="recent">Mais recentes</option>
            <option value="fit">Maior fit</option>
          </select>
          {selected.length > 0 && <button className="btn btn-secondary" onClick={() => rejectMany(selected)}><X size={15} /> Rejeitar</button>}
          <button className="btn btn-secondary" disabled={!shown.length} title={`Vão no próximo horário (${WINDOW})`} onClick={() => approveMany(selected.length ? selected : shown)}>
            <Check size={15} /> {selected.length ? 'Aprovar selecionadas' : 'Aprovar todas'}
          </button>
          <button className="btn btn-secondary" style={{ color: YELLOW }} disabled={!shown.length} title="Aprovar e executar agora, mesmo fora do horário" onClick={() => approveMany(selected.length ? selected : shown, true)}>
            <Zap size={15} /> {selected.length ? 'Selecionadas agora' : 'Todas agora'}
          </button>
        </div>
      </div>
      <div className="panel" style={{ padding: 0, marginBottom: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#14141f', borderBottom: '1px solid var(--border)' }}>
                <th className="jb-th jb-hide-sm" style={{ paddingRight: 0 }}>
                  <input type="checkbox" style={checkbox} aria-label="Selecionar todas" checked={shown.length > 0 && selected.length === shown.length}
                    onChange={(e) => setPicked(e.target.checked ? new Set(shown.map((a) => a.id)) : new Set())} />
                </th>
                <th className="jb-th jb-hide-sm" style={{ paddingRight: 0 }}>TIPO</th>
                <th className="jb-th">O QUÊ</th>
                <th className="jb-th" style={{ textAlign: 'center' }} title="Fit com o seu perfil (0–100)">FIT</th>
                <th className="jb-th jb-hide-sm">QUANDO</th>
                <th className="jb-th" style={{ textAlign: 'right', paddingLeft: 0 }}>AÇÕES</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((a) => <ProposalRow key={a.id} action={a} picked={picked.has(a.id)} onPick={(on) => pick(a.id, on)} onDone={refresh} setError={setActionError} />)}
            </tbody>
          </table>
          {!shown.length && <p style={{ padding: '2rem', textAlign: 'center', ...muted }}>Nada para aprovar{kind === 'all' ? ' agora' : ' neste filtro'}.</p>}
        </div>
      </div>
      {box.external_manual.length > 0 && <FoundList title="Externas: candidatura manual" hint="Vagas boas no site da empresa. Enquanto essa automação estiver desligada, candidate-se por este link para não perder a janela de 48 h." jobs={box.external_manual} />}
      {box.discarded.length > 0 && <FoundList title="Descartadas" hint="A triagem tirou da lista, com o motivo. Se discordar, traga de volta." jobs={box.discarded}
        action={(j) => <button className="btn btn-secondary" style={{ marginTop: 6 }} onClick={() => auto.recoverJob(j.id).then(refresh).catch((e) => setActionError(errorText(e)))}>Trazer de volta</button>} />}
    </div>
  );
};

// ── Needs you ────────────────────────────────────────────────────────────
const Screenshots = ({ action }: { action: Action }) => {
  const [urls, setUrls] = useState<string[]>([]);
  useEffect(() => {
    let alive = true;
    auto.events(action.id).then(async (events) => {
      const names = events.map((e) => e.screenshot_path || e.data?.screenshot).filter(Boolean).slice(-2) as string[];
      const loaded = await Promise.all(names.map((n) => auto.artifactUrl(action.id, n).catch(() => '')));
      if (alive) setUrls(loaded.filter(Boolean));
    }).catch(() => {});
    return () => { alive = false; };
  }, [action.id]);
  return <>{urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer"><img src={u} alt="Tela no momento" style={{ width: '100%', maxWidth: 480, borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)' }} /></a>)}</>;
};

const Fields = ({ fields }: { fields?: { label: string; value: string }[] }) => (fields?.length ? (
  <details><summary style={{ ...muted, cursor: 'pointer' }}>Respostas preenchidas ({fields.length})</summary>
    <ul style={{ ...muted, marginTop: 6, paddingLeft: 18 }}>{fields.map((f, i) => <li key={i}><strong>{f.label}:</strong> {f.value}</li>)}</ul>
  </details>) : null);

const AnswerForm = ({ action, onDone, setError }: { action: Action; onDone: () => void; setError: (e: string) => void }) => {
  const questions: Question[] = action.questions || [];
  const [values, setValues] = useState<Record<number, string>>({});
  const [save, setSave] = useState(true);
  const send = () => auto.answer(action.id, questions.map((q, i) => ({ question: q.label, answer: values[i] || '', field_type: q.type || 'text', save }))).then(onDone).catch((e) => setError(errorText(e)));
  return (
    <div style={stack}>
      {questions.map((q, i) => (
        <label key={i} style={{ display: 'block' }}>
          <div style={{ marginBottom: 4 }}>{q.label}</div>
          {q.options?.length
            ? <select style={input} value={values[i] || ''} onChange={(e) => setValues({ ...values, [i]: e.target.value })}>
                <option value="">Escolha…</option>
                {q.options.map((o) => <option key={o} value={o} style={{ color: '#000' }}>{o}</option>)}
              </select>
            : <input style={input} value={values[i] || ''} onChange={(e) => setValues({ ...values, [i]: e.target.value })} />}
        </label>
      ))}
      <label style={checkLabel}><input type="checkbox" style={checkbox} checked={save} onChange={(e) => setSave(e.target.checked)} /> Salvar para as próximas candidaturas</label>
      <div style={row}>
        <button className="btn btn-primary" disabled={questions.some((_, i) => !values[i]?.trim())} onClick={send}><Check size={15} /> Responder e continuar</button>
        <button className="btn btn-secondary" onClick={() => auto.cancel(action.id).then(onDone).catch((e) => setError(errorText(e)))}>Desistir desta</button>
      </div>
    </div>
  );
};

// What the person has to do: a row's situation drives the filter chips and the quick action
type Need = 'docs' | 'confirm' | 'solve';
const NEEDS: { id: Need; plural: string; color: string }[] = [
  { id: 'docs', plural: 'Revisar CV', color: '#8b85ff' }, { id: 'confirm', plural: 'Confirmar envio', color: GREEN }, { id: 'solve', plural: 'Resolver', color: YELLOW },
];
const needOf = (a: Action): Need => (a.status === 'review_docs' ? 'docs' : a.status === 'awaiting_confirm' ? 'confirm' : 'solve');
const needsWhat = (a: Action): { title: string; sub: string } => {
  const w = what(a);
  const reason = a.status === 'needs_user' ? (CODE_LABEL[a.error_code || ''] || a.error_code || '') : STATUS_LABEL[a.status] || '';
  return { title: a.title || w.title, sub: [reason, w.sub].filter(Boolean).join(' · ') };
};

const NeedsYouDetail = ({ action, onDone, novnc, setError }: { action: Action; onDone: () => void; novnc?: string; setError: (e: string) => void }) => {
  const act = (call: Promise<unknown>) => call.then(onDone).catch((e) => setError(errorText(e)));
  const url = action.status === 'needs_user' && action.error_code === 'external_manual' ? action.error_text?.match(/https?:\/\/\S+/)?.[0] : action.target_url;
  return (
    <div style={{ ...stack, gap: '0.5rem' }}>
      {action.status === 'review_docs' && <>
        <p style={muted}>Leia o CV gerado para esta vaga antes de ele ir ao recrutador.</p>
        {action.error_code === 'cv_review_failed' && action.error_text && <div style={{ border: '1px solid #8b85ff55', borderRadius: 8, padding: '0.6rem 0.75rem' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Comentário do revisor</div>
          <p style={{ ...muted, whiteSpace: 'pre-line', margin: 0 }}>{action.error_text}</p>
        </div>}
        <div style={row}>
          <a className="btn btn-secondary" href={`/api/jobs/${action.target_id}/document.pdf?kind=resume`} target="_blank" rel="noreferrer"><FileText size={15} /> CV</a>
          <a className="btn btn-secondary" href={`/api/jobs/${action.target_id}/document.pdf?kind=cover`} target="_blank" rel="noreferrer"><FileText size={15} /> Carta</a>
          <Link className="btn btn-secondary" to="/vagas">Editar em Vagas</Link>
          <button className="btn btn-primary" onClick={() => act(auto.approveDocs(action.id))}><Check size={15} /> Pode enviar</button>
          {action.error_code === 'cv_review_failed' && <button className="btn btn-secondary" title="Gera o CV e a carta de novo e o revisor lê outra vez" onClick={() => act(auto.retry(action.id))}><RefreshCw size={15} /> Refazer</button>}
          <button className="btn btn-secondary" onClick={() => act(auto.cancel(action.id))}><X size={15} /> Cancelar</button>
        </div>
      </>}
      {action.status === 'awaiting_confirm' && <>
        <p style={muted}>Formulário preenchido, parado no botão de envio. Confira no navegador e confirme.</p>
        <Fields fields={action.result?.fields} />
        <div style={row}>
          {novnc && <a className="btn btn-secondary" href={novnc} target="_blank" rel="noreferrer"><Monitor size={15} /> Ver navegador</a>}
          <button className="btn btn-primary" onClick={() => act(auto.confirmSubmit(action.id))}><Check size={15} /> Enviar candidatura</button>
        </div>
      </>}
      {action.status === 'needs_user' && <>
        <div><span style={badge(RED)}>{CODE_LABEL[action.error_code || ''] || action.error_code}</span></div>
        {action.error_text && <p style={muted}>{action.error_text}</p>}
        <Screenshots action={action} />
        {action.questions?.length
          ? <AnswerForm action={action} onDone={onDone} setError={setError} />
          : <div style={row}>
              {url && <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Abrir</a>}
              {novnc && <a className="btn btn-secondary" href={novnc} target="_blank" rel="noreferrer"><Monitor size={15} /> Ver navegador</a>}
              <button className="btn btn-primary" onClick={() => act(auto.retry(action.id))}><RefreshCw size={15} /> Já resolvi: tentar de novo</button>
              <button className="btn btn-secondary" onClick={() => act(auto.cancel(action.id))}>Desistir desta</button>
            </div>}
      </>}
    </div>
  );
};

const NeedsYouRow = ({ action, picked, onPick, onDone, novnc, setError }: { action: Action; picked: boolean; onPick: (on: boolean) => void; onDone: () => void; novnc?: string; setError: (e: string) => void }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const decide = (call: Promise<unknown>) => { setBusy(true); call.then(onDone).catch((e) => setError(errorText(e))).finally(() => setBusy(false)); };
  const need = needOf(action);
  const w = needsWhat(action);
  const quick = need === 'docs'
    ? { title: 'Pode enviar', run: () => auto.approveDocs(action.id) }
    : need === 'confirm' ? { title: 'Enviar candidatura', run: () => auto.confirmSubmit(action.id) }
    : action.questions?.length ? null : { title: 'Tentar de novo: o sistema repete esta ação agora. Use depois de resolver o problema.', run: () => auto.retry(action.id), icon: <RefreshCw size={15} /> };
  return (
    <>
      <tr className="jb-row" onClick={() => setOpen(!open)}>
        <td className="jb-td jb-hide-sm" style={{ width: 1, paddingRight: 0 }} onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" style={checkbox} checked={picked} onChange={(e) => onPick(e.target.checked)} aria-label="Selecionar" />
        </td>
        <td className="jb-td jb-hide-sm" style={{ width: 1, paddingRight: 0 }}><KindPill kind={action.kind} /></td>
        <td className="jb-td" style={{ maxWidth: 0, width: '100%' }}>
          <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.88rem', ...ellipsis }}>{w.title}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <KindPill kind={action.kind} className="ap-sm" />
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', ...ellipsis }}>{w.sub}</span>
          </div>
        </td>
        <td className="jb-td" style={{ textAlign: 'center' }}><FitBadge fit={action.fit} /></td>
        <td className="jb-td jb-hide-sm" style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{ago(action.sort_at || action.created_at)}</td>
        <td className="jb-td" style={{ textAlign: 'right', paddingLeft: 0, whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: 'inline-flex', flexWrap: 'nowrap', gap: 6 }}>
            {quick && <button className="jb-icon primary" title={quick.title} aria-label={quick.title} disabled={busy} onClick={() => decide(quick.run())}>{'icon' in quick ? quick.icon : <Check size={15} />}</button>}
            <button className="jb-icon danger" title="Desistir desta" disabled={busy} onClick={() => decide(auto.cancel(action.id))}><X size={15} /></button>
            {action.target_url && <a className="jb-icon jb-hide-sm" title="Abrir no LinkedIn" href={action.target_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /></a>}
          </div>
        </td>
      </tr>
      {open && (
        <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,.015)' }}>
          <td colSpan={6} className="jb-td"><NeedsYouDetail action={action} onDone={onDone} novnc={novnc} setError={setError} /></td>
        </tr>
      )}
    </>
  );
};

const NeedsYouTab = () => {
  const { data: items, error, refresh } = useLive<Action[]>(auto.needsUser, 15000);
  const { data: status } = useLive<AutomationStatus>(auto.status, 60000);
  const [params, setParams] = useSearchParams();
  const need = (NEEDS.some((n) => n.id === params.get('situacao')) ? params.get('situacao') : 'all') as Need | 'all';
  const [kind, setKind] = useState<'all' | string>('all');
  const [sort, setSort] = useState<'recent' | 'fit'>('recent');
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState('');
  if (!items) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  const setNeed = (n: Need | 'all') => {
    const next = new URLSearchParams(params);
    if (n === 'all') next.delete('situacao'); else next.set('situacao', n);
    setParams(next, { replace: true });
    setPicked(new Set());
  };
  const filtered = items.filter((a) => (need === 'all' || needOf(a) === need) && (kind === 'all' || a.kind === kind));
  const shown = sort === 'fit' ? [...filtered].sort((a, b) => (b.fit ?? -1) - (a.fit ?? -1)) : filtered;
  const selected = shown.filter((a) => picked.has(a.id));
  const kindsHere = Array.from(new Set(items.map((a) => a.kind)));
  const pick = (id: number, on: boolean) => setPicked((prev) => { const next = new Set(prev); if (on) next.add(id); else next.delete(id); return next; });
  const done = () => { setPicked(new Set()); refresh(); };
  const docs = (selected.length ? selected : shown).filter((a) => needOf(a) === 'docs');
  const sendDocs = () => {
    if (!selected.length && docs.length > 1 && !confirm(`Liberar o envio das ${docs.length} da lista?`)) return;
    Promise.all(docs.map((a) => auto.approveDocs(a.id))).then(done).catch((e) => setActionError(errorText(e)));
  };
  const cancelMany = (list: Action[]) => {
    if (!confirm(`Desistir de ${list.length} ${list.length === 1 ? 'ação' : 'ações'}?`)) return;
    Promise.all(list.map((a) => auto.cancel(a.id))).then(done).catch((e) => setActionError(errorText(e)));
  };
  return (
    <div style={stack}>
      <style>{listCss + approveCss}</style>
      <Failure text={actionError || error} />
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 2 }}>
        {[{ id: 'all' as const, plural: 'Todas', color: '' }, ...NEEDS].map((n) => (
          <button key={n.id} className={`jb-chip${need === n.id ? ' on' : ''}`} onClick={() => setNeed(n.id)}>
            {n.color && <span className="jb-dot" style={{ background: n.color }} />}
            {n.plural} <span className="n">{n.id === 'all' ? items.length : items.filter((a) => needOf(a) === n.id).length}</span>
          </button>
        ))}
      </div>
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <span style={muted}>{selected.length ? `${selected.length} selecionada(s)` : `${shown.length} esperando por você · toque na linha para ver detalhes`}</span>
        <div style={row}>
          {kindsHere.length > 1 && <select className="jb-select" value={kind} onChange={(e) => { setKind(e.target.value); setPicked(new Set()); }} title="Filtrar por tipo">
            <option value="all">Todos os tipos</option>
            {kindsHere.map((k) => <option key={k} value={k}>{KIND_LABEL[k] || k}</option>)}
          </select>}
          <select className="jb-select" value={sort} onChange={(e) => setSort(e.target.value as 'recent' | 'fit')} title="Ordenar">
            <option value="recent">Mais recentes</option>
            <option value="fit">Maior fit</option>
          </select>
          {selected.length > 0 && <button className="btn btn-secondary" onClick={() => cancelMany(selected)}><X size={15} /> Desistir</button>}
          {docs.length > 0 && <button className="btn btn-secondary" onClick={sendDocs}><Check size={15} /> {selected.length ? 'Pode enviar selecionadas' : 'Pode enviar todas'}</button>}
        </div>
      </div>
      <div className="panel" style={{ padding: 0, marginBottom: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#14141f', borderBottom: '1px solid var(--border)' }}>
                <th className="jb-th jb-hide-sm" style={{ paddingRight: 0 }}>
                  <input type="checkbox" style={checkbox} aria-label="Selecionar todas" checked={shown.length > 0 && selected.length === shown.length}
                    onChange={(e) => setPicked(e.target.checked ? new Set(shown.map((a) => a.id)) : new Set())} />
                </th>
                <th className="jb-th jb-hide-sm" style={{ paddingRight: 0 }}>TIPO</th>
                <th className="jb-th">O QUÊ</th>
                <th className="jb-th" style={{ textAlign: 'center' }} title="Fit com o seu perfil (0–100)">FIT</th>
                <th className="jb-th jb-hide-sm">QUANDO</th>
                <th className="jb-th" style={{ textAlign: 'right', paddingLeft: 0 }}>AÇÕES</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((a) => <NeedsYouRow key={a.id} action={a} picked={picked.has(a.id)} onPick={(on) => pick(a.id, on)} onDone={refresh} novnc={status?.novnc_url} setError={setActionError} />)}
            </tbody>
          </table>
          {!shown.length && <p style={{ padding: '2rem', textAlign: 'center', ...muted }}>Nada esperando por você{need === 'all' && kind === 'all' ? ' agora' : ' neste filtro'}.</p>}
        </div>
      </div>
    </div>
  );
};

// ── Running and history ──────────────────────────────────────────────────
const ActionLine = ({ action, right }: { action: Action; right?: React.ReactNode }) => (
  <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '0.7rem 0' }}>
    <div style={{ ...row, justifyContent: 'space-between' }}>
      <div><strong>{action.title || KIND_LABEL[action.kind]}</strong> <span style={muted}>· {KIND_LABEL[action.kind]}{action.executor === 'claude' ? ' · rotina Claude' : ''}</span></div>
      <div style={row}>{right}<span style={badge(action.status === 'done' ? GREEN : action.status === 'failed' ? RED : GRAY)}>{STATUS_LABEL[action.status] || action.status}{action.result?.dry_run ? ' (ensaio)' : ''}</span></div>
    </div>
    {action.error_text && <div style={muted}>{action.error_text}</div>}
  </div>
);

const RunningTab = () => {
  const { data: items, error, refresh } = useLive<Action[]>(auto.running, 5000);
  if (!items) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  return (
    <div className="panel">
      <Failure text={error} />
      {items.length === 0 && <p style={muted}>Nada em andamento.</p>}
      {items.map((a) => <ActionLine key={a.id} action={a} right={['approved', 'queued', 'escalated'].includes(a.status)
        ? <button className="btn btn-secondary" onClick={() => auto.cancel(a.id).then(refresh)}>Cancelar</button> : undefined} />)}
    </div>
  );
};

const HistoryItem = ({ action }: { action: Action }) => {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <ActionLine action={action} right={<button className="btn btn-secondary" onClick={() => setOpen(!open)}>{open ? 'Fechar' : 'Detalhes'}</button>} />
      {open && <div style={{ ...stack, padding: '0 0 0.8rem' }}>
        <div style={muted}>{when(action.finished_at)}{action.result?.proof ? ' · confirmado na página' : ''}{action.target_url ? <> · <a href={action.target_url} target="_blank" rel="noreferrer">abrir</a></> : null}</div>
        {action.payload?.text && <p style={{ ...muted, whiteSpace: 'pre-wrap' }}>{action.payload.text}</p>}
        <Fields fields={action.result?.fields} />
        <Screenshots action={action} />
      </div>}
    </div>
  );
};

const HistoryTab = () => {
  const { data: items, error } = useLive<Action[]>(auto.history, 30000);
  if (!items) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  return <div className="panel">{items.length === 0 && <p style={muted}>Nada feito ainda.</p>}{items.map((a) => <HistoryItem key={a.id} action={a} />)}</div>;
};

// ── Answers by email ─────────────────────────────────────────────────────
const CLASS_LABEL: Record<string, [string, string]> = {
  confirmation: ['Candidatura recebida', GRAY], viewed: ['Visualizada', GRAY], rejection: ['Recusa', RED], interview: ['Entrevista', GREEN], assessment: ['Teste', YELLOW],
  recruiter_question: ['Recrutador pergunta', YELLOW], offer: ['Oferta', GREEN], linkedin_alert: ['Aviso do LinkedIn', RED], other: ['Outro', GRAY],
};

const FunnelTable = ({ title, rows }: { title: string; rows: FunnelRow[] }) => (
  <div>
    <h4 style={{ fontSize: '0.95rem', margin: '0.8rem 0 0.4rem' }}>{title}</h4>
    <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
      <thead><tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}><th>&nbsp;</th><th>Candidaturas</th><th>Respostas</th><th>Entrevistas</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.bucket} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}><td style={{ padding: '4px 0' }}>{r.bucket}</td><td>{r.applied}</td><td>{r.answered}</td><td>{r.interviews}</td></tr>)}</tbody>
    </table>
  </div>
);

const ResponsesTab = () => {
  const { data, error, refresh } = useLive(auto.emailEvents, 60000);
  const { data: funnel } = useLive(auto.emailFunnel, 300000);
  const [running, setRunning] = useState(false);
  if (!data) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  const toReview = data.items.filter((e: EmailEvent) => e.needs_review);
  const runNow = () => { setRunning(true); auto.emailRun().finally(() => { setRunning(false); refresh(); }); };
  return (
    <div style={stack}>
      <div className="panel">
        <div style={{ ...row, justifyContent: 'space-between' }}>
          <div style={muted}>
            {data.last_run?.summary?.source === 'lolo'
              ? 'O Lolo lê o Gmail de hora em hora (7h–22h) e avisa no WhatsApp: confirmações e recusas ele marca como lidas e arquiva; entrevista, teste, pergunta de recrutador e proposta ficam na caixa de entrada.'
              : data.configured ? 'Leitura diária às 07:30, só leitura: nada é marcado como lido, movido ou respondido.'
                : 'Ainda sem leitura: o Lolo começa assim que o token dele (CAREEROPS_BOT_TOKEN) estiver configurado.'}
            {data.last_run ? ` Última: ${when(data.last_run.started_at)}${data.last_run.ok === false ? ' (falhou)' : ''}.` : ''}
            {data.auto_status ? ' Atualiza o status das vagas sozinho.' : ' Por enquanto só sugere: nenhum status muda sozinho.'}
          </div>
          {data.configured && <button className="btn btn-secondary" disabled={running} onClick={runNow}><RefreshCw size={15} /> {running ? 'Lendo…' : 'Ler agora'}</button>}
        </div>
      </div>
      <SuggestionsPanel />
      {toReview.length > 0 && <div className="panel">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>Para você olhar ({toReview.length})</h3>
        <div style={stack}>{toReview.map((e: EmailEvent) => <EmailLine key={e.id} event={e} onDone={refresh} />)}</div>
      </div>}
      <div className="panel">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>Todas as respostas</h3>
        {data.items.length === 0 && <p style={muted}>Nenhuma ainda.</p>}
        <div style={stack}>{data.items.filter((e: EmailEvent) => !e.needs_review).map((e: EmailEvent) => <EmailLine key={e.id} event={e} onDone={refresh} />)}</div>
      </div>
      {funnel && <div className="panel">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Funil</h3>
        <p style={muted}>Compare a linha "até 24 h" com "mais de 48 h": com volume suficiente, é o que mostra se candidatar-se cedo traz mais entrevistas no seu caso.</p>
        <FunnelTable title="Idade da vaga ao se candidatar" rows={funnel.by_age} />
        <FunnelTable title="Quem enviou" rows={funnel.by_executor} />
        <FunnelTable title="Mercado" rows={funnel.by_market} />
        <FunnelTable title="Busca" rows={funnel.by_search} />
      </div>}
    </div>
  );
};

// What recruiters said beyond "no", grouped by theme: to decide later what to do with each group
const SuggestionsPanel = () => {
  const { data, refresh } = useLive(auto.suggestions, 300000);
  if (!data || data.groups.length === 0) return null;
  const decide = (id: number, status: 'accepted' | 'dismissed') => auto.setSuggestion(id, status).then(refresh);
  return (
    <div className="panel">
      <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Sugestões dos recrutadores</h3>
      <p style={muted}>Só o que um e-mail disse de específico sobre você. Agrupadas por tema, as mais repetidas primeiro; nada muda no CV sozinho.</p>
      <div style={stack}>{data.groups.map((g) => (
        <details key={`${g.target}-${g.theme}`} style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
          <summary style={{ cursor: 'pointer' }}><strong>{g.target === 'cv' ? 'CV' : 'Você'} · {g.theme}</strong> <span style={badge(g.n > 1 ? YELLOW : GRAY)}>{g.n}</span></summary>
          {g.items.map((i) => (
            <div key={i.id} style={{ margin: '0.5rem 0 0 0.8rem' }}>
              <div>{i.suggestion}</div>
              <div style={muted}>{i.company} · {when(i.created_at)}{i.evidence ? ` · "${i.evidence}"` : ''}</div>
              <div style={{ ...row, marginTop: 4 }}>
                <button className="btn btn-secondary" onClick={() => decide(i.id, 'accepted')}><Check size={15} /> Vou tratar</button>
                <button className="btn btn-secondary" onClick={() => decide(i.id, 'dismissed')}>Descartar</button>
              </div>
            </div>
          ))}
        </details>
      ))}</div>
    </div>
  );
};

const EmailLine = ({ event, onDone }: { event: EmailEvent; onDone: () => void }) => {
  const [label, color] = CLASS_LABEL[event.classification] || [event.classification, GRAY];
  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.6rem' }}>
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <strong>{event.job_title ? `${event.job_title} · ${event.company}` : 'Sem vaga associada'}</strong>
        <span style={badge(color)}>{label}</span>
      </div>
      <div style={muted}>{event.sender_domain} · {when(event.received_at)}{event.status_applied ? ` · status: ${event.status_applied}` : ''}</div>
      {event.summary && <p style={muted}>{event.summary}</p>}
      {event.evidence_quote && <p style={{ ...muted, fontStyle: 'italic' }}>"{event.evidence_quote}"</p>}
      {event.needs_review && <div style={{ ...row, marginTop: 6 }}>
        <button className="btn btn-secondary" onClick={() => auto.emailReview(event.id).then(onDone)}><Check size={15} /> Certo</button>
        <select style={{ ...input, width: 'auto' }} value="" aria-label="Corrigir classificação" onChange={(e) => e.target.value && auto.emailReview(event.id, e.target.value).then(onDone)}>
          <option value="">Corrigir para…</option>
          {Object.entries(CLASS_LABEL).map(([k, [l]]) => <option key={k} value={k} style={{ color: '#000' }}>{l}</option>)}
        </select>
      </div>}
    </div>
  );
};

// ── Searches, limits, mode ───────────────────────────────────────────────
const LIMIT_LABEL: Record<string, string> = { apply: 'Candidaturas', comment: 'Comentários', connect: 'Convites', follow: 'Seguir', search: 'Buscas', job_read: 'Vagas lidas', check: 'Verificações', feed_scan: 'Leituras do feed', follow_scan: 'Sugestões' };

// what each kind reads as, writes first; the reads at the end
const LIMIT_ORDER = ['apply', 'comment', 'connect', 'follow', 'search', 'job_read', 'check', 'feed_scan', 'follow_scan'];
const STEP_NAMES = ['Degrau 1', 'Degrau 2', 'Degrau 3'];
const smallInput: React.CSSProperties = { ...input, width: 64, padding: '0.35rem 0.4rem', textAlign: 'center' };

const LimitRow = ({ limit, step, onSaved, setError }: { limit: Limit; step: number; onSaved: () => void; setError: (e: string) => void }) => {
  const initial = [limit.step0, limit.step1, limit.step2];
  const [values, setValues] = useState<string[]>(initial.map(String));
  const numbers = values.map((v) => Number(v));
  const valid = numbers.every((n, i) => values[i].trim() !== '' && Number.isInteger(n) && n >= 0 && n <= 200);
  const dirty = numbers.some((n, i) => n !== initial[i]);
  const save = () => auto.setLimit(limit.kind, { step0: numbers[0], step1: numbers[1], step2: numbers[2] }).then(onSaved).catch((e) => setError(errorText(e)));
  return (
    <tr style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
      <td style={{ padding: '6px 0' }}>{LIMIT_LABEL[limit.kind] || limit.kind}<div style={{ ...muted, fontSize: '0.75rem' }}>{limit.used} usado(s) {limit.period === 'week' ? 'na semana' : 'hoje'}</div></td>
      {values.map((v, i) => (
        <td key={i} style={{ textAlign: 'center' }}>
          <input type="number" min={0} max={200} inputMode="numeric" aria-label={`${LIMIT_LABEL[limit.kind] || limit.kind}, ${STEP_NAMES[i]}`}
            style={{ ...smallInput, borderColor: i === step ? 'rgba(108,99,255,.7)' : undefined, fontWeight: i === step ? 700 : 400 }}
            value={v} onChange={(e) => setValues(values.map((x, j) => (j === i ? e.target.value : x)))}
            onKeyDown={(e) => { if (e.key === 'Enter' && valid && dirty) save(); }} />
        </td>
      ))}
      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
        {dirty && <button className="jb-icon primary" title="Salvar" disabled={!valid} onClick={save}><Check size={15} /></button>}
      </td>
    </tr>
  );
};

const LimitsPanel = ({ status, onChange, setError }: { status: AutomationStatus; onChange: () => void; setError: (e: string) => void }) => {
  const { state } = status;
  const step = Math.min(Math.max(state.ramp_step, 0), 2);
  const rows = [...status.limits].sort((a, b) => LIMIT_ORDER.indexOf(a.kind) - LIMIT_ORDER.indexOf(b.kind));
  const set = (patch: Parameters<typeof auto.setState>[0]) => auto.setState(patch).then(onChange).catch((e) => setError(errorText(e)));
  return (
    <div className="panel" style={stack}>
      <style>{listCss}</style>
      <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Limites</h3>
      <p style={muted}>Quanto cada coisa pode acontecer por dia (convites: por semana) em cada degrau. Vale o degrau marcado; mude os números e salve (✓).</p>
      <div style={row}>
        {STEP_NAMES.map((name, i) => <button key={name} className={`btn ${step === i ? 'btn-primary' : 'btn-secondary'}`} onClick={() => set({ ramp_step: i })}>{name}</button>)}
      </div>
      <label style={checkLabel}>
        <input type="checkbox" style={checkbox} checked={state.ramp_auto} onChange={(e) => set({ ramp_auto: e.target.checked })} />
        <span>Subir sozinho um degrau a cada semana sem alerta. Desligado, fica no degrau que você escolher. Um alerta do LinkedIn sempre desce um degrau.</span>
      </label>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: '0.88rem', borderCollapse: 'collapse' }}>
          <thead><tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
            <th>&nbsp;</th>{STEP_NAMES.map((n, i) => <th key={n} style={{ textAlign: 'center', fontWeight: i === step ? 700 : 400, color: i === step ? '#fff' : undefined }}>{n.replace('Degrau ', 'D')}</th>)}<th>&nbsp;</th>
          </tr></thead>
          <tbody>{rows.map((l) => <LimitRow key={`${l.kind}:${l.step0}:${l.step1}:${l.step2}`} limit={l} step={step} onSaved={onChange} setError={setError} />)}</tbody>
        </table>
      </div>
    </div>
  );
};

const SettingsTab = () => {
  const { data: s, error, refresh } = useLive<AutomationStatus>(auto.status, 30000);
  const { data: searches, refresh: refreshSearches } = useLive<SearchRow[]>(auto.searches, 120000);
  const [actionError, setActionError] = useState('');
  if (!s) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  const set = (patch: Parameters<typeof auto.setState>[0]) => auto.setState(patch).then(refresh).catch((e) => setActionError(errorText(e)));
  return (
    <div style={stack}>
      <Failure text={actionError} />
      <div className="panel" style={stack}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Funcionamento</h3>
        <div style={row}>
          {(['off', 'dry_run', 'live'] as const).map((m) => <button key={m} className={`btn ${s.state.mode === m ? 'btn-primary' : 'btn-secondary'}`} onClick={() => set({ mode: m })}>{MODE_LABEL[m]}</button>)}
        </div>
        <p style={muted}>Ensaio faz tudo até o último clique e para. Ligada faz o clique final também, nas ações que você aprovou.</p>
        <div style={row}>
          {(['test', 'main'] as const).map((k) => <button key={k} className={`btn ${s.state.account_kind === k ? 'btn-primary' : 'btn-secondary'}`} onClick={() => set({ account_kind: k })}>{k === 'main' ? 'Conta principal' : 'Conta de teste'}</button>)}
        </div>
        <label style={checkLabel}>
          <input type="checkbox" style={checkbox} checked={s.state.allow_final_submit} onChange={(e) => set({ allow_final_submit: e.target.checked })} />
          <span>Permitir envio final de candidaturas. {s.final_submit_possible ? 'Ativo.' : 'Inativo: exige conta principal, modo Ligada e AUTOMATION_ALLOW_FINAL_SUBMIT=true no servidor.'}</span>
        </label>
        <p style={muted}>Restam {s.state.confirm_submit_left} envio(s) com sua confirmação e {s.state.review_cv_left} CV(s) para você ler antes. Rotina Claude hoje: {s.claude_today} de {s.claude_per_day}.</p>
      </div>
      <LimitsPanel status={s} onChange={refresh} setError={setActionError} />
      <div className="panel">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 6 }}>Buscas automáticas</h3>
        <p style={muted}>As mesmas de Vagas → Pesquisar. Mais recentes primeiro, últimas 48 h, duas rodadas por dia.</p>
        <div style={{ ...stack, gap: '0.3rem', marginTop: 8 }}>
          {(searches || []).map((x) => (
            <label key={x.id} style={{ ...row, ...muted, justifyContent: 'space-between' }}>
              <span style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flex: '1 1 260px' }}><input type="checkbox" style={checkbox} checked={x.enabled} onChange={(e) => auto.toggleSearch(x.id, e.target.checked).then(refreshSearches)} /> {x.name}</span>
              <span>{x.jobs_found} vaga(s){x.last_run_at ? ` · ${ago(x.last_run_at)}` : ''}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
};

const Automation = () => (
  <div>
    <div style={{ marginBottom: '1rem' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.4rem' }}>Automação</h1>
      <p style={muted}>Você aprova, o sistema executa. Nada sai sem a sua aprovação.</p>
    </div>
    <StatusBar />
    <TabbedPage tabs={[
      { id: 'aprovar', label: 'Aprovar', icon: <InboxIcon size={16} />, render: () => <ApproveTab /> },
      { id: 'voce', label: 'Precisa de você', icon: <UserRound size={16} />, render: () => <NeedsYouTab /> },
      { id: 'andamento', label: 'Em execução', icon: <RefreshCw size={16} />, render: () => <RunningTab /> },
      { id: 'historico', label: 'Histórico', icon: <ListChecks size={16} />, render: () => <HistoryTab /> },
      { id: 'respostas', label: 'Respostas', icon: <Mail size={16} />, render: () => <ResponsesTab /> },
      { id: 'ajustes', label: 'Buscas e limites', icon: <Settings2 size={16} />, render: () => <SettingsTab /> },
    ]} />
  </div>
);

export default Automation;
