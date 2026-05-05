import React, { useEffect, useState } from 'react';
import { documentService, UserDocument } from '../services/documentService';
import { 
  FileText, 
  Upload, 
  Trash2, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  RefreshCw, 
  Eye, 
  Check, 
  X,
  Plus,
  Sparkles,
  Zap,
  ChevronRight
} from 'lucide-react';

const DocumentRepository = () => {
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<UserDocument | null>(null);
  const [validationData, setValidationData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'pending'>('all');

  useEffect(() => {
    loadDocuments();
    const interval = setInterval(loadDocuments, 5000); // Poll for status updates
    return () => clearInterval(interval);
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentService.listDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error("Failed to load documents", error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await documentService.uploadDocument(file);
      loadDocuments();
    } catch (error) {
      alert("Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this document?")) return;
    try {
      await documentService.deleteDocument(id);
      loadDocuments();
    } catch (error) {
      alert("Failed to delete document");
    }
  };

  const startValidation = async (doc: UserDocument) => {
    try {
      const fullDoc = await documentService.getDocument(doc.id);
      setSelectedDoc(fullDoc);
      setValidationData(fullDoc.extracted_data || {});
    } catch (error) {
      alert("Failed to load document details");
    }
  };

  const handleValidate = async () => {
    if (!selectedDoc) return;
    try {
      await documentService.validateDocument(selectedDoc.id, validationData);
      setSelectedDoc(null);
      loadDocuments();
      alert("Document validated and added to Knowledge Base!");
    } catch (error) {
      alert("Failed to validate document");
    }
  };

  const handleOptimizeResume = async () => {
    setLoading(true);
    try {
      const result = await documentService.optimizeResume();
      if (result.error) {
        alert(result.error);
      } else {
        alert("Resume optimization suggestions generated! Check the Profile page.");
        // In a real app, we might redirect to a comparison view
      }
    } catch (error) {
      alert("Failed to optimize resume");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'validated':
        return <span className="badge" style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', display: 'flex', alignItems: 'center', gap: '4px' }}><CheckCircle2 size={14} /> Validated</span>;
      case 'awaiting_validation':
        return <span className="badge" style={{ backgroundColor: 'rgba(234, 179, 8, 0.2)', color: '#facc15', display: 'flex', alignItems: 'center', gap: '4px' }}><Clock size={14} /> Review Needed</span>;
      case 'processing':
        return <span className="badge" style={{ backgroundColor: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '4px' }}><RefreshCw size={14} className="animate-spin" /> Processing</span>;
      case 'failed':
        return <span className="badge" style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#f87171', display: 'flex', alignItems: 'center', gap: '4px' }}><AlertCircle size={14} /> Failed</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Document Repository</h1>
          <p style={{ color: 'var(--text-muted)' }}>Manage your professional documents and build your Knowledge Base.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-secondary" onClick={handleOptimizeResume}>
            <Sparkles size={18} /> Optimize Base Resume
          </button>
          <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
            <Upload size={18} /> {uploading ? 'Uploading...' : 'Upload Document'}
            <input type="file" hidden onChange={handleFileUpload} accept=".pdf,.doc,.docx,.txt" disabled={uploading} />
          </label>
        </div>
      </div>

      <div className="panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', gap: '2rem' }}>
          <button 
            onClick={() => setActiveTab('all')}
            style={{ background: 'none', border: 'none', color: activeTab === 'all' ? 'var(--primary-color)' : 'var(--text-muted)', fontWeight: 600, cursor: 'pointer', borderBottom: activeTab === 'all' ? '2px solid var(--primary-color)' : 'none', paddingBottom: '0.5rem' }}
          >
            All Documents ({documents.length})
          </button>
          <button 
            onClick={() => setActiveTab('pending')}
            style={{ background: 'none', border: 'none', color: activeTab === 'pending' ? 'var(--primary-color)' : 'var(--text-muted)', fontWeight: 600, cursor: 'pointer', borderBottom: activeTab === 'pending' ? '2px solid var(--primary-color)' : 'none', paddingBottom: '0.5rem' }}
          >
            Awaiting Review ({documents.filter(d => d.processing_status === 'awaiting_validation').length})
          </button>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <th style={{ padding: '1.2rem 1.5rem' }}>Document</th>
              <th style={{ padding: '1.2rem 1.5rem' }}>Status</th>
              <th style={{ padding: '1.2rem 1.5rem' }}>Added At</th>
              <th style={{ padding: '1.2rem 1.5rem', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents
              .filter(d => activeTab === 'all' || d.processing_status === 'awaiting_validation')
              .map(doc => (
              <tr key={doc.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.2s' }} className="hover-row">
                <td style={{ padding: '1.2rem 1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ backgroundColor: 'rgba(255,255,255,0.05)', padding: '8px', borderRadius: '8px' }}>
                      <FileText size={20} color="var(--primary-color)" />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600 }}>{doc.filename}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{doc.content_type}</div>
                    </div>
                  </div>
                </td>
                <td style={{ padding: '1.2rem 1.5rem' }}>
                  {getStatusBadge(doc.processing_status)}
                </td>
                <td style={{ padding: '1.2rem 1.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  {new Date(doc.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '1.2rem 1.5rem', textAlign: 'right' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                    {doc.processing_status === 'awaiting_validation' && (
                      <button className="btn btn-primary btn-sm" onClick={() => startValidation(doc)}>
                        Review
                      </button>
                    )}
                    {doc.processing_status === 'validated' && (
                      <button className="btn btn-secondary btn-sm" onClick={() => startValidation(doc)}>
                        <Eye size={14} />
                      </button>
                    )}
                    <button className="btn btn-secondary btn-sm" style={{ color: '#f87171' }} onClick={() => handleDelete(doc.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <div style={{ marginBottom: '1rem' }}><Upload size={48} opacity={0.2} /></div>
                  No documents found. Upload your first document to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Validation Modal */}
      {selectedDoc && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.8)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '2rem' }}>
          <div className="panel" style={{ width: '100%', maxWidth: '1200px', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><Zap color="var(--primary-color)" /> Review Extracted Info</h2>
              <button onClick={() => setSelectedDoc(null)} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}><X /></button>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', overflow: 'hidden', flex: 1 }}>
              {/* Raw Text (MarkItDown) */}
              <div style={{ padding: '1.5rem', overflowY: 'auto', borderRight: '1px solid rgba(255,255,255,0.1)', backgroundColor: 'rgba(0,0,0,0.2)' }}>
                <h3 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Raw Document (Markdown)</h3>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', lineHeight: '1.6', color: '#e2e8f0', fontFamily: 'monospace' }}>
                  {selectedDoc.raw_text}
                </pre>
              </div>

              {/* Extracted Data */}
              <div style={{ padding: '1.5rem', overflowY: 'auto' }}>
                <h3 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '1px' }}>AI Findings (Edit to Correct)</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                  {/* Summary */}
                  <section>
                    <label className="field-label">Professional Summary</label>
                    <textarea 
                      value={validationData.summary || ''} 
                      onChange={e => setValidationData({...validationData, summary: e.target.value})}
                      style={{ height: '100px' }}
                    />
                  </section>

                  {/* Skills */}
                  <section>
                    <label className="field-label">Extracted Skills</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {(validationData.skills || []).map((skill: string, i: number) => (
                        <span key={i} className="badge" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px' }}>
                          {skill}
                          <button onClick={() => {
                            const next = validationData.skills.filter((_:any, idx:number) => idx !== i);
                            setValidationData({...validationData, skills: next});
                          }} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex' }}><X size={12} /></button>
                        </span>
                      ))}
                      <button className="btn btn-secondary btn-sm" onClick={() => {
                        const s = prompt("New skill:");
                        if (s) setValidationData({...validationData, skills: [...(validationData.skills || []), s]});
                      }}><Plus size={14} /></button>
                    </div>
                  </section>

                  {/* Experiences */}
                  <section>
                    <label className="field-label">Experiences</label>
                    {(validationData.experiences || []).map((exp: any, i: number) => (
                      <div key={i} className="panel" style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', marginBottom: '1rem' }}>
                        <div style={{ fontWeight: 600 }}>{exp.role} @ {exp.company}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{exp.period}</div>
                        <textarea 
                          value={exp.description} 
                          onChange={e => {
                            const next = [...validationData.experiences];
                            next[i].description = e.target.value;
                            setValidationData({...validationData, experiences: next});
                          }}
                          style={{ height: '80px', fontSize: '0.9rem' }}
                        />
                      </div>
                    ))}
                  </section>

                  {/* STAR Cases */}
                  <section>
                    <label className="field-label">Raw STAR Cases (Key Achievements)</label>
                    {(validationData.star_cases || []).map((case_data: any, i: number) => (
                      <div key={i} className="panel" style={{ border: '1px solid var(--primary-color)', padding: '1rem', marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                          <input 
                            value={case_data.title} 
                            onChange={e => {
                              const next = [...validationData.star_cases];
                              next[i].title = e.target.value;
                              setValidationData({...validationData, star_cases: next});
                            }}
                            style={{ fontWeight: 'bold', background: 'transparent', border: 'none', width: '100%' }}
                          />
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.9rem' }}>
                          <div><strong>S:</strong> <textarea value={case_data.situation} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].situation = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '50px' }} /></div>
                          <div><strong>T:</strong> <textarea value={case_data.task} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].task = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '50px' }} /></div>
                          <div><strong>A:</strong> <textarea value={case_data.action} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].action = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '50px' }} /></div>
                          <div><strong>R:</strong> <textarea value={case_data.result} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].result = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '50px' }} /></div>
                        </div>
                      </div>
                    ))}
                  </section>
                </div>
              </div>
            </div>

            <div style={{ padding: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button className="btn btn-secondary" onClick={() => setSelectedDoc(null)}>Cancel</button>
              {selectedDoc.processing_status !== 'validated' && (
                <button className="btn btn-primary" onClick={handleValidate}>
                  <Check size={18} /> Approve & Add to Knowledge Base
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .hover-row:hover {
          background-color: rgba(255,255,255,0.02);
        }
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default DocumentRepository;
