import api from './api';

export interface AppSettings {
  gemini_api_key: string;
  linkedin_email: string;
  scrape_delay: number;
  max_jobs: number;
  openai_api_key?: string;
  openai_base_url?: string;
  ai_model_resume?: string;
  ai_model_cover?: string;
  ai_model_chat?: string;
  ai_model_outreach?: string;
  ai_model_import?: string;
  ai_model_optimizer?: string;
  ai_model_interview?: string;
  ai_model_fallback?: string;
}

export const settingsService = {
  getSettings: async () => {
    const response = await api.get<AppSettings>('/settings');
    return response.data;
  },
  updateSettings: async (settings: Partial<AppSettings>) => {
    const response = await api.post('/settings', settings);
    return response.data;
  },
  getAvailableModels: async () => {
    const response = await api.get<{id: string, name: string}[]>('/jobs/models');
    return response.data;
  },
  getSessionStatus: async () => {
    const response = await api.get<{ exists: boolean, last_updated: number }>('/settings/session-status');
    return response.data;
  }
};
