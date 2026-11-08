import api from './api';

export interface Job {
  id: number;
  linkedin_job_id: string;
  url: string;
  job_title: string;
  company: string;
  location: string;
  description: string;
  status: string;
  created_at: string;
  updated_at?: string | null;
  evaluation_score?: number | string | null;   // 0–5 from the AI evaluation
  archetype?: string | null;
  easy_apply: boolean;
  resume_markdown?: string;
  cover_letter?: string;
  linkedin_dm_draft?: string;
  company_name?: string;
  logo_url?: string;
  company_type?: string;
  career_site_url?: string;
  // ad requires living in a region / a work visa the candidate lacks (checked when the job is added)
  eligibility_status?: 'ok' | 'warning' | 'blocked' | null;
  eligibility_issues?: EligibilityIssue[];
  eligibility_checked_at?: string | null;
  // portfolio link of this job (pjaragao-portfolio.vercel.app), opened N times by the company
  portfolio_token?: string | null;
  portfolio_views?: number;
  portfolio_seconds?: number;
  portfolio_last_view_at?: string | null;
}

export interface EligibilityIssue {
  type: 'residency' | 'work_authorization';
  quote: string;
  reason?: string;
}

export interface JobFromLink {
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  source: string;
  warning?: string;   // e.g. the description looks cut off at the end
  employment_type?: string;
  seniority?: string;
  salary?: string;
  posted?: string;
  workplace?: string;
  existing?: { id: number; job_title: string; company: string; status: string } | null;
}

export interface AIOptions {
  tone?: string;
  orientation?: string;
}

export const jobService = {
  getJob: async (id: number) => (await api.get<Job>(`/jobs/${id}`)).data,
  // this job's own portfolio link (signed token; created on first use)
  getPortfolio: async (id: number) => (await api.get<{ url: string | null; views: number; seconds: number; last_view_at: string | null }>(`/jobs/${id}/portfolio`)).data,
  getJobs: async (status?: string) => {
    const url = status ? `/jobs/?status=${status}` : '/jobs/';
    const response = await api.get<{ jobs: Job[] }>(url);
    return response.data.jobs;
  },
  addManualJob: async (job: any) => {
    // Correct mapping for ManualJobCreate (expects 'title', not 'job_title')
    const payload = {
      title: job.job_title || job.title,
      company: job.company,
      location: job.location,
      url: job.url,
      description: job.description
    };
    const response = await api.post('/jobs/manual', payload);
    return response.data;
  },
  // Title, company, location and description read from the job's link, or from its pasted text (not saved)
  fromLink: async (url: string, text?: string) => {
    const response = await api.post<JobFromLink>('/jobs/from-url', { url, text: text || '' });
    return response.data;
  },
  deleteJob: async (id: number) => {
    const response = await api.delete(`/jobs/${id}`);
    return response.data;
  },
  recheckEligibility: async (id: number) => {
    const response = await api.post<{ status: string; issues: EligibilityIssue[] }>(`/jobs/${id}/eligibility`);
    return response.data;
  },
  updateStatus: async (id: number, status: string) => {
    const response = await api.patch(`/jobs/${id}/status`, { status });
    return response.data;
  },
  generateResume: async (id: number, options?: AIOptions) => {
    const response = await api.post<{ content: string }>(`/jobs/${id}/generate-resume`, options);
    return response.data;
  },
  generateCoverLetter: async (id: number, options?: AIOptions) => {
    const response = await api.post<{ content: string }>(`/jobs/${id}/generate-cover-letter`, options);
    return response.data;
  },
  chat: async (id: number, message: string, options?: AIOptions) => {
    const response = await api.post<{ reply: string }>(`/jobs/${id}/chat`, { message, ...options });
    return response.data;
  },
  outreach: async (id: number, type: 'dm' | 'email', options?: AIOptions) => {
    const response = await api.post<{ content: string }>(`/jobs/${id}/outreach?type=${type}`, options);
    return response.data;
  },
  prepareAutoApply: async (id: number, options?: AIOptions & { regenerate?: boolean }) => {
    const response = await api.post<{ apply_url: string; is_linkedin: boolean; generated: string[] }>(`/jobs/${id}/auto-apply/prepare`, options || {});
    return response.data;
  },
  downloadPDF: async (id: number, content: string) => {
    const response = await api.post(`/jobs/${id}/download-pdf`, { content }, { responseType: 'blob' });
    return response.data;
  }
};

// Auto Apply: CV and cover letter are prepared here, then the job opens in a new tab with a marker the CareerOps
// extension picks up. The tab is opened right away (inside the click) so the browser doesn't block it.
export async function startAutoApply(job: Job, options?: AIOptions, onStep?: (s: string) => void) {
  const tab = window.open('about:blank', '_blank');
  if (tab) tab.document.write('<p style="font:16px system-ui;padding:2rem">CareerOps: preparando CV e carta para a candidatura…</p>');
  try {
    onStep?.('Preparando CV e carta…');
    const prep = await jobService.prepareAutoApply(job.id, options);
    if (!prep.apply_url) throw new Error('Esta vaga não tem link para candidatura');
    const url = `${prep.apply_url.split('#')[0]}#careerops-apply=${job.id}`;
    if (tab) tab.location.href = url; else window.open(url, '_blank');
    onStep?.(prep.is_linkedin ? 'Aberta no LinkedIn: a extensão segue com o Easy Apply' : 'Aberta no site da vaga: a extensão serve de copiloto');
    return prep;
  } catch (e) {
    tab?.close();
    throw e;
  }
}
