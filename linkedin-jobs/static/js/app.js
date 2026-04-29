
let currentFilter = 'all';
let pollInterval = null;

// --- API calls ---
async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
}

async function refreshStats() {
    const data = await fetchJSON('/api/stats');
    document.getElementById('stat-total').textContent = data.total || 0;
    document.getElementById('stat-new').textContent = data.new || 0;
    document.getElementById('stat-scraped').textContent = data.scraped || 0;
    document.getElementById('stat-done').textContent = data.done || 0;
    document.getElementById('stat-error').textContent = data.error || 0;
}

async function refreshJobs() {
    const data = await fetchJSON('/api/jobs?status=' + currentFilter);
    const list = document.getElementById('jobs-list');

    if (!data.jobs || data.jobs.length === 0) {
        list.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>No jobs found.</p></div>';
        document.getElementById('job-count').textContent = '';
        return;
    }

    document.getElementById('job-count').textContent = '(' + data.jobs.length + ')';

    list.innerHTML = data.jobs.map(j => {
        const title = esc(j.job_title || 'Untitled');
        const company = esc(j.company || '');
        const location = esc(j.location || '');
        const isRemote = (j.location || '').toLowerCase().includes('remote');
        const detailParts = [];
        if (company) detailParts.push('🏢 ' + company);
        if (location) detailParts.push('📍 ' + location);
        const detail = detailParts.join('  ·  ');

        const statusLabels = {
            'new': '✨ NOVO',
            'scraped': '📄 DETALHES OK',
            'generating': '⏳ GERANDO',
            'done': '✅ PRONTO',
            'error': '⚠️ ERRO',
            'removed': '🗑️ REMOVIDO'
        };
        const statusLabel = statusLabels[j.status] || j.status.toUpperCase();

        const evaluation = j.evaluation || {};
        const overallScore = evaluation.overall_score || 0;
        const scoreClass = overallScore >= 4 ? 'high' : (overallScore >= 3 ? 'medium' : 'low');
        const archetype = evaluation.archetype || '';

        return `
                <div class="job-container" id="job-container-${j.id}">
                    <div class="job-row">
                        <div style="display:flex; align-items:center; margin-right: 10px; gap: 8px;">
                            <input type="checkbox" class="job-checkbox" data-id="${j.id}">
                            <button class="btn-icon btn-expand" onclick="toggleDetails(${j.id})" title="View Description">
                                ${j.description ? '▼' : '·'}
                            </button>
                        </div>
                        <div class="job-info">
                            <div class="job-title" title="${title}">${title}</div>
                            <div class="job-company">${detail}</div>
                            ${overallScore > 0 ? `
                                <div style="display:flex; align-items:center; gap:8px; margin-top:4px;">
                                    <span class="score-badge ${scoreClass}" title="Overall Score: ${overallScore}/5">${overallScore}</span>
                                    ${archetype ? `<span class="archetype-badge" title="Archetype">${esc(archetype)}</span>` : ''}
                                </div>
                            ` : ''}
                        </div>
                        <div class="job-meta">
                            ${j.easy_apply ? '<span class="badge easy-apply" title="Easy Apply" style="padding:4px 6px;">⚡</span>' : ''}
                            ${(j.description && j.description.length > 50) || j.status === 'scraped' || j.status === 'done' ? '<span class="badge scraped" style="padding:4px 6px; background:#2e7d32;" title="Detalhes Baixados">⬇️ 📄</span>' : ''}
                            ${j.file_name ? `<a href="/download/${encodeURIComponent(j.file_name)}" class="badge done" style="text-decoration:none; cursor:pointer;" title="Download CV">✅ CV</a>` : `<span class="badge" style="background:#555; cursor:pointer; display:inline-flex; align-items:center; gap:4px; margin-right:4px;" onclick="generateSingleCV(${j.id})" title="Gerar Currículo">CV 📄 ⬇️</span>`}
                            ${j.cover_letter ? `<span class="badge warning" style="display:inline-flex; align-items:center; gap:4px; margin-right:4px;">CL <span style="cursor:pointer;" onclick="copyCL(${j.id})" title="Copiar CL">📋</span> <a href="/download/cl/${j.id}" style="color:inherit; text-decoration:none;" title="Baixar CL PDF">⬇️</a></span>` : `<span class="badge" style="background:#555; cursor:pointer; display:inline-flex; align-items:center; gap:4px; margin-right:4px;" onclick="generateSingleCL(${j.id})" title="Gerar Cover Letter">CL 📋 ⬇️</span>`}
                            
                            <button class="btn-icon" onclick="evaluateJob(${j.id})" title="Evaluate Job" style="color:var(--accent);">📊</button>
                            <button class="btn-icon" onclick="openOutreachModal(${j.id})" title="Outreach Prep" style="color:#ff9800;">📧</button>
                            <a href="/chat/${j.id}" target="_blank" class="btn-icon" title="Chat Assistente" style="color:var(--accent)">💬</a>
                            <a href="${esc(j.url)}" target="_blank" class="btn-icon" title="Abrir no LinkedIn">🔗</a>
                            ${j.has_application
                ? `<button class="btn-icon" onclick="openAppModalForJob(${j.id}, '${esc(j.company).replace(/'/g, "\\'")}', '${esc(j.job_title).replace(/'/g, "\\'")}')" title="Application Tracked" style="color:var(--text-muted); background:rgba(255,255,255,0.05);">📨</button>`
                : `<button class="btn-icon" onclick="openAppModalForJob(${j.id}, '${esc(j.company).replace(/'/g, "\\'")}', '${esc(j.job_title).replace(/'/g, "\\'")}')" title="Track Application" style="color:#4caf50;">📥</button>`
            }
                            <button class="btn-icon danger" onclick="removeJob(${j.id})" title="Remover Vaga">🗑️</button>
                        </div>
                    </div>
                    <div class="job-details" id="details-${j.id}">
                        ${(() => {
                const hasCompany = j.company_description || j.company_profile_url;
                let team = [];
                try { team = j.hiring_team_json ? JSON.parse(j.hiring_team_json) : []; } catch (e) { }
                const hasTeam = team.length > 0;
                const hasEvaluation = evaluation && overallScore > 0;
                return `
                            <div class="detail-tabs">
                                <button class="detail-tab active" onclick="switchTab(${j.id}, 'desc', this)">📄 Descrição</button>
                                ${hasCompany ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'company', this)">🏢 Empresa</button>` : ''}
                                ${hasTeam ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'team', this)">👥 Equipe <span class="tab-count">${team.length}</span></button>` : ''}
                                ${j.cover_letter ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'cl', this)">📄 Cover Letter</button>` : ''}
                                ${hasEvaluation ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'evaluation', this)">📊 Evaluation</button>` : ''}
                                <button class="detail-tab" onclick="switchTab(${j.id}, 'gaps', this); loadSkillGaps(${j.id})">🎯 Gaps</button>
                            </div>
                            <div class="tab-panel active" id="tab-desc-${j.id}">
                                <div class="details-content">${esc(j.description)}</div>
                            </div>
                            ${hasCompany ? `
                            <div class="tab-panel" id="tab-company-${j.id}">
                                ${j.company_profile_url ? `
                                    <a href="${esc(j.company_profile_url)}" target="_blank" class="company-url">
                                        Ver Perfil no LinkedIn ↗
                                    </a>
                                ` : ''}
                                <div class="details-content">${esc(j.company_description)}</div>
                            </div>
                            ` : ''}
                            ${hasTeam ? `
                            <div class="tab-panel" id="tab-team-${j.id}">
                                <div class="hiring-team-list">
                                    ${team.map(p => `
                                        <div class="hiring-person">
                                            <a href="${esc(p.url)}" target="_blank">
                                                <span class="person-name">👤 ${esc(p.name)}</span>
                                                ${p.title ? `<span class="person-title">${esc(p.title)}</span>` : ''}
                                            </a>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            ` : ''}
                            ${j.cover_letter ? `
                            <div class="tab-panel" id="tab-cl-${j.id}">
                                <div class="details-content" id="cl-content-${j.id}">${esc(j.cover_letter)}</div>
                            </div>
                            ` : ''}
                            ${hasEvaluation ? `
                            <div class="tab-panel" id="tab-evaluation-${j.id}">
                                <div class="evaluation-summary">
                                    <div class="evaluation-score">
                                        <div class="evaluation-score-value" style="color: ${overallScore >= 4 ? '#2e7d32' : (overallScore >= 3 ? '#f57c00' : '#c62828')}">${overallScore}</div>
                                        <div class="evaluation-score-label">Overall</div>
                                    </div>
                                    <div class="evaluation-details">
                                        <div class="evaluation-detail-item">
                                            <span class="evaluation-detail-label">Match Score</span>
                                            <span class="evaluation-detail-value">${evaluation.match_score || 0}/5</span>
                                        </div>
                                        <div class="evaluation-detail-item">
                                            <span class="evaluation-detail-label">North Star</span>
                                            <span class="evaluation-detail-value">${evaluation.north_star_score || 0}/5</span>
                                        </div>
                                        <div class="evaluation-detail-item">
                                            <span class="evaluation-detail-label">Compensation</span>
                                            <span class="evaluation-detail-value">${evaluation.comp_score || 0}/5</span>
                                        </div>
                                        <div class="evaluation-detail-item">
                                            <span class="evaluation-detail-label">Cultural Fit</span>
                                            <span class="evaluation-detail-value">${evaluation.cultural_score || 0}/5</span>
                                        </div>
                                        <div class="evaluation-detail-item">
                                            <span class="evaluation-detail-label">Red Flags</span>
                                            <span class="evaluation-detail-value">${evaluation.red_flags || 'None'}</span>
                                        </div>
                                    </div>
                                </div>
                                ${evaluation.analysis ? `
                                    <div style="margin-top:12px;">
                                        <div style="font-weight:600; font-size:13px; margin-bottom:8px;">Analysis:</div>
                                        <div class="details-content">${esc(evaluation.analysis)}</div>
                                    </div>
                                ` : ''}
                                ${archetype ? `
                                    <div style="margin-top:12px;">
                                        <div style="font-weight:600; font-size:13px; margin-bottom:8px;">Archetype:</div>
                                        <span class="archetype-badge">${esc(archetype)}</span>
                                    </div>
                                ` : ''}
                            </div>
                            ` : ''}
                            <div class="tab-panel" id="tab-gaps-${j.id}">
                                <div id="gaps-content-${j.id}" class="details-content">
                                    <div class="empty-state" style="padding:20px">
                                        <button class="btn primary" onclick="analyzeSkillGaps(${j.id})">🚀 Analisar Gaps de Competência</button>
                                    </div>
                                </div>
                            </div>
                            `;
            })()}
                    </div>
                </div>
            `}).join('');
}

async function refreshConfig() {
    const data = await fetchJSON('/api/config');
    const grid = document.getElementById('config-grid');
    grid.innerHTML = data.items.map(i => `
                <div class="config-item">
                    <span class="config-label">${esc(i.label)}</span>
                    <span class="config-value ${i.ok ? 'ok' : (i.ok === false ? 'missing' : '')}">${esc(i.value)}</span>
                </div>
            `).join('');
}

async function refreshTaskStatus() {
    const data = await fetchJSON('/api/task-status');
    const banner = document.getElementById('task-banner');
    const dot = document.getElementById('status-dot');
    const headerText = document.getElementById('header-status-text');

    if (data.running) {
        banner.style.display = 'flex';
        document.getElementById('task-name').textContent = data.task;
        document.getElementById('task-progress').textContent = data.progress;
        dot.className = 'status-dot warning';
        headerText.textContent = 'Running: ' + data.task;
        setButtons(true);
        // Disable model-select while running
        document.getElementById('model-select').disabled = true;
        // Show "Finish Login" button only during login tasks
        const finishBtn = document.getElementById('btn-finish-login');
        finishBtn.style.display = data.task.toLowerCase().includes('login') ? 'inline-flex' : 'none';
    } else {
        banner.style.display = 'none';
        dot.className = 'status-dot';
        headerText.textContent = 'Ready';
        setButtons(false);
        document.getElementById('model-select').disabled = false;

        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
            refreshStats();
            refreshJobs();
        }
    }

    // Update logs
    if (data.logs && data.logs.length > 0) {
        const logBody = document.getElementById('log-body');
        logBody.innerHTML = data.logs.map(l =>
            `<div class="log-entry"><span class="log-time">${l.time}</span><span class="log-msg">${esc(l.msg)}</span></div>`
        ).join('');
        logBody.scrollTop = logBody.scrollHeight;
    }
}

async function runTask(task) {
    const modelName = document.getElementById('model-select').value;
    let endpoint = '/api/run';
    let body = { task, model_name: modelName };

    if (task === 'search') {
        endpoint = '/api/search/run';
        body = {};
    }

    const res = await fetchJSON(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (res.ok) {
        // Start polling
        refreshTaskStatus();
        pollInterval = setInterval(() => {
            refreshTaskStatus();
            refreshStats();
        }, 2000);
    } else {
        alert(res.error || 'Failed to start task');
    }
}

async function cancelTask() {
    await fetchJSON('/api/cancel', { method: 'POST' });
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    refreshTaskStatus();
    refreshStats();
    refreshJobs();
}

async function finishLogin() {
    await fetchJSON('/api/finish-login', { method: 'POST' });
}

function toggleDetails(id) {
    const el = document.getElementById('details-' + id);
    const container = document.getElementById('job-container-' + id);
    if (el) {
        const isActive = el.classList.toggle('active');
        if (container) container.classList.toggle('expanded', isActive);
        // Scroll job row into view when expanding
        if (isActive && container) {
            setTimeout(() => container.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
        }
    }
}

function switchTab(jobId, tab, btn) {
    // Hide all tab panels for this job
    const details = document.getElementById('details-' + jobId);
    details.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    details.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
    // Show selected
    const panel = document.getElementById('tab-' + tab + '-' + jobId);
    if (panel) panel.classList.add('active');
    btn.classList.add('active');
}

function copyCL(jobId) {
    const clElem = document.getElementById('cl-content-' + jobId);
    if (!clElem) return;
    navigator.clipboard.writeText(clElem.textContent).then(() => {
        alert("Cover Letter copiada para a área de transferência!");
    }).catch(err => {
        console.error("Erro ao copiar cover letter: ", err);
    });
}

async function removeJob(id) {
    if (!confirm('Remove this job?')) return;
    const res = await fetchJSON('/api/jobs/delete/' + id, { method: 'POST' });
    if (res.ok) {
        refreshJobs();
        refreshStats();
    }
}

async function clearAllJobs() {
    if (!confirm('Mark all non-Done jobs as removed?')) return;
    const res = await fetchJSON('/api/jobs/clear', { method: 'POST' });
    if (res.ok) {
        refreshJobs();
        refreshStats();
    }
}

function setFilter(filter, el) {
    currentFilter = filter;
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    refreshJobs();
}

function setButtons(disabled) {
    document.querySelectorAll('.actions-row .btn').forEach(b => b.disabled = disabled);
}

function clearLogs() {
    document.getElementById('log-body').innerHTML =
        '<div class="empty-state" style="padding:20px"><p style="color:var(--text-muted)">Waiting for activity...</p></div>';
}

function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// Close dropdown if clicked outside
window.onclick = function (event) {
    if (!event.target.closest('.dropdown')) {
        const dropdowns = document.getElementsByClassName("dropdown");
        for (let i = 0; i < dropdowns.length; i++) {
            const openDropdown = dropdowns[i];
            if (openDropdown.classList.contains('show')) openDropdown.classList.remove('show');
        }
    }
}

async function runGenerateTask(taskType, onlySelected) {
    let jobIds = null;
    if (onlySelected) {
        const checkboxes = document.querySelectorAll('.job-checkbox:checked');
        if (checkboxes.length === 0) {
            alert('Nenhuma vaga selecionada.');
            return;
        }
        jobIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.id));
    }
    document.getElementById('generate-dropdown').classList.remove('show');

    const modelName = document.getElementById('model-select').value;
    const res = await fetchJSON('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: taskType, job_ids: jobIds, model_name: modelName })
    });

    if (res.ok) {
        refreshTaskStatus();
        pollInterval = setInterval(() => {
            refreshTaskStatus();
            refreshStats();
        }, 2000);
    } else {
        alert(res.error || 'Failed to start task');
    }
}

async function refreshModels() {
    try {
        const data = await fetchJSON('/api/models');
        const selectElement = document.getElementById('model-select');
        if (data.models && data.models.length > 0) {
            selectElement.innerHTML = data.models.map(m => `
                        <option value="${esc(m)}" ${m === 'gemini-3-flash-preview' ? 'selected' : ''}>${esc(m)}</option>
                    `).join('');
        } else {
            selectElement.innerHTML = '<option value="gemini-3-flash-preview">gemini-3-flash-preview</option>';
        }
    } catch (e) {
        console.error("Failed to load models list");
    }
}

async function submitManualJob() {
    const btn = document.querySelector('#addJobModal .btn.success');
    const data = {
        title: document.getElementById('manual-job-title').value.trim(),
        company: document.getElementById('manual-company').value.trim(),
        location: document.getElementById('manual-location').value.trim(),
        url: document.getElementById('manual-url').value.trim(),
        description: document.getElementById('manual-description').value.trim(),
    };
    if (!data.title || !data.company || !data.description) {
        alert("Please fill in Title, Company, and Description.");
        return;
    }
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
        const res = await fetchJSON('/api/jobs/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            closeAddJobModal();
            // Clear fields
            document.getElementById('manual-job-title').value = '';
            document.getElementById('manual-company').value = '';
            document.getElementById('manual-location').value = '';
            document.getElementById('manual-url').value = '';
            document.getElementById('manual-description').value = '';
            refreshJobs();
        } else {
            alert('Error adding job: ' + res.error);
        }
    } catch (e) {
        alert('Connection error');
    } finally {
        btn.disabled = false;
        btn.textContent = "Save Job";
    }
}

function openAddJobModal() {
    document.getElementById('addJobModal').style.display = 'block';
}
function closeAddJobModal() {
    document.getElementById('addJobModal').style.display = 'none';
}

async function generateSingleCV(id) {
    if (!confirm('Gerar Currículo para esta vaga? Isso pode demorar alguns segundos.')) return;
    const modelName = document.getElementById('model-select').value;
    const res = await fetchJSON('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: 'generate', job_ids: [id], model_name: modelName })
    });
    if (res.ok) {
        refreshTaskStatus();
        if (!pollInterval) {
            pollInterval = setInterval(() => {
                refreshTaskStatus();
                refreshStats();
            }, 2000);
        }
    } else {
        alert(res.error || 'Failed to start task');
    }
}

async function generateSingleCL(id) {
    if (!confirm('Gerar Cover Letter para esta vaga? Isso pode demorar alguns segundos.')) return;
    const modelName = document.getElementById('model-select').value;
    const res = await fetchJSON('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: 'generate_cover_letter', job_ids: [id], model_name: modelName })
    });
    if (res.ok) {
        refreshTaskStatus();
        if (!pollInterval) {
            pollInterval = setInterval(() => {
                refreshTaskStatus();
                refreshStats();
            }, 2000);
        }
    } else {
        alert(res.error || 'Failed to start task');
    }
}

function openAppModalForJob(jobId, company, title) {
    document.getElementById('app-id').value = '';
    document.getElementById('app-job-id').value = jobId;
    document.getElementById('app-company').value = company || '';
    document.getElementById('app-title').value = title || '';
    document.querySelector('#appModal h2').innerHTML = '📥 Register Application';
    document.getElementById('appModal').style.display = 'block';
}

function closeAppModal() {
    document.getElementById('appModal').style.display = 'none';
}

function editApp(id) {
    const app = window.appsData[id];
    if (!app) return;
    document.getElementById('app-id').value = app.id;
    document.getElementById('app-job-id').value = app.job_id || '';
    document.getElementById('app-company').value = app.company_name || '';
    document.getElementById('app-title').value = app.job_title || '';
    document.getElementById('app-method').value = app.apply_method || 'LinkedIn Easy Apply';
    document.getElementById('app-status').value = app.status || 'Applied';
    document.getElementById('app-notes').value = app.notes || '';
    document.querySelector('#appModal h2').innerHTML = '✏️ Edit Application';
    document.getElementById('appModal').style.display = 'block';
}

async function submitApp() {
    const btn = document.querySelector('#appModal .btn.success');
    const appId = document.getElementById('app-id').value;
    const data = {
        job_id: document.getElementById('app-job-id').value,
        company: document.getElementById('app-company').value.trim(),
        job_title: document.getElementById('app-title').value.trim(),
        apply_method: document.getElementById('app-method').value,
        status: document.getElementById('app-status').value,
        notes: document.getElementById('app-notes').value.trim(),
    };
    if (!data.company || !data.job_title) {
        alert("Please fill in Company and Job Title.");
        return;
    }
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
        let endpoint = '/api/applications';
        if (appId) {
            endpoint = '/api/applications/update/' + appId;
        }
        const res = await fetchJSON(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            closeAppModal();
            refreshAppsBoard();
        } else {
            alert('Error saving application: ' + res.error);
        }
    } catch (e) {
        alert('Connection error');
    } finally {
        btn.disabled = false;
        btn.textContent = "Save Application";
    }
}

function openAppModal() {
    document.getElementById('app-id').value = '';
    document.getElementById('app-job-id').value = '';
    document.getElementById('app-company').value = '';
    document.getElementById('app-title').value = '';
    document.getElementById('app-notes').value = '';
    document.querySelector('#appModal h2').innerHTML = '📥 Register Application';
    document.getElementById('appModal').style.display = 'block';
}

function switchMainView(viewId, btn) {
    document.getElementById('jobs-view').style.display = 'none';
    document.getElementById('apps-view').style.display = 'none';
    document.querySelectorAll('.main-nav button').forEach(b => b.classList.remove('active'));

    document.getElementById(viewId).style.display = 'block';
    btn.classList.add('active');

    if (viewId === 'apps-view') {
        refreshAppsBoard();
    } else if (viewId === 'strategies-view') {
        loadStrategies();
    }
}

window.appsData = {};

function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    ev.dataTransfer.setData("text", ev.currentTarget.dataset.id);
}

async function drop(ev, newStatus) {
    ev.preventDefault();
    const id = ev.dataTransfer.getData("text");
    if (!id) return;

    const res = await fetchJSON('/api/applications/update/' + id, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) refreshAppsBoard();
}

async function refreshAppsBoard() {
    const data = await fetchJSON('/api/applications');
    const board = document.getElementById('apps-board');
    if (!data.applications || data.applications.length === 0) {
        board.innerHTML = '<div class="empty-state">Nenhuma aplicação rastreada ainda.</div>';
        return;
    }

    window.appsData = {};
    const columns = {
        'Applied': [],
        'Screening': [],
        'Interview': [],
        'Offer': [],
        'Rejected': []
    };

    data.applications.forEach(a => {
        window.appsData[a.id] = a;
        const s = a.status;
        if (columns[s]) columns[s].push(a);
        else columns['Applied'].push(a);
    });

    let html = '';
    for (const [status, apps] of Object.entries(columns)) {
        html += `
        <div class="kanban-column" ondragover="allowDrop(event)" ondrop="drop(event, '${status}')">
            <div class="kanban-header">${status} <span class="badge" style="background:rgba(0,0,0,0.3)">${apps.length}</span></div>
            <div class="kanban-cards">
                ${apps.map(a => `
                    <div class="kanban-card" draggable="true" ondragstart="drag(event)" data-id="${a.id}" onclick="editApp(${a.id})" title="Click to edit">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="font-weight:600;">${esc(a.job_title)}</span>
                            <button class="btn-icon danger" style="padding:0; font-size:10px" onclick="event.stopPropagation(); deleteApp(${a.id})" title="Delete App">🗑️</button>
                        </div>
                        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px">
                            🏢 ${esc(a.company_name)} ${a.location ? ` • 📍 ${esc(a.location)}` : ''}
                        </div>
                        <div style="font-size:11px; display:flex; justify-content:space-between; align-items:center;">
                            ${a.url ? `<a href="${esc(a.url)}" target="_blank" onclick="event.stopPropagation();" style="color:var(--accent); text-decoration:none;">🔗 Ver Vaga</a>` : '<span></span>'}
                            <span style="opacity:0.6">${a.created_at ? a.created_at.substring(0, 10) : ''}</span>
                        </div>
                        ${a.notes ? `<div style="font-size:10px; color:var(--warning); margin-top:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block; width:100%; box-sizing:border-box;" title="${esc(a.notes)}">📝 ${esc(a.notes)}</div>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>`;
    }
    board.innerHTML = html;
}

async function deleteApp(id) {
    if (!confirm("Remover o tracking desta aplicação?")) return;
    const res = await fetchJSON('/api/applications/delete/' + id, { method: 'POST' });
    if (res.ok) {
        refreshAppsBoard();
        refreshJobs();
    }
}

// --- Init ---
refreshModels();
refreshStats();
refreshJobs();
refreshConfig();
// Check if task already running
refreshTaskStatus();

// --- Evaluation Functions ---
async function evaluateJob(jobId) {
    if (!confirm('Evaluate this job? This will analyze the job description against your profile.')) return;
    
    const btn = document.querySelector(`#job-container-${jobId} .btn-icon[onclick="evaluateJob(${jobId})"]`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳';
    }
    
    try {
        const res = await fetchJSON('/api/jobs/' + jobId + '/evaluate', {
            method: 'POST'
        });
        
        if (res.ok) {
            alert('Job evaluated successfully!');
            refreshJobs();
        } else {
            alert('Failed to evaluate: ' + (res.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '📊';
        }
    }
}

async function batchEvaluateJobs() {
    const checkboxes = document.querySelectorAll('.job-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('No jobs selected.');
        return;
    }
    
    if (!confirm(`Evaluate ${checkboxes.length} selected jobs? This may take a moment.`)) return;
    
    const jobIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.id));
    
    try {
        let successCount = 0;
        let failCount = 0;
        
        for (const jobId of jobIds) {
            try {
                const res = await fetchJSON('/api/jobs/' + jobId + '/evaluate', {
                    method: 'POST'
                });
                if (res.ok) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (e) {
                failCount++;
            }
        }
        
        alert(`Evaluation complete: ${successCount} succeeded, ${failCount} failed.`);
        refreshJobs();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}
// --- Search Strategies ---
async function loadStrategies() {
    const strategies = await fetchJSON('/api/strategies');
    const list = document.getElementById('strategies-list');
    
    if (!strategies || strategies.length === 0) {
        list.innerHTML = '<div class="empty-state">Nenhuma estratégia de busca cadastrada. Clique em "New Strategy" para começar.</div>';
        return;
    }

    list.innerHTML = strategies.map(s => `
        <div class="strategy-card" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <span style="font-weight:600; font-size:16px;">${esc(s.title)}</span>
                <span class="badge ${s.is_active ? 'scraped' : ''}">${s.is_active ? 'Ativa' : 'Inativa'}</span>
            </div>
            <div style="font-size:13px; color:var(--text-secondary); display:grid; gap:8px;">
                <div><strong>Palavras-chave:</strong> ${esc((s.keywords || []).join(', '))}</div>
                <div><strong>Locais:</strong> ${esc((s.locations || []).join(', '))}</div>
                <div><strong>Remoto Apenas:</strong> ${s.remote_only ? 'Sim' : 'Não'}</div>
            </div>
            <div style="margin-top:16px; display:flex; gap:8px;">
                <button class="btn danger" style="padding:4px 12px; font-size:12px;" onclick="deleteStrategy(${s.id})">🗑️ Deletar</button>
            </div>
        </div>
    `).join('');
}

function openAddStrategyModal() {
    document.getElementById('addStrategyModal').style.display = 'block';
}

function closeAddStrategyModal() {
    document.getElementById('addStrategyModal').style.display = 'none';
}

async function submitStrategy() {
    const btn = document.querySelector('#addStrategyModal .btn.success');
    const data = {
        title: document.getElementById('strat-title').value.trim(),
        keywords: document.getElementById('strat-keywords').value.split(',').map(k => k.trim()).filter(k => k),
        locations: document.getElementById('strat-locations').value.split(',').map(l => l.trim()).filter(l => l),
        remote_only: document.getElementById('strat-remote').checked
    };

    if (!data.title || data.keywords.length === 0) {
        alert("Preencha o título e pelo menos uma palavra-chave.");
        return;
    }

    btn.disabled = true;
    btn.textContent = "Salvando...";
    try {
        const res = await fetchJSON('/api/strategies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            closeAddStrategyModal();
            loadStrategies();
            // Limpar campos
            document.getElementById('strat-title').value = '';
            document.getElementById('strat-keywords').value = '';
            document.getElementById('strat-locations').value = '';
        } else {
            alert('Erro ao salvar estratégia: ' + res.error);
        }
    } catch (e) {
        alert('Erro de conexão');
    } finally {
        btn.disabled = false;
        btn.textContent = "Save Strategy";
    }
}

async function deleteStrategy(id) {
    if (!confirm('Deletar esta estratégia?')) return;
    const res = await fetchJSON('/api/strategies/delete/' + id, { method: 'POST' });
    if (res.ok) loadStrategies();
}

// --- Outreach ---
let currentOutreachJobId = null;

async function openOutreachModal(jobId) {
    currentOutreachJobId = jobId;
    const data = await fetchJSON('/api/jobs/' + jobId);
    const j = data.job;
    
    document.getElementById('outreach-email').value = j.recruiter_email || '';
    document.getElementById('outreach-linkedin').value = j.recruiter_linkedin_url || '';
    document.getElementById('outreach-email-draft').value = j.email_draft || '';
    document.getElementById('outreach-dm-draft').value = j.linkedin_dm_draft || '';
    
    document.getElementById('outreachModal').style.display = 'block';
    switchOutreachTab('email');
}

function closeOutreachModal() {
    document.getElementById('outreachModal').style.display = 'none';
}

function switchOutreachTab(tab) {
    document.getElementById('outreach-email-panel').style.display = tab === 'email' ? 'block' : 'none';
    document.getElementById('outreach-dm-panel').style.display = tab === 'dm' ? 'block' : 'none';
    document.getElementById('tab-btn-email').classList.toggle('active', tab === 'email');
    document.getElementById('tab-btn-dm').classList.toggle('active', tab === 'dm');
}

async function sendOutreachEmail() {
    if (!currentOutreachJobId) return;
    const email = document.getElementById('outreach-email').value;
    const body = document.getElementById('outreach-email-draft').value;
    
    if (!email || !body) {
        alert("Preencha o e-mail e o conteúdo.");
        return;
    }

    if (!confirm(`Enviar e-mail para ${email}?`)) return;

    const res = await fetchJSON('/api/outreach/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: currentOutreachJobId, email, body })
    });
    
    if (res.ok) alert("🚀 E-mail enviado com sucesso!");
    else alert("❌ Erro ao enviar e-mail: " + (res.error || 'Verifique o .env'));
}

async function sendOutreachDM() {
    if (!currentOutreachJobId) return;
    const url = document.getElementById('outreach-linkedin').value;
    const message = document.getElementById('outreach-dm-draft').value;
    
    if (!url || !message) {
        alert("Preencha o perfil do LinkedIn e a mensagem.");
        return;
    }

    if (!confirm(`Enviar nota de conexão via Playwright para ${url}?`)) return;

    const res = await fetchJSON('/api/outreach/dm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: currentOutreachJobId, url, message })
    });
    
    if (res.ok) alert("🤝 Solicitação de conexão enviada para a fila!");
    else alert("❌ Erro ao iniciar tarefa: " + (res.error || 'Verifique os logs'));
}

// --- Skill Gaps ---
async function loadSkillGaps(jobId) {
    const content = document.getElementById('gaps-content-' + jobId);
    const gaps = await fetchJSON('/api/jobs/' + jobId + '/skill-gaps');
    
    if (!gaps || Object.keys(gaps).length === 0) {
        return; // Keep "Analyze" button
    }

    let html = `
        <div class="gaps-summary" style="margin-bottom:20px; padding:15px; background:rgba(255,255,255,0.05); border-radius:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:16px;">Match Score: ${gaps.match_score}%</span>
                <div class="score-bar-container" style="width:150px; height:8px; background:rgba(0,0,0,0.3); border-radius:4px; overflow:hidden;">
                    <div class="score-bar" style="width:${gaps.match_score}%; height:100%; background:var(--accent);"></div>
                </div>
            </div>
            <p style="margin-top:10px; font-style:italic;">${esc(gaps.summary)}</p>
        </div>

        <div class="gaps-section">
            <h4 style="color:var(--error); margin-bottom:10px;">🔴 Gaps de Competência</h4>
            <div class="gaps-list" style="display:grid; gap:10px;">
                ${gaps.gaps.map(g => `
                    <div style="padding:10px; border-left:3px solid ${g.severity === 'high' ? 'var(--error)' : 'var(--warning)'}; background:rgba(255,255,255,0.02);">
                        <div style="font-weight:600;">${esc(g.skill)} <span class="badge ${g.severity}">${g.severity}</span></div>
                        <div style="font-size:12px; opacity:0.8;">${esc(g.reason)}</div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="gaps-section" style="margin-top:20px;">
            <h4 style="color:var(--warning); margin-bottom:10px;">🔶 Experiência Faltante</h4>
            <ul style="padding-left:20px;">
                ${gaps.missing_experience.map(e => `<li>${esc(e)}</li>`).join('')}
            </ul>
        </div>

        <div class="gaps-section" style="margin-top:20px;">
            <h4 style="color:var(--success); margin-bottom:10px;">📚 Sugestões de Treinamento</h4>
            <div style="display:grid; gap:10px;">
                ${gaps.training_suggestions.map(s => `
                    <div style="padding:10px; background:rgba(0,212,170,0.05); border-radius:6px;">
                        <div style="font-weight:600; color:var(--success);">${esc(s.topic)}</div>
                        <div style="font-size:12px;">${esc(s.action)}</div>
                    </div>
                `).join('')}
            </div>
        </div>
        
        <div style="margin-top:20px; text-align:center;">
            <button class="btn" style="font-size:11px;" onclick="analyzeSkillGaps(${jobId})">🔄 Re-analisar</button>
        </div>
    `;
    
    content.innerHTML = html;
}

async function analyzeSkillGaps(jobId) {
    const res = await fetchJSON('/api/jobs/' + jobId + '/skill-gaps', { method: 'POST' });
    if (res.ok) {
        refreshTaskStatus();
        const poll = setInterval(() => {
            fetchJSON('/api/jobs/' + jobId + '/skill-gaps').then(gaps => {
                if (gaps && Object.keys(gaps).length > 0) {
                    loadSkillGaps(jobId);
                    clearInterval(poll);
                    refreshTaskStatus();
                }
            });
        }, 3000);
    } else {
        alert(res.error || 'Failed to start analysis');
    }
}
