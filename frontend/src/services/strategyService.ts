import api from './api';

export interface Strategy {
  id: number;
  title: string;
  keywords: string[];
  locations: string[];
  remote_only: boolean;
  active: boolean;
  created_at: string;
}

export const strategyService = {
  getStrategies: async () => {
    const response = await api.get<{ strategies: Strategy[] }>('/strategies');
    return response.data.strategies;
  },
  saveStrategy: async (strategy: Omit<Strategy, 'id' | 'active' | 'created_at'>) => {
    const response = await api.post('/strategies', strategy);
    return response.data;
  },
  deleteStrategy: async (id: number) => {
    const response = await api.delete(`/strategies/${id}`);
    return response.data;
  },
  runStrategy: async (id: number) => {
    const response = await api.post(`/strategies/${id}/run`);
    return response.data;
  }
};
