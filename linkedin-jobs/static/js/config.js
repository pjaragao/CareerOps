let currentProvider = 'gemini';

async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
}

function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

async function loadAIProviders() {
    const container = document.getElementById('ai-providers-container');
    const data = await fetchJSON('/api/ai/providers');
    
    if (!data) {
        container.innerHTML = '<div class="empty-state">Failed to load AI providers</div>';
        return;
    }

    const providers = ['gemini', 'nvidia', 'alibaba', 'ollama', 'openai', 'custom'];
    const currentProvider = data.provider || 'gemini';
    const currentModel = data.model || '';
    const currentBaseUrl = data.base_url || '';
    const providerIcons = {
        'gemini': '🧠',
        'nvidia': '🎮',
        'alibaba': '🇨🇳',
        'ollama': '🦙',
        'openai': '🤖',
        'custom': '⚙️'
    };
    
    container.innerHTML = providers.map(provider => {
        const isCurrent = provider === currentProvider;
        const defaultModel = data.default_models && data.default_models[provider] || '';
        const providerModels = data.provider_models && data.provider_models[provider] || [];
        
        return `
            <div class="provider-card ${isCurrent ? 'active' : ''}" id="provider-card-${provider}">
                <div class="provider-header">
                    <div class="provider-name">
                        <span class="provider-icon">${providerIcons[provider] || '🤖'}</span>
                        ${provider.charAt(0).toUpperCase() + provider.slice(1)}
                    </div>
                    <div class="provider-status-badge ${isCurrent ? 'connected' : 'disconnected'}">
                        ${isCurrent ? '● Active' : '○ Inactive'}
                    </div>
                </div>
                <div class="compact-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>API Key</label>
                            <input type="password" id="key-${provider}" value="${isCurrent ? '••••••••' : ''}" placeholder="Enter API key">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Model</label>
                        <input type="text" id="model-${provider}" value="${isCurrent ? esc(currentModel) : esc(defaultModel)}" placeholder="e.g., ${esc(defaultModel)}">
                        ${providerModels.length > 0 ? `<small style="color: var(--text-secondary); font-size: 11px;">Available: ${providerModels.slice(0, 3).join(', ')}...</small>` : ''}
                    </div>
                    <div class="form-group">
                        <label>Base URL (optional)</label>
                        <input type="text" id="base-url-${provider}" value="${isCurrent ? esc(currentBaseUrl) : ''}" placeholder="https://api.example.com/v1">
                    </div>
                </div>
                <div style="display:flex; gap:8px; margin-top:16px;">
                    <button class="btn success" onclick="testProvider('${provider}')" id="test-${provider}" style="flex:1; font-size:12px; padding:6px;">
                        🧪 Test
                    </button>
                    <button class="btn primary" onclick="saveProvider('${provider}')" style="flex:1; font-size:12px; padding:6px;">
                        💾 Save
                    </button>
                    ${!isCurrent ? `
                        <button class="btn" onclick="setActiveProvider('${provider}')" style="flex:1; font-size:12px; padding:6px;">
                            ▶ Activate
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function testProvider(provider) {
    const btn = document.getElementById(`test-${provider}`);
    const status = document.getElementById(`status-${provider}`);
    
    btn.disabled = true;
    btn.textContent = 'Testing...';
    status.className = 'provider-status testing';
    status.textContent = '⏳ Testing...';
    
    try {
        const res = await fetchJSON('/api/ai/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider })
        });
        
        if (res.ok) {
            status.className = 'provider-status connected';
            status.textContent = '✓ Connected';
            alert('Connection successful!');
        } else {
            status.className = 'provider-status disconnected';
            status.textContent = '✗ Failed: ' + (res.error || 'Unknown error');
            alert('Connection failed: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        status.className = 'provider-status disconnected';
        status.textContent = '✗ Error: ' + e.message;
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test Connection';
    }
}

async function saveProvider(provider) {
    const config = {
        provider,
        api_key: document.getElementById(`key-${provider}`).value.trim(),
        model: document.getElementById(`model-${provider}`).value.trim(),
        base_url: document.getElementById(`base-url-${provider}`).value.trim()
    };
    
    try {
        const res = await fetchJSON('/api/ai/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (res.ok) {
            alert('Configuration saved successfully!');
            loadAIProviders();
        } else {
            alert('Failed to save: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function setActiveProvider(provider) {
    try {
        const res = await fetchJSON('/api/ai/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, set_active: true })
        });
        
        if (res.ok) {
            alert(`${provider.charAt(0).toUpperCase() + provider.slice(1)} is now the active provider!`);
            loadAIProviders();
        } else {
            alert('Failed to set active: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadProfileSettings() {
    const container = document.getElementById('profile-settings-container');
    const data = await fetchJSON('/api/profile/settings');
    
    if (!data.ok || !data.profile) {
        container.innerHTML = '<div class="empty-state">Failed to load profile settings</div>';
        return;
    }
    
    const p = data.profile;
    const targetRoles = p.target_roles || [];
    const skills = p.skills || {};
    const technicalSkills = skills.technical || [];
    const softSkills = skills.soft || [];
    const salary = p.salary || {};
    const dealBreakers = p.deal_breakers || [];
    const proofPoints = p.proof_points || [];
    const workPrefs = p.work_preferences || {};
    const personal = p.personal || {};
    
    container.innerHTML = `
        <!-- Personal Info Tab -->
        <div id="profile-tab-personal" class="profile-tab-content active">
            <div class="section-card">
                <div class="section-card-title"><span>👤</span> Personal Information</div>
                <div class="compact-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Full Name</label>
                            <input type="text" id="profile-full-name" value="${esc(personal.full_name || '')}" placeholder="Your full name">
                        </div>
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" id="profile-email" value="${esc(personal.email || '')}" placeholder="your@email.com">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Location</label>
                            <input type="text" id="profile-location" value="${esc(personal.location || '')}" placeholder="City, Country">
                        </div>
                        <div class="form-group">
                            <label>Timezone</label>
                            <input type="text" id="profile-timezone" value="${esc(personal.timezone || '')}" placeholder="e.g., America/Sao_Paulo">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>LinkedIn URL</label>
                            <input type="text" id="profile-linkedin" value="${esc(personal.linkedin_url || '')}" placeholder="https://linkedin.com/in/...">
                        </div>
                        <div class="form-group">
                            <label>GitHub URL</label>
                            <input type="text" id="profile-github" value="${esc(personal.github_url || '')}" placeholder="https://github.com/...">
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>🎯</span> Superpower</div>
                <div class="compact-form">
                    <div class="form-group">
                        <textarea id="profile-superpower" style="min-height:80px;" placeholder="What makes you unique?">${esc(p.superpower || '')}</textarea>
                    </div>
                </div>
            </div>
        </div>

        <!-- Professional Tab -->
        <div id="profile-tab-professional" class="profile-tab-content">
            <div class="section-card">
                <div class="section-card-title"><span>💼</span> Target Roles</div>
                <div class="compact-form">
                    <div class="form-group">
                        <label>Desired Positions (comma-separated)</label>
                        <textarea id="profile-roles" style="min-height:60px;" placeholder="e.g., Senior Backend Engineer, Full Stack Developer">${esc(targetRoles.join(', '))}</textarea>
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>🛠️</span> Skills</div>
                <div class="compact-form">
                    <div class="form-group">
                        <label>Technical Skills (comma-separated)</label>
                        <textarea id="profile-skills" style="min-height:60px;" placeholder="e.g., Python, Flask, PostgreSQL">${esc(technicalSkills.join(', '))}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Soft Skills (comma-separated)</label>
                        <textarea id="profile-soft-skills" style="min-height:60px;" placeholder="e.g., Problem Solving, Communication">${esc(softSkills.join(', '))}</textarea>
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>💰</span> Salary Expectations</div>
                <div class="compact-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Min Annual (USD)</label>
                            <input type="text" id="profile-min-salary" value="${esc(salary.min_annual || '')}" placeholder="e.g., 80000">
                        </div>
                        <div class="form-group">
                            <label>Target Annual (USD)</label>
                            <input type="text" id="profile-target-salary" value="${esc(salary.target_annual || '')}" placeholder="e.g., 120000">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Preferred Contract Rate (USD/hr)</label>
                        <input type="text" id="profile-contract-rate" value="${esc(salary.preferred_contract_rate || '')}" placeholder="e.g., 50">
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>📝</span> Professional Summary</div>
                <div class="compact-form">
                    <div class="form-group">
                        <textarea id="profile-summary" style="min-height:100px;" placeholder="Brief professional summary">${esc(p.professional_summary || '')}</textarea>
                    </div>
                </div>
            </div>
        </div>

        <!-- Preferences Tab -->
        <div id="profile-tab-preferences" class="profile-tab-content">
            <div class="section-card">
                <div class="section-card-title"><span>⚡</span> Work Preferences</div>
                <div class="compact-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Preferred Contract Type</label>
                            <select id="profile-contract-type">
                                <option value="full-time" ${workPrefs.preferred_contract_type === 'full-time' ? 'selected' : ''}>Full-time</option>
                                <option value="contract" ${workPrefs.preferred_contract_type === 'contract' ? 'selected' : ''}>Contract</option>
                                <option value="both" ${workPrefs.preferred_contract_type === 'both' ? 'selected' : ''}>Both</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Remote Only</label>
                            <select id="profile-remote-only">
                                <option value="true" ${workPrefs.remote_only ? 'selected' : ''}>Yes</option>
                                <option value="false" ${!workPrefs.remote_only ? 'selected' : ''}>No</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Willing to Relocate</label>
                            <select id="profile-relocate">
                                <option value="true" ${workPrefs.willing_to_relocate ? 'selected' : ''}>Yes</option>
                                <option value="false" ${!workPrefs.willing_to_relocate ? 'selected' : ''}>No</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Min Company Size</label>
                            <input type="text" id="profile-min-company" value="${esc(workPrefs.min_company_size || '')}" placeholder="e.g., 20">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Languages (comma-separated)</label>
                        <input type="text" id="profile-languages" value="${esc((workPrefs.languages || []).join(', '))}" placeholder="e.g., en, pt">
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>🚫</span> Deal Breakers</div>
                <div class="compact-form">
                    <div class="form-group">
                        <textarea id="profile-deal-breakers" style="min-height:80px;" placeholder="One per line">${esc(dealBreakers.join('\n'))}</textarea>
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-card-title"><span>🏆</span> Proof Points</div>
                <div class="compact-form">
                    <div class="form-group">
                        <label>Achievements (format: Title: Description)</label>
                        <textarea id="profile-proof-points" style="min-height:100px;" placeholder="Title: Description of achievement">${esc(proofPoints.map(pp => pp.title + ': ' + pp.description).join('\n'))}</textarea>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="sticky-actions">
            <button class="btn primary" onclick="saveProfileSettings()" style="width:100%;">
                💾 Save Profile Settings
            </button>
        </div>
    `;
    
    // Initialize first tab as active
    const firstTab = container.querySelector('.profile-tab-content');
    if (firstTab) {
        firstTab.classList.add('active');
    }
}

async function saveProfileSettings() {
    const fullName = document.getElementById('profile-full-name')?.value.trim() || '';
    const email = document.getElementById('profile-email')?.value.trim() || '';
    const location = document.getElementById('profile-location')?.value.trim() || '';
    const timezone = document.getElementById('profile-timezone')?.value.trim() || '';
    const linkedinUrl = document.getElementById('profile-linkedin')?.value.trim() || '';
    const githubUrl = document.getElementById('profile-github')?.value.trim() || '';
    
    const targetRoles = document.getElementById('profile-roles')?.value.trim() || '';
    const technicalSkills = document.getElementById('profile-skills')?.value.trim() || '';
    const softSkills = document.getElementById('profile-soft-skills')?.value.trim() || '';
    const minSalary = document.getElementById('profile-min-salary')?.value.trim() || '';
    const targetSalary = document.getElementById('profile-target-salary')?.value.trim() || '';
    const contractRate = document.getElementById('profile-contract-rate')?.value.trim() || '';
    const professionalSummary = document.getElementById('profile-summary')?.value.trim() || '';
    const superpower = document.getElementById('profile-superpower')?.value.trim() || '';
    
    const contractType = document.getElementById('profile-contract-type')?.value || 'full-time';
    const remoteOnly = document.getElementById('profile-remote-only')?.value === 'true';
    const willingToRelocate = document.getElementById('profile-relocate')?.value === 'true';
    const minCompanySize = document.getElementById('profile-min-company')?.value.trim() || '';
    const languages = document.getElementById('profile-languages')?.value.trim() || '';
    
    const dealBreakers = document.getElementById('profile-deal-breakers')?.value.trim() || '';
    const proofPoints = document.getElementById('profile-proof-points')?.value.trim() || '';
    
    // Parse proof points
    const parsedProofPoints = [];
    proofPoints.split('\n').forEach(line => {
        const colonIndex = line.indexOf(':');
        if (colonIndex > 0) {
            parsedProofPoints.push({
                title: line.substring(0, colonIndex).trim(),
                description: line.substring(colonIndex + 1).trim(),
                metrics: ''
            });
        }
    });
    
    const settings = {
        personal: {
            full_name: fullName,
            email: email,
            location: location,
            timezone: timezone,
            linkedin_url: linkedinUrl,
            github_url: githubUrl,
            portfolio_url: '',
        },
        target_roles: targetRoles.split(',').map(r => r.trim()).filter(r => r),
        skills: {
            technical: technicalSkills.split(',').map(s => s.trim()).filter(s => s),
            soft: softSkills.split(',').map(s => s.trim()).filter(s => s)
        },
        salary: {
            min_annual: minSalary ? parseInt(minSalary) : null,
            target_annual: targetSalary ? parseInt(targetSalary) : null,
            preferred_contract_rate: contractRate ? parseInt(contractRate) : null,
            currency: 'USD'
        },
        professional_summary: professionalSummary,
        superpower: superpower,
        work_preferences: {
            preferred_contract_type: contractType,
            remote_only: remoteOnly,
            willing_to_relocate: willingToRelocate,
            min_company_size: minCompanySize ? parseInt(minCompanySize) : null,
            max_company_size: null,
            languages: languages.split(',').map(l => l.trim()).filter(l => l)
        },
        deal_breakers: dealBreakers.split('\n').map(d => d.trim()).filter(d => d),
        proof_points: parsedProofPoints,
        interview_stories: [],
        notes: ''
    };
    
    try {
        const res = await fetchJSON('/api/profile/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (res.ok) {
            alert('Profile settings saved successfully!');
        } else {
            alert('Failed to save: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function loadStories() {
    const container = document.getElementById('stories-container');
    const data = await fetchJSON('/api/stories');
    
    if (!data.stories || data.stories.length === 0) {
        container.innerHTML = `
            <div class="add-story-card" onclick="openStoryModal()">
                <div style="font-size: 48px; margin-bottom: 12px;">➕</div>
                <h3 style="margin: 0 0 8px 0; font-size: 16px;">Add Your First Story</h3>
                <p style="margin: 0; color: var(--text-secondary); font-size: 13px;">
                    Create STAR+R stories for interview preparation
                </p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="add-story-card" onclick="openStoryModal()" style="min-height: auto; padding: 16px;">
            <div style="font-size: 24px; margin-bottom: 8px;">➕</div>
            <span style="font-size: 13px; font-weight: 500;">Add New Story</span>
        </div>
        ${data.stories.map(s => `
            <div class="story-card" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 10px; padding: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div>
                        <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">${esc(s.title || 'Untitled')}</div>
                        <div style="font-size: 12px; color: var(--accent);">${esc(s.tags?.join(', ') || s.competency || 'General')}</div>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn" onclick="editStory(${s.id})" style="font-size: 11px; padding: 4px 10px; min-height: auto;">✏️ Edit</button>
                        <button class="btn danger" onclick="deleteStory(${s.id})" style="font-size: 11px; padding: 4px 10px; min-height: auto;">🗑️</button>
                    </div>
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 12px;">
                    <strong>S:</strong> ${esc(s.situation || '').substring(0, 100)}${(s.situation || '').length > 100 ? '...' : ''}
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    ${(s.archetypes || []).map(a => `<span class="archetype-badge">${esc(a)}</span>`).join('')}
                </div>
            </div>
        `).join('')}
    `;
}

function openStoryModal(storyId = null) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    
    const isEdit = storyId !== null;
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h2>${isEdit ? '✏️ Edit Story' : '➕ Add Story'}</h2>
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            </div>
            <input type="hidden" id="story-id" value="${storyId || ''}">
            <div class="form-group">
                <label>Title *</label>
                <input type="text" id="story-title" placeholder="e.g., Led team migration to microservices">
            </div>
            <div class="form-group">
                <label>Competency *</label>
                <input type="text" id="story-competency" placeholder="e.g., Leadership, Problem Solving">
            </div>
            <div class="form-group">
                <label>Situation (S) *</label>
                <textarea id="story-situation" style="min-height:60px;" placeholder="What was the context?"></textarea>
            </div>
            <div class="form-group">
                <label>Task (T) *</label>
                <textarea id="story-task" style="min-height:60px;" placeholder="What was your responsibility?"></textarea>
            </div>
            <div class="form-group">
                <label>Action (A) *</label>
                <textarea id="story-action" style="min-height:80px;" placeholder="What steps did you take?"></textarea>
            </div>
            <div class="form-group">
                <label>Result (R) *</label>
                <textarea id="story-result" style="min-height:60px;" placeholder="What was the outcome?"></textarea>
            </div>
            <div class="form-group">
                <label>Reflection (R) *</label>
                <textarea id="story-reflection" style="min-height:60px;" placeholder="What did you learn?"></textarea>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px;">
                <button class="btn" onclick="this.closest('.modal').remove()">Cancel</button>
                <button class="btn success" onclick="saveStory(this)">Save Story</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    if (isEdit) {
        loadStoryData(storyId);
    }
}

async function loadStoryData(storyId) {
    const data = await fetchJSON('/api/stories/' + storyId);
    if (data.story) {
        const s = data.story;
        document.getElementById('story-title').value = s.title || '';
        document.getElementById('story-competency').value = s.competency || '';
        document.getElementById('story-situation').value = s.situation || '';
        document.getElementById('story-task').value = s.task || '';
        document.getElementById('story-action').value = s.action || '';
        document.getElementById('story-result').value = s.result || '';
        document.getElementById('story-reflection').value = s.reflection || '';
    }
}

async function saveStory(btn) {
    const storyId = document.getElementById('story-id').value;
    const story = {
        title: document.getElementById('story-title').value.trim(),
        competency: document.getElementById('story-competency').value.trim(),
        situation: document.getElementById('story-situation').value.trim(),
        task: document.getElementById('story-task').value.trim(),
        action: document.getElementById('story-action').value.trim(),
        result: document.getElementById('story-result').value.trim(),
        reflection: document.getElementById('story-reflection').value.trim()
    };
    
    if (!story.title || !story.competency || !story.situation || !story.task || !story.action || !story.result || !story.reflection) {
        alert('Please fill in all fields');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = 'Saving...';
    
    try {
        let endpoint = '/api/stories';
        if (storyId) {
            endpoint = '/api/stories/' + storyId;
        }
        
        const res = await fetchJSON(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(story)
        });
        
        if (res.ok) {
            btn.closest('.modal').remove();
            loadStories();
        } else {
            alert('Failed to save: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Save Story';
    }
}

async function editStory(storyId) {
    openStoryModal(storyId);
}

async function deleteStory(storyId) {
    if (!confirm('Delete this story?')) return;
    
    const res = await fetchJSON('/api/stories/' + storyId, { method: 'DELETE' });
    if (res.ok) {
        loadStories();
    } else {
        alert('Failed to delete: ' + (res.error || 'Unknown error'));
    }
}

async function generateStoriesForJob(jobId) {
    if (!confirm('Generate interview stories for this job? This may take a moment.')) return;
    
    try {
        const res = await fetchJSON('/api/stories/generate/' + jobId, { method: 'POST' });
        if (res.ok) {
            alert('Stories generated successfully!');
            loadStories();
        } else {
            alert('Failed to generate: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    loadAIProviders();
    loadProfileSettings();
    loadStories();
});
