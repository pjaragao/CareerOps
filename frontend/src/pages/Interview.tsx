import React, { useEffect, useState } from 'react';
import { interviewService, STARStory } from '../services/interviewService';
import { MessageSquare, Plus, Wand2, Trash2, CheckCircle, X } from 'lucide-react';

const InterviewPage = () => {
  const [stories, setStories] = useState<STARStory[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [rawExperience, setRawExperience] = useState('');
  const [showGenerator, setShowGenerator] = useState(false);
  const [generatedStory, setGeneratedStory] = useState<Omit<STARStory, 'id' | 'tags'> | null>(null);

  useEffect(() => {
    loadStories();
  }, []);

  const loadStories = async () => {
    const data = await interviewService.getStories();
    setStories(data);
  };

  const handleGenerate = async () => {
    if (!rawExperience.trim()) return;
    setIsGenerating(true);
    try {
      const result = await interviewService.generateSTAR(rawExperience);
      setGeneratedStory(result);
    } catch (error) {
      alert("Failed to generate STAR case");
    } finally {
      setIsGenerating(false);
    }
  };

  const [showManual, setShowManual] = useState(false);
  const [manualStory, setManualStory] = useState<Omit<STARStory, 'id' | 'tags'>>({
    title: '',
    situation: '',
    task: '',
    action: '',
    result: ''
  });

  const [selectedStory, setSelectedStory] = useState<STARStory | null>(null);

  const handleSaveStory = async (storyData: Omit<STARStory, 'id' | 'tags'>, isAi: boolean) => {
    try {
      await interviewService.saveStory({ ...storyData, tags: [isAi ? 'AI Generated' : 'Manual'] });
      setGeneratedStory(null);
      setRawExperience('');
      setShowGenerator(false);
      setShowManual(false);
      setManualStory({ title: '', situation: '', task: '', action: '', result: '' });
      await loadStories();
    } catch (error) {
      alert("Failed to save STAR case");
    }
  };

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Interview Prep</h1>
          <p style={{ color: 'var(--text-muted)' }}>Train with CBIS and STAR methodology assisted by AI.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowManual(true)}>
            <Plus size={18} /> Add Manual Case
          </button>
          <button className="btn btn-primary" onClick={() => setShowGenerator(true)}>
            <Wand2 size={18} /> New AI STAR Case
          </button>
        </div>
      </div>

      {showManual && (
        <div className="panel" style={{ border: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '1.5rem' }}>Create Manual STAR Case</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <input 
              placeholder="Case Title" 
              value={manualStory.title}
              onChange={e => setManualStory({...manualStory, title: e.target.value})}
            />
            {['situation', 'task', 'action', 'result'].map(part => (
              <textarea 
                key={part}
                placeholder={part.charAt(0).toUpperCase() + part.slice(1)}
                value={(manualStory as any)[part]}
                onChange={e => setManualStory({...manualStory, [part]: e.target.value})}
                style={{ height: '80px' }}
              />
            ))}
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowManual(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => handleSaveStory(manualStory, false)}>Save Case</button>
            </div>
          </div>
        </div>
      )}

      {showGenerator && (
        <div className="panel" style={{ border: '1px solid var(--accent)', background: 'rgba(108, 99, 255, 0.05)' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Wand2 size={20} color="var(--accent)" /> AI STAR Case Generator
          </h3>
          {!generatedStory ? (
            <>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                Paste a raw description of a professional experience or achievement, and the AI will structure it into a STAR story for you.
              </p>
              <textarea 
                value={rawExperience}
                onChange={e => setRawExperience(e.target.value)}
                placeholder="Ex: I managed a team of 5 to migrate our legacy database to Supabase, reducing latency by 40%..."
                style={{ width: '100%', height: '120px', padding: '1rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '12px', color: '#fff', marginBottom: '1rem' }}
              />
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button className="btn btn-secondary" onClick={() => setShowGenerator(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleGenerate} disabled={isGenerating}>
                  {isGenerating ? 'Generating...' : 'Generate STAR Case'}
                </button>
              </div>
            </>
          ) : (
            <div className="animate-fade-in">
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ color: 'var(--accent)', marginBottom: '0.5rem' }}>{generatedStory.title}</h4>
                <div style={{ display: 'grid', gap: '1rem' }}>
                  {['situation', 'task', 'action', 'result'].map(part => (
                    <div key={part}>
                      <strong style={{ textTransform: 'capitalize', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{part}</strong>
                      <p style={{ fontSize: '0.95rem', marginTop: '4px' }}>{(generatedStory as any)[part]}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button className="btn btn-secondary" onClick={() => setGeneratedStory(null)}>Retry</button>
                <button className="btn btn-primary" onClick={() => handleSaveStory(generatedStory, true)}>
                  <CheckCircle size={18} /> Save to Repository
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.5rem', marginTop: '2rem' }}>
        {stories.map(story => (
          <div key={story.id} className="panel" style={{ marginBottom: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>{story.title}</h3>
              <button onClick={async () => {
                if(confirm("Delete this case?")) {
                  await interviewService.deleteStory(story.id);
                  loadStories();
                }
              }} className="btn btn-secondary" style={{ padding: '6px', color: 'var(--error)' }}>
                <Trash2 size={16} />
              </button>
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {story.situation}
            </p>
            <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '4px' }}>
                {(story.tags || []).map(tag => (
                  <span key={tag} style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px' }}>{tag}</span>
                ))}
              </div>
              <button className="btn btn-secondary" style={{ fontSize: '0.8rem' }} onClick={() => setSelectedStory(story)}>View Full Case</button>
            </div>
          </div>
        ))}
      </div>

      {selectedStory && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '2rem' }} onClick={() => setSelectedStory(null)}>
          <div className="panel animate-scale-in" style={{ width: '100%', maxWidth: '800px', maxHeight: '90vh', overflowY: 'auto', border: '1px solid var(--border)', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
              <div>
                <h2 style={{ color: 'var(--accent)', marginBottom: '0.5rem' }}>{selectedStory.title}</h2>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {(selectedStory.tags || []).map(tag => (
                    <span key={tag} style={{ fontSize: '0.75rem', padding: '4px 10px', background: 'rgba(108, 99, 255, 0.1)', color: 'var(--accent)', borderRadius: '6px', border: '1px solid rgba(108, 99, 255, 0.2)' }}>{tag}</span>
                  ))}
                </div>
              </div>
              <button className="btn btn-secondary" onClick={() => setSelectedStory(null)} style={{ padding: '8px' }}><X size={24} /></button>
            </div>

            <div style={{ display: 'grid', gap: '2rem' }}>
              {[
                { key: 'situation', label: 'Situation', color: '#3b82f6' },
                { key: 'task', label: 'Task', color: '#8b5cf6' },
                { key: 'action', label: 'Action', color: '#d946ef' },
                { key: 'result', label: 'Result', color: '#22c55e' }
              ].map(part => (
                <div key={part.key} style={{ borderLeft: `4px solid ${part.color}`, paddingLeft: '1.5rem' }}>
                  <h4 style={{ color: part.color, textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '1px', marginBottom: '0.5rem', fontWeight: 800 }}>{part.label}</h4>
                  <p style={{ fontSize: '1.05rem', lineHeight: 1.7, color: 'rgba(255,255,255,0.9)' }}>{(selectedStory as any)[part.key]}</p>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '3rem', textAlign: 'right' }}>
              <button className="btn btn-primary" onClick={() => setSelectedStory(null)}>Close Case</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InterviewPage;
