import api from './api';

export const authService = {
  startLogin: async () => {
    const response = await api.post('/auth/login');
    return response.data;
  },
  finishLogin: async () => {
    const response = await api.post('/auth/finish-login');
    return response.data;
  },
  getStatus: async () => {
    const response = await api.get('/auth/status');
    return response.data;
  },
  uploadSession: async (data: any) => {
    const response = await api.post('/auth/session-upload', data);
    return response.data;
  }
};
