/* eslint-disable @typescript-eslint/no-explicit-any -- JSON bags, as the backend sends them */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, CircleStop, ExternalLink, FileText, Inbox as InboxIcon, ListChecks, Mail, Monitor, Play, RefreshCw, Settings2, UserRound, X } from 'lucide-react';
import TabbedPage from '../components/TabbedPage';
import { automationService as auto, Action, AutomationStatus, EmailEvent, FoundJob, FunnelRow, Inbox, Question, SearchRow } from '../services/automationService';

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

const KIND_LABEL: Record<string, string> = { apply: 'Candidatura', comment: 'Comentário', connect: 'Conexão', follow: 'Seguir', search: 'Busca', check: 'Verificação', feed_scan: 'Leitura do feed', follow_scan: 'Sugestões para seguir' };
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

// ── Approve ──────────────────────────────────────────────────────────────
const Choice = ({ onApprove, onReject, busy, approveLabel = 'Aprovar' }: { onApprove: () => void; onReject: () => void; busy: boolean; approveLabel?: string }) => (
  <div style={row}>
    <button className="btn btn-primary" disabled={busy} onClick={onApprove}><Check size={15} /> {approveLabel}</button>
    <button className="btn btn-secondary" disabled={busy} onClick={onReject}><X size={15} /> Rejeitar</button>
  </div>
);

const ProposalCard = ({ action, onDone, setError }: { action: Action; onDone: () => void; setError: (e: string) => void }) => {
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState<string>(action.payload.text || '');
  const decide = (call: Promise<unknown>) => {
    setBusy(true);
    call.then(onDone).catch((e) => setError(errorText(e))).finally(() => setBusy(false));
  };
  const p = action.payload;
  return (
    <div className="panel" style={stack}>
      {action.kind === 'apply' && <>
        <div style={{ ...row, justifyContent: 'space-between' }}>
          <strong>{action.job_title || p.title}</strong>
          {action.triage_score != null && <span style={badge(action.triage_score >= 85 ? GREEN : YELLOW)}>Nota {action.triage_score}</span>}
        </div>
        <div style={muted}>{action.company || p.company}{action.location ? ` · ${action.location}` : ''}</div>
        <div style={row}>
          {action.posted_at && <span style={badge(isRecent(action.posted_at) ? GREEN : GRAY)}>Publicada {ago(action.posted_at)}</span>}
          <span style={badge(action.easy_apply ? GREEN : YELLOW)}>{action.easy_apply ? 'Easy Apply' : 'Site da empresa'}</span>
          {action.eligibility_status === 'warning' && <span style={badge(YELLOW)}>Elegibilidade: atenção</span>}
        </div>
        {action.triage_reason && <p style={muted}>{action.triage_reason}</p>}
        {action.salary_flag && <p style={{ ...muted, color: YELLOW }}>{action.salary_flag}</p>}
      </>}
      {action.kind === 'comment' && <>
        <div style={muted}><strong>{p.author}</strong>{p.relevance != null ? ` · relevância ${p.relevance}` : ''}</div>
        <p style={{ ...muted, whiteSpace: 'pre-wrap', maxHeight: 130, overflow: 'auto' }}>{p.post_head}</p>
        <textarea style={{ ...input, minHeight: 90 }} value={text} onChange={(e) => setText(e.target.value)} aria-label="Comentário" />
      </>}
      {(action.kind === 'connect' || action.kind === 'follow') && <>
        <strong>{p.name || action.title}</strong>
        {p.headline && <div style={muted}>{p.headline}</div>}
        {p.reason && <p style={muted}>{p.reason}</p>}
        {p.why && <p style={muted}>{p.why}</p>}
      </>}
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <Choice busy={busy} onApprove={() => decide(auto.approve(action.id, action.kind === 'comment' ? text : undefined))} onReject={() => decide(auto.reject(action.id))} />
        {action.target_url && <a style={muted} href={action.target_url} target="_blank" rel="noreferrer">Abrir <ExternalLink size={12} /></a>}
      </div>
    </div>
  );
};

const SECTIONS: { key: 'apply' | 'comment' | 'connect' | 'follow'; title: string }[] = [
  { key: 'apply', title: 'Vagas para se candidatar' }, { key: 'comment', title: 'Comentários' }, { key: 'connect', title: 'Conexões' }, { key: 'follow', title: 'Seguir' },
];

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
          <div style={muted}>{j.company}{j.triage_score != null ? ` · nota ${j.triage_score}` : ''}</div>
          {j.triage_reason && <p style={muted}>{j.triage_reason}</p>}
          {action && action(j)}
        </div>
      ))}
    </div>
  </details>
);

const ApproveTab = () => {
  const { data: box, error, refresh } = useLive<Inbox>(auto.inbox, 30000);
  const [actionError, setActionError] = useState('');
  if (!box) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  const total = SECTIONS.reduce((n, s) => n + box[s.key].length, 0);
  const approveAll = (items: Action[]) => {
    const missing = items.filter((a) => a.kind === 'comment' && !a.payload.text);
    auto.approveBatch(items.filter((a) => !missing.includes(a)).map((a) => a.id))
      .then((r) => { if (r.refused.length) setActionError(`${r.refused.length} não aprovado(s): revise um a um.`); refresh(); })
      .catch((e) => setActionError(errorText(e)));
  };
  return (
    <div>
      <Failure text={actionError || error} />
      {total === 0 && <div className="panel"><p style={muted}>Nada para aprovar agora.</p></div>}
      {SECTIONS.filter((s) => box[s.key].length).map((s) => (
        <section key={s.key} style={{ marginBottom: '1.5rem' }}>
          <div style={{ ...row, justifyContent: 'space-between', marginBottom: '0.7rem' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{s.title} ({box[s.key].length})</h3>
            <button className="btn btn-secondary" onClick={() => approveAll(box[s.key])}><Check size={15} /> Aprovar todos</button>
          </div>
          <div style={stack}>
            {box[s.key].map((a) => <ProposalCard key={a.id} action={a} onDone={refresh} setError={setActionError} />)}
          </div>
        </section>
      ))}
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

const NeedsYouCard = ({ action, onDone, novnc }: { action: Action; onDone: () => void; novnc?: string }) => {
  const [error, setError] = useState('');
  const act = (call: Promise<unknown>) => call.then(onDone).catch((e) => setError(errorText(e)));
  const url = action.status === 'needs_user' && action.error_code === 'external_manual' ? action.error_text?.match(/https?:\/\/\S+/)?.[0] : action.target_url;
  return (
    <div className="panel" style={stack}>
      <div style={{ ...row, justifyContent: 'space-between' }}>
        <strong>{action.title}</strong>
        <span style={badge(YELLOW)}>{KIND_LABEL[action.kind]}</span>
      </div>
      {action.status === 'review_docs' && <>
        <p style={muted}>Leia o CV gerado para esta vaga antes de ele ir ao recrutador.</p>
        <div style={row}>
          <a className="btn btn-secondary" href={`/api/jobs/${action.target_id}/document.pdf?kind=resume`} target="_blank" rel="noreferrer"><FileText size={15} /> CV</a>
          <a className="btn btn-secondary" href={`/api/jobs/${action.target_id}/document.pdf?kind=cover`} target="_blank" rel="noreferrer"><FileText size={15} /> Carta</a>
          <Link className="btn btn-secondary" to="/vagas">Editar em Vagas</Link>
          <button className="btn btn-primary" onClick={() => act(auto.approveDocs(action.id))}><Check size={15} /> Pode enviar</button>
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
              <button className="btn btn-primary" onClick={() => act(auto.retry(action.id))}><RefreshCw size={15} /> Resolvi, tentar de novo</button>
              <button className="btn btn-secondary" onClick={() => act(auto.cancel(action.id))}>Desistir desta</button>
            </div>}
      </>}
      <Failure text={error} />
    </div>
  );
};

const NeedsYouTab = () => {
  const { data: items, error, refresh } = useLive<Action[]>(auto.needsUser, 15000);
  const { data: status } = useLive<AutomationStatus>(auto.status, 60000);
  if (!items) return error ? <Failure text={error} /> : <p style={muted}>Carregando…</p>;
  return (
    <div style={stack}>
      <Failure text={error} />
      {items.length === 0 && <div className="panel"><p style={muted}>Nada esperando por você.</p></div>}
      {items.map((a) => <NeedsYouCard key={a.id} action={a} onDone={refresh} novnc={status?.novnc_url} />)}
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
  recruiter_question: ['Recrutador pergunta', YELLOW], offer: ['Oferta', GREEN], other: ['Outro', GRAY],
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
            {data.configured ? `Leitura diária às 07:30, só leitura: nada é marcado como lido, movido ou respondido.` : 'Falta configurar GMAIL_ADDRESS e GMAIL_APP_PASSWORD no servidor.'}
            {data.last_run ? ` Última: ${when(data.last_run.started_at)}${data.last_run.ok === false ? ' (falhou)' : ''}.` : ''}
            {data.auto_status ? ' Atualiza o status das vagas sozinho.' : ' Por enquanto só sugere: nenhum status muda sozinho.'}
          </div>
          {data.configured && <button className="btn btn-secondary" disabled={running} onClick={runNow}><RefreshCw size={15} /> {running ? 'Lendo…' : 'Ler agora'}</button>}
        </div>
      </div>
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
      <div className="panel">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 6 }}>Limites (degrau {s.state.ramp_step + 1} de 3)</h3>
        <p style={muted}>Sobe um degrau a cada semana sem alerta. Qualquer alerta do LinkedIn desce um e exige que você religue.</p>
        <table style={{ width: '100%', fontSize: '0.88rem', borderCollapse: 'collapse', marginTop: 8 }}>
          <thead><tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}><th>&nbsp;</th><th>Usado</th><th>Limite</th><th>Período</th></tr></thead>
          <tbody>{s.limits.map((l) => <tr key={l.kind} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}><td style={{ padding: '5px 0' }}>{LIMIT_LABEL[l.kind] || l.kind}</td><td>{l.used}</td><td>{l.limit}</td><td>{l.period === 'week' ? 'semana' : 'dia'}</td></tr>)}</tbody>
        </table>
      </div>
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
