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
}

export interface AIOptions {
  tone?: string;
  orientation?: string;
}

export const jobService = {
  getJobs: async (status: string = 'all') => {
    const response = await api.get<{ jobs: Job[] }>(`/jobs?status=${status}`);
    return response.data.jobs;
  },
  addManualJob: async (job: any) => {
    const response = await api.post('/jobs', job);
    return response.data;
  },
  deleteJob: async (id: number) => {
    const response = await api.delete(`/jobs/${id}`);
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
  downloadPDF: async (id: number, content: string) => {
    const response = await api.post(`/jobs/${id}/download-pdf`, { content }, { responseType: 'blob' });
    return response.data;
  }
};
