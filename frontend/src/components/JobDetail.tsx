import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Job, jobService, startAutoApply } from '../services/jobService';
import { X, FileText, MessageSquare, Wand2, RefreshCw, Copy, Download, Send, ExternalLink, Rocket, Mail, MessageCircle, ChevronDown, ChevronUp, MapPin, Building2 } from 'lucide-react';
import api from '../services/api';

export type JobTab = 'info' | 'docs' | 'chat';
export type JobAction = 'resume' | 'cover' | 'dm' | 'autoapply';

interface JobDetailProps {
  job: Job;
  onClose: () => void;
  initialTab?: JobTab;
  autoRun?: JobAction;   // run this action as soon as the window opens (list shortcuts)
  onChanged?: () => void;
}

const STATUSES: [string, string][] = [
  ['new', 'Avaliar'], ['scraped', 'Captada'], ['applied', 'Candidatado'], ['interviewing', 'Entrevista'],
  ['offer', 'Proposta'], ['rejected', 'Recusada'], ['archived', 'Arquivada'],
];

const HEADINGS = 'Job Summary|Job Description|About the job|About us|About the role|About|The Role|Your role|Core Responsibilities|Key Responsibilities|Responsibilities|What you.ll do|What we.re looking for|Who you are|Requirements|Qualifications|Preferred Qualifications|Skills|Benefits|What we offer|Sobre a vaga|Sobre nós|Sobre a empresa|Responsabilidades|Atribuições|Requisitos|Qualificações|Diferenciais|Benefícios|O que oferecemos';

// Imported descriptions sometimes lost their line breaks ("Job SummaryYou will…"): put paragraphs back
function formatDescription(text: string): string {
  if (!text) return '';
  if ((text.match(/\n/g) || []).length > 4) return text;
  return text
    .replace(new RegExp(`([a-z\\u00e0-\\u00ff.)])(${HEADINGS})`, 'g'), '$1\n\n$2')
    .replace(new RegExp(`^(${HEADINGS})(?=[A-Z])`, 'gm'), '$1\n')
    .replace(new RegExp(`\\n\\n(${HEADINGS})(?=[A-Z])`, 'g'), '\n\n$1\n')
    .replace(/([.!?])(?=[A-ZÀ-Ú"“])/g, '$1\n\n')
    .replace(/\n{3,}/g, '\n\n');
}

const isHeading = (line: string) => line.length > 2 && line.length < 45 && !/[.,;]$/.test(line) && new RegExp(`^(${HEADINGS})\\s*:?$`, 'i').test(line.trim());

const DOCS: { id: JobAction; label: string; field: keyof Job; icon: React.ReactNode }[] = [
  { id: 'resume', label: 'CV personalizado', field: 'resume_markdown', icon: <FileText size={15} /> },
  { id: 'cover', label: 'Cover letter', field: 'cover_letter', icon: <Mail size={15} /> },
  { id: 'dm', label: 'Mensagem LinkedIn', field: 'linkedin_dm_draft', icon: <MessageCircle size={15} /> },
];

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.8rem' };
const input: React.CSSProperties = { padding: '0.5rem 0.7rem', fontSize: '0.82rem', borderRadius: 8, background: '#1a1a25', color: '#fff', border: '1px solid var(--border)' };

const JobDetail: React.FC<JobDetailProps> = ({ job: initialJob, onClose, initialTab = 'info', autoRun, onChanged }) => {
  const [job, setJob] = useState<Job>(initialJob);
  const [tab, setTab] = useState<JobTab>(initialTab);
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [tone, setTone] = useState('semi-formal');
  const [orientation, setOrientation] = useState('');
  const [chatMode, setChatMode] = useState<'assistant' | 'simulator'>('assistant');
  const [chatMessage, setChatMessage] = useState('');
  const [employerQuestion, setEmployerQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState<{ role: string; text: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const autoDone = useRef(false);

  const refresh = async () => {
    const r = await api.get<Job>(`/jobs/${job.id}`);
    setJob(r.data);
    onChanged?.();
  };

  const busy = (id: string, v: boolean) => setRunning(prev => ({ ...prev, [id]: v }));
  const errText = (e: unknown) => (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail || (e as Error)?.message || 'Erro';

  const generate = async (id: JobAction) => {
    if (id === 'autoapply') return autoApply();
    busy(id, true);
    setNotice(null);
    try {
      if (id === 'resume') await jobService.generateResume(job.id, { tone, orientation });
      else if (id === 'cover') await jobService.generateCoverLetter(job.id, { tone, orientation });
      else await jobService.outreach(job.id, 'dm', { tone, orientation });
      await refresh();
      setTab('docs');
      setOpen(prev => ({ ...prev, [id]: true }));
    } catch (e) {
      setNotice({ text: errText(e), ok: false });
    } finally { busy(id, false); }
  };

  const autoApply = async () => {
    busy('autoapply', true);
    setNotice({ text: 'Preparando CV e carta…', ok: true });
    try {
      await startAutoApply(job, { tone, orientation }, (s) => setNotice({ text: s, ok: true }));
      await refresh();
    } catch (e) {
      setNotice({ text: errText(e), ok: false });
    } finally { busy('autoapply', false); }
  };

  useEffect(() => {
    if (autoRun && !autoDone.current) { autoDone.current = true; generate(autoRun); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun]);

  // the page behind stays where it was: no scrolling under the window, nothing jumps when it closes
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const setStatus = async (status: string) => {
    setJob(j => ({ ...j, status }));
    try { await jobService.updateStatus(job.id, status); onChanged?.(); } catch { setNotice({ text: 'Não consegui mudar o status', ok: false }); }
  };

  const sendChat = async () => {
    const msg = chatMode === 'assistant' ? employerQuestion : chatMessage;
    if (!msg.trim()) return;
    if (chatMode === 'simulator') { setChatMessage(''); setChatHistory(prev => [...prev, { role: 'user', text: msg }]); }
    setChatLoading(true);
    try {
      const data = await jobService.chat(job.id, msg, { tone, orientation });
      if (chatMode === 'assistant') setChatHistory([{ role: 'ai', text: data.reply }]);
      else setChatHistory(prev => [...prev, { role: 'ai', text: data.reply }]);
    } catch (e) {
      setNotice({ text: errText(e), ok: false });
    } finally { setChatLoading(false); }
  };

  const downloadPDF = async (content: string, label: string) => {
    try {
      const data = await jobService.downloadPDF(job.id, content);
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${label.replace(/\s+/g, '_')}_${job.company || job.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch { setNotice({ text: 'Falha ao gerar o PDF', ok: false }); }
  };

  const jobUrl = job.url ? (job.url.startsWith('http') ? job.url : `https://${job.url}`) : '';
  const tool = (id: JobAction | 'chat', label: string, icon: React.ReactNode, onClick: () => void, primary = false, title = '') => (
    <button key={id} onClick={onClick} disabled={!!running[id]} title={title} className={`btn ${primary ? 'btn-primary' : 'btn-secondary'}`}
      style={{ height: 34, padding: '0 12px', fontSize: '0.78rem', fontWeight: 700, gap: 6, whiteSpace: 'nowrap' }}>
      {running[id] ? <RefreshCw size={14} className="animate-spin" /> : icon} {label}
    </button>
  );

  const description = formatDescription(job.description || '');

  // portal: on top of the screen wherever the list is scrolled (inside the page it was placed relative to the page)
  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(5, 5, 10, 0.78)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(10px)', padding: 20 }}>
      <div onClick={e => e.stopPropagation()} className="panel job-window" style={{
        width: '100%', maxWidth: 1100, height: '90vh', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden',
        border: '1px solid rgba(108, 99, 255, 0.3)', boxShadow: '0 20px 50px rgba(0,0,0,0.5)', background: 'var(--bg-card)',
      }}>
        {/* Header: who/where, status, actions */}
        <div style={{ padding: '1rem 1.5rem 0.8rem', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
            <div style={{ minWidth: 0 }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', margin: 0 }}>{job.job_title}</h2>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: 4, ...muted }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--accent)', fontWeight: 600 }}><Building2 size={13} /> {job.company}</span>
                {job.location && <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><MapPin size={13} /> {job.location}</span>}
                {job.easy_apply && <span style={{ color: '#10b981', fontWeight: 600 }}>Easy Apply</span>}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
              <select value={job.status} onChange={e => setStatus(e.target.value)} style={{ ...input, height: 34, padding: '0 8px' }} title="Status da vaga">
                {STATUSES.map(([v, l]) => <option key={v} value={v} style={{ color: '#000' }}>{l}</option>)}
                {!STATUSES.some(([v]) => v === job.status) && <option value={job.status} style={{ color: '#000' }}>{job.status}</option>}
              </select>
              <button onClick={onClose} className="btn btn-secondary" style={{ padding: 6, borderRadius: '50%' }} title="Fechar (Esc)"><X size={18} /></button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {tool('autoapply', 'Auto Apply', <Rocket size={14} />, autoApply, true,
              'Gera CV e carta (se faltarem), abre a vaga e a extensão preenche a candidatura')}
            {tool('resume', job.resume_markdown ? 'Refazer CV' : 'Gerar CV', <FileText size={14} />, () => generate('resume'))}
            {tool('cover', job.cover_letter ? 'Refazer carta' : 'Gerar carta', <Mail size={14} />, () => generate('cover'))}
            {tool('dm', 'Mensagem LinkedIn', <MessageCircle size={14} />, () => generate('dm'))}
            {tool('chat', 'Chat com a vaga', <MessageSquare size={14} />, () => setTab('chat'))}
            {jobUrl && (
              <a href={jobUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ height: 34, padding: '0 12px', fontSize: '0.78rem', fontWeight: 700, gap: 6 }}>
                <ExternalLink size={14} /> Abrir vaga
              </a>
            )}
          </div>
          {notice && <div style={{ fontSize: '0.8rem', color: notice.ok ? '#10b981' : 'var(--error, #ff4d4d)' }}>{notice.text}</div>}
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '1.5rem', padding: '0 1.5rem', borderBottom: '1px solid var(--border)' }}>
          {([['info', 'Vaga', <FileText size={15} />], ['docs', 'Documentos', <Wand2 size={15} />], ['chat', 'Chat', <MessageSquare size={15} />]] as [JobTab, string, React.ReactNode][]).map(([id, label, icon]) => (
            <button key={id} onClick={() => setTab(id)} style={{
              padding: '0.75rem 0', background: 'transparent', border: 'none', borderBottom: `2px solid ${tab === id ? 'var(--accent)' : 'transparent'}`,
              color: tab === id ? 'var(--accent)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem',
            }}>
              {icon} {label}
              {id === 'docs' && <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>({DOCS.filter(d => job[d.field]).length}/3)</span>}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, minHeight: 0, padding: '1rem 1.5rem', overflowY: 'auto' }}>
          {tab === 'info' && (
            <div style={{ maxWidth: 820, color: '#d4d4dc', lineHeight: 1.6, fontSize: '0.9rem' }}>
              {description ? description.split('\n').map((l, i) => {
                const t = l.trim();
                if (!t) return <div key={i} style={{ height: '0.6rem' }} />;
                if (isHeading(t)) return <h4 key={i} style={{ color: '#fff', margin: '0.6rem 0 0.2rem', fontSize: '0.95rem' }}>{t.replace(/:$/, '')}</h4>;
                if (/^[•\-*·]\s*/.test(t)) return <div key={i} style={{ paddingLeft: '1rem', textIndent: '-0.7rem' }}>• {t.replace(/^[•\-*·]\s*/, '')}</div>;
                return <p key={i} style={{ margin: 0 }}>{t}</p>;
              }) : <p style={muted}>Sem descrição. Abra a vaga e importe de novo pela extensão.</p>}
            </div>
          )}

          {tab === 'docs' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'flex-end', background: 'rgba(108, 99, 255, 0.05)', padding: '0.8rem', borderRadius: 10, border: '1px solid rgba(108, 99, 255, 0.2)' }}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent)' }}>TOM
                  <select value={tone} onChange={e => setTone(e.target.value)} style={input}>
                    <option value="semi-formal" style={{ color: '#000' }}>Semi-formal</option>
                    <option value="formal" style={{ color: '#000' }}>Formal</option>
                    <option value="informal" style={{ color: '#000' }}>Casual</option>
                  </select>
                </label>
                <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent)' }}>ORIENTAÇÃO PARA A IA (opcional)
                  <input value={orientation} onChange={e => setOrientation(e.target.value)} placeholder="Ex.: destaque modelagem financeira e Python" style={input} />
                </label>
              </div>
              {DOCS.map(d => {
                const content = job[d.field] as string | undefined;
                return (
                  <div key={d.id} style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0.7rem 1rem', background: 'rgba(255,255,255,0.02)' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: content ? '#10b981' : '#444' }} />
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: '0.86rem', color: content ? '#fff' : '#888' }}>{d.icon} {d.label}</span>
                      <span style={{ ...muted, fontSize: '0.72rem' }}>{content ? `${content.length} caracteres` : 'não gerado'}</span>
                      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                        <button className="btn btn-secondary" disabled={!!running[d.id]} onClick={() => generate(d.id)} style={{ padding: '4px 10px', fontSize: '0.72rem', gap: 5 }}>
                          {running[d.id] ? <RefreshCw size={12} className="animate-spin" /> : <Wand2 size={12} />} {content ? 'Refazer' : 'Gerar'}
                        </button>
                        {content && <>
                          <button className="btn btn-secondary" onClick={() => { navigator.clipboard.writeText(content); setNotice({ text: `${d.label} copiado`, ok: true }); }} style={{ padding: '4px 8px' }} title="Copiar"><Copy size={12} /></button>
                          {d.id !== 'dm' && <button className="btn btn-secondary" onClick={() => downloadPDF(content, d.label)} style={{ padding: '4px 8px' }} title="Baixar PDF"><Download size={12} /></button>}
                          <button className="btn btn-secondary" onClick={() => setOpen(prev => ({ ...prev, [d.id]: !prev[d.id] }))} style={{ padding: '4px 8px' }} title={open[d.id] ? 'Recolher' : 'Ver'}>
                            {open[d.id] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>
                        </>}
                      </div>
                    </div>
                    {open[d.id] && content && (
                      <pre style={{ margin: 0, padding: '1rem', background: '#0a0a0f', borderTop: '1px solid var(--border)', maxHeight: 380, overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '0.8rem', color: '#ccc', lineHeight: 1.5 }}>{content}</pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {tab === 'chat' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '0.8rem' }}>
              <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.03)', padding: 3, borderRadius: 8, width: 'fit-content' }}>
                {([['assistant', 'Responder pergunta do formulário'], ['simulator', 'Conversa livre sobre a vaga']] as const).map(([m, l]) => (
                  <button key={m} onClick={() => { setChatMode(m); setChatHistory([]); }} style={{ padding: '5px 12px', borderRadius: 6, border: 'none', background: chatMode === m ? 'var(--accent)' : 'transparent', color: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: '0.75rem' }}>{l}</button>
                ))}
              </div>
              {chatMode === 'assistant' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
                  <textarea value={employerQuestion} onChange={e => setEmployerQuestion(e.target.value)} placeholder="Cole a pergunta do empregador (ex.: Why do you want to work at …?)"
                    style={{ ...input, height: 100, resize: 'vertical', fontFamily: 'inherit' }} />
                  <input value={orientation} onChange={e => setOrientation(e.target.value)} placeholder="Orientação (opcional)" style={input} />
                  <button className="btn btn-primary" onClick={sendChat} disabled={chatLoading} style={{ alignSelf: 'flex-start', gap: 6 }}>
                    {chatLoading ? <RefreshCw className="animate-spin" size={15} /> : <Wand2 size={15} />} Gerar resposta
                  </button>
                  {chatHistory[0] && (
                    <div style={{ background: 'rgba(108, 99, 255, 0.05)', padding: '1rem', border: '1px solid var(--border)', borderRadius: 10 }}>
                      <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: '#fff', fontFamily: 'inherit', margin: 0 }}>{chatHistory[0].text}</pre>
                      <button onClick={() => navigator.clipboard.writeText(chatHistory[0].text)} className="btn btn-secondary" style={{ marginTop: '0.5rem', fontSize: '0.7rem' }}><Copy size={12} /> Copiar</button>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div style={{ flex: 1, minHeight: 250, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.8rem', background: 'rgba(0,0,0,0.2)', borderRadius: 12 }}>
                    {!chatHistory.length && <p style={muted}>Pergunte sobre a vaga: fit com seu perfil, pontos fracos, salário, perguntas prováveis na entrevista…</p>}
                    {chatHistory.map((m, i) => (
                      <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', background: m.role === 'user' ? 'var(--accent)' : 'rgba(255,255,255,0.08)', padding: '0.6rem 1rem', borderRadius: 12, maxWidth: '85%', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>{m.text}</div>
                    ))}
                    {chatLoading && <RefreshCw className="animate-spin" size={16} />}
                  </div>
                  <div style={{ display: 'flex', gap: '0.6rem' }}>
                    <input value={chatMessage} onChange={e => setChatMessage(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendChat()} placeholder="Escreva sua pergunta…" style={{ ...input, flex: 1 }} />
                    <button onClick={sendChat} className="btn btn-primary" style={{ padding: '0.6rem' }}><Send size={16} /></button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
};

export default JobDetail;
