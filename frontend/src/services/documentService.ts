import api from './api';

// What the AI extracted from the files, reviewed by you before it becomes knowledge
export interface ExperienceItem { role?: string; company?: string; period?: string; description?: string; [key: string]: unknown }
export interface StarCase { title?: string; situation?: string; task?: string; action?: string; result?: string; [key: string]: unknown }
export interface KnowledgeData {
  summary?: string;
  skills?: string[];
  experiences?: ExperienceItem[];
  star_cases?: StarCase[];
  [key: string]: unknown;
}

export interface UserDocument {
  id: number;
  filename: string;
  content_type: string;
  processing_status: 'pending' | 'processing' | 'awaiting_validation' | 'validated' | 'failed';
  created_at: string;
  last_processed_at: string | null;
  extracted_data?: KnowledgeData;
  validated_data?: KnowledgeData;
  raw_text?: string;
}

export const documentService = {
  listDocuments: async (): Promise<UserDocument[]> => {
    const response = await api.get('/documents');
    return response.data;
  },

  getDocument: async (id: number): Promise<UserDocument> => {
    const response = await api.get(`/documents/${id}`);
    return response.data;
  },

  uploadDocument: async (file: File): Promise<{ id: number; status: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  processBulk: async (docIds: number[]): Promise<{ ok: boolean }> => {
    const response = await api.post('/documents/process-bulk', docIds);
    return response.data;
  },

  consolidate: async (docIds: number[]): Promise<KnowledgeData> => {
    const response = await api.post('/documents/consolidate', docIds);
    return response.data;
  },

  validateDocument: async (id: number, validatedData: KnowledgeData): Promise<{ ok: boolean }> => {
    const response = await api.post(`/documents/${id}/validate`, {
      validated_data: validatedData
    });
    return response.data;
  },

  validateBulk: async (docIds: number[], mergedData: KnowledgeData): Promise<{ ok: boolean }> => {
    const response = await api.post('/documents/bulk-validate', {
      doc_ids: docIds,
      merged_data: mergedData
    });
    return response.data;
  },

  deleteDocument: async (id: number): Promise<{ ok: boolean }> => {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },

  optimizeResume: async (): Promise<{ error?: string; [key: string]: unknown }> => {
    const response = await api.post('/documents/optimize-resume');
    return response.data;
  },

  aggregateKnowledge: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/documents/aggregate');
    return response.data;
  }
};
