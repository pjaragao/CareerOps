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
  easy_apply: boolean;
  resume_markdown?: string;
  cover_letter?: string;
  linkedin_dm_draft?: string;
  company_name?: string;
  logo_url?: string;
  company_type?: string;
  career_site_url?: string;
}

export interface AIOptions {
  tone?: string;
  orientation?: string;
}

export const jobService = {
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
  deleteJob: async (id: number) => {
    const response = await api.delete(`/jobs/${id}`);
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
