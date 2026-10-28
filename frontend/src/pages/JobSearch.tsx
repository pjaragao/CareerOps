import React, { useState } from 'react';
import { Search, ExternalLink, Copy, Check, Lightbulb, Clock, Smartphone, Bookmark } from 'lucide-react';

// Job titles that match the profile (modelagem, dados, IA, infraestrutura), most fitting group first
const GROUPS = [
  {
    id: 'financas', label: 'Modelagem e finanças', remoteOkTag: 'finance',
    titles: ['Financial Modeling Analyst', 'Financial Modeling Manager', 'Project Finance Analyst', 'Project Finance Associate',
      'Infrastructure Finance Analyst', 'FP&A Manager', 'Senior FP&A Analyst', 'Valuation Analyst',
      'Financial Analyst Renewable Energy', 'Pricing Manager'],
    combo: '("financial modeling" OR "project finance" OR "infrastructure finance" OR "FP&A")',
  },
  {
    id: 'dados', label: 'Dados e forecasting', remoteOkTag: 'data-science',
    titles: ['Forecasting Analyst', 'Demand Forecasting Data Scientist', 'Data Scientist Time Series', 'Quantitative Analyst Energy',
      'Analytics Engineer', 'Senior Data Analyst Finance', 'Business Intelligence Manager'],
    combo: '("forecasting" OR "time series") AND ("data scientist" OR "analyst")',
  },
  {
    id: 'ia', label: 'IA aplicada', remoteOkTag: 'ai',
    titles: ['AI Engineer', 'Applied AI Engineer', 'LLM Engineer', 'AI Agent Developer', 'AI Solutions Engineer',
      'Forward Deployed Engineer', 'AI Automation Engineer', 'Finance Automation Lead', 'Solutions Engineer Fintech'],
    combo: '("AI engineer" OR "LLM engineer" OR "applied AI" OR "AI automation")',
  },
  {
    id: 'nicho', label: 'Nicho: infraestrutura', remoteOkTag: 'finance',
    titles: ['Utility Rate Analyst', 'Water Infrastructure Financial Analyst', 'Infrastructure Advisory Consultant',
      'PPP Financial Advisor', 'Concessions Financial Advisor', 'Climate Finance Analyst', 'Sustainable Infrastructure Analyst',
      'Development Finance Consultant', 'Energy Transition Financial Analyst'],
    combo: '("utility rate" OR "PPP" OR "concessions" OR "infrastructure advisory" OR "climate finance")',
  },
];

type ModeId = 'remoto-br' | 'remoto-latam' | 'visto-eu' | 'visto-us';

// Where to look: remote jobs that accept someone living in Brazil pass the eligibility check; visa modes are for moving
const MODES: { id: ModeId; label: string; hint: string; location: string; remote: boolean; extra: string; atsTerms: string }[] = [
  {
    id: 'remoto-br', label: 'Remoto aceitando Brasil (EUA e Europa)', location: 'Brazil', remote: true, extra: '',
    hint: 'Localização "Brazil" + remoto: o LinkedIn mostra vagas de empresas dos EUA e da Europa abertas a quem mora aqui. Com "United States" quase tudo exige autorização de trabalho.',
    atsTerms: '("LATAM" OR "Latin America" OR "Brazil" OR "anywhere" OR "worldwide")',
  },
  {
    id: 'remoto-latam', label: 'Remoto LATAM / contractor', location: 'Latin America', remote: true, extra: '',
    hint: 'Vagas com fuso das Américas, muitas como contractor ou via EOR (Deel, Remote.com). É o caminho mais comum para empresas europeias contratarem do Brasil.',
    atsTerms: '("LATAM" OR "Latin America" OR "contractor" OR "Deel" OR "EOR")',
  },
  {
    id: 'visto-eu', label: 'Mudança para a Europa com visto', location: 'European Union', remote: false, extra: ' AND ("visa sponsorship" OR relocation)',
    hint: 'Presencial ou híbrido com patrocínio de visto ou relocation. Cidades-alvo: Lisboa, Madri, Amsterdã, Berlim, Dublin.',
    atsTerms: '("visa sponsorship" OR "relocation") (Lisbon OR Madrid OR Amsterdam OR Berlin OR Dublin)',
  },
  {
    id: 'visto-us', label: 'Mudança para os EUA com visto', location: 'United States', remote: false, extra: ' AND "visa sponsorship"',
    hint: 'Poucas vagas e H-1B é por sorteio. Vale para consultorias grandes de infraestrutura; para EB-2 NIW, fale com um advogado.',
    atsTerms: '("visa sponsorship" OR "H-1B")',
  },
];

type Search = { query: string; plain: string; mode: ModeId; recent: boolean; remoteOkTag: string };

const enc = encodeURIComponent;
const modeOf = (id: ModeId) => MODES.find(m => m.id === id) ?? MODES[0];

const PLATFORMS: { name: string; note: string; modes: ModeId[]; url: (s: Search) => string }[] = [
  {
    name: 'LinkedIn Vagas', note: 'Ordenado por mais recentes. Candidate-se nas primeiras 48 horas.',
    modes: ['remoto-br', 'remoto-latam', 'visto-eu', 'visto-us'],
    url: s => {
      const m = modeOf(s.mode);
      const p = new URLSearchParams({ keywords: s.query + m.extra, location: m.location, sortBy: 'DD' });
      if (m.remote) p.set('f_WT', '2');
      if (s.recent) p.set('f_TPR', 'r172800');
      return `https://www.linkedin.com/jobs/search/?${p}`;
    },
  },
  {
    name: 'Google · Greenhouse, Lever, Ashby, Workable', note: 'Vagas direto nos sites de candidatura das empresas, muitas que nem vão ao LinkedIn.',
    modes: ['remoto-br', 'remoto-latam', 'visto-eu', 'visto-us'],
    url: s => {
      const sites = '(site:boards.greenhouse.io OR site:job-boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com OR site:apply.workable.com)';
      const q = `${sites} ${s.query} ${modeOf(s.mode).atsTerms}`;
      return `https://www.google.com/search?q=${enc(q)}${s.recent ? '&tbs=qdr:w' : ''}`;
    },
  },
  { name: 'We Work Remotely', note: 'Confira na vaga se aceita "Anywhere" ou "Americas".', modes: ['remoto-br', 'remoto-latam'],
    url: s => `https://weworkremotely.com/remote-jobs/search?term=${enc(s.plain)}` },
  { name: 'Remotive', note: 'Mostra a região permitida em cada vaga.', modes: ['remoto-br', 'remoto-latam'],
    url: s => `https://remotive.com/remote-jobs?query=${enc(s.plain)}` },
  { name: 'Himalayas', note: 'Filtre por país "Brazil" na página.', modes: ['remoto-br', 'remoto-latam'],
    url: s => `https://himalayas.app/jobs?q=${enc(s.plain)}` },
  { name: 'Remote OK', note: 'Busca pela categoria do grupo escolhido.', modes: ['remoto-br', 'remoto-latam'],
    url: s => `https://remoteok.com/remote-${s.remoteOkTag}-jobs` },
  { name: 'Get on Board', note: 'Focado em LATAM: empresas que contratam da região.', modes: ['remoto-br', 'remoto-latam'],
    url: s => `https://www.getonbrd.com/jobs?q=${enc(s.plain)}` },
  { name: 'Wellfound', note: 'Startups, muitas de IA. Filtre por "Remote" e "Brazil" na página.', modes: ['remoto-br', 'remoto-latam'],
    url: () => 'https://wellfound.com/jobs' },
  { name: 'Arc.dev', note: 'Dados e IA para quem está fora dos EUA.', modes: ['remoto-br', 'remoto-latam'],
    url: () => 'https://arc.dev/remote-jobs' },
  { name: 'Turing', note: 'Dados e IA, contratos remotos com empresas dos EUA.', modes: ['remoto-br', 'remoto-latam'],
    url: () => 'https://www.turing.com/jobs' },
  { name: 'Devex', note: 'Banco Mundial, BID, CAF e consultorias de desenvolvimento: o seu nicho de infraestrutura.', modes: ['remoto-br', 'remoto-latam', 'visto-eu', 'visto-us'],
    url: s => `https://www.devex.com/jobs/search?query=${enc(s.plain)}` },
  { name: 'Banco Mundial · carreiras', note: 'Vagas e consultorias (STC/ETC). Lagoas do Norte é o seu cartão de visita.', modes: ['remoto-br', 'remoto-latam', 'visto-us'],
    url: () => 'https://www.worldbank.org/en/about/careers' },
  { name: 'Relocate.me', note: 'Só vagas com relocation e visto, a maioria na Europa.', modes: ['visto-eu'],
    url: () => 'https://relocate.me/international-jobs' },
  { name: 'Arbeitnow', note: 'Alemanha, já filtrado por patrocínio de visto.', modes: ['visto-eu'],
    url: s => `https://www.arbeitnow.com/?search=${enc(s.plain)}&visa_sponsorship=true` },
];

const TIPS = [
  'Candidate-se nas primeiras 48 horas do anúncio: a maior parte das entrevistas sai dos primeiros candidatos.',
  'Na descrição, procure "LATAM", "anywhere", "worldwide", "async" ou "contractor". "Must reside in" ou "authorized to work in" bloqueiam.',
  '"Remote – EU" ou "Remote – US" quase sempre exige residência. Na dúvida, adicione a vaga: a checagem de elegibilidade avisa.',
  'Vaga boa? Salve no LinkedIn e importe em lote pela extensão (ou adicione em Vagas e candidaturas): o CV e a carta saem no idioma da vaga.',
  'Depois de se candidatar, conecte-se com o gerente da vaga ou um recrutador, com nota citando a vaga.',
  'Prioridade: Modelagem e Nicho de infraestrutura, onde pouca gente junta engenharia, DCF e Python. Dados e IA têm mais vagas, e mais concorrência.',
];

const css = `
.js-chip{display:inline-flex;align-items:center;min-height:30px;padding:4px 12px;text-align:left;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.03);color:var(--text-muted);font-size:.78rem;font-weight:600;cursor:pointer;transition:all .15s}
.js-chip:hover{border-color:rgba(255,255,255,.18);color:#fff}
.js-chip.on{background:rgba(108,99,255,.16);border-color:rgba(108,99,255,.55);color:#fff}
.js-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(250px,100%),1fr));gap:.8rem}
.js-card{display:flex;flex-direction:column;gap:.5rem;padding:1rem;border:1px solid var(--border);border-radius:12px;background:rgba(255,255,255,.02);color:inherit;text-decoration:none;transition:all .15s}
.js-card:hover{border-color:rgba(108,99,255,.55);background:rgba(108,99,255,.07)}
`;

// remembered per browser; storage may be blocked (private mode): the page works without it
const saved = <T,>(key: string, fallback: T): T => {
  try { const v = localStorage.getItem(`jobSearch.${key}`); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
};
const remember = (key: string, value: unknown) => { try { localStorage.setItem(`jobSearch.${key}`, JSON.stringify(value)); } catch { /* not remembered */ } };

// On a phone the link opens in the same tab, so Android/iOS hand linkedin.com links to the LinkedIn app
const isPhone = (() => { try { return window.matchMedia('(pointer: coarse)').matches; } catch { return false; } })();
const SAVED_JOBS = 'https://www.linkedin.com/my-items/saved-jobs/';

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.9rem' };

const JobSearch = () => {
  const [groupId, setGroupId] = useState<string>(() => saved('group', GROUPS[0].id));
  const [query, setQuery] = useState<string>(() => saved('query', GROUPS[0].combo));
  const [plain, setPlain] = useState<string>(() => saved('plain', GROUPS[0].titles[0]));
  const [mode, setMode] = useState<ModeId>(() => saved('mode', 'remoto-br'));
  const [recent, setRecent] = useState<boolean>(() => saved('recent', true));
  const [copied, setCopied] = useState(false);

  const group = GROUPS.find(g => g.id === groupId) ?? GROUPS[0];
  const pick = (q: string, p: string) => { setQuery(q); setPlain(p); remember('query', q); remember('plain', p); };
  const chooseGroup = (id: string) => {
    const g = GROUPS.find(x => x.id === id) ?? GROUPS[0];
    setGroupId(g.id); remember('group', g.id);
    pick(g.combo, g.titles[0]);
  };
  const chooseMode = (id: ModeId) => { setMode(id); remember('mode', id); };
  const editQuery = (q: string) => {
    // free text: the boards without boolean search get the first term, without quotes and parentheses
    const first = q.split(/\s+(?:OR|AND)\s+/)[0].replace(/["()]/g, '').trim();
    pick(q, first || q);
  };

  const search: Search = { query, plain, mode, recent, remoteOkTag: group.remoteOkTag };
  const m = modeOf(mode);
  const platforms = PLATFORMS.filter(p => p.modes.includes(mode));

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100 }}>
      <style>{css}</style>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Search /> Pesquisar vagas
        </h1>
        <p style={muted}>
          Escolha o cargo e onde quer trabalhar: cada botão abre a busca pronta no LinkedIn ou em outra plataforma (no celular, direto no app do LinkedIn).
          Os cargos combinam com o seu perfil (modelagem financeira, dados e IA, infraestrutura).
        </p>
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.8rem' }}>1. O que buscar</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '0.9rem' }}>
          {GROUPS.map(g => (
            <button key={g.id} className={`js-chip${g.id === groupId ? ' on' : ''}`} onClick={() => chooseGroup(g.id)}>{g.label}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: '0.9rem' }}>
          <button className={`js-chip${query === group.combo ? ' on' : ''}`} onClick={() => pick(group.combo, group.titles[0])}>
            Todos do grupo
          </button>
          {group.titles.map(t => (
            <button key={t} className={`js-chip${query === `"${t}"` ? ' on' : ''}`} onClick={() => pick(`"${t}"`, t)}>{t}</button>
          ))}
        </div>
        <label className="field-label">Busca (pode editar; aspas e OR valem no LinkedIn e no Google)</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={query} onChange={e => editQuery(e.target.value)} />
          <button className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }} onClick={async () => {
            try { await navigator.clipboard.writeText(query + m.extra); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* select manually */ }
          }}>
            {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copiado' : 'Copiar'}
          </button>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.8rem' }}>2. Onde</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '0.8rem' }}>
          {MODES.map(x => (
            <button key={x.id} className={`js-chip${x.id === mode ? ' on' : ''}`} onClick={() => chooseMode(x.id)}>{x.label}</button>
          ))}
        </div>
        <p style={{ ...muted, marginBottom: '0.8rem' }}>{m.hint}</p>
        <button className={`js-chip${recent ? ' on' : ''}`} onClick={() => { setRecent(!recent); remember('recent', !recent); }}>
          <Clock size={13} style={{ marginRight: 6 }} /> Só recentes (LinkedIn: 48 horas; Google: 7 dias)
        </button>
      </div>

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.8rem' }}>3. Abrir a busca</h3>
        <div className="js-grid">
          {platforms.map(p => (
            <a key={p.name} className="js-card" href={p.url(search)} {...(isPhone ? {} : { target: '_blank', rel: 'noopener noreferrer' })}>
              <strong style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                {p.name} <ExternalLink size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
              </strong>
              <span style={{ ...muted, fontSize: '0.82rem' }}>{p.note}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginBottom: '1rem', display: 'flex', gap: '1rem' }}>
        <Smartphone size={20} style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={{ ...muted, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <span>
            <strong style={{ color: '#fff' }}>Pelo celular:</strong> toque em <strong>LinkedIn Vagas</strong> e a busca abre no app
            (se abrir no navegador, segure o link e escolha abrir no LinkedIn). O app às vezes ignora os filtros de remoto e data:
            confira-os na tela de busca. Salve as vagas que interessam com o marcador <Bookmark size={13} style={{ verticalAlign: -2 }} />.
          </span>
          <span>
            <strong style={{ color: '#fff' }}>Depois, no computador:</strong> abra <a href={SAVED_JOBS} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)', fontWeight: 600 }}>Minhas
            vagas → Salvas</a> e clique em <strong>📥 Importar vagas salvas</strong> na extensão. Todas entram em Vagas e candidaturas,
            com checagem de elegibilidade, CV e carta.
          </span>
        </div>
      </div>

      <div className="panel" style={{ display: 'flex', gap: '1rem' }}>
        <Lightbulb size={20} style={{ flexShrink: 0, marginTop: 2, color: '#ffb020' }} />
        <ul style={{ ...muted, margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {TIPS.map(t => <li key={t}>{t}</li>)}
        </ul>
      </div>
    </div>
  );
};

export default JobSearch;
