import api from './api';

export interface ReviewCategory { id: string; name: string; score: number; max: number; notes?: string }
export interface ReviewIssue { severity: 'high' | 'medium' | 'low'; section?: string; problem: string; fix?: string; example?: string }
export interface ResumeReview {
  score: number;
  verdict?: string;
  recruiter_view?: string;
  categories?: ReviewCategory[];
  strengths?: string[];
  issues?: ReviewIssue[];
  keywords?: { present?: string[]; missing?: string[] };
}
export interface FormSuggestions {
  target_job_titles?: { title: string; fit?: string; why?: string }[];
  experience_level?: { value: string; alternative?: string; why?: string };
  job_status?: { value: string; why?: string };
  salary_range?: { value: string; minimum?: string; why?: string; note?: string };
  other_fields?: { field: string; value: string; why?: string }[];
}
export interface GeneralResume {
  id: number;
  title: string;
  lang: 'en' | 'pt' | string;
  target_title: string;
  used_on: string;
  content_md: string;
  review?: ResumeReview | null;
  review_at?: string | null;
  form_suggestions?: FormSuggestions | null;
  form_suggestions_at?: string | null;
  created_at: string;
  updated_at: string;
}
export type ResumeFields = Partial<Pick<GeneralResume, 'title' | 'lang' | 'target_title' | 'used_on' | 'content_md'>>;

export const generalResumeService = {
  list: async () => (await api.get<{ resumes: GeneralResume[] }>('/general-resumes')).data.resumes,
  create: async (data: ResumeFields) => (await api.post<GeneralResume>('/general-resumes', data)).data,
  update: async (id: number, data: ResumeFields) => (await api.put<GeneralResume>(`/general-resumes/${id}`, data)).data,
  remove: async (id: number) => (await api.delete(`/general-resumes/${id}`)).data,
  review: async (id: number) => (await api.post<GeneralResume>(`/general-resumes/${id}/review`)).data,
  improve: async (id: number) => (await api.post<{ resume_markdown: string; changes: string[] }>(`/general-resumes/${id}/improve`)).data,
  formSuggestions: async (id: number) => (await api.post<GeneralResume>(`/general-resumes/${id}/form-suggestions`)).data,
  downloadPDF: async (resume: GeneralResume) => {
    const data = (await api.get(`/general-resumes/${resume.id}/pdf`, { responseType: 'blob' })).data;
    const url = window.URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Resume_${(resume.target_title || resume.title).replace(/[^A-Za-z0-9_-]+/g, '_')}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

// FastAPI errors carry the reason in detail
export const errorText = (e: unknown) => {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail || err?.message || 'erro desconhecido';
};
