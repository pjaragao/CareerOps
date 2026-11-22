import React, { useCallback, useEffect, useState } from 'react';
import api from '../services/api';
import { RefreshCw, Plus, ChevronDown, ChevronRight, Radar } from 'lucide-react';

// The daily search beyond LinkedIn (backend: discovery_service.py): per source, what came, what the cheap filter cut,
// what entered, what the triage proposed and what you approved; the health of each source; switches.
type SourceStat = {
  kind: string; label: string; family: 'linkedin' | 'ats' | 'board'; enabled: boolean;
  added: number; triaged: number; proposed: number; approved: number; applied: number;
  fetched: number; filtered: number; duplicates: number; deferred: number; errors: number;
  boards: number; ok: number; failing: number; gone: number; last_ok_at: string | null; last_run_at: string | null; last_error: string | null;
};
type Round = { kind: string; started_at: string; finished_at: string | null; added: number; deferred: number };
type Board = { id: number; kind: string; slug: string; company: string | null; origin: string; enabled: boolean; status: string;
  last_ok_at: string | null; last_error: string | null; jobs_seen: number; jobs_added: number };

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.85rem' };
const th: React.CSSProperties = { textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: 'var(--text-muted)', fontSize: '0.75rem', whiteSpace: 'nowrap' };
const td: React.CSSProperties = { textAlign: 'right', padding: '6px 8px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' };
const FAMILY = { linkedin: 'LinkedIn', ats: 'Site da empresa (1×/dia, 6h)', board: 'Site de vagas (6h e 14h)' };
const ORIGIN: Record<string, string> = { applied: 'candidatura', probe: 'achada pelo nome', board: 'indicada por site de vagas', catalog: 'catálogo', manual: 'você' };

const when = (iso: string | null): string => {
  if (!iso) return '—';
  const h = Math.round((Date.now() - new Date(iso).getTime()) / 3600000);
  return h < 1 ? 'agora' : h < 48 ? `há ${h} h` : `há ${Math.round(h / 24)} d`;
};
const health = (s: SourceStat): { color: string; text: string } => {
  if (s.family === 'linkedin') return { color: 'var(--text-muted)', text: 'buscas do LinkedIn' };
  if (!s.enabled) return { color: 'var(--text-muted)', text: 'desligada' };
  if (s.last_error === 'sem chave da API') return { color: 'var(--text-muted)', text: 'sem chave da API' };
  if (s.family === 'ats') return { color: s.failing ? '#ffb020' : '#3fb950', text: `${s.ok} empresas ok${s.failing ? `, ${s.failing} com erro` : ''}${s.gone ? `, ${s.gone} saíram` : ''}` };
  if (s.failing) return { color: '#f85149', text: 'com erro' };
  return s.last_ok_at ? { color: '#3fb950', text: `ok ${when(s.last_ok_at)}` } : { color: 'var(--text-muted)', text: 'ainda não lida' };
};

const Boards = ({ kind }: { kind: string }) => {
  const [items, setItems] = useState<Board[] | null>(null);
  const load = useCallback(() => { api.get<{ items: Board[] }>('/job-searches/sources', { params: { kind } }).then(({ data }) => setItems(data.items)).catch(() => setItems([])); }, [kind]);
  useEffect(load, [load]);
  if (!items) return <p style={muted}>Carregando…</p>;
  if (!items.length) return <p style={muted}>Nenhuma empresa ainda: a lista se monta na próxima leitura.</p>;
  return (
    <div style={{ maxHeight: 320, overflowY: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
        <tbody>
          {items.map(b => (
            <tr key={b.id} style={{ borderTop: '1px solid var(--border)', opacity: b.enabled && b.status !== 'gone' ? 1 : 0.5 }}>
              <td style={{ padding: '5px 8px' }}>
                <strong>{b.company || b.slug}</strong> <span style={muted}>· {ORIGIN[b.origin] || b.origin}</span>
                {b.last_error && <div style={{ ...muted, fontSize: '0.75rem', color: b.status === 'gone' ? 'var(--text-muted)' : '#ffb020' }}>{b.status === 'gone' ? 'Saiu deste sistema de vagas' : b.last_error}</div>}
              </td>
              <td style={td}>{b.jobs_seen} abertas</td>
              <td style={td}>{b.jobs_added} novas</td>
              <td style={{ ...td, width: 1 }}>
                <input type="checkbox" checked={b.enabled} title="Ler esta empresa todo dia"
                  onChange={(e) => api.put(`/job-searches/sources/${b.id}`, { enabled: e.target.checked }).then(load)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const SourcesPanel = () => {
  const [stats, setStats] = useState<SourceStat[] | null>(null);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [err, setErr] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [link, setLink] = useState('');
  const [msg, setMsg] = useState('');
  const load = useCallback(() => {
    api.get<{ sources: SourceStat[]; rounds: Round[] }>('/job-searches/sources/stats', { params: { days: 7 } })
      .then(({ data }) => { setStats(data.sources); setRounds(data.rounds); setErr(''); })
      .catch((e) => setErr(e?.response?.status === 401 ? 'Token recusado: confira em Configurações → Acesso.' : 'Não consegui carregar as fontes.'));
  }, []);
  useEffect(load, [load]);

  const toggle = (kind: string, enabled: boolean) => api.put(`/job-searches/sources/kinds/${kind}`, { enabled }).then(load);
  const run = (family: 'ats' | 'board') => api.post(`/job-searches/sources/run/${family}`)
    .then(() => { setMsg(family === 'ats' ? 'Lendo os sites das empresas… os números aparecem aqui em alguns minutos.' : 'Lendo os sites de vagas…'); setTimeout(load, 60000); })
    .catch(() => setMsg('Não consegui começar a leitura.'));
  const add = () => api.post('/job-searches/sources', { url: link })
    .then(({ data }) => { setMsg(`${data.company || data.slug} entra na leitura diária (${data.kind}).`); setLink(''); load(); })
    .catch((e) => setMsg(e?.response?.data?.detail || 'Link não reconhecido.'));

  const total = (stats || []).reduce((a, s) => ({ added: a.added + s.added, proposed: a.proposed + s.proposed, approved: a.approved + s.approved }), { added: 0, proposed: 0, approved: 0 });
  const families: Array<'linkedin' | 'ats' | 'board'> = ['ats', 'board', 'linkedin'];

  return (
    <div className="panel" style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: '0.6rem' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}><Radar size={18} /> Fontes da busca diária</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => run('ats')}><RefreshCw size={14} /> Ler empresas agora</button>
          <button className="btn btn-secondary" onClick={() => run('board')}><RefreshCw size={14} /> Ler sites de vagas agora</button>
        </div>
      </div>
      <p style={{ ...muted, marginBottom: '0.8rem' }}>
        Além do LinkedIn, o sistema lê todo dia os sites de vagas das empresas (Greenhouse, Lever, Ashby…) e sites de vagas remotas. Um filtro sem IA
        deixa passar só cargo do seu perfil, local possível a partir do Brasil (ou com visto) e idioma que você usa; o resto passa pela mesma triagem.
        Últimos 7 dias: <strong style={{ color: '#fff' }}>{total.added}</strong> vagas novas, <strong style={{ color: '#fff' }}>{total.proposed}</strong> propostas,{' '}
        <strong style={{ color: '#fff' }}>{total.approved}</strong> aprovadas por você.
      </p>
      {err && <p style={{ ...muted, color: '#f85149' }}>{err}</p>}
      {msg && <p style={{ ...muted, color: 'var(--accent)' }}>{msg}</p>}
      {stats && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th style={{ ...th, textAlign: 'left' }}>Fonte</th>
                <th style={th} title="Vagas lidas nas fontes">Lidas</th>
                <th style={th} title="Cortadas pelo filtro sem IA (cargo, local, idioma, data)">Filtradas</th>
                <th style={th} title="Já estavam aqui por outra fonte">Repetidas</th>
                <th style={th} title="Entraram para a triagem">Novas</th>
                <th style={th} title="Foram para a sua lista de aprovação">Propostas</th>
                <th style={th}>Aprovadas</th>
                <th style={{ ...th, textAlign: 'left' }}>Estado</th>
                <th style={th}>Ligada</th>
              </tr>
            </thead>
            {families.map(fam => (
              <tbody key={fam}>
                <tr><td colSpan={9} style={{ padding: '10px 8px 4px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.04em' }}>{FAMILY[fam]}</td></tr>
                {stats.filter(s => s.family === fam).map(s => {
                  const h = health(s);
                  const canOpen = s.family === 'ats';
                  return (
                    <React.Fragment key={s.kind}>
                      <tr style={{ borderTop: '1px solid var(--border)', opacity: s.enabled ? 1 : 0.55, cursor: canOpen ? 'pointer' : 'default' }}
                        onClick={() => canOpen && setOpen(open === s.kind ? null : s.kind)}>
                        <td style={{ ...td, textAlign: 'left', fontWeight: 600 }}>
                          {canOpen && (open === s.kind ? <ChevronDown size={13} /> : <ChevronRight size={13} />)} {s.label}
                          {canOpen && <span style={{ ...muted, fontWeight: 400 }}> · {s.boards}</span>}
                        </td>
                        <td style={td}>{s.family === 'linkedin' ? '—' : s.fetched}</td>
                        <td style={td}>{s.family === 'linkedin' ? '—' : s.filtered}</td>
                        <td style={td}>{s.family === 'linkedin' ? '—' : s.duplicates}</td>
                        <td style={{ ...td, color: '#fff' }}>{s.added}</td>
                        <td style={{ ...td, color: '#fff' }}>{s.proposed}</td>
                        <td style={td}>{s.approved}</td>
                        <td style={{ ...td, textAlign: 'left', color: h.color }} title={s.last_error || ''}>{h.text}</td>
                        <td style={td} onClick={(e) => e.stopPropagation()}>
                          {s.family !== 'linkedin' && <input type="checkbox" checked={s.enabled} onChange={(e) => toggle(s.kind, e.target.checked)} />}
                        </td>
                      </tr>
                      {open === s.kind && <tr><td colSpan={9} style={{ padding: '4px 8px 10px' }}><Boards kind={s.kind} /></td></tr>}
                    </React.Fragment>
                  );
                })}
              </tbody>
            ))}
          </table>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: '0.9rem' }}>
        <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="Link de uma vaga da empresa (Greenhouse, Lever, Ashby, Workday…) para acompanhar"
          style={{ flex: 1, minWidth: 0 }} />
        <button className="btn btn-primary" disabled={link.length < 10} onClick={add}><Plus size={14} /> Acompanhar</button>
      </div>
      {rounds.length > 0 && (
        <p style={{ ...muted, marginTop: '0.6rem', fontSize: '0.78rem' }}>
          Últimas leituras: {rounds.slice(0, 4).map(r => `${r.kind === 'round:ats' ? 'empresas' : 'sites de vagas'} ${when(r.started_at)} (+${r.added}${r.deferred ? `, ${r.deferred} para amanhã` : ''})`).join(' · ')}
        </p>
      )}
    </div>
  );
};

export default SourcesPanel;
