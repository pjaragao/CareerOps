import React, { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import {
  Megaphone, Sparkles, Send, Check, X, Copy, ExternalLink, Calendar, Users, BarChart3, Link2, Plus, Undo2, UserPlus, Compass, Brain, MessageSquare, Pin, Trash2,
} from 'lucide-react';
import {
  linkedinCopilotService as svc, CopilotPost, PostStatus, CopilotStatus, Market, Inspiration, EngagementItem, Prospect, ProspectStatus, WeekMetrics,
  NetworkingPlan, VoiceData, VoiceItem, VoiceKind,
} from '../services/linkedinCopilotService';

type Tab = 'posts' | 'prospects' | 'networking' | 'voice' | 'metrics';

const field: React.CSSProperties = {
  width: '100%', padding: '0.7rem', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
  borderRadius: '10px', color: '#fff', fontFamily: 'inherit', fontSize: '0.9rem',
};
const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.85rem' };
const chip = (color: string): React.CSSProperties => ({
  padding: '2px 8px', borderRadius: '6px', fontSize: '0.75rem', background: `${color}22`, color, whiteSpace: 'nowrap',
});

const PILLARS: Record<Market, Record<string, string>> = {
  br: {
    E: 'Engenharia e saneamento', C: 'Concessões e modelagem técnico-financeira', O: 'IA e dados em projeto, orçamento e obra',
    G: 'Gestão financeira de engenharia', T: 'Tecnologia na infraestrutura',
  },
  intl: {
    M: 'Financial modeling & valuation', S: 'Forecasting & statistics', D: 'Data & financial systems',
    A: 'AI for finance', I: 'Infrastructure & project finance',
  },
};
const MARKET_LABEL: Record<Market, string> = { br: 'Brasil · PT', intl: 'Exterior · EN' };
const pillarLabel = (m: Market, p: string) => PILLARS[m]?.[p] || '';
const STATUS_COLOR: Record<string, string> = {
  draft: '#9aa4b2', approved: '#4da3ff', published: '#00d4aa', failed: '#ff6b6b',
  to_contact: '#9aa4b2', invited: '#4da3ff', accepted: '#00d4aa', replied: '#c38bff', skipped: '#666',
};

const copy = async (text: string) => {
  try { await navigator.clipboard.writeText(text); } catch { /* clipboard blocked: user can still select the text */ }
};
const errMsg = (e: unknown): string => {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail || err?.message || 'Erro';
};

// ── Modal ─────────────────────────────────────────────────────────────────
// Portal to <body>: the page's fade-in animation (transform) would otherwise pin "fixed" to the page, not the window
const Modal = ({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) => createPortal(
  <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
    <div className="panel" onClick={e => e.stopPropagation()} style={{ width: 'min(640px, 100%)', maxHeight: '90vh', overflow: 'auto', marginBottom: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3>{title}</h3>
        <button className="btn btn-secondary" style={{ padding: 6 }} onClick={onClose}><X size={16} /></button>
      </div>
      {children}
    </div>
  </div>,
  document.body,
);

// ── LinkedIn API status (header) and setup guide ──────────────────────────
const code: React.CSSProperties = { background: 'rgba(255,255,255,0.08)', padding: '1px 6px', borderRadius: 5, fontSize: '0.82rem', overflowWrap: 'anywhere' };

const CopyLine = ({ value }: { value: string }) => (
  <div style={{ display: 'flex', gap: 6, alignItems: 'center', margin: '4px 0' }}>
    <code style={{ ...code, flex: 1, padding: '4px 8px' }}>{value}</code>
    <button className="btn btn-secondary" style={{ padding: 5 }} title="Copiar" onClick={() => copy(value)}><Copy size={13} /></button>
  </div>
);

// One backend variable: what to set it to and whether the running backend already has it
const EnvRow = ({ name, ok, value, current, hint }: { name: string; ok: boolean; value?: string; current?: string; hint?: string }) => (
  <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '6px 8px' }}>
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <span style={{ color: ok ? '#00d4aa' : '#ffb020' }}>{ok ? '✓' : '⚠'}</span>
      <code style={code}>{name}</code>
      {hint && <span style={muted}>{hint}</span>}
    </div>
    {value && !ok && <CopyLine value={value} />}
    {value && !ok && current && <div style={{ ...muted, fontSize: '0.78rem' }}>hoje: <code style={code}>{current}</code></div>}
  </div>
);

const ApiStatus = ({ status, reload }: { status: CopilotStatus | null; reload: () => void }) => {
  const [open, setOpen] = useState(false);
  if (!status) return null;
  const color = status.connected ? '#00d4aa' : status.configured ? '#ffb020' : '#ff6b6b';
  const text = status.connected ? `API: ${status.member_name || 'conectada'}` : status.configured ? 'API não conectada' : 'API não configurada';
  const connect = async () => {
    try { window.location.href = await svc.connectUrl(); } catch (e) { alert(errMsg(e)); }
  };
  // The address this app is opened from (e.g. the Tailscale name): LinkedIn sends the browser back here after login
  const origin = window.location.origin;
  const redirect = `${origin}/api/linkedin-copilot/oauth/callback`;
  const redirectOk = status.redirect_uri === redirect;
  const frontendOk = (status.frontend_url || '').replace(/\/$/, '') === origin;
  return (
    <>
      <button className="btn btn-secondary" style={{ ...smallBtn, gap: 6 }} onClick={() => setOpen(true)} title="Publicação automática pela API do LinkedIn">
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} /> {text}
      </button>
      {open && (
        <Modal title="Publicação pela API do LinkedIn" onClose={() => setOpen(false)}>
          {status.connected ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p>Conectado como <strong>{status.member_name}</strong>. Expira em {status.expires_at ? new Date(status.expires_at).toLocaleDateString() : '?'} (reconecte quando expirar).</p>
              <p style={muted}>Posts aprovados com horário são publicados sozinhos; sem horário, use "Publicar agora".</p>
              <div><button className="btn btn-secondary" onClick={async () => { await svc.disconnect(); reload(); setOpen(false); }}>Desconectar</button></div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.9rem', lineHeight: 1.5 }}>
              <p style={muted}>Sem a API, tudo funciona: você copia o post, publica no LinkedIn e clica em "Já publiquei". A API só serve para publicar e agendar daqui.</p>
              <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: 8 }}>
                <li style={status.configured ? { opacity: 0.55 } : undefined}>
                  Em <a href="https://www.linkedin.com/developers/apps/new" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>linkedin.com/developers</a>, crie um app.
                  O LinkedIn exige uma Página vinculada: pode ser uma página simples com o seu nome.
                </li>
                <li style={status.configured ? { opacity: 0.55 } : undefined}>
                  Na aba <strong>Products</strong>, adicione <em>Sign In with LinkedIn using OpenID Connect</em> e <em>Share on LinkedIn</em> (aprovação imediata).
                </li>
                <li style={redirectOk ? { opacity: 0.55 } : undefined}>
                  Na aba <strong>Auth</strong>, em <em>Authorized redirect URLs</em>, adicione o endereço de retorno deste app:
                  <CopyLine value={redirect} />
                  <div style={muted}>Depois do login, o LinkedIn manda o seu navegador para esse endereço. Por isso ele é o endereço pelo qual você abre o app, não <code style={code}>localhost</code>.</div>
                </li>
                <li>
                  No backend (no Coolify: <em>Environment Variables</em>), defina as variáveis e faça o redeploy:
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                    <EnvRow name="LINKEDIN_CLIENT_ID" ok={status.configured} hint="Client ID da aba Auth" />
                    <EnvRow name="LINKEDIN_CLIENT_SECRET" ok={status.configured} hint="Client Secret da aba Auth" />
                    <EnvRow name="LINKEDIN_REDIRECT_URI" ok={redirectOk} value={redirect} current={status.redirect_uri} />
                    <EnvRow name="FRONTEND_URL" ok={frontendOk} value={origin} current={status.frontend_url} />
                  </div>
                </li>
                <li>
                  Volte aqui e clique em <strong>Conectar LinkedIn</strong>. O acesso vale 60 dias.
                </li>
              </ol>
              {status.configured && !redirectOk && (
                <div style={{ color: '#ffb020', fontSize: '0.85rem' }}>
                  O backend ainda usa <code style={code}>{status.redirect_uri}</code> como retorno: corrija <code style={code}>LINKEDIN_REDIRECT_URI</code> (passo 4) antes de conectar, senão o login do LinkedIn não volta para cá.
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button className="btn btn-primary" disabled={!status.configured || !redirectOk} onClick={connect}
                  title={!status.configured ? 'Configure as variáveis primeiro (passos 1 a 4)' : !redirectOk ? 'Corrija LINKEDIN_REDIRECT_URI primeiro' : ''}><Link2 size={16} /> Conectar LinkedIn</button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
};

// ── Posts ─────────────────────────────────────────────────────────────────
const PostCard = ({ post, connected, onChange }: { post: CopilotPost; connected: boolean; onChange: () => void }) => {
  const [body, setBody] = useState(post.body);
  const [when, setWhen] = useState('');
  const [busy, setBusy] = useState(false);
  const dirty = body !== post.body;
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); onChange(); } catch (e) { alert(errMsg(e)); } finally { setBusy(false); }
  };
  const editable = post.status === 'draft' || post.status === 'failed' || post.status === 'approved';
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', minWidth: 0, marginBottom: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <span style={chip(STATUS_COLOR[post.status])}>{post.status}</span>
          <span style={chip(post.market === 'br' ? '#00b894' : '#4da3ff')}>{MARKET_LABEL[post.market]}</span>
          {post.pillar && <span style={chip('#ffb020')}>{post.pillar}{pillarLabel(post.market, post.pillar) ? ` · ${pillarLabel(post.market, post.pillar)}` : ''}</span>}
          {post.topic && <span style={muted}>{post.topic}</span>}
        </div>
        <span style={muted}>{body.length} car.</span>
      </div>
      <textarea value={body} onChange={e => setBody(e.target.value)} readOnly={!editable} rows={12} style={{ ...field, resize: 'vertical' }} />
      {post.error && <div style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{post.error}</div>}
      {post.status === 'approved' && post.scheduled_for && (
        <div style={muted}><Calendar size={13} /> Publicação agendada: {new Date(post.scheduled_for).toLocaleString()}</div>
      )}
      {post.status === 'published' && (
        <div style={muted}>Publicado em {post.published_at ? new Date(post.published_at).toLocaleString() : '—'}{post.linkedin_urn ? ` · ${post.linkedin_urn}` : ''}</div>
      )}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={() => copy(body)}><Copy size={15} /> Copiar</button>
        {dirty && <button className="btn btn-secondary" disabled={busy} onClick={() => run(() => svc.updatePost(post.id, body))}>Salvar edição</button>}
        {(post.status === 'draft' || post.status === 'failed') && !dirty && (<>
          <input type="datetime-local" value={when} onChange={e => setWhen(e.target.value)} style={{ ...field, width: 'auto' }} title="Vazio = agora" />
          <button className="btn btn-primary" disabled={busy}
            onClick={() => run(() => svc.approvePost(post.id, when ? new Date(when).toISOString() : undefined))}>
            <Check size={15} /> Aprovar{when ? ' e agendar' : ''}
          </button>
          <button className="btn btn-secondary" disabled={busy} onClick={() => run(() => svc.markPublished(post.id))}>Já publiquei</button>
        </>)}
        {post.status === 'approved' && (<>
          <button className="btn btn-secondary" disabled={busy} onClick={() => run(() => svc.unapprovePost(post.id))}><Undo2 size={15} /> Voltar a rascunho</button>
          {connected
            ? <button className="btn btn-primary" disabled={busy} onClick={() => confirm('Publicar agora no LinkedIn?') && run(() => svc.publishPost(post.id))}><Send size={15} /> Publicar agora</button>
            : <button className="btn btn-secondary" disabled={busy} onClick={() => run(() => svc.markPublished(post.id))}>Já publiquei</button>}
        </>)}
        {post.status !== 'published' && (
          <button className="btn btn-secondary" disabled={busy} style={{ color: 'var(--error)' }}
            onClick={() => confirm('Descartar este rascunho?') && run(() => svc.discardPost(post.id))}><X size={15} /></button>
        )}
      </div>
    </div>
  );
};

const clamp = (lines: number): React.CSSProperties => ({
  display: '-webkit-box', WebkitLineClamp: lines, WebkitBoxOrient: 'vertical', overflow: 'hidden', overflowWrap: 'anywhere',
});
const ago = (iso: string) => {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return days <= 0 ? 'hoje' : days === 1 ? 'ontem' : `há ${days} dias`;
};
// Themes saved before the extension read post links: find the post by its opening words
// No link saved: search the post's opening words as an exact phrase. With the extension, the post found there gets
// its link saved back here.
const themeLink = (i: Inspiration) => {
  if (i.post_url) return i.post_url;
  const words = i.post_text.replace(/[“”"#@]/g, ' ').split(/\s+/).filter(Boolean).slice(0, 8).join(' ');
  return `https://www.linkedin.com/search/results/content/?keywords=${encodeURIComponent(`"${words}"`)}&sortBy=%22date_posted%22`;
};

// Dense tables (same look as the job list)
const th: React.CSSProperties = { padding: '0.7rem 1rem', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.04em', whiteSpace: 'nowrap' };
const td: React.CSSProperties = { padding: '0.65rem 1rem', verticalAlign: 'middle' };
const iconBtn: React.CSSProperties = { padding: '6px', display: 'inline-flex', alignItems: 'center' };
const smallBtn: React.CSSProperties = { padding: '0.35rem 0.7rem', fontSize: '0.78rem' };
const DenseTable = ({ head, children }: { head: React.ReactNode; children: React.ReactNode }) => (
  <div className="panel" style={{ padding: 0, overflowX: 'auto', minWidth: 0 }}>
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
      <thead><tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>{head}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  </div>
);
const Pills = <T extends string>({ items, value, onChange }: { items: { id: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void }) => (
  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
    {items.map(f => (
      <button key={f.id} className={`btn ${value === f.id ? 'btn-primary' : 'btn-secondary'}`} style={smallBtn} onClick={() => onChange(f.id)}>
        {f.label}{f.count !== undefined && <span style={{ opacity: 0.7 }}>{f.count}</span>}
      </button>
    ))}
  </div>
);

const ThemesList = () => {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | 'new' | 'used'>('all');
  const load = useCallback(async () => setItems(await svc.inspirations()), []);
  useEffect(() => { svc.inspirations().then(setItems).catch(() => setItems([])); }, []);
  const generate = async (i: Inspiration) => {
    setBusy(i.id);
    try { await svc.generatePosts({ market: i.market, count: 1, inspiration_id: i.id }); await load(); alert('Rascunho criado: veja em "Gerar post".'); }
    catch (e) { alert(errMsg(e)); } finally { setBusy(null); }
  };
  const shown = items.filter(i => filter === 'all' || (filter === 'new' ? !i.used_count : i.used_count > 0))
    .sort((x, y) => y.created_at.localeCompare(x.created_at));
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Pills value={filter} onChange={setFilter} items={[
          { id: 'all', label: 'Todos', count: items.length },
          { id: 'new', label: 'Não usados', count: items.filter(i => !i.used_count).length },
          { id: 'used', label: 'Já usados', count: items.filter(i => i.used_count > 0).length },
        ]} />
        <span style={muted}>Salvos pelo 📌 da extensão ou ao comentar. Com menos de 2 rascunhos esperando, a IA escreve um do tema novo mais recente.</span>
      </div>
      <DenseTable head={<>
        <th style={th}>AUTOR & POST</th><th className="hide-sm" style={th}>IDIOMA</th><th className="hide-sm" style={th}>SALVO</th><th className="hide-sm" style={th}>STATUS</th><th style={{ ...th, textAlign: 'right' }}>AÇÕES</th>
      </>}>
        {shown.map(i => (
          <tr key={i.id} className="row-hover" style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setOpen(open === i.id ? null : i.id)}>
            <td style={{ ...td, maxWidth: 0, width: '100%' }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'baseline', minWidth: 0 }}>
                <strong style={{ color: '#fff', whiteSpace: 'nowrap' }}>{i.author_name || 'Autor desconhecido'}</strong>
                {i.author_headline && <span style={{ ...muted, fontSize: '0.75rem', ...clamp(1) }}>{i.author_headline}</span>}
              </div>
              <div style={{ ...muted, ...(open === i.id ? { whiteSpace: 'pre-line', overflowWrap: 'anywhere' } : clamp(1)) }}>{i.post_text}</div>
              {i.note && <div style={{ fontSize: '0.8rem', color: '#a29bfe', ...(open === i.id ? { overflowWrap: 'anywhere' } : clamp(1)) }}>💬 {i.note}</div>}
            </td>
            <td className="hide-sm" style={td}><span style={chip(i.market === 'br' ? '#00b894' : '#4da3ff')}>{i.market === 'br' ? 'PT' : 'EN'}</span></td>
            <td className="hide-sm" style={{ ...td, ...muted, whiteSpace: 'nowrap' }}>{ago(i.created_at)}</td>
            <td className="hide-sm" style={td}><span style={chip(i.used_count ? '#9aa4b2' : '#00d4aa')}>{i.used_count ? `usado ${i.used_count}x` : 'novo'}</span></td>
            <td style={{ ...td, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                <button className="btn btn-primary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} disabled={busy !== null} onClick={() => generate(i)}
                  title={`Escreve um post seu (${MARKET_LABEL[i.market]}) sobre este tema`}><Sparkles size={13} /> {busy === i.id ? 'Gerando…' : 'Gerar post'}</button>
                <a className="btn btn-secondary" style={iconBtn} href={themeLink(i)} target="_blank" rel="noreferrer"
                  title={i.post_url ? 'Abrir o post no LinkedIn' : 'Sem link salvo: buscar o post no LinkedIn (a extensão salva o link quando o post aparecer)'}><ExternalLink size={15} /></a>
                <button className="btn btn-secondary" style={{ ...iconBtn, color: 'var(--error)' }} title="Remover tema"
                  onClick={async () => { await svc.deleteInspiration(i.id); load(); }}><X size={15} /></button>
              </div>
            </td>
          </tr>
        ))}
      </DenseTable>
      {!shown.length && <p style={muted}>Nenhum tema aqui: no feed, use o 📌 da extensão ou comente em um post.</p>}
    </>
  );
};

const POST_FILTERS: { id: 'active' | PostStatus; label: string }[] = [
  { id: 'active', label: 'Pendentes' }, { id: 'draft', label: 'Rascunhos' }, { id: 'approved', label: 'Agendados' }, { id: 'published', label: 'Publicados' },
];

const GeneratePosts = ({ connected }: { connected: boolean }) => {
  const [posts, setPosts] = useState<CopilotPost[]>([]);
  const [market, setMarket] = useState<Market>('intl');
  const [form, setForm] = useState({ count: 2, pillar: '', topic: '', source_notes: '' });
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'active' | PostStatus>('active');
  const load = useCallback(async () => setPosts(await svc.listPosts()), []);
  useEffect(() => { svc.listPosts().then(setPosts); }, []);
  const generate = async () => {
    setLoading(true);
    try {
      await svc.generatePosts({ market, count: form.count, pillar: form.pillar || undefined, topic: form.topic || undefined, source_notes: form.source_notes || undefined });
      await load();
      setFilter('draft');
    } catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  const matches = (p: CopilotPost, f: 'active' | PostStatus) => (f === 'active' ? p.status !== 'published' : p.status === f);
  const shown = posts.filter(p => matches(p, filter));
  return (
    <>
      <div className="panel" style={{ minWidth: 0, marginBottom: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', gap: 8, flexWrap: 'wrap' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Sparkles size={18} /> Gerar rascunhos</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['br', 'intl'] as Market[]).map(m => (
              <button key={m} className={`btn ${market === m ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => { setMarket(m); setForm(f => ({ ...f, pillar: '' })); }}>{MARKET_LABEL[m]}</button>
            ))}
          </div>
        </div>
        <p style={{ ...muted, marginBottom: '1rem' }}>
          {market === 'br'
            ? 'Brasil, em português: engenharia e saneamento, concessões e modelagem técnico-financeira, dados e IA na infraestrutura.'
            : 'Exterior, em inglês: dados, finanças e modelagem; engenharia como domínio.'}
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: '0.8rem' }}>
          <select value={form.count} onChange={e => setForm({ ...form, count: Number(e.target.value) })} style={field}>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n} style={{ color: '#000' }}>{n} post{n > 1 ? 's' : ''}</option>)}
          </select>
          <select value={form.pillar} onChange={e => setForm({ ...form, pillar: e.target.value })} style={field}>
            <option value="" style={{ color: '#000' }}>Pilar: rodízio automático</option>
            {Object.entries(PILLARS[market]).map(([k, v]) => <option key={k} value={k} style={{ color: '#000' }}>{k} · {v}</option>)}
          </select>
          <input value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })} placeholder="Tema (opcional)" style={field} />
        </div>
        <textarea value={form.source_notes} onChange={e => setForm({ ...form, source_notes: e.target.value })} rows={2}
          placeholder="Material novo (opcional): commits da semana, um resultado, uma lição de obra ou de orçamento… A IA usa isso como fonte principal."
          style={{ ...field, marginTop: '0.8rem', resize: 'vertical' }} />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.8rem' }}>
          <button className="btn btn-primary" onClick={generate} disabled={loading}><Sparkles size={16} /> {loading ? 'Gerando…' : 'Gerar'}</button>
        </div>
      </div>
      <Pills value={filter} onChange={setFilter} items={POST_FILTERS.map(f => ({ ...f, count: posts.filter(p => matches(p, f.id)).length }))} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(480px, 100%), 1fr))', gap: '1.5rem' }}>
        {shown.map(p => <PostCard key={`${p.id}-${p.status}-${p.body.length}`} post={p} connected={connected} onChange={load} />)}
      </div>
      {!shown.length && <p style={muted}>Nada aqui ainda.</p>}
    </>
  );
};

type PostsSub = 'themes' | 'comments' | 'generate';
const PostsTab = ({ connected, initial }: { connected: boolean; initial: PostsSub }) => {
  const [sub, setSub] = useState<PostsSub>(initial);
  return (
    <>
      <Pills value={sub} onChange={setSub} items={[
        { id: 'themes', label: '📌 Posts salvos' }, { id: 'comments', label: '💬 Comentários a postar' }, { id: 'generate', label: '✨ Gerar post' },
      ]} />
      {sub === 'themes' && <ThemesList />}
      {sub === 'comments' && <EngagementTab />}
      {sub === 'generate' && <GeneratePosts connected={connected} />}
    </>
  );
};

// ── Engagement ────────────────────────────────────────────────────────────
const AddEngagement = ({ onAdded }: { onAdded: () => void }) => {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ post_text: '', post_url: '', author_name: '' });
  const [loading, setLoading] = useState(false);
  const add = async () => {
    if (form.post_text.trim().length < 20) return;
    setLoading(true);
    try {
      const item = await svc.addEngagement({ post_text: form.post_text, post_url: form.post_url || undefined, author_name: form.author_name || undefined });
      if (item.status === 'skipped') alert(`A IA sugere pular (relevância ${item.relevance}): ${item.reason}`);
      setForm({ post_text: '', post_url: '', author_name: '' });
      setOpen(false);
      onAdded();
    } catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  return (
    <>
      <button className="btn btn-primary" style={iconBtn} title="Adicionar post à fila manualmente" onClick={() => setOpen(true)}><Plus size={16} /></button>
      {open && (
        <Modal title="Adicionar post à fila" onClose={() => setOpen(false)}>
          <p style={{ ...muted, marginBottom: '0.8rem' }}>
            Mais rápido pela extensão: o botão ✨ IA em cada post do feed, ou selecione o texto → botão direito → <em>Enviar ao CareerOps Copilot</em>.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(220px, 100%), 1fr))', gap: '0.8rem' }}>
            <input value={form.post_url} onChange={e => setForm({ ...form, post_url: e.target.value })} placeholder="Link do post (opcional)" style={field} />
            <input value={form.author_name} onChange={e => setForm({ ...form, author_name: e.target.value })} placeholder="Autor (opcional)" style={field} />
          </div>
          <textarea value={form.post_text} onChange={e => setForm({ ...form, post_text: e.target.value })} rows={6} placeholder="Texto do post"
            style={{ ...field, marginTop: '0.8rem', resize: 'vertical' }} autoFocus />
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.8rem' }}>
            <button className="btn btn-primary" onClick={add} disabled={loading}>{loading ? 'Analisando…' : 'Analisar e rascunhar comentário'}</button>
          </div>
        </Modal>
      )}
    </>
  );
};

const EngagementTab = () => {
  const [data, setData] = useState<{ items: EngagementItem[]; done_today: number; daily_target: number }>({ items: [], done_today: 0, daily_target: 10 });
  const [open, setOpen] = useState<number | null>(null);
  const load = useCallback(async () => setData(await svc.engagementQueue()), []);
  useEffect(() => { svc.engagementQueue().then(setData); }, []);
  const mark = async (id: number, status: 'done' | 'skipped', comment?: string) => {
    await svc.updateEngagement(id, { status, ...(comment !== undefined ? { comment_draft: comment } : {}) });
    load();
  };
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={muted}>Hoje: <strong style={{ color: '#fff' }}>{data.done_today}</strong> / {data.daily_target} comentários ·
          {' '}{data.items.length} na fila · some sozinho quando você comenta o post (mesmo com outro texto) · clique na linha para editar</span>
        <AddEngagement onAdded={load} />
      </div>
      <DenseTable head={<>
        <th style={th}>REL.</th><th style={th}>AUTOR & POST</th><th className="hide-sm" style={th}>COMENTÁRIO SUGERIDO</th><th style={{ ...th, textAlign: 'right' }}>AÇÕES</th>
      </>}>
        {data.items.map(item => (
          <EngagementRow key={item.id} item={item} open={open === item.id} onToggle={() => setOpen(open === item.id ? null : item.id)} onMark={mark} />
        ))}
      </DenseTable>
      {!data.items.length && <p style={muted}>Fila vazia. No feed, o botão ✨ IA da extensão rascunha o comentário e coloca o post aqui.</p>}
    </>
  );
};

const EngagementRow = ({ item, open, onToggle, onMark }: {
  item: EngagementItem; open: boolean; onToggle: () => void; onMark: (id: number, s: 'done' | 'skipped', c?: string) => void;
}) => {
  const [comment, setComment] = useState(item.comment_draft || '');
  return (
    <>
      <tr className="row-hover" style={{ borderBottom: open ? 'none' : '1px solid var(--border)', cursor: 'pointer' }} onClick={onToggle}>
        <td style={td}><span style={chip((item.relevance ?? 0) >= 70 ? '#00d4aa' : '#ffb020')}>{item.relevance ?? '?'}</span></td>
        <td style={{ ...td, maxWidth: 0, width: '50%' }}>
          <strong style={{ color: '#fff' }}>{item.author_name || 'Autor desconhecido'}</strong>
          <div style={{ ...muted, ...clamp(1) }}>{item.post_text}</div>
        </td>
        <td className="hide-sm" style={{ ...td, maxWidth: 0, width: '50%' }}><div style={{ ...muted, ...clamp(2) }}>{comment || '—'}</div></td>
        <td style={{ ...td, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" style={iconBtn} title="Copiar comentário" onClick={() => copy(comment)}><Copy size={15} /></button>
            {item.post_url && <a className="btn btn-secondary" style={iconBtn} href={item.post_url} target="_blank" rel="noreferrer" title="Abrir post"><ExternalLink size={15} /></a>}
            <button className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => onMark(item.id, 'skipped')}>Pular</button>
            <button className="btn btn-primary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => onMark(item.id, 'done', comment)}><Check size={13} /> Comentei</button>
          </div>
        </td>
      </tr>
      {open && (
        <tr style={{ borderBottom: '1px solid var(--border)' }}>
          <td />
          <td colSpan={3} style={{ ...td, paddingTop: 0 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))', gap: '1rem' }}>
              <div>
                {item.reason && <p style={{ ...muted, marginBottom: 6 }}>{item.reason}</p>}
                <div style={{ ...muted, maxHeight: 220, overflow: 'auto', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.2)', padding: '0.7rem', borderRadius: 10 }}>{item.post_text}</div>
              </div>
              <textarea value={comment} onChange={e => setComment(e.target.value)} rows={7} style={{ ...field, resize: 'vertical' }} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

// ── Prospects ─────────────────────────────────────────────────────────────
const STATUS_LABEL: Partial<Record<ProspectStatus, string>> = {
  to_contact: 'para conectar', invited: 'convidado', accepted: 'aceitou', replied: 'respondeu', skipped: 'pulado',
};
const NEXT_STATUS: Partial<Record<ProspectStatus, { to: ProspectStatus; label: string }[]>> = {
  to_contact: [{ to: 'invited', label: 'Já convidei' }, { to: 'skipped', label: 'Pular' }],
  invited: [{ to: 'accepted', label: 'Aceitou' }, { to: 'replied', label: 'Respondeu' }],
  accepted: [{ to: 'replied', label: 'Respondeu' }],
};

const ProspectsTab = () => {
  const [data, setData] = useState<{ items: Prospect[]; invited_this_week: number; weekly_target: number }>({ items: [], invited_this_week: 0, weekly_target: 20 });
  const [filter, setFilter] = useState<'to_contact' | 'invited' | 'all'>('to_contact');
  const load = useCallback(async () => setData(await svc.prospects()), []);
  useEffect(() => { svc.prospects().then(setData); }, []);
  const update = async (id: number, patch: Partial<Pick<Prospect, 'status'>>) => { await svc.updateProspect(id, patch); load(); };
  const inStatus = (p: Prospect, f: typeof filter) => f === 'all' || (f === 'invited' ? p.status !== 'to_contact' : p.status === f);
  const shown = data.items.filter(p => inStatus(p, filter));
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Pills value={filter} onChange={setFilter} items={[
          { id: 'to_contact', label: 'Para conectar', count: data.items.filter(p => inStatus(p, 'to_contact')).length },
          { id: 'invited', label: 'Convidados', count: data.items.filter(p => inStatus(p, 'invited')).length },
          { id: 'all', label: 'Todos', count: data.items.length },
        ]} />
        <span style={muted}>Semana: <strong style={{ color: '#fff' }}>{data.invited_this_week}</strong> / {data.weekly_target} convites ·
          vêm dos autores e comentaristas dos posts que você salva ou comenta</span>
        {/* The extension reads Connections, Sent invitations and Messaging in that tab and moves people to convidado/aceitou/respondeu
            (it also does this by itself every 12 h); come back and reload to see the new statuses */}
        <a className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} href="https://www.linkedin.com/mynetwork/invite-connect/connections/#careerops-check"
          target="_blank" rel="noreferrer" onClick={() => setTimeout(load, 90000)}
          title="Lê suas conexões, convites enviados e mensagens no LinkedIn e marca quem já foi convidado, aceitou ou respondeu">Verificar aceites</a>
      </div>
      <DenseTable head={<>
        <th style={th}>PESSOA</th><th style={th}>FIT</th><th className="hide-sm" style={th}>MERCADO</th><th className="hide-sm" style={th}>STATUS</th><th style={{ ...th, textAlign: 'right' }}>AÇÕES</th>
      </>}>
        {shown.map(p => <ProspectRow key={p.id} p={p} onUpdate={update} />)}
      </DenseTable>
      {!shown.length && <p style={muted}>Ninguém aqui. Salve (📌) ou comente posts no feed: o autor e quem comentou são avaliados.</p>}
    </>
  );
};

const ProspectRow = ({ p, onUpdate }: { p: Prospect; onUpdate: (id: number, patch: Partial<Pick<Prospect, 'status'>>) => void }) => {
  // The extension finishes the job on LinkedIn: it opens the profile, clicks Conectar → "Enviar sem nota" and marks it as invited here
  const connectUrl = p.profile_url ? `${p.profile_url.split('#')[0]}#careerops-connect=${p.id}` : null;
  const [writing, setWriting] = useState(false);
  return (
    <tr className="row-hover" style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={{ ...td, maxWidth: 0, width: '100%' }} title={p.reason || ''}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'baseline', minWidth: 0 }}>
          {p.profile_url
            ? <a href={p.profile_url} target="_blank" rel="noreferrer" style={{ color: '#fff', fontWeight: 700, textDecoration: 'none', whiteSpace: 'nowrap' }}>{p.name || 'Sem nome'}</a>
            : <strong style={{ whiteSpace: 'nowrap' }}>{p.name || 'Sem nome'}</strong>}
          {p.segment && <span style={{ ...muted, fontSize: '0.72rem' }}>{p.segment}</span>}
        </div>
        <div style={{ ...muted, ...clamp(1) }}>{[p.headline, p.company].filter(Boolean).join(' · ')}</div>
        {p.reason && <div style={{ ...muted, fontSize: '0.78rem', opacity: 0.75, ...clamp(1) }}>{p.reason}</div>}
      </td>
      <td style={td}><span style={chip((p.fit ?? 0) >= 70 ? '#00d4aa' : '#ffb020')}>{p.fit ?? '?'}</span></td>
      <td className="hide-sm" style={td}>{p.market && <span style={chip(p.market === 'br' ? '#00b894' : '#4da3ff')}>{p.market === 'br' ? 'BR' : 'EXT'}</span>}</td>
      <td className="hide-sm" style={td}><span style={chip(STATUS_COLOR[p.status])}>{STATUS_LABEL[p.status] || p.status}</span></td>
      <td style={{ ...td, textAlign: 'right' }}>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          {p.status === 'to_contact' && connectUrl && (
            <a className="btn btn-primary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} href={connectUrl} target="_blank" rel="noreferrer"
              title="Abre o perfil e a extensão envia o convite sem nota"><UserPlus size={13} /> Conectar</a>
          )}
          {!!p.jobs?.length && p.status !== 'skipped' && (
            <button className={`btn ${p.message_sent_at ? 'btn-secondary' : 'btn-primary'}`} style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => setWriting(true)}
              title={p.message_sent_at ? `Mensagem enviada em ${new Date(p.message_sent_at).toLocaleDateString()}`
                : `Trabalha na empresa da vaga ${p.jobs[0].job_title}: ${p.status === 'to_contact' ? 'nota para o convite' : 'mensagem se colocando à disposição'}`}>
              <MessageSquare size={13} /> {p.message_sent_at ? 'Enviada' : 'Mensagem'}
            </button>
          )}
          {(NEXT_STATUS[p.status] || []).map(n => (
            <button key={n.to} className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => onUpdate(p.id, { status: n.to })}>{n.label}</button>
          ))}
        </div>
        {writing && <MessageModal p={p} onClose={() => setWriting(false)} onSent={() => { setWriting(false); onUpdate(p.id, {}); }} />}
      </td>
    </tr>
  );
};

// Direct message to a connection: drafted from their profile, the related jobs and your line of thought; you send it on LinkedIn
const MessageModal = ({ p, initial, onClose, onSent }: { p: Prospect; initial?: string; onClose: () => void; onSent: () => void }) => {
  const [text, setText] = useState(initial ?? p.message_draft ?? '');
  const [instruction, setInstruction] = useState('');
  const [meta, setMeta] = useState<{ topic?: string; stance?: string; instruction?: string }>({});
  const firstDraft = !initial && !p.message_draft;   // nothing to show yet: write one on open
  const [busy, setBusy] = useState(firstDraft);
  const request = useCallback((req?: string) => svc.draftMessage(p.id, req)
    .then(r => { setText(r.message_draft || ''); setMeta({ topic: r.topic, stance: r.stance, instruction: req }); })
    .catch(e => alert(errMsg(e))).finally(() => setBusy(false)), [p.id]);
  const draft = (req?: string) => { setBusy(true); request(req); };
  useEffect(() => { if (firstDraft) request(); }, [firstDraft, request]);
  const sent = async () => { await svc.messageSent(p.id, { text, ...meta }); onSent(); };
  return (
    <Modal title={`${p.status === 'to_contact' ? 'Nota de convite' : 'Mensagem'} para ${p.name || 'a pessoa'}`} onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, textAlign: 'left' }}>
        <div style={muted}>{[p.headline, p.company].filter(Boolean).join(' · ')}</div>
        {!!p.jobs?.length && <div style={{ ...muted, fontSize: '0.8rem' }}>vaga: {p.jobs.map(j => `${j.job_title} · ${j.company}`).join(' | ')}</div>}
        {p.status === 'to_contact' && <div style={{ fontSize: '0.8rem', color: '#ffb020' }}>Ainda não é conexão: isto é a nota do convite (até 300 caracteres). No LinkedIn, use Conectar → Adicionar nota.</div>}
        <textarea value={busy ? 'Escrevendo…' : text} onChange={e => setText(e.target.value)} rows={7} style={field} disabled={busy} />
        <div style={{ display: 'flex', gap: 6 }}>
          <input value={instruction} onChange={e => setInstruction(e.target.value)} placeholder="Refazer com um pedido (ex.: cite a vaga, pergunte sobre o time)"
            style={{ ...field, padding: '0.45rem 0.6rem' }} onKeyDown={e => { if (e.key === 'Enter' && instruction.trim()) draft(instruction.trim()); }} />
          <button className="btn btn-secondary" style={smallBtn} disabled={busy} onClick={() => draft(instruction.trim() || undefined)}><Sparkles size={13} /> Refazer</button>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" style={smallBtn} disabled={!text} onClick={() => copy(text)}><Copy size={13} /> Copiar</button>
          {p.profile_url && <a className="btn btn-secondary" style={smallBtn} href={p.profile_url} target="_blank" rel="noreferrer"
            onClick={() => copy(text)} title="Copia a mensagem e abre o perfil: clique em Mensagem e cole"><ExternalLink size={13} /> Copiar e abrir perfil</a>}
          <button className="btn btn-primary" style={smallBtn} disabled={busy || !text.trim()} onClick={sent}
            title="Registra a mensagem no prospect e na sua linha de pensamento"><Check size={13} /> Enviei</button>
        </div>
      </div>
    </Modal>
  );
};

// ── Networking (from the jobs in the system) ──────────────────────────────
const marketChip = (m: Market | null) => m && <span style={chip(m === 'br' ? '#00b894' : '#4da3ff')}>{m === 'br' ? 'BR' : 'EXT'}</span>;

const PlanSection = ({ title, hint, count, children }: { title: string; hint: string; count: number; children: React.ReactNode }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}><h3 style={{ fontSize: '1rem' }}>{title}</h3><span style={muted}>{count} · {hint}</span></div>
    <DenseTable head={<><th style={th}>SUGESTÃO</th><th style={{ ...th, textAlign: 'right' }}>AÇÕES</th></>}>{children}</DenseTable>
  </div>
);

const PlanRow = ({ done, onToggle, children, actions }: { done: boolean; onToggle: () => void; children: React.ReactNode; actions: React.ReactNode }) => (
  <tr className="row-hover" style={{ borderBottom: '1px solid var(--border)', opacity: done ? 0.5 : 1 }}>
    <td style={{ ...td, maxWidth: 0, width: '100%' }}>{children}</td>
    <td style={{ ...td, textAlign: 'right' }}><div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
      {actions}
      <button className={`btn ${done ? 'btn-primary' : 'btn-secondary'}`} style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={onToggle}
        title={done ? 'Desmarcar' : 'Marcar como feito'}><Check size={13} />{done ? ' Feito' : ''}</button>
    </div></td>
  </tr>
);

const NetworkingTab = () => {
  const [plan, setPlan] = useState<NetworkingPlan | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { svc.networking().then(setPlan).finally(() => setLoaded(true)); }, []);
  const generate = async () => {
    setBusy(true);
    try { setPlan(await svc.generateNetworking()); } catch (e) { alert(errMsg(e)); } finally { setBusy(false); }
  };
  const done = (key: string) => !!plan?.done.includes(key);
  const toggle = async (key: string) => { if (plan) setPlan(await svc.markNetworking(plan.id, key, !done(key))); };
  const job = (id: number | null) => plan?.jobs.find(x => x.id === id);
  const jobLabel = (id: number | null) => { const j = job(id); return j ? `${j.job_title} · ${j.company}` : null; };
  const p = plan?.plan;
  const contacts = p?.contacts || [];
  const pursued = (plan?.jobs || []).filter(j => ['applied', 'interviewing', 'offer'].includes(j.status));
  const linkBtn = (href: string, text: string, title?: string) => (
    <a className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} href={href} target="_blank" rel="noreferrer" title={title}><ExternalLink size={13} /> {text}</a>
  );
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={muted}>
          {plan ? <>Plano de {new Date(plan.created_at).toLocaleString()} para {pursued.length} vaga(s) em andamento.</>
            : 'Quem pode te contratar nas vagas em que você se candidatou, com nota de convite e mensagem prontas.'}
          {' '}Abra a vaga no LinkedIn e clique em 📥 CareerOps para trazer o "Meet the hiring team": aí os contatos vêm com nome e perfil.
        </span>
        <button className="btn btn-primary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} disabled={busy} onClick={generate}>
          <Sparkles size={13} /> {busy ? 'Gerando (≈1 min)…' : plan ? 'Gerar novo plano' : 'Gerar plano'}
        </button>
      </div>
      {loaded && !plan && !busy && <p style={muted}>Nenhum plano ainda.</p>}
      {p && !p.contacts && <p style={muted}>Este plano é do formato antigo: gere um novo.</p>}
      {p && p.contacts && <>
        <PlanSection title="Contatos de contratação" hint="convide com a nota; depois do aceite, mande a mensagem" count={contacts.length}>
          {contacts.map((c, i) => (
            <PlanRow key={i} done={done(`contacts:${i}`)} onToggle={() => toggle(`contacts:${i}`)} actions={<>
              <button className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => copy(c.note)} title="Copiar a nota do convite (até 300 caracteres)"><Copy size={13} /> Nota</button>
              <button className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => copy(c.message)} title="Copiar a mensagem para depois do aceite"><Copy size={13} /> Mensagem</button>
              {c.profile_url ? linkBtn(c.profile_url, 'Perfil') : linkBtn(c.url, 'Buscar', `Busca: ${c.search}`)}
            </>}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span style={chip(c.profile_url ? '#00d4aa' : '#9aa4b2')}>{c.profile_url ? 'pessoa' : 'cargo'}</span>
                <strong style={{ whiteSpace: 'nowrap' }}>{c.name || c.role}</strong>
                {c.name && c.role && <span style={{ ...muted, ...clamp(1) }}>{c.role}</span>}
                {c.prospect_status && <span style={chip(STATUS_COLOR[c.prospect_status])}>{STATUS_LABEL[c.prospect_status] || c.prospect_status}</span>}
              </div>
              <div style={{ ...muted, fontSize: '0.78rem' }}>vaga: {jobLabel(c.job_id) || c.company}{c.why ? ` · ${c.why}` : ''}</div>
              <div style={{ fontSize: '0.85rem', marginTop: 4 }}><span style={muted}>Nota: </span>{c.note}</div>
              <details style={{ fontSize: '0.85rem' }}><summary style={{ ...muted, cursor: 'pointer' }}>Mensagem depois do aceite</summary>
                <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{c.message}</div></details>
            </PlanRow>
          ))}
        </PlanSection>
        <PlanSection title="Posts para interagir" hint="atividade do time de contratação e posts que citam a empresa; comente com o ângulo" count={p.posts.length}>
          {p.posts.map((x, i) => (
            <PlanRow key={i} done={done(`posts:${i}`)} onToggle={() => toggle(`posts:${i}`)} actions={<>
              {x.angle && <button className="btn btn-secondary" style={smallBtn} title="Copiar o ângulo (cole como pedido no ✨ Comentário IA)" onClick={() => copy(x.angle || '')}><Copy size={13} /></button>}
              {x.people.map(pp => <React.Fragment key={pp.url}>{linkBtn(pp.url, pp.name.split(' ')[0], `Posts recentes de ${pp.name}`)}</React.Fragment>)}
              {linkBtn(x.url, 'Empresa', `Posts recentes que citam ${x.company}`)}
            </>}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}><strong>{x.company}</strong>{x.job_id && <span style={{ ...muted, ...clamp(1) }}>{job(x.job_id)?.job_title}</span>}</div>
              {x.angle && <div style={{ fontSize: '0.85rem', ...clamp(3) }}>{x.angle}</div>}
              {x.why && <div style={{ ...muted, fontSize: '0.78rem', opacity: 0.75, ...clamp(1) }}>{x.why}</div>}
            </PlanRow>
          ))}
        </PlanSection>
        <PlanSection title="Empresas para seguir" hint="abra a busca e clique em Seguir na página da empresa" count={p.companies.length}>
          {p.companies.map((c, i) => (
            <PlanRow key={i} done={done(`companies:${i}`)} onToggle={() => toggle(`companies:${i}`)} actions={linkBtn(c.url, 'Abrir')}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}><strong>{c.company}</strong>{marketChip(c.market)}{c.similar && <span style={chip('#c38bff')}>similar</span>}</div>
              {c.why && <div style={{ ...muted, ...clamp(2) }}>{c.why}</div>}
              {!!c.job_ids.length && <div style={{ ...muted, fontSize: '0.75rem', opacity: 0.7, ...clamp(1) }}>{[...new Set(c.job_ids.map(jobLabel).filter(Boolean))].join(' · ')}</div>}
            </PlanRow>
          ))}
        </PlanSection>
        <PlanSection title="Pessoas para seguir" hint="referências nos temas das vagas" count={(p.follow || []).length}>
          {(p.follow || []).map((x, i) => (
            <PlanRow key={i} done={done(`follow:${i}`)} onToggle={() => toggle(`follow:${i}`)} actions={linkBtn(x.url, 'Buscar')}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'baseline', flexWrap: 'wrap' }}><strong>{x.role}</strong>{marketChip(x.market)}</div>
              {x.why && <div style={{ ...muted, ...clamp(2) }}>{x.why}</div>}
              <div style={{ ...muted, fontSize: '0.75rem', opacity: 0.7 }}>busca: {x.search}</div>
            </PlanRow>
          ))}
        </PlanSection>
      </>}
    </>
  );
};

// ── Line of thought (what you already said: new texts stay consistent with it) ─
const KIND_LABEL: Record<VoiceKind, string> = { comment: 'comentário', reply: 'resposta', message: 'mensagem', post: 'post', position: 'posição' };

const VoiceTab = () => {
  const [data, setData] = useState<VoiceData | null>(null);
  const [profile, setProfile] = useState('');
  const [q, setQ] = useState('');
  const [kind, setKind] = useState<'all' | VoiceKind>('all');
  const [busy, setBusy] = useState(false);
  const [newPos, setNewPos] = useState({ topic: '', text: '' });
  const [open, setOpen] = useState<number | null>(null);
  const load = useCallback(async (query?: string) => {
    const d = await svc.voice(query);
    setData(d);
    return d;
  }, []);
  useEffect(() => { svc.voice().then(d => { setData(d); setProfile(d.text); }); }, []);
  const consolidate = async () => {
    setBusy(true);
    try { const r = await svc.consolidateVoice(); setProfile(r.text); await load(q); if (r.changes) alert(r.changes); }
    catch (e) { alert(errMsg(e)); } finally { setBusy(false); }
  };
  const addPosition = async () => {
    if (newPos.text.trim().length < 3) return;
    await svc.addPosition(newPos.text.trim(), newPos.topic.trim());
    setNewPos({ topic: '', text: '' });
    load(q);
  };
  const patch = async (v: VoiceItem, change: Partial<Pick<VoiceItem, 'topic' | 'stance' | 'text' | 'pinned'>>) => { await svc.updateVoice(v.id, change); load(q); };
  const remove = async (v: VoiceItem) => { if (confirm('Apagar este registro da linha de pensamento?')) { await svc.deleteVoice(v.id); load(q); } };
  const items = (data?.items || []).filter(v => kind === 'all' || v.kind === kind);
  const count = (k: VoiceKind) => (data?.items || []).filter(v => v.kind === k).length;
  return (
    <>
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: '1rem' }}>Suas posições</h3>
          <span style={muted}>
            {data?.updated_at ? `consolidado em ${new Date(data.updated_at).toLocaleDateString()}` : 'ainda não consolidado'}
            {data && data.new_since_profile > 0 && ` · ${data.new_since_profile} registro(s) novo(s) desde então`}
          </span>
        </div>
        <p style={muted}>Vai em todo comentário, resposta, post e mensagem que a IA escreve, junto com os registros mais parecidos com o assunto. Edite à vontade: o texto é seu.</p>
        <textarea value={profile} onChange={e => setProfile(e.target.value)} rows={10} style={{ ...field, fontSize: '0.85rem' }}
          placeholder="Ex.:&#10;IA em finanças:&#10;- Todo número vem do banco de dados, nunca do modelo — …" />
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" style={smallBtn} disabled={busy || !data?.total} onClick={consolidate}
            title="A IA reescreve as posições a partir de tudo o que você já disse e dos seus pedidos"><Sparkles size={13} /> {busy ? 'Consolidando…' : 'Consolidar com IA'}</button>
          <button className="btn btn-primary" style={smallBtn} disabled={profile === (data?.text ?? '')} onClick={async () => { await svc.saveVoiceProfile(profile); load(q); }}><Check size={13} /> Salvar</button>
        </div>
      </div>
      <div className="panel" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <input value={newPos.topic} onChange={e => setNewPos({ ...newPos, topic: e.target.value })} placeholder="Tema (ex.: concessões de saneamento)" style={{ ...field, width: 220, flex: '0 1 220px', padding: '0.45rem 0.6rem' }} />
        <input value={newPos.text} onChange={e => setNewPos({ ...newPos, text: e.target.value })} placeholder="Sua posição, em uma frase — entra fixa em todos os textos"
          style={{ ...field, flex: '1 1 300px', padding: '0.45rem 0.6rem' }} onKeyDown={e => { if (e.key === 'Enter') addPosition(); }} />
        <button className="btn btn-primary" style={smallBtn} onClick={addPosition}><Plus size={13} /> Posição</button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Pills value={kind} onChange={setKind} items={[
          { id: 'all', label: 'Tudo', count: data?.items.length ?? 0 },
          ...(['position', 'comment', 'reply', 'message', 'post'] as VoiceKind[]).map(k => ({ id: k, label: KIND_LABEL[k], count: count(k) })),
        ]} />
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') load(q); }} placeholder="Buscar por assunto (Enter)"
          style={{ ...field, width: 240, padding: '0.4rem 0.6rem' }} />
      </div>
      <DenseTable head={<><th style={th}>O QUE VOCÊ DISSE</th><th className="hide-sm" style={th}>TIPO</th><th style={{ ...th, textAlign: 'right' }}>AÇÕES</th></>}>
        {items.map(v => (
          <React.Fragment key={v.id}>
            <tr className="row-hover" style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setOpen(open === v.id ? null : v.id)}>
              <td style={{ ...td, maxWidth: 0, width: '100%' }}>
                {(v.topic || v.stance) && <div style={{ fontWeight: 600, ...clamp(1) }}>{v.topic}{v.topic && v.stance && v.kind !== 'position' ? ' — ' : ''}{v.kind !== 'position' && <span style={{ fontWeight: 400 }}>{v.stance}</span>}</div>}
                <div style={{ ...muted, ...clamp(open === v.id ? 20 : 2) }}>{v.text}</div>
                {v.instruction && <div style={{ fontSize: '0.78rem', color: '#ffb020', ...clamp(1) }}>seu pedido: {v.instruction}</div>}
              </td>
              <td className="hide-sm" style={td}><span style={chip(v.kind === 'position' ? '#c38bff' : '#9aa4b2')}>{KIND_LABEL[v.kind]}</span></td>
              <td style={{ ...td, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                  <button className={`btn ${v.pinned ? 'btn-primary' : 'btn-secondary'}`} style={smallBtn} onClick={() => patch(v, { pinned: !v.pinned })}
                    title={v.pinned ? 'Fixo: vai em todos os textos. Clique para soltar' : 'Fixar: vai em todos os textos, qualquer que seja o assunto'}><Pin size={13} /></button>
                  <button className="btn btn-secondary" style={smallBtn} title="Apagar" onClick={() => remove(v)}><Trash2 size={13} /></button>
                </div>
              </td>
            </tr>
            {open === v.id && v.kind !== 'position' && (
              <tr style={{ borderBottom: '1px solid var(--border)' }}><td colSpan={3} style={{ ...td, background: 'rgba(0,0,0,0.15)' }}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <input defaultValue={v.topic || ''} placeholder="Tema" style={{ ...field, flex: '0 1 220px', padding: '0.4rem 0.6rem' }} onBlur={e => e.target.value !== (v.topic || '') && patch(v, { topic: e.target.value })} />
                  <input defaultValue={v.stance || ''} placeholder="Posição que este texto toma" style={{ ...field, flex: '1 1 300px', padding: '0.4rem 0.6rem' }} onBlur={e => e.target.value !== (v.stance || '') && patch(v, { stance: e.target.value })} />
                </div>
                {v.context && <div style={{ ...muted, fontSize: '0.78rem', marginTop: 6, ...clamp(4) }}>em resposta a: {v.context}</div>}
                {v.post_url && <a href={v.post_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', fontSize: '0.8rem' }}>abrir o post</a>}
              </td></tr>
            )}
          </React.Fragment>
        ))}
      </DenseTable>
      {!items.length && <p style={muted}>Nada aqui ainda. Comentários e respostas que você envia pelo LinkedIn (com a extensão), posts publicados e mensagens marcadas como enviadas entram sozinhos.</p>}
    </>
  );
};

// ── Metrics ───────────────────────────────────────────────────────────────
const MANUAL: { key: keyof WeekMetrics; label: string }[] = [
  { key: 'profile_views', label: 'Visitas ao perfil' },
  { key: 'search_appearances', label: 'Aparições em busca' },
  { key: 'post_impressions', label: 'Impressões dos posts' },
  { key: 'recruiter_messages', label: 'Mensagens de recrutador' },
  { key: 'interviews', label: 'Entrevistas' },
];

const MetricsTab = () => {
  const [weeks, setWeeks] = useState<WeekMetrics[]>([]);
  const load = useCallback(async () => setWeeks(await svc.metrics()), []);
  useEffect(() => { svc.metrics().then(setWeeks); }, []);
  const save = async (w: WeekMetrics, key: keyof WeekMetrics, value: string) => {
    const next = { ...w, [key]: value === '' ? null : Number(value) };
    await svc.saveMetrics(w.week_start, Object.fromEntries(MANUAL.map(m => [m.key, next[m.key]]).concat([['notes', next.notes]])));
    load();
  };
  const th: React.CSSProperties = { textAlign: 'left', padding: '0.6rem', ...muted, borderBottom: '1px solid var(--border)' };
  const td: React.CSSProperties = { padding: '0.5rem 0.6rem', borderBottom: '1px solid rgba(255,255,255,0.05)' };
  return (
    <div className="panel" style={{ overflowX: 'auto' }}>
      <p style={{ ...muted, marginBottom: '1rem' }}>
        Posts, comentários e convites são contados automaticamente. Os números do LinkedIn (visitas, buscas, impressões) você copia do painel "Analytics" do perfil uma vez por semana.
      </p>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead><tr>
          <th style={th}>Semana</th><th style={th}>Posts</th><th style={th}>Comentários</th><th style={th}>Convites</th><th style={th}>Aceitos</th>
          {MANUAL.map(m => <th key={m.key} style={th}>{m.label}</th>)}
        </tr></thead>
        <tbody>
          {weeks.map(w => (
            <tr key={w.week_start}>
              <td style={td}>{new Date(w.week_start + 'T12:00:00').toLocaleDateString()}</td>
              <td style={td}>{w.posts}</td><td style={td}>{w.comments}</td><td style={td}>{w.invites}</td><td style={td}>{w.accepted}</td>
              {MANUAL.map(m => (
                <td key={m.key} style={td}>
                  <input type="number" min={0} defaultValue={(w[m.key] as number | null) ?? ''} onBlur={e => save(w, m.key, e.target.value)}
                    style={{ ...field, width: 90, padding: '0.35rem' }} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ── Page ──────────────────────────────────────────────────────────────────
const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'posts', label: 'Posts', icon: <Megaphone size={16} /> },
  { id: 'prospects', label: 'Prospecção', icon: <Users size={16} /> },
  { id: 'networking', label: 'Networking', icon: <Compass size={16} /> },
  { id: 'voice', label: 'Linha de pensamento', icon: <Brain size={16} /> },
  { id: 'metrics', label: 'Métricas', icon: <BarChart3 size={16} /> },
];

const LinkedInCopilot = () => {
  const [params, setParams] = useSearchParams();
  // ?tab=engagement (old links, e.g. from Início) opens the comment queue inside Posts
  const [tab, setTab] = useState<Tab>(() => (TABS.find(t => t.id === params.get('tab'))?.id ?? 'posts'));
  const postsSub: PostsSub = params.get('tab') === 'engagement' ? 'comments' : 'themes';
  const [status, setStatus] = useState<CopilotStatus | null>(null);
  const loadStatus = useCallback(() => svc.status().then(setStatus).catch(() => setStatus(null)), []);
  useEffect(() => { svc.status().then(setStatus).catch(() => setStatus(null)); }, []);
  useEffect(() => {
    const result = params.get('linkedin');
    if (!result) return;
    if (result === 'error') alert(`Falha ao conectar o LinkedIn: ${params.get('reason') || ''}`);
    setParams({}, { replace: true });
    svc.status().then(setStatus).catch(() => setStatus(null));
  }, [params, setParams]);

  return (
    <div className="animate-fade-in copilot-page">
      {/* .panel's own bottom margin doubles the gap between blocks here */}
      <style>{'.copilot-page .panel { margin-bottom: 0; }'}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem 1.5rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, whiteSpace: 'nowrap' }}>LinkedIn Copilot</h1>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TABS.map(t => (
            <button key={t.id} className={`btn ${tab === t.id ? 'btn-primary' : 'btn-secondary'}`} style={{ padding: '0.45rem 0.9rem' }}
              onClick={() => { setTab(t.id); setParams({ tab: t.id }, { replace: true }); }}>{t.icon} {t.label}</button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto' }}><ApiStatus status={status} reload={loadStatus} /></div>
      </div>
      <p style={{ ...muted, marginBottom: '1.2rem' }}>
        A IA rascunha; você aprova. Posts só saem aprovados; convites saem sem nota, um por clique em "Conectar"; comentários e follows você faz no LinkedIn.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {tab === 'posts' && <PostsTab connected={!!status?.connected} initial={postsSub} />}
        {tab === 'prospects' && <ProspectsTab />}
        {tab === 'networking' && <NetworkingTab />}
        {tab === 'voice' && <VoiceTab />}
        {tab === 'metrics' && <MetricsTab />}
      </div>
    </div>
  );
};

export default LinkedInCopilot;
