import api from './api';

export interface PipelineUrl {
  id: number;
  url: string;
  source: string;
  status: string;
  created_at: string;
}

export const pipelineService = {
  getUrls: async (status: string = 'pending') => {
    const response = await api.get<{ urls: PipelineUrl[] }>(`/pipeline?status=${status}`);
    return response.data.urls;
  },
  addUrl: async (url: string, source: string = 'manual') => {
    const response = await api.post('/pipeline', { url, source });
    return response.data;
  },
  deleteUrl: async (id: number) => {
    const response = await api.delete(`/pipeline/${id}`);
    return response.data;
  }
};
