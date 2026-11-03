/* eslint-disable @typescript-eslint/no-explicit-any -- JSON bags, as the backend sends them */
import api from './api';
import type { EligibilityIssue } from './jobService';

export type ActionKind = 'apply' | 'comment' | 'follow' | 'connect' | 'search' | 'check' | 'feed_scan' | 'follow_scan' | 'saved_import';

export interface Question { key?: string; label: string; type?: string; options?: string[] }

export interface Action {
  id: number;
  kind: ActionKind;
  lane: string;
  status: string;
  title: string | null;
  target_id: number | null;
  target_url: string | null;
  payload: Record<string, any>;
  executor: string | null;
  error_code: string | null;
  error_text: string | null;
  questions: Question[];
  result: Record<string, any>;
  updated_at: string;
  finished_at: string | null;
  // for jobs
  triage_score?: number | null;
  triage_reason?: string | null;
  posted_at?: string | null;
  employer_market?: string | null;
  salary_flag?: string | null;
  easy_apply?: boolean | null;
  eligibility_status?: 'ok' | 'warning' | 'blocked' | null;
  eligibility_issues?: EligibilityIssue[];
  fit?: number | null;
  sort_at?: string | null;
  created_at?: string;
  company?: string | null;
  job_title?: string | null;
  location?: string | null;
}

export interface FoundJob {
  id: number;
  job_title: string | null;
  company: string | null;
  location: string | null;
  url: string;
  triage_score: number | null;
  triage_reason: string | null;
  posted_at: string | null;
  salary_flag?: string | null;
}

export interface Inbox {
  items: Action[];
  apply: Action[];
  comment: Action[];
  connect: Action[];
  follow: Action[];
  external_manual: FoundJob[];
  discarded: FoundJob[];
}

export interface Limit { kind: string; period: string; limit: number; used: number; left: number; step0: number; step1: number; step2: number }

export interface AutomationStatus {
  role: string;
  state: {
    mode: 'off' | 'dry_run' | 'live';
    account_kind: 'test' | 'main';
    allow_final_submit: boolean;
    halted_at: string | null;
    halted_reason: string | null;
    halted_lanes: string[];
    invites_paused_until: string | null;
    ramp_step: number;
    ramp_auto: boolean;
    confirm_submit_left: number;
    review_cv_left: number;
    session_status: string | null;
  };
  counts: Record<string, number>;
  limits: Limit[];
  claude_today: number;
  claude_per_day: number;
  worker_online: boolean;
  final_submit_possible: boolean;
  novnc_url: string;
}

export interface EmailEvent {
  id: number;
  job_id: number | null;
  received_at: string | null;
  sender_domain: string | null;
  subject: string | null;
  classification: string;
  confidence: number | null;
  summary: string | null;
  evidence_quote: string | null;
  status_applied: string | null;
  needs_review: boolean;
  baseline: boolean;
  job_title?: string | null;
  company?: string | null;
}

export interface SuggestionItem { id: number; company: string | null; suggestion: string; evidence: string | null; job_id: number | null; created_at: string }
export interface SuggestionGroup { target: 'cv' | 'me'; theme: string; n: number; items: SuggestionItem[] }

export interface FunnelRow { bucket: string; applied: number; answered: number; interviews: number }

export interface SearchRow { id: number; slug: string; name: string; enabled: boolean; last_run_at: string | null; jobs_found: number }

const base = '/automation';
const data = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data);

export interface SavedImportSettings { enabled: boolean; day_start: number; day_end: number; day_every: number; night_every: number }
export interface SavedImportRun { id: number; status: string; run_now: boolean; created_at: string; finished_at: string | null; result: Record<string, any>; error_code: string | null; error_text: string | null }

export const automationService = {
  status: () => data(api.get<AutomationStatus>(`${base}/status`)),
  setState: (patch: Partial<Pick<AutomationStatus['state'], 'mode' | 'account_kind' | 'allow_final_submit' | 'ramp_step' | 'ramp_auto'>>) => data(api.patch(`${base}/state`, patch)),
  halt: () => data(api.post(`${base}/halt`, { reason: 'Parado por você' })),
  resume: () => data(api.post(`${base}/resume`)),
  inbox: () => data(api.get<Inbox>(`${base}/inbox`)),
  approve: (id: number, text?: string, runNow = false) => data(api.post(`${base}/actions/${id}/approve`, { text: text ?? null, run_now: runNow })),
  approveBatch: (ids: number[], runNow = false) => data(api.post<{ approved: number[]; refused: number[] }>(`${base}/approve-batch`, { ids, run_now: runNow })),
  revise: (id: number, instruction: string, text?: string) => data(api.post<Action>(`${base}/actions/${id}/revise`, { instruction, text: text ?? null })),
  reject: (id: number) => data(api.post(`${base}/actions/${id}/reject`)),
  recoverJob: (jobId: number) => data(api.post(`${base}/jobs/${jobId}/recover`)),
  needsUser: () => data(api.get<{ items: Action[] }>(`${base}/needs-user`)).then((r) => r.items),
  answer: (id: number, answers: { question: string; answer: string; field_type?: string; save: boolean }[]) => data(api.post(`${base}/needs-user/${id}/answer`, { answers })),
  approveDocs: (id: number) => data(api.post(`${base}/actions/${id}/approve-docs`)),
  confirmSubmit: (id: number) => data(api.post(`${base}/actions/${id}/confirm-submit`)),
  retry: (id: number) => data(api.post(`${base}/actions/${id}/retry`)),
  cancel: (id: number) => data(api.post(`${base}/actions/${id}/cancel`)),
  running: () => data(api.get<{ items: Action[] }>(`${base}/running`)).then((r) => r.items),
  history: () => data(api.get<{ items: Action[] }>(`${base}/history`)).then((r) => r.items),
  events: (id: number) => data(api.get<{ items: { id: number; at: string; source: string; level: string; event: string; data: any; screenshot_path: string | null }[] }>(`${base}/actions/${id}/events`)).then((r) => r.items),
  artifactUrl: async (id: number, name: string) => URL.createObjectURL((await api.get(`${base}/actions/${id}/artifacts/${name}`, { responseType: 'blob' })).data),
  searches: () => data(api.get<{ items: SearchRow[] }>(`${base}/searches`)).then((r) => r.items),
  toggleSearch: (id: number, enabled: boolean) => data(api.patch(`${base}/searches/${id}`, { enabled })),
  savedImport: () => data(api.get<{ settings: SavedImportSettings; runs: SavedImportRun[] }>(`${base}/saved-import`)),
  setSavedImport: (value: SavedImportSettings) => data(api.put<SavedImportSettings>(`${base}/saved-import`, value)),
  runSavedImport: () => data(api.post<SavedImportRun & { already?: boolean; mode: string }>(`${base}/saved-import/run`)),
  setLimit: (kind: string, steps: { step0: number; step1: number; step2: number }) => data(api.put(`${base}/limits/${kind}`, steps)),
  emailEvents: () => data(api.get<{ items: EmailEvent[]; configured: boolean; auto_status: boolean; last_run: { started_at: string; ok: boolean | null; summary: any } | null }>(`${base}/email/events`)),
  emailFunnel: () => data(api.get<{ by_age: FunnelRow[]; by_search: FunnelRow[]; by_market: FunnelRow[]; by_executor: FunnelRow[] }>(`${base}/email/funnel`)),
  emailReview: (id: number, classification?: string) => data(api.post(`${base}/email/events/${id}/review`, { classification: classification ?? null })),
  emailRun: () => data(api.post(`${base}/email/run`)),
  suggestions: () => data(api.get<{ groups: SuggestionGroup[] }>(`${base}/suggestions`)),
  setSuggestion: (id: number, status: 'new' | 'accepted' | 'dismissed') => data(api.patch(`${base}/suggestions/${id}`, { status })),
};
