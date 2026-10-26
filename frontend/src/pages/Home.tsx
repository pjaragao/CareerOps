import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Megaphone, MessageCircle, Users, Briefcase, UserCircle, ArrowRight, Puzzle } from 'lucide-react';
import { linkedinCopilotService as copilot, CopilotPost } from '../services/linkedinCopilotService';
import { jobService, Job } from '../services/jobService';

interface Summary {
  drafts: number;
  scheduled: number;
  engagementPending: number;
  doneToday: number;
  dailyTarget: number;
  toContact: number;
  invitedWeek: number;
  weeklyTarget: number;
  jobs: Record<string, number>;
}

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.9rem' };

const Card = ({ icon, title, value, detail, to, cta }: {
  icon: React.ReactNode; title: string; value: string; detail: string; to: string; cta: string;
}) => (
  <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>{icon} {title}</div>
    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{value}</div>
    <div style={muted}>{detail}</div>
    <Link to={to} className="btn btn-primary" style={{ alignSelf: 'flex-start', marginTop: 'auto' }}>{cta} <ArrowRight size={15} /></Link>
  </div>
);

const count = (items: { status: string }[], ...statuses: string[]) => items.filter(i => statuses.includes(i.status)).length;

const Home = () => {
  const [s, setS] = useState<Summary | null>(null);
  useEffect(() => {
    Promise.all([
      copilot.listPosts().catch(() => [] as CopilotPost[]),
      copilot.engagementQueue().catch(() => ({ items: [], done_today: 0, daily_target: 10 })),
      copilot.prospects().catch(() => ({ items: [], invited_this_week: 0, weekly_target: 20 })),
      jobService.getJobs('all').catch(() => [] as Job[]),
    ]).then(([posts, eng, pros, jobs]) => {
      const jobCounts: Record<string, number> = {};
      for (const j of jobs || []) jobCounts[j.status] = (jobCounts[j.status] || 0) + 1;
      setS({
        drafts: count(posts, 'draft', 'failed'),
        scheduled: count(posts, 'approved'),
        engagementPending: eng.items.length,
        doneToday: eng.done_today,
        dailyTarget: eng.daily_target,
        toContact: count(pros.items, 'to_contact'),
        invitedWeek: pros.invited_this_week,
        weeklyTarget: pros.weekly_target,
        jobs: jobCounts,
      });
    });
  }, []);

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.4rem' }}>Início</h1>
        <p style={muted}>O que fazer hoje. Brasil em português (engenharia, saneamento, modelagem); exterior em inglês (dados, finanças, modelagem).</p>
      </div>
      {!s ? <p style={muted}>Carregando…</p> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1.2rem' }}>
          <Card icon={<Megaphone size={18} />} title="Posts para revisar" value={String(s.drafts)}
            detail={`${s.scheduled} aprovado(s) aguardando publicação. Meta: 3 por semana (2 EN, 1 PT).`}
            to="/linkedin-copilot" cta={s.drafts ? 'Revisar rascunhos' : 'Gerar rascunhos'} />
          <Card icon={<MessageCircle size={18} />} title="Comentários hoje" value={`${s.doneToday}/${s.dailyTarget}`}
            detail={`${s.engagementPending} post(s) na fila com comentário rascunhado.`}
            to="/linkedin-copilot?tab=engagement" cta="Abrir fila" />
          <Card icon={<Users size={18} />} title="Convites na semana" value={`${s.invitedWeek}/${s.weeklyTarget}`}
            detail={`${s.toContact} pessoa(s) com nota pronta para convidar.`}
            to="/linkedin-copilot?tab=prospects" cta="Abrir prospecção" />
          <Card icon={<Briefcase size={18} />} title="Candidaturas em andamento" value={String((s.jobs.applied || 0) + (s.jobs.interviewing || 0))}
            detail={`${s.jobs.interviewing || 0} em entrevista · ${(s.jobs.new || 0) + (s.jobs.scraped || 0)} vaga(s) para avaliar.`}
            to="/vagas" cta="Ver vagas" />
          <Card icon={<UserCircle size={18} />} title="Perfil do LinkedIn" value="EN + PT"
            detail="Textos prontos para o perfil principal (Brasil) e o perfil em inglês (exterior)."
            to="/perfil?tab=linkedin" cta="Ver textos" />
          <Card icon={<Puzzle size={18} />} title="Extensão" value="Chrome / Edge"
            detail="Painel do perfil no LinkedIn, importação de vagas e envio ao Copilot."
            to="/configuracoes?tab=extensao" cta="Instalar" />
        </div>
      )}
    </div>
  );
};

export default Home;
