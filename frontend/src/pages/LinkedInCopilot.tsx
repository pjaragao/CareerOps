import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Megaphone, Sparkles, Send, Check, X, Copy, ExternalLink, Calendar, Users, BarChart3, Link2, Plus, Undo2, UserPlus,
} from 'lucide-react';
import {
  linkedinCopilotService as svc, CopilotPost, PostStatus, CopilotStatus, Market, Inspiration, EngagementItem, Prospect, ProspectStatus, WeekMetrics,
} from '../services/linkedinCopilotService';

type Tab = 'posts' | 'prospects' | 'metrics';

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
const Modal = ({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) => (
  <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
    <div className="panel" onClick={e => e.stopPropagation()} style={{ width: 'min(640px, 100%)', maxHeight: '90vh', overflow: 'auto', marginBottom: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3>{title}</h3>
        <button className="btn btn-secondary" style={{ padding: 6 }} onClick={onClose}><X size={16} /></button>
      </div>
      {children}
    </div>
  </div>
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
const themeLink = (i: Inspiration) => i.post_url
  || `https://www.linkedin.com/search/results/content/?keywords=${encodeURIComponent(i.post_text.split('\n')[0].slice(0, 80))}`;

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
                  title={i.post_url ? 'Abrir o post no LinkedIn' : 'Sem link salvo: buscar o post no LinkedIn'}><ExternalLink size={15} /></a>
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
          {(NEXT_STATUS[p.status] || []).map(n => (
            <button key={n.to} className="btn btn-secondary" style={{ ...smallBtn, whiteSpace: 'nowrap' }} onClick={() => onUpdate(p.id, { status: n.to })}>{n.label}</button>
          ))}
        </div>
      </td>
    </tr>
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
        {tab === 'metrics' && <MetricsTab />}
      </div>
    </div>
  );
};

export default LinkedInCopilot;
