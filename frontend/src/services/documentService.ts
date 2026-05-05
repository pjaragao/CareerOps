import api from './api';

export interface UserDocument {
  id: number;
  filename: string;
  content_type: string;
  processing_status: 'pending' | 'processing' | 'awaiting_validation' | 'validated' | 'failed';
  created_at: string;
  last_processed_at: string | null;
  extracted_data?: any;
  validated_data?: any;
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

  validateDocument: async (id: number, validatedData: any): Promise<{ ok: boolean }> => {
    const response = await api.post(`/documents/${id}/validate`, {
      validated_data: validatedData
    });
    return response.data;
  },

  validateBulk: async (docIds: number[], mergedData: any): Promise<{ ok: boolean }> => {
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

  optimizeResume: async (): Promise<any> => {
    const response = await api.post('/documents/optimize-resume');
    return response.data;
  },

  aggregateKnowledge: async (): Promise<{ ok: boolean }> => {
    const response = await api.post('/documents/aggregate');
    return response.data;
  }
};
