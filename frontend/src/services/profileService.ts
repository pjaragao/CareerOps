import api from './api';

export interface ProfileLanguageData {
  about?: string;
  experience?: Array<{
    company: string;
    role: string;
    period: string;
    description: string;
  }>;
  education?: Array<{
    institution: string;
    degree: string;
    year: string;
  }>;
  skills?: string[];
  keywords?: string[];
}

export interface Profile {
  personal?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
    linkedin?: string;
    github?: string;
    website?: string;
  };
  legal?: {
    visa_status?: string;
    work_auth?: string;
    gender?: string;
    ethnicity?: string;
    disability?: string;
    veteran?: string;
  };
  preferences?: {
    target_role?: string;
    work_mode?: string;
    min_salary?: string;
    experience_level?: string;
  };
  languages?: Record<string, ProfileLanguageData>;
  // Fallback
  experience?: any;
  education?: any;
  skills?: any;
  keywords?: any;
  about?: string;
}

export const profileService = {
  getProfile: async () => {
    const response = await api.get<Profile>('/profile');
    return response.data;
  },
  saveProfile: async (profile: Profile) => {
    const response = await api.post('/profile', profile);
    return response.data;
  },
  // lang: 'en' = CV for jobs abroad, 'pt' = CV for jobs in Brazil
  getResume: async (lang: 'en' | 'pt' = 'en') => {
    const response = await api.get<{ content: string }>('/profile/resume', { params: { lang } });
    return response.data;
  },
  saveResume: async (content: string, lang: 'en' | 'pt' = 'en') => {
    const response = await api.post('/profile/resume', { content }, { params: { lang } });
    return response.data;
  },
  uploadResume: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<Profile>('/profile/upload-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },
  importFromLinkedin: async () => {
    const response = await api.post('/profile/import-linkedin');
    return response.data;
  },
  optimizeSection: async (section: string, content: string, lang: string = 'pt', strategy_context?: any) => {
    const response = await api.post<{ result: string }>('/profile/optimize', { section, content, lang, strategy_context });
    return response.data.result;
  },
  getScore: async (content: string) => {
    const response = await api.post('/profile/score', { content });
    return response.data;
  },
  getHeadlineVariants: async (lang: string, count = 3, strategy_context?: any) => {
    const response = await api.post('/profile/headline-variants', { lang, count, strategy_context });
    return response.data;
  },
  optimizeExperience: async (lang: string, strategy_context?: any) => {
    const response = await api.post('/profile/optimize-experience', { lang, strategy_context });
    return response.data;
  },
  restructureExperience: async (lang: string, strategy_context?: any) => {
    const response = await api.post('/profile/restructure-experience', { lang, strategy_context });
    return response.data;
  },
  analyzeSkills: async (targetRole: string, lang: string = 'pt', strategy_context?: any) => {
    const response = await api.post('/profile/analyze-skills', { target_role: targetRole, lang, strategy_context });
    return response.data;
  },
  simulateSSI: async () => {
    const response = await api.post('/profile/ssi-simulate');
    return response.data;
  },
  atsMatch: async (jobDescription: string, lang: string = 'pt', strategy_context?: any) => {
    const response = await api.post('/profile/ats-match', { job_description: jobDescription, lang, strategy_context });
    return response.data;
  },
  getLatestAnalysis: async (type: string) => {
    const response = await api.get(`/profile/optimizer-analysis?type=${type}`);
    return response.data.analysis;
  },
  runFullAudit: async (lang: string, strategy_context?: any) => {
    const response = await api.post('/profile/run-full-audit', { lang, strategy_context });
    return response.data.results;
  }
};
