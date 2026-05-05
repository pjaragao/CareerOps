import React, { useEffect, useState } from 'react';
import { profileService, Profile } from '../services/profileService';
import { 
  Save, 
  User, 
  Shield, 
  Briefcase, 
  FileText, 
  Wand2, 
  Plus, 
  Trash2, 
  GraduationCap, 
  Code,
  Zap,
  Globe
} from 'lucide-react';

const ProfilePage = () => {
  const [profile, setProfile] = useState<Profile>({
    languages: {
      pt: { experience: [], education: [], skills: [] }
    }
  });
  const [resume, setResume] = useState('');
  const [activeTab, setActiveTab] = useState('personal');
  const [activeLanguage, setActiveLanguage] = useState('pt');
  const [newLanguage, setNewLanguage] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const p = await profileService.getProfile().catch(() => ({} as Profile));
      const r = await profileService.getResume().catch(() => ({ content: '' }));
      
      setProfile({
        personal: p.personal || {},
        legal: p.legal || {},
        preferences: p.preferences || {},
        languages: p.languages || { pt: { experience: [], education: [], skills: [] } }
      });
      setResume(r.content || '');
    } catch (error) {
      console.error("Failed to load profile", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await profileService.saveProfile(profile);
      await profileService.saveResume(resume);
      alert("Profile saved successfully!");
    } catch (error) {
      alert("Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  const updateProfile = (section: 'personal' | 'legal' | 'preferences', field: string, value: any) => {
    setProfile(prev => ({
      ...prev,
      [section]: {
        ...(prev[section] || {}),
        [field]: value
      }
    }));
  };

  const updateLanguageData = (field: 'experience' | 'education' | 'skills' | 'about', value: any) => {
    setProfile(prev => ({
      ...prev,
      languages: {
        ...(prev.languages || {}),
        [activeLanguage]: {
          ...(prev.languages?.[activeLanguage] || {}),
          [field]: value
        }
      }
    }));
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      const extractedProfile = await profileService.uploadResume(file);
      setProfile(prev => ({
        ...prev,
        ...extractedProfile,
        languages: {
          ...(prev.languages || {}),
          [activeLanguage]: {
            ...(prev.languages?.[activeLanguage] || {}),
            experience: extractedProfile.languages?.[activeLanguage]?.experience || extractedProfile.experience || prev.languages?.[activeLanguage]?.experience,
            education: extractedProfile.languages?.[activeLanguage]?.education || extractedProfile.education || prev.languages?.[activeLanguage]?.education,
            skills: extractedProfile.languages?.[activeLanguage]?.skills || extractedProfile.skills || prev.languages?.[activeLanguage]?.skills
          }
        }
      }));
      alert("AI extracted your info successfully! Please review the tabs.");
    } catch (error) {
      alert("Failed to parse resume with AI");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem' }}>Loading profile...</div>;

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>Profile & Onboarding</h1>
          <p style={{ color: 'var(--text-muted)' }}>Set up your professional data for AI-powered job matching.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-secondary" onClick={async () => {
            setLoading(true);
            try {
              await profileService.importFromLinkedin();
              await loadData();
              alert("Successfully imported from LinkedIn!");
            } catch (e) {
              alert("Failed to import from LinkedIn. Check your session.");
            } finally {
              setLoading(false);
            }
          }} disabled={loading}>
            <Globe size={18} /> Import from LinkedIn
          </button>
          <label className="btn btn-secondary" style={{ cursor: 'pointer' }}>
            <Wand2 size={18} /> AI Onboarding
            <input type="file" hidden onChange={handleFileUpload} accept=".pdf,.doc,.docx" />
          </label>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            <Save size={18} /> {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: '2rem' }}>
        <div className="panel" style={{ height: 'max-content', padding: '0.5rem' }}>
          {[
            { id: 'personal', icon: <User size={18} />, label: 'Personal Info' },
            { id: 'about', icon: <Code size={18} />, label: 'About / Summary' },
            { id: 'experience', icon: <Briefcase size={18} />, label: 'Work Experience' },
            { id: 'education', icon: <GraduationCap size={18} />, label: 'Education' },
            { id: 'skills', icon: <Code size={18} />, label: 'Skills & Stack' },
            { id: 'legal', icon: <Shield size={18} />, label: 'Legal & Diversity' },
            { id: 'preferences', icon: <Zap size={18} />, label: 'Preferences' },
            { id: 'resume', icon: <FileText size={18} />, label: 'Base Resume' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`nav-link ${activeTab === tab.id ? 'active' : ''}`}
              style={{ width: '100%', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: '12px', padding: '0.8rem 1rem', borderRadius: '10px' }}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {['experience', 'education', 'skills', 'about'].includes(activeTab) && (
            <div className="panel" style={{ padding: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <span style={{ fontWeight: 'bold' }}>Language:</span>
              {Object.keys(profile.languages || { pt: {} }).map(lang => (
                <button 
                  key={lang}
                  className={`btn ${activeLanguage === lang ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveLanguage(lang)}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
              <div style={{ display: 'flex', gap: '0.5rem', marginLeft: 'auto' }}>
                <input 
                  type="text" 
                  placeholder="New (e.g. es)" 
                  value={newLanguage} 
                  onChange={e => setNewLanguage(e.target.value)}
                  style={{ width: '100px', padding: '0.4rem', background: 'rgba(255,255,255,0.05)', color: 'white', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px' }}
                />
                <button className="btn btn-secondary" onClick={() => {
                  if (newLanguage && !profile.languages?.[newLanguage]) {
                    setProfile({ ...profile, languages: { ...(profile.languages || {}), [newLanguage]: { experience: [], education: [], skills: [], about: '' } } });
                    setActiveLanguage(newLanguage);
                    setNewLanguage('');
                  }
                }}><Plus size={16} /> Add</button>
              </div>
            </div>
          )}
          
          <div className="panel" style={{ padding: '2rem' }}>
          {activeTab === 'personal' && (
            <div className="animate-fade-in">
              <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <User /> Personal Information
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <label className="field-label">Full Name</label>
                  <input type="text" value={profile.personal?.name || ''} onChange={e => updateProfile('personal', 'name', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Email</label>
                  <input type="email" value={profile.personal?.email || ''} onChange={e => updateProfile('personal', 'email', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Phone Number</label>
                  <input type="text" value={profile.personal?.phone || ''} onChange={e => updateProfile('personal', 'phone', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Location</label>
                  <input type="text" value={profile.personal?.location || ''} onChange={e => updateProfile('personal', 'location', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">LinkedIn URL</label>
                  <input type="text" value={profile.personal?.linkedin || ''} onChange={e => updateProfile('personal', 'linkedin', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">GitHub/Portfolio</label>
                  <input type="text" value={profile.personal?.github || ''} onChange={e => updateProfile('personal', 'github', e.target.value)} />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="animate-fade-in">
              <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}><User /> About / Summary</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <textarea 
                  value={profile.languages?.[activeLanguage]?.about || ''} 
                  onChange={e => updateLanguageData('about', e.target.value)}
                  placeholder="Professional summary..."
                  style={{ height: '200px' }}
                />
              </div>
            </div>
          )}

          {activeTab === 'experience' && (
            <div className="animate-fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><Briefcase /> Work Experience</h2>
                <button className="btn btn-secondary" onClick={() => updateLanguageData('experience', [...(profile.languages?.[activeLanguage]?.experience || []), { company: '', role: '', period: '', description: '' }])}>
                  <Plus size={16} /> Add Role
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {(profile.languages?.[activeLanguage]?.experience || []).map((exp, i) => (
                  <div key={i} className="panel" style={{ background: 'rgba(255,255,255,0.02)', padding: '1.5rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '1rem', marginBottom: '1rem' }}>
                      <input placeholder="Company" value={exp.company} onChange={e => {
                        const next = [...(profile.languages?.[activeLanguage]?.experience || [])];
                        next[i].company = e.target.value;
                        updateLanguageData('experience', next);
                      }} />
                      <input placeholder="Role" value={exp.role} onChange={e => {
                        const next = [...(profile.languages?.[activeLanguage]?.experience || [])];
                        next[i].role = e.target.value;
                        updateLanguageData('experience', next);
                      }} />
                      <input placeholder="Period (e.g. 2020 - Present)" value={exp.period} onChange={e => {
                        const next = [...(profile.languages?.[activeLanguage]?.experience || [])];
                        next[i].period = e.target.value;
                        updateLanguageData('experience', next);
                      }} />
                      <button className="btn btn-secondary" style={{ color: '#ff4d4d' }} onClick={() => {
                        const next = profile.languages?.[activeLanguage]?.experience?.filter((_, idx) => idx !== i);
                        updateLanguageData('experience', next);
                      }}><Trash2 size={16} /></button>
                    </div>
                    <textarea placeholder="Key Achievements / Description" value={exp.description} onChange={e => {
                      const next = [...(profile.languages?.[activeLanguage]?.experience || [])];
                      next[i].description = e.target.value;
                      updateLanguageData('experience', next);
                    }} style={{ height: '100px' }} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'education' && (
            <div className="animate-fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><GraduationCap /> Education</h2>
                <button className="btn btn-secondary" onClick={() => updateLanguageData('education', [...(profile.languages?.[activeLanguage]?.education || []), { institution: '', degree: '', year: '' }])}>
                  <Plus size={16} /> Add Education
                </button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {(profile.languages?.[activeLanguage]?.education || []).map((edu, i) => (
                  <div key={i} className="panel" style={{ background: 'rgba(255,255,255,0.02)', padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '1rem' }}>
                    <input placeholder="Institution" value={edu.institution} onChange={e => {
                      const next = [...(profile.languages?.[activeLanguage]?.education || [])];
                      next[i].institution = e.target.value;
                      updateLanguageData('education', next);
                    }} />
                    <input placeholder="Degree" value={edu.degree} onChange={e => {
                      const next = [...(profile.languages?.[activeLanguage]?.education || [])];
                      next[i].degree = e.target.value;
                      updateLanguageData('education', next);
                    }} />
                    <input placeholder="Year" value={edu.year} onChange={e => {
                      const next = [...(profile.languages?.[activeLanguage]?.education || [])];
                      next[i].year = e.target.value;
                      updateLanguageData('education', next);
                    }} />
                    <button className="btn btn-secondary" style={{ color: '#ff4d4d' }} onClick={() => {
                      const next = profile.languages?.[activeLanguage]?.education?.filter((_, idx) => idx !== i);
                      updateLanguageData('education', next);
                    }}><Trash2 size={16} /></button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'skills' && (
            <div className="animate-fade-in">
              <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}><Code /> Skills & Stack</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div>
                  <label className="field-label">Tech Stack (one per line or comma separated)</label>
                  <textarea 
                    value={profile.languages?.[activeLanguage]?.skills?.join(', ') || ''} 
                    onChange={e => updateLanguageData('skills', e.target.value.split(/[,|\n]/).map(s => s.trim()).filter(s => s))}
                    placeholder="Python, React, AWS, Docker, AI, LLMs..."
                    style={{ height: '200px' }}
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'legal' && (
            <div className="animate-fade-in">
              <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Shield /> Legal & Diversity
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <label className="field-label">Visa Status</label>
                  <select value={profile.legal?.visa_status || ''} onChange={e => updateProfile('legal', 'visa_status', e.target.value)}>
                    <option value="">Select...</option>
                    <option value="citizen">Citizen</option>
                    <option value="resident">Permanent Resident</option>
                    <option value="h1b">H1-B</option>
                    <option value="sponsorship_required">Sponsorship Required</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">Work Authorization</label>
                  <input type="text" placeholder="e.g. Authorized to work in EU" value={profile.legal?.work_auth || ''} onChange={e => updateProfile('legal', 'work_auth', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Gender</label>
                  <select value={profile.legal?.gender || ''} onChange={e => updateProfile('legal', 'gender', e.target.value)}>
                    <option value="">Select...</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="non-binary">Non-binary</option>
                    <option value="decline">Decline</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">Ethnicity</label>
                  <select value={profile.legal?.ethnicity || ''} onChange={e => updateProfile('legal', 'ethnicity', e.target.value)}>
                    <option value="">Select...</option>
                    <option value="white">White</option>
                    <option value="hispanic">Hispanic</option>
                    <option value="black">Black</option>
                    <option value="asian">Asian</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'preferences' && (
            <div className="animate-fade-in">
              <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Zap /> Career Preferences
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <label className="field-label">Target Role</label>
                  <input type="text" value={profile.preferences?.target_role || ''} onChange={e => updateProfile('preferences', 'target_role', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Work Mode</label>
                  <select value={profile.preferences?.work_mode || ''} onChange={e => updateProfile('preferences', 'work_mode', e.target.value)}>
                    <option value="remote">Remote Only</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">On-site</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">Min Salary (Annual)</label>
                  <input type="text" placeholder="e.g. 100k USD" value={profile.preferences?.min_salary || ''} onChange={e => updateProfile('preferences', 'min_salary', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Experience Level</label>
                  <select value={profile.preferences?.experience_level || ''} onChange={e => updateProfile('preferences', 'experience_level', e.target.value)}>
                    <option value="entry">Entry</option>
                    <option value="mid">Mid</option>
                    <option value="senior">Senior</option>
                    <option value="lead">Lead / Principal</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'resume' && (
            <div className="animate-fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><FileText /> Base Resume (Markdown)</h2>
              </div>
              <textarea 
                value={resume}
                onChange={e => setResume(e.target.value)}
                style={{ width: '100%', height: '500px', fontFamily: 'monospace' }}
              />
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
