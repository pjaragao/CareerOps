import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Megaphone, Sparkles, Send, Check, X, Copy, ExternalLink, Calendar, Users, MessageCircle, BarChart3, Link2, Plus, Undo2,
} from 'lucide-react';
import {
  linkedinCopilotService as svc, CopilotPost, CopilotStatus, Market, Inspiration, EngagementItem, Prospect, ProspectStatus, WeekMetrics,
} from '../services/linkedinCopilotService';

type Tab = 'posts' | 'engagement' | 'prospects' | 'metrics';

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

// ── Connection banner ─────────────────────────────────────────────────────
const ConnectionBar = ({ status, reload }: { status: CopilotStatus | null; reload: () => void }) => {
  if (!status) return null;
  const connect = async () => {
    try { window.location.href = await svc.connectUrl(); } catch (e) { alert(errMsg(e)); }
  };
  return (
    <div className="panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '1rem 1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: status.connected ? '#00d4aa' : '#ff6b6b' }} />
        {status.connected ? (
          <span>Publicação conectada como <strong>{status.member_name}</strong>
            <span style={muted}> · expira em {status.expires_at ? new Date(status.expires_at).toLocaleDateString() : '?'}</span></span>
        ) : status.configured ? (
          <span>API do LinkedIn não conectada. Sem conexão, você copia o post e marca como publicado.</span>
        ) : (
          <span>API do LinkedIn não configurada (defina <code>LINKEDIN_CLIENT_ID</code> e <code>LINKEDIN_CLIENT_SECRET</code>). Até lá, copie e publique manualmente.</span>
        )}
      </div>
      {status.configured && (status.connected
        ? <button className="btn btn-secondary" onClick={async () => { await svc.disconnect(); reload(); }}>Desconectar</button>
        : <button className="btn btn-primary" onClick={connect}><Link2 size={16} /> Conectar LinkedIn</button>)}
    </div>
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
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
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

const PostsTab = ({ connected }: { connected: boolean }) => {
  const [posts, setPosts] = useState<CopilotPost[]>([]);
  const [market, setMarket] = useState<Market>('intl');
  const [form, setForm] = useState({ count: 2, pillar: '', topic: '', source_notes: '' });
  const [loading, setLoading] = useState(false);
  const [inspirations, setInspirations] = useState<Inspiration[]>([]);
  const load = useCallback(async () => setPosts(await svc.listPosts()), []);
  const loadInspirations = useCallback(async () => setInspirations(await svc.inspirations()), []);
  useEffect(() => { svc.listPosts().then(setPosts); svc.inspirations().then(setInspirations).catch(() => setInspirations([])); }, []);
  const fromInspiration = async (id: number) => {
    setLoading(true);
    try { await svc.generatePosts({ market, count: 1, inspiration_id: id }); await load(); await loadInspirations(); }
    catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  const generate = async () => {
    setLoading(true);
    try {
      await svc.generatePosts({ market, count: form.count, pillar: form.pillar || undefined, topic: form.topic || undefined, source_notes: form.source_notes || undefined });
      await load();
    } catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  return (
    <>
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: 8, flexWrap: 'wrap' }}>
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
        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 1fr', gap: '1rem' }}>
          <select value={form.count} onChange={e => setForm({ ...form, count: Number(e.target.value) })} style={field}>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n} style={{ color: '#000' }}>{n} post{n > 1 ? 's' : ''}</option>)}
          </select>
          <select value={form.pillar} onChange={e => setForm({ ...form, pillar: e.target.value })} style={field}>
            <option value="" style={{ color: '#000' }}>Pilar: rodízio automático</option>
            {Object.entries(PILLARS[market]).map(([k, v]) => <option key={k} value={k} style={{ color: '#000' }}>{k} · {v}</option>)}
          </select>
          <input value={form.topic} onChange={e => setForm({ ...form, topic: e.target.value })} placeholder="Tema (opcional)" style={field} />
          <textarea value={form.source_notes} onChange={e => setForm({ ...form, source_notes: e.target.value })} rows={4}
            placeholder="Material novo (opcional): commits da semana, um resultado, uma lição de obra ou de orçamento… A IA usa isso como fonte principal."
            style={{ ...field, gridColumn: 'span 3', resize: 'vertical' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button className="btn btn-primary" onClick={generate} disabled={loading}><Sparkles size={16} /> {loading ? 'Gerando…' : 'Gerar'}</button>
        </div>
      </div>
      {inspirations.length > 0 && (
        <div className="panel">
          <h3 style={{ marginBottom: '0.6rem' }}>📌 Temas salvos ({inspirations.length})</h3>
          <p style={{ ...muted, marginBottom: '0.8rem' }}>
            Posts que você salvou no feed pela extensão. "Gerar post" escreve um post seu ({MARKET_LABEL[market]}) sobre o mesmo tema, a partir da sua experiência — sem copiar o original.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {inspirations.map(i => (
              <div key={i.id} style={{ display: 'flex', gap: 12, alignItems: 'center', background: 'rgba(0,0,0,0.2)', padding: '0.6rem 0.8rem', borderRadius: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ fontSize: '0.85rem' }}>{i.author_name || 'Autor desconhecido'}</strong>
                  {i.used_count > 0 && <span style={{ ...muted, marginLeft: 6 }}>· usado {i.used_count}x</span>}
                  <div style={{ ...muted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{i.post_text}</div>
                </div>
                {i.post_url && <a className="btn btn-secondary" href={i.post_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /></a>}
                <button className="btn btn-primary" disabled={loading} onClick={() => fromInspiration(i.id)}><Sparkles size={14} /> Gerar post</button>
                <button className="btn btn-secondary" style={{ color: 'var(--error)' }}
                  onClick={async () => { await svc.deleteInspiration(i.id); loadInspirations(); }}><X size={14} /></button>
              </div>
            ))}
          </div>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(480px, 1fr))', gap: '1.5rem' }}>
        {posts.map(p => <PostCard key={`${p.id}-${p.status}-${p.body.length}`} post={p} connected={connected} onChange={load} />)}
      </div>
      {!posts.length && <p style={muted}>Nenhum rascunho ainda.</p>}
    </>
  );
};

// ── Engagement ────────────────────────────────────────────────────────────
const EngagementTab = () => {
  const [data, setData] = useState<{ items: EngagementItem[]; done_today: number; daily_target: number }>({ items: [], done_today: 0, daily_target: 10 });
  const [form, setForm] = useState({ post_text: '', post_url: '', author_name: '' });
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => setData(await svc.engagementQueue()), []);
  useEffect(() => { svc.engagementQueue().then(setData); }, []);
  const add = async () => {
    if (form.post_text.trim().length < 20) return;
    setLoading(true);
    try {
      const item = await svc.addEngagement({ post_text: form.post_text, post_url: form.post_url || undefined, author_name: form.author_name || undefined });
      if (item.status === 'skipped') alert(`A IA sugere pular (relevância ${item.relevance}): ${item.reason}`);
      setForm({ post_text: '', post_url: '', author_name: '' });
      await load();
    } catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  const mark = async (id: number, status: 'done' | 'skipped', comment?: string) => {
    await svc.updateEngagement(id, { status, ...(comment !== undefined ? { comment_draft: comment } : {}) });
    load();
  };
  return (
    <>
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Plus size={18} /> Adicionar post à fila</h3>
          <span style={muted}>Hoje: <strong style={{ color: '#fff' }}>{data.done_today}</strong> / {data.daily_target} comentários</span>
        </div>
        <p style={{ ...muted, marginBottom: '0.8rem' }}>
          Mais rápido pela extensão: selecione o texto do post no LinkedIn → botão direito → <em>Enviar ao CareerOps Copilot</em>
          (clique com o botão direito no horário do post para levar o link junto).
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <input value={form.post_url} onChange={e => setForm({ ...form, post_url: e.target.value })} placeholder="Link do post (opcional)" style={field} />
          <input value={form.author_name} onChange={e => setForm({ ...form, author_name: e.target.value })} placeholder="Autor (opcional)" style={field} />
          <textarea value={form.post_text} onChange={e => setForm({ ...form, post_text: e.target.value })} rows={4} placeholder="Texto do post"
            style={{ ...field, gridColumn: 'span 2', resize: 'vertical' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button className="btn btn-primary" onClick={add} disabled={loading}>{loading ? 'Analisando…' : 'Analisar e rascunhar comentário'}</button>
        </div>
      </div>
      {data.items.map(item => <EngagementCard key={item.id} item={item} onMark={mark} />)}
      {!data.items.length && <p style={muted}>Fila vazia. Capture posts de pessoas da sua área-alvo enquanto navega.</p>}
    </>
  );
};

const EngagementCard = ({ item, onMark }: { item: EngagementItem; onMark: (id: number, s: 'done' | 'skipped', c?: string) => void }) => {
  const [comment, setComment] = useState(item.comment_draft || '');
  return (
    <div className="panel" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      <div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
          <span style={chip('#00d4aa')}>{item.relevance ?? '?'}</span>
          <strong>{item.author_name || 'Autor desconhecido'}</strong>
        </div>
        {item.reason && <p style={{ ...muted, marginBottom: 8 }}>{item.reason}</p>}
        <div style={{ ...muted, maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.2)', padding: '0.8rem', borderRadius: 10 }}>{item.post_text}</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <textarea value={comment} onChange={e => setComment(e.target.value)} rows={6} style={{ ...field, resize: 'vertical' }} />
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => copy(comment)}><Copy size={15} /> Copiar</button>
          {item.post_url && <a className="btn btn-secondary" href={item.post_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Abrir post</a>}
          <button className="btn btn-secondary" onClick={() => onMark(item.id, 'skipped')}>Pular</button>
          <button className="btn btn-primary" onClick={() => onMark(item.id, 'done', comment)}><Check size={15} /> Comentei</button>
        </div>
      </div>
    </div>
  );
};

// ── Prospects ─────────────────────────────────────────────────────────────
const NEXT_STATUS: Partial<Record<ProspectStatus, { to: ProspectStatus; label: string }[]>> = {
  to_contact: [{ to: 'invited', label: 'Convite enviado' }, { to: 'skipped', label: 'Pular' }],
  invited: [{ to: 'accepted', label: 'Aceitou' }, { to: 'replied', label: 'Respondeu' }],
  accepted: [{ to: 'replied', label: 'Respondeu' }],
};

const ProspectsTab = () => {
  const [data, setData] = useState<{ items: Prospect[]; invited_this_week: number; weekly_target: number }>({ items: [], invited_this_week: 0, weekly_target: 20 });
  const [form, setForm] = useState({ profile_text: '', profile_url: '', name: '' });
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => setData(await svc.prospects()), []);
  useEffect(() => { svc.prospects().then(setData); }, []);
  const add = async () => {
    if (form.profile_text.trim().length < 20) return;
    setLoading(true);
    try {
      const p = await svc.addProspect({ profile_text: form.profile_text, profile_url: form.profile_url || undefined, name: form.name || undefined });
      if (p.status === 'skipped') alert(`A IA sugere pular (fit ${p.fit}): ${p.reason}`);
      setForm({ profile_text: '', profile_url: '', name: '' });
      await load();
    } catch (e) { alert(errMsg(e)); } finally { setLoading(false); }
  };
  const update = async (id: number, patch: Partial<Pick<Prospect, 'status' | 'note_draft'>>) => { await svc.updateProspect(id, patch); load(); };
  return (
    <>
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Plus size={18} /> Adicionar pessoa</h3>
          <span style={muted}>Semana: <strong style={{ color: '#fff' }}>{data.invited_this_week}</strong> / {data.weekly_target} convites</span>
        </div>
        <p style={{ ...muted, marginBottom: '0.8rem' }}>
          Pela extensão: abra o perfil → botão direito na página → <em>Enviar ao CareerOps Copilot</em>.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <input value={form.profile_url} onChange={e => setForm({ ...form, profile_url: e.target.value })} placeholder="Link do perfil" style={field} />
          <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Nome (opcional)" style={field} />
          <textarea value={form.profile_text} onChange={e => setForm({ ...form, profile_text: e.target.value })} rows={4}
            placeholder="Headline, empresa, about… (cole o que tiver)" style={{ ...field, gridColumn: 'span 2', resize: 'vertical' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button className="btn btn-primary" onClick={add} disabled={loading}>{loading ? 'Analisando…' : 'Analisar e rascunhar convite'}</button>
        </div>
      </div>
      {data.items.map(p => <ProspectCard key={`${p.id}-${p.status}`} p={p} onUpdate={update} />)}
      {!data.items.length && <p style={muted}>Nenhuma pessoa na lista ainda.</p>}
    </>
  );
};

const ProspectCard = ({ p, onUpdate }: { p: Prospect; onUpdate: (id: number, patch: Partial<Pick<Prospect, 'status' | 'note_draft'>>) => void }) => {
  const [note, setNote] = useState(p.note_draft || '');
  return (
    <div className="panel" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      <div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
          <span style={chip(STATUS_COLOR[p.status])}>{p.status}</span>
          <span style={chip('#00d4aa')}>fit {p.fit ?? '?'}</span>
          {p.market && <span style={chip(p.market === 'br' ? '#00b894' : '#4da3ff')}>{MARKET_LABEL[p.market]}</span>}
          {p.segment && <span style={chip('#ffb020')}>{p.segment}</span>}
        </div>
        <strong>{p.name || 'Sem nome'}</strong>
        <div style={muted}>{[p.headline, p.company].filter(Boolean).join(' · ')}</div>
        {p.reason && <p style={{ ...muted, marginTop: 8 }}>{p.reason}</p>}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <textarea value={note} onChange={e => setNote(e.target.value.slice(0, 300))} rows={4} style={{ ...field, resize: 'vertical' }} />
        <div style={{ ...muted, textAlign: 'right' }}>{note.length}/300</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => copy(note)}><Copy size={15} /> Copiar nota</button>
          {p.profile_url && <a className="btn btn-secondary" href={p.profile_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Abrir perfil</a>}
          {(NEXT_STATUS[p.status] || []).map(n => (
            <button key={n.to} className={n.to === 'skipped' ? 'btn btn-secondary' : 'btn btn-primary'}
              onClick={() => onUpdate(p.id, { status: n.to, ...(note !== (p.note_draft || '') ? { note_draft: note } : {}) })}>{n.label}</button>
          ))}
        </div>
      </div>
    </div>
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
  { id: 'engagement', label: 'Engajamento', icon: <MessageCircle size={16} /> },
  { id: 'prospects', label: 'Prospecção', icon: <Users size={16} /> },
  { id: 'metrics', label: 'Métricas', icon: <BarChart3 size={16} /> },
];

const LinkedInCopilot = () => {
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (TABS.find(t => t.id === params.get('tab'))?.id ?? 'posts'));
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
    <div className="animate-fade-in">
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>LinkedIn Copilot</h1>
        <p style={{ color: 'var(--text-muted)' }}>
          A IA rascunha; você aprova. Só posts aprovados são publicados pela API oficial — comentários, conexões e follows você faz no LinkedIn.
        </p>
      </div>
      <ConnectionBar status={status} reload={loadStatus} />
      <div style={{ display: 'flex', gap: 8, margin: '1.5rem 0' }}>
        {TABS.map(t => (
          <button key={t.id} className={`btn ${tab === t.id ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setTab(t.id)}>{t.icon} {t.label}</button>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {tab === 'posts' && <PostsTab connected={!!status?.connected} />}
        {tab === 'engagement' && <EngagementTab />}
        {tab === 'prospects' && <ProspectsTab />}
        {tab === 'metrics' && <MetricsTab />}
      </div>
    </div>
  );
};

export default LinkedInCopilot;
