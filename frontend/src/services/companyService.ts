
import api from './api';

export interface Company {
  id: number;
  name: string;
  career_site_url: string;
  description: string;
  logo_url: string;
  industry: string;
  tech_stack: string;
  remote_policy: string;
  domain: string;
  company_type: 'DIRECT_EMPLOYER' | 'RECRUITMENT_AGENCY' | 'JOB_PLATFORM';
  job_count: number;
  created_at: string;
}

export const companyService = {
  getCompanies: async (type?: string) => {
    const url = type ? `/companies/?type=${type}` : '/companies/';
    const response = await api.get<{ companies: Company[] }>(url);
    return response.data.companies;
  },
  getCompany: async (id: number) => {
    const response = await api.get<Company>(`/companies/${id}`);
    return response.data;
  },
  updateCompany: async (id: number, data: Partial<Company>) => {
    const response = await api.put(`/companies/${id}/`, data);
    return response.data;
  },
  getCompanyJobs: async (id: number) => {
    const response = await api.get<{ jobs: any[] }>(`/companies/${id}/jobs/`);
    return response.data.jobs;
  }
};
