import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { jobService, Job } from '../services/jobService';
import {
  Plus, MapPin, Trash2, LayoutDashboard, List as ListIcon, ExternalLink, Rocket, FileText, Mail, MessageSquare,
  Search, ChevronDown, ChevronLeft, ChevronRight, ArrowUpDown, Check, X, AlertTriangle,
} from 'lucide-react';
import JobDetail, { JobTab, JobAction } from '../components/JobDetail';
import NewJobModal from '../components/NewJobModal';

// ── Status: one source for labels and colours (list, filters, menu, kanban) ─────────────────────────────────────
const STATUS: { id: string; label: string; color: string }[] = [
  { id: 'new', label: 'Avaliar', color: '#f5c542' },
  { id: 'scraped', label: 'Captada', color: '#8b85ff' },
  { id: 'applied', label: 'Candidatado', color: '#00c853' },
  { id: 'interviewing', label: 'Entrevista', color: '#00b0ff' },
  { id: 'offer', label: 'Proposta', color: '#c77dff' },
  { id: 'rejected', label: 'Recusada', color: '#ff5c5c' },
  { id: 'archived', label: 'Arquivada', color: '#7a7a90' },
];
const statusOf = (id: string) => STATUS.find(s => s.id === id) || { id, label: id, color: '#7a7a90' };

type SortKey = 'recent' | 'oldest' | 'updated' | 'company' | 'title' | 'status' | 'score';
const SORTS: { id: SortKey; label: string }[] = [
  { id: 'recent', label: 'Mais recentes' }, { id: 'updated', label: 'Atualizadas por último' }, { id: 'oldest', label: 'Mais antigas' },
  { id: 'score', label: 'Melhor avaliação' }, { id: 'status', label: 'Status (funil)' }, { id: 'company', label: 'Empresa A–Z' },
  { id: 'title', label: 'Cargo A–Z' },
];
type DocFilter = 'all' | 'with' | 'without';

const time = (d?: string | null) => (d ? new Date(d).getTime() : 0);
const ago = (d?: string | null) => {
  if (!d) return '';
  const days = Math.floor((Date.now() - time(d)) / 86400000);
  if (days <= 0) return 'hoje';
  if (days === 1) return 'ontem';
  if (days < 30) return `${days} d`;
  return new Date(d).toLocaleDateString();
};
const jobLink = (job: Job) => (job.url ? (job.url.startsWith('http') ? job.url : `https://${job.url}`) : '');

// remembered per browser; storage may be blocked (private mode): the page works without it
const saved = <T,>(key: string, fallback: T): T => {
  try { const v = localStorage.getItem(`jobBoard.${key}`); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
};
const remember = (key: string, value: unknown) => { try { localStorage.setItem(`jobBoard.${key}`, JSON.stringify(value)); } catch { /* not remembered */ } };

const css = `
.jb-chip{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);font-size:.76rem;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .15s}
.jb-chip:hover{border-color:rgba(255,255,255,.18);color:#fff}
.jb-chip.on{background:rgba(108,99,255,.16);border-color:rgba(108,99,255,.55);color:#fff}
.jb-chip .n{font-size:.7rem;opacity:.7}
.jb-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.jb-pill{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px 0 9px;border-radius:999px;font-size:.72rem;font-weight:700;border:1px solid transparent;cursor:pointer;transition:filter .15s, border-color .15s;white-space:nowrap}
.jb-pill:hover{filter:brightness(1.25);border-color:rgba(255,255,255,.15)}
.jb-row{border-bottom:1px solid var(--border);cursor:pointer;transition:background .12s}
.jb-row:hover{background:rgba(255,255,255,.025)}
.jb-row .jb-acts{opacity:.35;transition:opacity .15s}
.jb-row:hover .jb-acts{opacity:1}
.jb-icon{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);cursor:pointer;transition:all .15s}
.jb-icon:hover{color:#fff;border-color:rgba(255,255,255,.2);background:rgba(255,255,255,.07)}
.jb-icon.primary{background:linear-gradient(135deg,var(--accent),var(--accent-light));color:#fff;border-color:transparent}
.jb-icon.danger:hover{color:#ff5c5c;border-color:rgba(255,92,92,.4)}
.jb-th{padding:.7rem 1rem;text-align:left;color:var(--text-muted);font-size:.68rem;font-weight:700;letter-spacing:.06em;white-space:nowrap}
.jb-td{padding:.75rem 1rem;vertical-align:middle}
.jb-select{height:32px;padding:0 30px 0 10px;width:auto;font-size:.76rem;border-radius:9px;appearance:none;-webkit-appearance:none;cursor:pointer;background:rgba(255,255,255,.04) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23a0a0c0' fill='none' stroke-width='1.5'/%3E%3C/svg%3E") no-repeat right 10px center}
.jb-menu{position:fixed;z-index:10001;min-width:180px;padding:6px;border-radius:12px;background:#171723;border:1px solid rgba(255,255,255,.1);box-shadow:0 18px 40px rgba(0,0,0,.55);animation:jbPop .12s ease-out}
.jb-menu button{display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;border:none;background:none;color:var(--text-main);font-size:.8rem;border-radius:8px;cursor:pointer;text-align:left}
.jb-menu button:hover{background:rgba(255,255,255,.06)}
.jb-page{min-width:32px;height:32px;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);font-size:.78rem;font-weight:600;cursor:pointer}
.jb-page.on{background:rgba(108,99,255,.2);border-color:rgba(108,99,255,.6);color:#fff}
.jb-page:disabled{opacity:.35;cursor:default}
@keyframes jbPop{from{opacity:0;transform:translateY(-4px) scale(.98)}to{opacity:1;transform:none}}
@media (max-width: 760px){.jb-hide-sm{display:none}}
`;

// Status menu: opens under the pill, on top of everything (portal), closes on click outside, scroll or Esc
const StatusMenu = ({ anchor, current, onPick, onClose }: { anchor: DOMRect; current: string; onPick: (s: string) => void; onClose: () => void }) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const away = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose(); };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', key);
    window.addEventListener('scroll', onClose, true);
    window.addEventListener('resize', onClose);
    return () => {
      document.removeEventListener('mousedown', away); document.removeEventListener('keydown', key);
      window.removeEventListener('scroll', onClose, true); window.removeEventListener('resize', onClose);
    };
  }, [onClose]);
  const height = STATUS.length * 36 + 12;
  const top = anchor.bottom + 6 + height > window.innerHeight ? anchor.top - 6 - height : anchor.bottom + 6;
  return createPortal(
    <div ref={ref} className="jb-menu" style={{ top, left: Math.min(anchor.left, window.innerWidth - 200) }} onClick={e => e.stopPropagation()}>
      {STATUS.map(s => (
        <button key={s.id} onClick={() => { onPick(s.id); onClose(); }}>
          <span className="jb-dot" style={{ background: s.color }} /> {s.label}
          {s.id === current && <Check size={14} style={{ marginLeft: 'auto', color: 'var(--accent-light)' }} />}
        </button>
      ))}
    </div>,
    document.body,
  );
};

const StatusPill = ({ status, onClick }: { status: string; onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void }) => {
  const s = statusOf(status);
  return (
    <button className="jb-pill" onClick={onClick} title="Mudar o status" style={{ background: `${s.color}1f`, color: s.color }}>
      <span className="jb-dot" style={{ background: s.color }} /> {s.label} {onClick && <ChevronDown size={12} style={{ opacity: 0.7 }} />}
    </button>
  );
};

// The ad asks to live in a region / for a work visa the candidate lacks: red = requirement, yellow = soft or unclear
const ELIGIBILITY_LABEL = { residency: 'Residência', work_authorization: 'Visto' } as const;
export const EligibilityBadge = ({ job }: { job: Job }) => {
  if (job.eligibility_status !== 'blocked' && job.eligibility_status !== 'warning') return null;
  const issues = job.eligibility_issues || [];
  const color = job.eligibility_status === 'blocked' ? '#ff5c5c' : '#f5c542';
  const kinds = [...new Set(issues.map(i => ELIGIBILITY_LABEL[i.type] || i.type))].join(' + ') || 'Elegibilidade';
  const tip = issues.map(i => `"${i.quote}"${i.reason ? ` — ${i.reason}` : ''}`).join('\n');
  return (
    <span title={tip} style={{ display: 'inline-flex', alignItems: 'center', gap: 3, flexShrink: 0, padding: '1px 6px', borderRadius: 6, fontSize: '0.66rem',
      fontWeight: 800, color, background: `${color}1f`, border: `1px solid ${color}55` }}>
      <AlertTriangle size={10} /> {kinds}
    </span>
  );
};

const JobBoard = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>(() => saved('view', 'table'));
  const [statusFilter, setStatusFilter] = useState<string>(() => saved('status', 'active'));
  const [docFilter, setDocFilter] = useState<DocFilter>(() => saved('docs', 'all'));
  const [sort, setSort] = useState<SortKey>(() => saved('sort', 'recent'));
  const [pageSize, setPageSize] = useState<number>(() => saved('pageSize', 25));
  const [query, setQuery] = useState('');
  // the page belongs to the filters it was chosen under: other filters start at page 1
  const [pageState, setPageState] = useState({ key: '', page: 1 });
  const [menu, setMenu] = useState<{ job: Job; rect: DOMRect } | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selected, setSelected] = useState<{ job: Job; tab?: JobTab; action?: JobAction } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { remember('view', viewMode); }, [viewMode]);
  useEffect(() => { remember('status', statusFilter); remember('docs', docFilter); remember('sort', sort); remember('pageSize', pageSize); },
    [statusFilter, docFilter, sort, pageSize]);

  // Every job (archived ones too) in one list: filters, counts, sort and pages are done here, instantly
  const fetchAll = async (): Promise<Job[]> => {
    const [active, archived] = await Promise.all([jobService.getJobs('all'), jobService.getJobs('archived')]);
    const byId = new Map<number, Job>();
    [...(active || []), ...(archived || [])].forEach(j => byId.set(j.id, j));
    return [...byId.values()];
  };
  const loadJobs = useCallback(() => fetchAll().then(setJobs).catch(e => console.error('[JobBoard] Failed to load jobs', e)), []);
  useEffect(() => {
    fetchAll().then(setJobs).catch(e => console.error('[JobBoard] Failed to load jobs', e)).finally(() => setLoading(false));
  }, []);
  // New jobs are checked (residency / visa) and get CV + cover letter in the background: refresh until they're done
  useEffect(() => {
    const recent = Date.now() - 15 * 60_000;
    const processing = jobs.some(j => ['scraped', 'new'].includes(j.status) && !!j.description && (!j.eligibility_checked_at ||
      (j.eligibility_status !== 'blocked' && (!j.resume_markdown || !j.cover_letter) && new Date(j.eligibility_checked_at).getTime() > recent)));
    if (!processing) return;
    const t = setTimeout(loadJobs, 20_000);
    return () => clearTimeout(t);
  }, [jobs, loadJobs]);

  const setStatus = async (job: Job, status: string) => {
    if (job.status === status) return;
    setJobs(prev => prev.map(j => (j.id === job.id ? { ...j, status } : j)));
    try { await jobService.updateStatus(job.id, status); }
    catch { setJobs(prev => prev.map(j => (j.id === job.id ? { ...j, status: job.status } : j))); }
  };
  const remove = async (job: Job) => {
    if (!confirm(`Excluir a vaga "${job.job_title}" (${job.company})?`)) return;
    setJobs(prev => prev.filter(j => j.id !== job.id));
    try { await jobService.deleteJob(job.id); } catch { loadJobs(); }
  };

  // ── filter → sort → page ──
  const q = query.trim().toLowerCase();
  const matchesText = (j: Job) => !q || `${j.job_title} ${j.company} ${j.location}`.toLowerCase().includes(q);
  const matchesDocs = (j: Job) => docFilter === 'all' || (docFilter === 'with' ? !!j.resume_markdown : !j.resume_markdown);
  const base = useMemo(() => jobs.filter(j => matchesText(j) && matchesDocs(j)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [jobs, q, docFilter]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: base.length, active: base.filter(j => j.status !== 'archived' && j.status !== 'rejected').length };
    base.forEach(j => { c[j.status] = (c[j.status] || 0) + 1; });
    return c;
  }, [base]);
  const filtered = useMemo(() => {
    const rows = base.filter(j => statusFilter === 'all' || (statusFilter === 'active' ? j.status !== 'archived' && j.status !== 'rejected' : j.status === statusFilter));
    const funnel = (s: string) => { const i = STATUS.findIndex(x => x.id === s); return i < 0 ? 99 : i; };
    const cmp: Record<SortKey, (a: Job, b: Job) => number> = {
      recent: (a, b) => time(b.created_at) - time(a.created_at),
      oldest: (a, b) => time(a.created_at) - time(b.created_at),
      updated: (a, b) => time(b.updated_at || b.created_at) - time(a.updated_at || a.created_at),
      score: (a, b) => Number(b.evaluation_score || 0) - Number(a.evaluation_score || 0),
      status: (a, b) => funnel(a.status) - funnel(b.status) || time(b.created_at) - time(a.created_at),
      company: (a, b) => (a.company || '').localeCompare(b.company || '', 'pt'),
      title: (a, b) => (a.job_title || '').localeCompare(b.job_title || '', 'pt'),
    };
    return [...rows].sort(cmp[sort]);
  }, [base, statusFilter, sort]);
  const filterKey = [q, statusFilter, docFilter, sort, pageSize].join('|');
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(pageState.key === filterKey ? pageState.page : 1, pages);
  const setPage = (n: number) => { setPageState({ key: filterKey, page: n }); listRef.current?.scrollTo({ top: 0 }); };
  const shown = filtered.slice((current - 1) * pageSize, current * pageSize);

  const QUICK: { action?: JobAction; tab?: JobTab; title: string; icon: React.ReactNode; primary?: boolean }[] = [
    { action: 'autoapply', title: 'Auto Apply: gera CV e carta se faltarem, abre a vaga e a extensão preenche a candidatura', icon: <Rocket size={15} />, primary: true },
    { action: 'resume', tab: 'docs', title: 'Gerar CV personalizado', icon: <FileText size={15} /> },
    { action: 'cover', tab: 'docs', title: 'Gerar cover letter', icon: <Mail size={15} /> },
    { tab: 'chat', title: 'Chat com a vaga', icon: <MessageSquare size={15} /> },
  ];
  const quick = (job: Job) => QUICK.map(x => (
    <button key={x.title} title={x.title} className={`jb-icon${x.primary ? ' primary' : ''}`}
      onClick={e => { e.stopPropagation(); setSelected({ job, tab: x.tab, action: x.action }); }}>{x.icon}</button>
  ));
  const openMenu = (job: Job) => (e: React.MouseEvent<HTMLButtonElement>) => { e.stopPropagation(); setMenu({ job, rect: e.currentTarget.getBoundingClientRect() }); };

  const pageButtons = () => {
    const nums: (number | '…')[] = [];
    for (let i = 1; i <= pages; i++) {
      // up to 7 pages: all of them; more: first, last, the current one and its neighbours (a gap of one shows the number)
      if (pages <= 7 || i === 1 || i === pages || Math.abs(i - current) <= 1 || (i === 2 && current <= 4) || (i === pages - 1 && current >= pages - 3)) nums.push(i);
      else if (nums[nums.length - 1] !== '…') nums.push('…');
    }
    return nums;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', width: '100%', minWidth: 0 }}>
      <style>{css}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
        <div style={{ marginRight: 'auto' }}>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', margin: 0 }}>Vagas</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: '2px 0 0' }}>
            {counts.applied || 0} candidatura(s) · {counts.interviewing || 0} em entrevista · {jobs.length} no total
          </p>
        </div>
        <div style={{ background: 'rgba(255,255,255,.03)', padding: 3, borderRadius: 10, display: 'flex', border: '1px solid var(--border)' }}>
          {([['table', 'Lista', <ListIcon size={14} />], ['kanban', 'Kanban', <LayoutDashboard size={14} />]] as const).map(([id, label, icon]) => (
            <button key={id} onClick={() => setViewMode(id)} style={{
              padding: '6px 12px', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6,
              background: viewMode === id ? 'var(--accent)' : 'transparent', color: viewMode === id ? '#fff' : 'var(--text-muted)',
            }}>{icon} {label}</button>
          ))}
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)} style={{ height: 34, padding: '0 14px', fontSize: '0.78rem', fontWeight: 700 }}>
          <Plus size={16} /> Nova vaga
        </button>
      </div>

      {/* Search, filters, sort */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 360 }}>
          <Search size={15} style={{ position: 'absolute', left: 11, top: 9, color: 'var(--text-muted)' }} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar cargo, empresa ou local"
            style={{ height: 34, padding: '0 32px 0 34px', fontSize: '0.8rem', borderRadius: 10 }} />
          {query && <button onClick={() => setQuery('')} title="Limpar" style={{ position: 'absolute', right: 8, top: 8, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={15} /></button>}
        </div>
        <select className="jb-select" value={docFilter} onChange={e => setDocFilter(e.target.value as DocFilter)} title="Filtrar por CV gerado">
          <option value="all">Todos os documentos</option>
          <option value="with">Com CV gerado</option>
          <option value="without">Sem CV gerado</option>
        </select>
        {viewMode === 'table' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
            <ArrowUpDown size={14} style={{ color: 'var(--text-muted)' }} />
            <select className="jb-select" value={sort} onChange={e => setSort(e.target.value as SortKey)} title="Ordenar">
              {SORTS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
        )}
      </div>
      {viewMode === 'table' && (
        <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 2 }}>
          {[{ id: 'active', label: 'Em aberto', color: '' }, { id: 'all', label: 'Todas', color: '' }, ...STATUS].map(s => (
            <button key={s.id} className={`jb-chip${statusFilter === s.id ? ' on' : ''}`} onClick={() => setStatusFilter(s.id)}
              title={s.id === 'active' ? 'Tudo menos arquivadas e recusadas' : undefined}>
              {s.color && <span className="jb-dot" style={{ background: s.color }} />}
              {s.label} <span className="n">{counts[s.id] || 0}</span>
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)', marginBottom: 0 }}>Carregando vagas…</div>
      ) : viewMode === 'table' ? (
        <div className="panel" style={{ padding: 0, marginBottom: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div ref={listRef} style={{ overflow: 'auto', maxHeight: 'calc(100vh - 330px)', minHeight: 240 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, zIndex: 2, background: '#14141f', borderBottom: '1px solid var(--border)' }}>
                  <th className="jb-th">VAGA E EMPRESA</th>
                  <th className="jb-th">STATUS</th>
                  <th className="jb-th jb-hide-sm">DOCUMENTOS</th>
                  <th className="jb-th jb-hide-sm">ATUALIZADA</th>
                  <th className="jb-th" style={{ textAlign: 'right' }}>AÇÕES</th>
                </tr>
              </thead>
              <tbody>
                {shown.map(job => (
                  <tr key={job.id} className="jb-row" onClick={() => setSelected({ job })}>
                    <td className="jb-td" style={{ maxWidth: 0, width: '100%' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                        <span style={{ fontWeight: 700, color: '#fff', fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.job_title}</span>
                        <EligibilityBadge job={job} />
                      </div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'flex', gap: 10, overflow: 'hidden', whiteSpace: 'nowrap' }}>
                        <span style={{ color: 'var(--accent-light)', fontWeight: 600 }}>{job.company}</span>
                        {job.location && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, overflow: 'hidden', textOverflow: 'ellipsis' }}><MapPin size={11} /> {job.location}</span>}
                      </div>
                    </td>
                    <td className="jb-td"><StatusPill status={job.status} onClick={openMenu(job)} /></td>
                    <td className="jb-td jb-hide-sm">
                      <div style={{ display: 'flex', gap: 6, fontSize: '0.7rem', fontWeight: 700 }}>
                        <span title={job.resume_markdown ? 'CV gerado' : 'Sem CV'} style={{ color: job.resume_markdown ? '#00c853' : 'rgba(255,255,255,.2)' }}>CV</span>
                        <span title={job.cover_letter ? 'Carta gerada' : 'Sem carta'} style={{ color: job.cover_letter ? '#00c853' : 'rgba(255,255,255,.2)' }}>Carta</span>
                      </div>
                    </td>
                    <td className="jb-td jb-hide-sm" style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{ago(job.updated_at || job.created_at)}</td>
                    <td className="jb-td" style={{ textAlign: 'right' }}>
                      <div className="jb-acts" style={{ display: 'inline-flex', gap: 6 }}>
                        {quick(job)}
                        {jobLink(job) && <a href={jobLink(job)} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="jb-icon" title="Abrir a vaga"><ExternalLink size={15} /></a>}
                        <button className="jb-icon danger" title="Excluir" onClick={e => { e.stopPropagation(); remove(job); }}><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!shown.length && <p style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nenhuma vaga com estes filtros.</p>}
          </div>
          {/* Pages */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.6rem 1rem', borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
              {filtered.length ? `${(current - 1) * pageSize + 1}–${Math.min(current * pageSize, filtered.length)} de ${filtered.length}` : '0 vagas'}
            </span>
            <select className="jb-select" value={pageSize} onChange={e => setPageSize(Number(e.target.value))} title="Vagas por página" style={{ height: 30 }}>
              {[10, 25, 50, 100].map(n => <option key={n} value={n}>{n} por página</option>)}
            </select>
            <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
              <button className="jb-page" disabled={current <= 1} onClick={() => setPage(current - 1)} title="Anterior"><ChevronLeft size={14} /></button>
              {pageButtons().map((n, i) => n === '…'
                ? <span key={`e${i}`} style={{ alignSelf: 'center', color: 'var(--text-muted)', padding: '0 4px' }}>…</span>
                : <button key={n} className={`jb-page${n === current ? ' on' : ''}`} onClick={() => setPage(n)}>{n}</button>)}
              <button className="jb-page" disabled={current >= pages} onClick={() => setPage(current + 1)} title="Próxima"><ChevronRight size={14} /></button>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
          <div style={{ display: 'inline-flex', gap: '0.8rem', minHeight: 'calc(100vh - 290px)' }}>
            {STATUS.filter(s => s.id !== 'archived').map(col => {
              const items = base.filter(j => j.status === col.id);
              return (
                <div key={col.id} onDragOver={e => e.preventDefault()}
                  onDrop={e => { const id = Number(e.dataTransfer.getData('jobId')); const job = jobs.find(j => j.id === id); if (job) setStatus(job, col.id); }}
                  style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8, background: 'rgba(255,255,255,.015)', borderRadius: 14, padding: '0.8rem', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 2px 4px' }}>
                    <span className="jb-dot" style={{ background: col.color }} />
                    <h3 style={{ fontSize: '0.74rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.05em', color: '#fff' }}>{col.label}</h3>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{items.length}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', maxHeight: 'calc(100vh - 340px)' }}>
                    {items.map(job => (
                      <div key={job.id} draggable onDragStart={e => e.dataTransfer.setData('jobId', String(job.id))} onClick={() => setSelected({ job })}
                        className="card-hover" style={{ padding: '0.8rem', borderRadius: 12, cursor: 'grab', background: 'rgba(30,30,42,.6)', border: '1px solid var(--border)', borderLeft: `3px solid ${col.color}` }}>
                        <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#fff', marginBottom: 2 }}>{job.job_title}</div>
                        {(job.eligibility_status === 'blocked' || job.eligibility_status === 'warning') && <div style={{ marginBottom: 4 }}><EligibilityBadge job={job} /></div>}
                        <div style={{ fontSize: '0.74rem', color: 'var(--accent-light)', marginBottom: 8 }}>{job.company}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, minWidth: 0, overflow: 'hidden', whiteSpace: 'nowrap' }}><MapPin size={11} /> {job.location || 'Remoto'}</span>
                          <div style={{ display: 'flex', gap: 4 }}>{quick(job).slice(0, 2)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {menu && <StatusMenu anchor={menu.rect} current={menu.job.status} onPick={s => setStatus(menu.job, s)} onClose={() => setMenu(null)} />}

      {showAddModal && <NewJobModal onClose={() => setShowAddModal(false)} onSaved={() => { setShowAddModal(false); loadJobs(); }} />}

      {selected && <JobDetail key={`${selected.job.id}-${selected.action || selected.tab || ''}`} job={selected.job} initialTab={selected.tab} autoRun={selected.action}
        onClose={() => setSelected(null)}
        onChanged={() => loadJobs()} />}
    </div>
  );
};

export default JobBoard;
