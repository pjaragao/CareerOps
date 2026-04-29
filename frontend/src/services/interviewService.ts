import api from './api';

export interface STARStory {
  id: number;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  tags: string[];
}

export const interviewService = {
  getStories: async () => {
    const response = await api.get<{ stories: STARStory[] }>('/interview/stories');
    return response.data.stories;
  },
  saveStory: async (story: Omit<STARStory, 'id'>) => {
    const response = await api.post('/interview/stories', story);
    return response.data;
  },
  generateSTAR: async (description: string) => {
    const response = await api.post<Omit<STARStory, 'id' | 'tags'>>('/interview/generate-star', { description });
    return response.data;
  },
  deleteStory: async (id: number) => {
    const response = await api.delete(`/interview/stories/${id}`);
    return response.data;
  }
};
