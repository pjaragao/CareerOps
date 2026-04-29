import api from './api';

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

export const profileService = {
  getProfile: async () => {
    const response = await api.get<Profile>('/profile');
    return response.data;
  },
  saveProfile: async (profile: Profile) => {
    const response = await api.post('/profile', profile);
    return response.data;
  },
  getResume: async () => {
    const response = await api.get<{ content: string }>('/profile/resume');
    return response.data;
  },
  saveResume: async (content: string) => {
    const response = await api.post('/profile/resume', { content });
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
  optimizeSection: async (section: string, content: string) => {
    const response = await api.post<{ result: string }>('/profile/optimize', { section, content });
    return response.data.result;
  }
};
