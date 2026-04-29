import api from './api';

export interface DashboardStats {
  total_jobs: number;
  new_jobs: number;
  pipeline_pending: number;
  stories_count: number;
  apps_count: number;
}

export const dashboardService = {
  getStats: async () => {
    const response = await api.get<DashboardStats>('/dashboard/stats/');
    return response.data;
  },
  getSkillGaps: async () => {
    const response = await api.get<any[]>('/dashboard/skill-gaps/');
    return response.data;
  }
};
