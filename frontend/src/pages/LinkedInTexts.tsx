import React, { useEffect, useState } from 'react';
import { Copy, Check, Puzzle } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../services/api';

type Lang = 'en' | 'pt';
interface Texts { title: string; description: string }
interface ProfileCopy {
  en: { headline: string; about: string };
  pt: { headline: string; about: string };
  positions: ({ id: string; company: string; start: string; end: string | null; optional?: boolean } & Record<Lang, Texts>)[];
  projects: ({ id: string; start: string; end: string | null } & Record<Lang, Texts>)[];
  education?: ({ id: string; school: string; start: string; end: string } & Record<Lang, { degree: string; field: string; description: string }>)[];
  licenses?: ({ id: string; issuer: string; credential_id: string } & Record<Lang, { name: string }>)[];
  languages?: Record<Lang, string>[];
  skills_top: string[];
  skills: string[];
  remove: Record<Lang, string>[];
}

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.85rem' };
const MARKET: Record<Lang, string> = {
  pt: 'Português — perfil principal, mercado Brasil: engenharia e saneamento, modelagem técnico-financeira, dados e IA.',
  en: 'English — perfil em outro idioma, mercado exterior: dados, finanças e modelagem; engenharia como domínio.',
};

const CopyBtn = ({ text }: { text: string }) => {
  const [ok, setOk] = useState(false);
  return (
    <button className="btn btn-secondary" style={{ padding: '4px 10px' }}
      onClick={async () => { try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* select manually */ } }}>
      {ok ? <Check size={14} /> : <Copy size={14} />} {ok ? 'Copiado' : 'Copiar'}
    </button>
  );
};

const Block = ({ label, meta, text }: { label: string; meta?: string; text: string }) => (
  <div className="panel" style={{ padding: '1rem 1.2rem' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 6 }}>
      <div><strong>{label}</strong> {meta && <span style={muted}>· {meta}</span>}</div>
      <CopyBtn text={text} />
    </div>
    <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: '#d6d6e2' }}>{text}</div>
  </div>
);

const LinkedInTexts = () => {
  const [data, setData] = useState<ProfileCopy | null>(null);
  const [error, setError] = useState(false);
  const [lang, setLang] = useState<Lang>('pt');
  useEffect(() => {
    api.get<ProfileCopy>('/linkedin-copilot/profile-copy').then(r => setData(r.data)).catch(() => setError(true));
  }, []);

  if (error) return <p style={muted}>Textos não encontrados: rode <code>python3 international/build_linkedin_profile.py</code>.</p>;
  if (!data) return <p style={muted}>Carregando…</p>;
  const date = (ym: string | null) => (ym ? ym.split('-').reverse().join('/') : (lang === 'pt' ? 'atual' : 'present'));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['pt', 'en'] as Lang[]).map(l => (
            <button key={l} className={`btn ${lang === l ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setLang(l)}>
              {l === 'pt' ? 'Português (Brasil)' : 'English (exterior)'}
            </button>
          ))}
        </div>
        <span style={muted}>
          Mais rápido no próprio LinkedIn: painel <strong>CareerOps · Perfil</strong> da extensão
          (<Link to="/configuracoes?tab=extensao" style={{ color: 'var(--accent)' }}><Puzzle size={12} /> instalar</Link>).
        </span>
      </div>
      <p style={muted}>{MARKET[lang]}</p>

      <Block label={lang === 'pt' ? 'Título' : 'Headline'} meta={`${data[lang].headline.length}/220`} text={data[lang].headline} />
      <Block label={lang === 'pt' ? 'Sobre' : 'About'} meta={`${data[lang].about.length}/2600`} text={data[lang].about} />

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Experiência' : 'Experience'}</h3>
      {data.positions.map(p => (
        <Block key={p.id} label={p[lang].title}
          meta={`${p.company} · ${date(p.start)} – ${date(p.end)}${p.optional ? (lang === 'pt' ? ' · opcional' : ' · optional') : ''}`}
          text={p[lang].description} />
      ))}

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Projetos' : 'Projects'}</h3>
      {data.projects.map(p => (
        <Block key={p.id} label={p[lang].title} meta={`${date(p.start)} – ${date(p.end)}`} text={p[lang].description} />
      ))}

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Formação acadêmica' : 'Education'}</h3>
      {(data.education || []).map(e => (
        <Block key={e.id} label={`${e[lang].degree} — ${e[lang].field}`} meta={`${e.school} · ${e.start}–${e.end}`} text={e[lang].description} />
      ))}

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Licenças e certificados' : 'Licenses & certifications'}</h3>
      {(data.licenses || []).map(l => (
        <Block key={l.id} label={l[lang].name} meta={`${l.issuer} · ${l.credential_id}`} text={l[lang].name} />
      ))}

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Idiomas' : 'Languages'}</h3>
      <Block label={lang === 'pt' ? 'Idiomas' : 'Languages'} text={(data.languages || []).map(l => l[lang]).join('\n')} />

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Competências (únicas para os dois idiomas)' : 'Skills (shared by both languages)'}</h3>
      <Block label="Top 5" text={data.skills_top.join(' · ')} />
      <Block label={lang === 'pt' ? 'Adicionar' : 'Add'} text={data.skills.join(' · ')} />

      <h3 style={{ marginTop: '0.5rem' }}>{lang === 'pt' ? 'Apagar / corrigir' : 'Remove / fix'}</h3>
      <div className="panel" style={{ padding: '1rem 1.2rem' }}>
        <ul style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.remove.map((r, i) => <li key={i} style={{ fontSize: '0.9rem' }}>{r[lang]}</li>)}
        </ul>
      </div>
    </div>
  );
};

export default LinkedInTexts;
