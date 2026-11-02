import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

// The token for what acts on your behalf (publishing, automation): typed once in Configurações → Acesso.
// Storage may be blocked (private mode): the rest of the app works without it.
const TOKEN_KEY = 'careerops.token';
export const getAccessToken = (): string => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
export const setAccessToken = (token: string): void => { try { localStorage.setItem(TOKEN_KEY, token); } catch { /* not remembered */ } };

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.set('X-CareerOps-Token', token);
  return config;
});

export default api;
