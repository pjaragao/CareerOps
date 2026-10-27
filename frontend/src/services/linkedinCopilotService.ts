import api from './api';

export type PostStatus = 'draft' | 'approved' | 'published' | 'failed' | 'discarded';

// br = Brazil (Portuguese: engineering, sanitation, modeling) · intl = abroad (English: data, finance, modeling)
export type Market = 'br' | 'intl';

export interface CopilotPost {
  id: number;
  market: Market;
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
  market: Market | null;
  profile_url: string | null;
  name: string | null;
  headline: string | null;
  company: string | null;
  segment: string | null;
  fit: number | null;
  reason: string | null;
  note_draft: string | null;
  message_draft: string | null;
  message_sent_at: string | null;
  status: ProspectStatus;
}

export type VoiceKind = 'comment' | 'reply' | 'message' | 'post' | 'position';

// One thing you said in public (or a position you wrote): new texts stay consistent with these
export interface VoiceItem {
  id: number;
  kind: VoiceKind;
  lang: string | null;
  topic: string | null;
  stance: string | null;
  text: string;
  context: string | null;
  instruction: string | null;
  post_url: string | null;
  pinned: boolean;
  used_count: number;
  created_at: string;
}

export interface VoiceData {
  items: VoiceItem[];
  text: string;             // the consolidated profile of positions
  updated_at: string | null;
  total: number;
  new_since_profile: number;
}

export interface PlanCompany { company: string; job_ids: number[]; market: Market | null; similar: boolean; why: string | null; url: string }
export interface PlanPerson { action: 'connect' | 'follow'; role: string | null; company: string | null; search: string; market: Market | null; job_id: number | null; why: string | null; url: string }
export interface PlanPost { topic: string; search: string; market: Market | null; angle: string | null; why: string | null; url: string }
export interface PlanMessage { prospect_id: number; name: string | null; headline: string | null; job_id: number | null; text: string; why: string | null }

export interface NetworkingPlan {
  id: number;
  created_at: string;
  done: string[];           // "people:3"…
  jobs: { id: number; job_title: string; company: string; status: string }[];
  plan: { companies: PlanCompany[]; people: PlanPerson[]; posts: PlanPost[]; messages: PlanMessage[] };
}

export interface Inspiration {
  id: number;
  post_url: string | null;
  author_name: string | null;
  author_headline: string | null;
  post_text: string;
  note: string | null;
  used_count: number;
  market: Market;
  created_at: string;
}

export interface CopilotStatus {
  configured: boolean;
  connected: boolean;
  member_name: string | null;
  expires_at: string | null;
  redirect_uri?: string;
  frontend_url?: string;
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
  generatePosts: async (req: { market: Market; count: number; pillar?: string; topic?: string; source_notes?: string; inspiration_id?: number }) =>
    (await api.post<{ posts: CopilotPost[] }>(`${base}/posts/generate`, req)).data.posts,
  updatePost: async (id: number, body: string) => (await api.patch<CopilotPost>(`${base}/posts/${id}`, { body })).data,
  approvePost: async (id: number, scheduled_for?: string) =>
    (await api.post<CopilotPost>(`${base}/posts/${id}/approve`, { scheduled_for: scheduled_for || null })).data,
  unapprovePost: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/unapprove`)).data,
  publishPost: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/publish`)).data,
  markPublished: async (id: number) => (await api.post<CopilotPost>(`${base}/posts/${id}/mark-published`)).data,
  discardPost: async (id: number) => (await api.delete(`${base}/posts/${id}`)).data,

  inspirations: async () => (await api.get<{ items: Inspiration[] }>(`${base}/inspirations`)).data.items,
  deleteInspiration: async (id: number) => (await api.delete(`${base}/inspirations/${id}`)).data,

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

  draftMessage: async (id: number, instruction?: string) =>
    (await api.post<Prospect & { topic?: string; stance?: string }>(`${base}/prospects/${id}/message`, { instruction: instruction || null })).data,
  messageSent: async (id: number, req: { text: string; instruction?: string; topic?: string; stance?: string }) =>
    (await api.post<Prospect>(`${base}/prospects/${id}/message/sent`, req)).data,

  voice: async (q?: string) => (await api.get<VoiceData>(`${base}/voice`, { params: q ? { q } : {} })).data,
  addPosition: async (text: string, topic?: string) => (await api.post<VoiceItem>(`${base}/voice`, { kind: 'position', text, topic: topic || null })).data,
  updateVoice: async (id: number, patch: Partial<Pick<VoiceItem, 'topic' | 'stance' | 'text' | 'pinned'>>) =>
    (await api.patch<VoiceItem>(`${base}/voice/${id}`, patch)).data,
  deleteVoice: async (id: number) => (await api.delete(`${base}/voice/${id}`)).data,
  saveVoiceProfile: async (text: string) => (await api.put(`${base}/voice-profile`, { text })).data,
  consolidateVoice: async () => (await api.post<{ text: string; changes: string }>(`${base}/voice-profile/consolidate`)).data,

  networking: async () => (await api.get<{ plan: NetworkingPlan | null }>(`${base}/networking`)).data.plan,
  generateNetworking: async () => (await api.post<{ plan: NetworkingPlan }>(`${base}/networking/generate`)).data.plan,
  markNetworking: async (id: number, key: string, done: boolean) =>
    (await api.patch<{ plan: NetworkingPlan }>(`${base}/networking/${id}`, { key, done })).data.plan,

  metrics: async () => (await api.get<{ weeks: WeekMetrics[] }>(`${base}/metrics`)).data.weeks,
  saveMetrics: async (week_start: string, values: Partial<WeekMetrics>) =>
    (await api.put(`${base}/metrics/${week_start}`, values)).data,
};
