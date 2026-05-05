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
  ChevronRight,
  ArrowRight,
  ClipboardList
} from 'lucide-react';

type Step = 'upload' | 'analyze' | 'review' | 'finalize';

const DocumentRepository = () => {
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [currentStep, setCurrentStep] = useState<Step>('upload');
  
  // Review state
  const [selectedDoc, setSelectedDoc] = useState<UserDocument | null>(null);
  const [validationData, setValidationData] = useState<any>(null);
  const [isBulkReview, setIsBulkReview] = useState(false);
  const [pendingDocIds, setPendingDocIds] = useState<number[]>([]);

  useEffect(() => {
    loadDocuments();
    const interval = setInterval(() => {
      // Only poll if we are in analysis step or have pending docs
      loadDocuments();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await documentService.listDocuments();
      setDocuments(docs);
      
      // Auto-determine step based on data if not manually set
      const pendingAnalysis = docs.filter(d => d.processing_status === 'pending');
      const awaitingReview = docs.filter(d => d.processing_status === 'awaiting_validation');
      
      if (currentStep === 'upload' && docs.length > 0 && pendingAnalysis.length > 0) {
        // Stay in upload or move to analyze? Let's let user click.
      }
    } catch (error) {
      console.error("Failed to load documents", error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      const uploadPromises = Array.from(files).map(file => documentService.uploadDocument(file));
      await Promise.all(uploadPromises);
      await loadDocuments();
    } catch (error) {
      console.error("Upload error", error);
      alert("Failed to upload one or more documents");
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async () => {
    const pending = documents.filter(d => d.processing_status === 'pending');
    if (pending.length === 0) return;
    
    try {
      await documentService.processBulk(pending.map(p => p.id));
      setCurrentStep('analyze');
    } catch (error) {
      alert("Failed to start analysis");
    }
  };

  const startBulkReview = () => {
    const pending = documents.filter(d => d.processing_status === 'awaiting_validation');
    if (pending.length === 0) return;

    const merged = {
      summary: "",
      personal: {},
      education: [] as any[],
      skills: [] as string[],
      experiences: [] as any[],
      star_cases: [] as any[]
    };

    pending.forEach(d => {
      const data = d.extracted_data || {};
      if (data.skills) merged.skills = Array.from(new Set([...merged.skills, ...data.skills]));
      if (data.education) merged.education = [...merged.education, ...data.education];
      if (data.experiences) merged.experiences = [...merged.experiences, ...data.experiences];
      if (data.star_cases) merged.star_cases = [...merged.star_cases, ...data.star_cases];
      if (data.summary && !merged.summary) merged.summary = data.summary;
    });

    setValidationData(merged);
    setIsBulkReview(true);
    setPendingDocIds(pending.map(p => p.id));
    setSelectedDoc({ filename: 'Consolidated Knowledge', processing_status: 'awaiting_validation' } as any);
    setCurrentStep('review');
  };

  const handleValidate = async () => {
    if (pendingDocIds.length === 0) return;
    try {
      if (isBulkReview) {
        await documentService.validateBulk(pendingDocIds, validationData);
      } else {
        await documentService.validateDocument(pendingDocIds[0], validationData);
      }
      setSelectedDoc(null);
      await loadDocuments();
      setCurrentStep('finalize');
    } catch (error) {
      alert("Failed to validate");
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
      }
    } catch (error) {
      alert("Failed to optimize resume");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this document?")) return;
    try {
      await documentService.deleteDocument(id);
      loadDocuments();
    } catch (error) {
      alert("Failed to delete");
    }
  };

  // Helper to get status counts
  const counts = {
    pending: documents.filter(d => d.processing_status === 'pending').length,
    processing: documents.filter(d => d.processing_status === 'processing').length,
    review: documents.filter(d => d.processing_status === 'awaiting_validation').length,
    done: documents.filter(d => d.processing_status === 'validated').length,
    failed: documents.filter(d => d.processing_status === 'failed').length
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '1rem', background: 'linear-gradient(to right, #60a5fa, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          AI Onboarding Wizard
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>
          Follow the steps to build your professional knowledge base from your documents.
        </p>
      </div>

      {/* Stepper */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3rem', position: 'relative' }}>
        <div style={{ position: 'absolute', top: '24px', left: '10%', right: '10%', height: '2px', background: 'rgba(255,255,255,0.1)', zIndex: 0 }}></div>
        
        {[
          { id: 'upload', label: 'Upload Files', icon: <Upload size={20} /> },
          { id: 'analyze', label: 'AI Analysis', icon: <Zap size={20} /> },
          { id: 'review', label: 'Review Info', icon: <ClipboardList size={20} /> },
          { id: 'finalize', label: 'Finish', icon: <CheckCircle2 size={20} /> }
        ].map((s, i) => {
          const isActive = currentStep === s.id;
          const isDone = ['upload', 'analyze', 'review', 'finalize'].indexOf(currentStep) > i;
          
          return (
            <div key={s.id} style={{ zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', width: '20%' }}>
              <div style={{ 
                width: '48px', 
                height: '48px', 
                borderRadius: '50%', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                backgroundColor: isActive ? 'var(--primary-color)' : (isDone ? '#22c55e' : '#1e293b'),
                color: 'white',
                marginBottom: '0.8rem',
                boxShadow: isActive ? '0 0 20px rgba(59, 130, 246, 0.5)' : 'none',
                transition: 'all 0.3s ease'
              }}>
                {isDone ? <Check size={24} /> : s.icon}
              </div>
              <span style={{ 
                fontWeight: 600, 
                fontSize: '0.9rem', 
                color: isActive ? 'white' : 'var(--text-muted)',
                textAlign: 'center'
              }}>
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Content Area */}
      <div className="panel" style={{ minHeight: '400px', padding: '2.5rem', display: 'flex', flexDirection: 'column' }}>
        
        {/* Step 1: Upload */}
        {currentStep === 'upload' && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              border: '2px dashed rgba(255,255,255,0.1)', 
              borderRadius: '16px', 
              padding: '4rem 2rem', 
              backgroundColor: 'rgba(255,255,255,0.02)',
              marginBottom: '2rem',
              transition: 'all 0.3s ease',
              cursor: 'pointer'
            }} onMouseOver={e => e.currentTarget.style.borderColor = 'var(--primary-color)'} onMouseOut={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}>
              <label style={{ cursor: 'pointer' }}>
                <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', width: '80px', height: '80px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
                  <Plus size={40} color="var(--primary-color)" />
                </div>
                <h3 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Drop your files here</h3>
                <p style={{ color: 'var(--text-muted)' }}>PDF, Word or Text documents (Resumes, Cover Letters, Portfolios)</p>
                <input type="file" multiple hidden onChange={handleFileUpload} accept=".pdf,.doc,.docx,.txt" />
              </label>
            </div>

            {documents.length > 0 && (
              <div style={{ marginBottom: '2rem', textAlign: 'left' }}>
                <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}><FileText size={18} /> Uploaded Files ({documents.length})</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  {documents.map(doc => (
                    <div key={doc.id} className="panel" style={{ padding: '0.8rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                        <FileText size={16} color="var(--primary-color)" />
                        <span style={{ fontSize: '0.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{doc.filename}</span>
                      </div>
                      <button onClick={() => handleDelete(doc.id)} style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: '4px' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'auto' }}>
              <button 
                className="btn btn-primary btn-lg" 
                disabled={documents.length === 0 || uploading} 
                onClick={handleAnalyze}
                style={{ paddingLeft: '2rem', paddingRight: '2rem' }}
              >
                {uploading ? 'Uploading...' : 'Start AI Analysis'} <ArrowRight size={20} style={{ marginLeft: '10px' }} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Analyze */}
        {currentStep === 'analyze' && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ marginBottom: '3rem' }}>
              <div style={{ position: 'relative', width: '120px', height: '120px', margin: '0 auto 2rem' }}>
                <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', borderRadius: '50%', border: '4px solid rgba(59, 130, 246, 0.1)', borderTopColor: 'var(--primary-color)' }} className="animate-spin"></div>
                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
                  <Zap size={40} color="var(--primary-color)" />
                </div>
              </div>
              <h2 style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>AI is extracting your experience...</h2>
              <p style={{ color: 'var(--text-muted)' }}>This takes about 30-60 seconds depending on the number of files.</p>
            </div>

            <div className="panel" style={{ background: 'rgba(0,0,0,0.2)', padding: '1.5rem', textAlign: 'left' }}>
              <h4 style={{ marginBottom: '1rem' }}>Processing Queue</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {documents.map(doc => (
                  <div key={doc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <FileText size={16} color="var(--text-muted)" />
                      <span>{doc.filename}</span>
                    </div>
                    <div>
                      {doc.processing_status === 'processing' ? (
                        <span style={{ color: 'var(--primary-color)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}><RefreshCw size={14} className="animate-spin" /> Analyzing...</span>
                      ) : doc.processing_status === 'awaiting_validation' ? (
                        <span style={{ color: '#22c55e', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}><CheckCircle2 size={14} /> Ready</span>
                      ) : doc.processing_status === 'failed' ? (
                        <span style={{ color: '#f87171', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}><AlertCircle size={14} /> Error</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Waiting...</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '3rem' }}>
              <button 
                className="btn btn-primary btn-lg" 
                disabled={counts.review === 0 || counts.processing > 0} 
                onClick={startBulkReview}
              >
                Review Results <ChevronRight size={20} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Review */}
        {currentStep === 'review' && validationData && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>Review & Approve</h2>
              <p style={{ color: 'var(--text-muted)' }}>The AI consolidated info from all your files. Please check and correct if necessary.</p>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', paddingRight: '1rem', marginBottom: '2rem' }}>
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
                  <label className="field-label">Skills</label>
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
                  <label className="field-label">Work Experience</label>
                  {(validationData.experiences || []).map((exp: any, i: number) => (
                    <div key={i} className="panel" style={{ background: 'rgba(255,255,255,0.02)', padding: '1.5rem', marginBottom: '1.5rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{exp.role}</div>
                          <div style={{ color: 'var(--primary-color)', fontWeight: 600 }}>{exp.company}</div>
                        </div>
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>{exp.period}</div>
                      </div>
                      <textarea 
                        value={exp.description} 
                        onChange={e => {
                          const next = [...validationData.experiences];
                          next[i].description = e.target.value;
                          setValidationData({...validationData, experiences: next});
                        }}
                        style={{ height: '120px', fontSize: '0.95rem', lineHeight: '1.6' }}
                      />
                    </div>
                  ))}
                </section>

                {/* STAR Cases */}
                <section>
                  <label className="field-label">Key Achievements (STAR Cases)</label>
                  {(validationData.star_cases || []).map((case_data: any, i: number) => (
                    <div key={i} className="panel" style={{ border: '1px solid rgba(59, 130, 246, 0.3)', padding: '1.5rem', marginBottom: '1.5rem' }}>
                      <input 
                        value={case_data.title} 
                        onChange={e => {
                          const next = [...validationData.star_cases];
                          next[i].title = e.target.value;
                          setValidationData({...validationData, star_cases: next});
                        }}
                        style={{ fontWeight: 800, fontSize: '1.1rem', background: 'transparent', border: 'none', width: '100%', marginBottom: '1rem', color: 'white' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '30px 1fr', gap: '10px' }}>
                          <span style={{ color: 'var(--primary-color)', fontWeight: 800 }}>S</span>
                          <textarea value={case_data.situation} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].situation = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '60px', fontSize: '0.9rem' }} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '30px 1fr', gap: '10px' }}>
                          <span style={{ color: 'var(--primary-color)', fontWeight: 800 }}>T</span>
                          <textarea value={case_data.task} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].task = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '60px', fontSize: '0.9rem' }} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '30px 1fr', gap: '10px' }}>
                          <span style={{ color: 'var(--primary-color)', fontWeight: 800 }}>A</span>
                          <textarea value={case_data.action} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].action = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '80px', fontSize: '0.9rem' }} />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '30px 1fr', gap: '10px' }}>
                          <span style={{ color: 'var(--primary-color)', fontWeight: 800 }}>R</span>
                          <textarea value={case_data.result} onChange={e => {
                            const next = [...validationData.star_cases]; next[i].result = e.target.value; setValidationData({...validationData, star_cases: next});
                          }} style={{ height: '60px', fontSize: '0.9rem' }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </section>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '2rem' }}>
              <button className="btn btn-secondary" onClick={() => setCurrentStep('analyze')}>Back</button>
              <button className="btn btn-primary btn-lg" onClick={handleValidate}>
                <CheckCircle2 size={20} /> Approve & Build Knowledge Base
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Finalize */}
        {currentStep === 'finalize' && (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <div style={{ backgroundColor: 'rgba(34, 197, 94, 0.1)', width: '100px', height: '100px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 2rem' }}>
              <CheckCircle2 size={60} color="#22c55e" />
            </div>
            <h2 style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>System Ready!</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '1.2rem', marginBottom: '3rem', maxWidth: '600px', margin: '0 auto 3rem' }}>
              Your professional knowledge base has been built. The AI now knows your story in detail and can help you optimize your resume and LinkedIn.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
              <div className="panel" style={{ padding: '2rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                <Sparkles size={32} color="var(--primary-color)" style={{ marginBottom: '1rem' }} />
                <h4 style={{ fontSize: '1.2rem', marginBottom: '0.8rem' }}>Update Base Resume</h4>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>Inject your new achievements and STAR cases into your master resume file.</p>
                <button className="btn btn-primary w-full" onClick={handleOptimizeResume}>Improve Resume Now</button>
              </div>
              <div className="panel" style={{ padding: '2rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                <ChevronRight size={32} color="var(--primary-color)" style={{ marginBottom: '1rem' }} />
                <h4 style={{ fontSize: '1.2rem', marginBottom: '0.8rem' }}>Go to Dashboard</h4>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>Start applying for jobs or optimize your LinkedIn profile with your new data.</p>
                <button className="btn btn-secondary w-full" onClick={() => window.location.href = '/'}>View Dashboard</button>
              </div>
            </div>

            <button 
              className="btn btn-text" 
              style={{ marginTop: '3rem', color: 'var(--text-muted)' }} 
              onClick={() => {
                setDocuments([]);
                setCurrentStep('upload');
              }}
            >
              Start over with new files
            </button>
          </div>
        )}

      </div>

      <style>{`
        .animate-fade-in { animation: fadeIn 0.5s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .btn-lg { padding: 1rem 2.5rem; font-size: 1.1rem; border-radius: 12px; }
        .field-label { font-weight: 700; color: #94a3b8; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 1px; margin-bottom: 0.8rem; display: block; }
        .w-full { width: 100%; }
        .btn-text:hover { text-decoration: underline; }
      `}</style>
    </div>
  );
};

export default DocumentRepository;
