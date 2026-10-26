import api from './api';

export type PostStatus = 'draft' | 'approved' | 'published' | 'failed' | 'discarded';

export interface CopilotPost {
  id: number;
  pillar: string | null;
  topic: string | null;
  source_notes: string | null;
  body: string;
  status: PostStatus;
  scheduled_for: string | null;
  published_at: string | null;
  linkedin_urn: string | null;
  error: string | null;
  created_at: string;
}

export interface EngagementItem {
  id: number;
  post_url: string | null;
  author_name: string | null;
  author_headline: string | null;
  post_text: string;
  relevance: number | null;
  reason: string | null;
  comment_draft: string | null;
  status: 'pending' | 'done' | 'skipped';
}

export type ProspectStatus = 'to_contact' | 'invited' | 'accepted' | 'replied' | 'skipped';

export interface Prospect {
  id: number;
  profile_url: string | null;
  name: string | null;
  headline: string | null;
  company: string | null;
  segment: string | null;
  fit: number | null;
  reason: string | null;
  note_draft: string | null;
  status: ProspectStatus;
}

export interface CopilotStatus {
  configured: boolean;
  connected: boolean;
  member_name: string | null;
  expires_at: string | null;
}

export interface WeekMetrics {
  week_start: string;
  posts: number;
  comments: number;
  invites: number;
  accepted: number;
  profile_views: number | null;
  search_appearances: number | null;
  post_impressions: number | null;
  recruiter_messages: number | null;
  interviews: number | null;
  notes: string | null;
}

const base = '/linkedin-copilot';

export const linkedinCopilotService = {
  status: async () => (await api.get<CopilotStatus>(`${base}/status`)).data,
  connectUrl: async () => (await api.get<{ url: string }>(`${base}/oauth/start`)).data.url,
  disconnect: async () => (await api.post(`${base}/disconnect`)).data,

  listPosts: async () => (await api.get<{ posts: CopilotPost[] }>(`${base}/posts`)).data.posts,
  generatePosts: async (req: { count: number; pillar?: string; topic?: string; source_notes?: string }) =>
    (await api.post<{ posts: CopilotPost[] }>(`${base}/posts/generate`, req)).data.posts,
  updatePost: async (id: number, body: string) => (await api.patch<CopilotPost>(`${base}/posts/${id}`, { body })).data,
  approvePost: async (id: number, scheduled_for?: string) =>
    (await api.post<CopilotPost>(`${base}/posts/${id}/approve`, { scheduled_for: scheduled_for || null })).data,
  unapprovePost: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/unapprove`)).data,
  publishPost: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/publish`)).data,
  markPublished: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/mark-published`)).data,
  discardPost: async (id: number) => (await api.delete(`${base}/posts/${id}`)).data,

  engagementQueue: async () =>
    (await api.get<{ items: EngagementItem[]; done_today: number; daily_target: number }>(`${base}/engagement`)).data,
  addEngagement: async (req: { post_text: string; post_url?: string; author_name?: string }) =>
    (await api.post<EngagementItem>(`${base}/engagement`, req)).data,
  updateEngagement: async (id: number, patch: Partial<Pick<EngagementItem, 'status' | 'comment_draft'>>) =>
    (await api.patch<EngagementItem>(`${base}/engagement/${id}`, patch)).data,

  prospects: async () =>
    (await api.get<{ items: Prospect[]; invited_this_week: number; weekly_target: number }>(`${base}/prospects`)).data,
  addProspect: async (req: { profile_text: string; profile_url?: string; name?: string }) =>
    (await api.post<Prospect>(`${base}/prospects`, req)).data,
  updateProspect: async (id: number, patch: Partial<Pick<Prospect, 'status' | 'note_draft'>>) =>
    (await api.patch<Prospect>(`${base}/prospects/${id}`, patch)).data,

  metrics: async () => (await api.get<{ weeks: WeekMetrics[] }>(`${base}/metrics`)).data.weeks,
  saveMetrics: async (week_start: string, values: Partial<WeekMetrics>) =>
    (await api.put(`${base}/metrics/${week_start}`, values)).data,
};
