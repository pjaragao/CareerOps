import axios from 'axios';

const API_URL = 'http://localhost:8005/api';

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
    const response = await axios.get(`${API_URL}/documents`);
    return response.data;
  },

  getDocument: async (id: number): Promise<UserDocument> => {
    const response = await axios.get(`${API_URL}/documents/${id}`);
    return response.data;
  },

  uploadDocument: async (file: File): Promise<{ id: number; status: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API_URL}/documents/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  validateDocument: async (id: number, validatedData: any): Promise<{ ok: boolean }> => {
    const response = await axios.post(`${API_URL}/documents/${id}/validate`, {
      validated_data: validatedData
    });
    return response.data;
  },

  deleteDocument: async (id: number): Promise<{ ok: boolean }> => {
    const response = await axios.delete(`${API_URL}/documents/${id}`);
    return response.data;
  },

  optimizeResume: async (): Promise<any> => {
    const response = await axios.post(`${API_URL}/documents/optimize-resume`);
    return response.data;
  },

  aggregateKnowledge: async (): Promise<{ ok: boolean }> => {
    const response = await axios.post(`${API_URL}/documents/aggregate`);
    return response.data;
  }
};
