
// DOM Elements
const menuToggle = document.getElementById('menuToggle');
const mobileMenu = document.getElementById('mobileMenu');
const headlineTextArea = document.getElementById('headline-content');
const aboutTextArea = document.getElementById('about-content');
const headlineChars = document.getElementById('headline-chars');
const aboutChars = document.getElementById('about-chars');

// Mobile Menu Toggle
if (menuToggle) {
    menuToggle.addEventListener('click', () => {
        const isOpen = mobileMenu.style.display === 'block';
        mobileMenu.style.display = isOpen ? 'none' : 'block';
        menuToggle.classList.toggle('active');
    });
}

// Character Counters
if (headlineTextArea) {
    headlineTextArea.addEventListener('input', () => {
        headlineChars.textContent = headlineTextArea.value.length;
    });
}

if (aboutTextArea) {
    aboutTextArea.addEventListener('input', () => {
        aboutChars.textContent = aboutTextArea.value.length;
    });
}

// API Functions
async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
}

async function analyzeFullProfile() {
    const btn = document.querySelector('.hero-actions .btn.primary');
    const model = document.getElementById('model-select').value;
    
    // Get current resume content
    const resumeRes = await fetchJSON('/api/profile/resume');
    if (!resumeRes.ok) {
        alert("Resume not found. Please create resume_base.md first.");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '⏳ Analisando...';

    const res = await fetchJSON('/api/profile/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            section: 'analyze',
            content: resumeRes.content,
            model_name: model
        })
    });

    if (res.ok) {
        showAnalysis(res.result);
    } else {
        alert("Error: " + res.error);
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="icon">🔍</span> Analisar Perfil Atual';
}

async function optimizeSection(section) {
    const textArea = document.getElementById(`${section}-content`);
    const btn = event.target;
    const model = document.getElementById('model-select').value;
    
    let content = textArea.value.trim();
    if (!content) {
        // Fallback to resume context if empty
        const resumeRes = await fetchJSON('/api/profile/resume');
        if (resumeRes.ok) content = resumeRes.content;
    }

    const originalBtnText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ Gerando...';

    const res = await fetchJSON('/api/profile/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            section: section,
            content: content,
            model_name: model
        })
    });

    if (res.ok) {
        textArea.value = res.result;
        textArea.dispatchEvent(new Event('input')); // Update char count
    } else {
        alert("Error: " + res.error);
    }

    btn.disabled = false;
    btn.innerHTML = originalBtnText;
}

async function generateSSIPan() {
    const btn = event.target;
    const model = document.getElementById('model-select').value;
    const resultBox = document.getElementById('ssi-result');
    
    const resumeRes = await fetchJSON('/api/profile/resume');
    const content = resumeRes.ok ? resumeRes.content : "";

    btn.disabled = true;
    btn.innerHTML = '⏳ Gerando Plano...';

    const res = await fetchJSON('/api/profile/ssi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            content: content,
            model_name: model
        })
    });

    if (res.ok) {
        resultBox.innerHTML = `<h4>🎯 Plano de Ação Semanal</h4><div class="markdown-body">${res.result.replace(/\n/g, '<br>')}</div>`;
        resultBox.style.display = 'block';
    } else {
        alert("Error: " + res.error);
    }

    btn.disabled = false;
    btn.innerHTML = 'Gerar Plano Semanal';
}

function showAnalysis(text) {
    const overlay = document.getElementById('analysis-overlay');
    const box = document.getElementById('analysis-text');
    box.innerHTML = text.replace(/\n/g, '<br>');
    overlay.style.display = 'flex';
}

function closeOverlay() {
    document.getElementById('analysis-overlay').style.display = 'none';
}

function copyText(id) {
    const text = document.getElementById(id).value;
    navigator.clipboard.writeText(text).then(() => {
        const btn = event.target;
        const original = btn.innerText;
        btn.innerText = "Copiado!";
        setTimeout(() => btn.innerText = original, 2000);
    });
}

// Initial Load — intentionally does not pre-fill any textarea.
// Use "Analisar Perfil Atual" to analyze resume_base.md,
// or "Importar do LinkedIn" to import live profile data.
function _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function loadModels() {
    const select = document.getElementById('model-select');
    if (!select) return;
    try {
        const res = await fetchJSON('/api/models');
        if (res.models && res.models.length > 0) {
            select.innerHTML = '';
            res.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === 'gemini-3-flash-preview') opt.selected = true;
                select.appendChild(opt);
            });
        }
    } catch(e) {
        console.error("Error loading models:", e);
    }
}

// Initial Load
(async function init() {
    await loadModels();
    await checkProfileStatus();
})();

async function checkProfileStatus() {
    try {
        const res = await fetchJSON('/api/profile/status');
        if (res.ok && res.stats) {
            const banner = document.getElementById('last-optimized-banner');
            const dateSpan = document.getElementById('last-optimized-date');
            const scoreSpan = document.getElementById('last-optimized-score');
            
            if (banner && res.stats.last_optimized_at) {
                const date = new Date(res.stats.last_optimized_at);
                dateSpan.textContent = date.toLocaleDateString();
                scoreSpan.textContent = res.stats.score || '--';
                banner.style.display = 'block';
            }
        }
    } catch(e) {
        console.error("Error checking profile status:", e);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Optimization Wizard
// ─────────────────────────────────────────────────────────────────────────────

let wizardState = {
    currentStep: 1,
    profile: null,
    suggestions: null,
    score: null
};

function startWizard() {
    const wizard = document.getElementById('profile-wizard');
    const hero = document.querySelector('.hero-section');
    wizard.style.display = 'block';
    hero.style.display = 'none';
    goToStep(1);
    runScrapeStep();
}

function goToStep(step) {
    wizardState.currentStep = step;
    
    // Update indicators
    document.querySelectorAll('.step-indicator').forEach(el => {
        const s = parseInt(el.dataset.step);
        el.classList.toggle('active', s === step);
        el.classList.toggle('complete', s < step);
    });

    // Update panes
    document.querySelectorAll('.step-pane').forEach(el => {
        el.classList.toggle('active', el.id === `step-${step}`);
    });
}

async function runScrapeStep() {
    const progressBar = document.getElementById('scrape-progress-bar');
    const statusText = document.getElementById('scrape-status-text');
    
    progressBar.style.width = '10%';
    statusText.textContent = "Iniciando raspagem...";

    try {
        const startRes = await fetchJSON('/api/profile/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!startRes.ok) throw new Error(startRes.error);

        // Polling loop
        for (let i = 0; i < 60; i++) {
            await _sleep(2000);
            progressBar.style.width = `${10 + (i * 1.5)}%`;
            
            const statusRes = await fetchJSON('/api/task-status');
            if (!statusRes.running && statusRes.task === 'Import LinkedIn Profile') {
                if (statusRes.error) throw new Error(statusRes.error);
                break;
            }
        }

        const resultRes = await fetchJSON('/api/profile/import-result');
        if (!resultRes.ok) throw new Error("Não foi possível obter os dados do perfil.");

        wizardState.profile = resultRes.profile;
        progressBar.style.width = '100%';
        statusText.textContent = "Perfil importado com sucesso!";
        
        await _sleep(1000);
        goToStep(2);
        runScoreStep();

    } catch (e) {
        alert("Erro na raspagem: " + e.message);
        location.reload();
    }
}

async function runScoreStep() {
    const scoreVal = document.getElementById('wizard-score');
    const scoreReason = document.getElementById('wizard-score-reason');
    const model = document.getElementById('model-select').value;

    // Convert profile to MD for scoring
    const lang = wizardState.profile.en ? 'en' : 'pt';
    const data = wizardState.profile[lang];
    const profileMd = `Headline: ${data.headline}\n\nAbout: ${data.about}\n\nExperience: ${JSON.stringify(data.experience)}`;

    try {
        const res = await fetchJSON('/api/profile/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: profileMd, model_name: model })
        });

        if (res.ok) {
            wizardState.score = res.result;
            scoreVal.textContent = res.result.score;
            scoreReason.textContent = res.result.reason;
        }
    } catch (e) {
        console.error("Score error:", e);
    }
}

async function runOptimizeStep() {
    if (wizardState.currentStep !== 3) return;
    
    const container = document.getElementById('suggestions-container');
    const loading = document.querySelector('.suggestions-loading');
    const model = document.getElementById('model-select').value;
    
    loading.style.display = 'block';
    container.style.display = 'none';

    try {
        // Run headline and about optimization in parallel
        const lang = wizardState.profile.en ? 'en' : 'pt';
        const profile = wizardState.profile[lang];
        
        const [headlineRes, aboutRes] = await Promise.all([
            fetchJSON('/api/profile/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ section: 'headline', content: profile.headline, model_name: model })
            }),
            fetchJSON('/api/profile/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ section: 'about', content: profile.about, model_name: model })
            })
        ]);

        wizardState.suggestions = {
            headline: headlineRes.result,
            about: aboutRes.result
        };

        container.innerHTML = `
            <div class="opt-card">
                <h5>Nova Headline</h5>
                <p>${wizardState.suggestions.headline}</p>
            </div>
            <div class="opt-card">
                <h5>Novo 'Sobre'</h5>
                <p>${wizardState.suggestions.about.slice(0, 300)}...</p>
            </div>
        `;
        
        loading.style.display = 'none';
        container.style.display = 'block';

    } catch (e) {
        alert("Erro na otimização: " + e.message);
    }
}

// Override goToStep for Step 3 to trigger optimization
const originalGoToStep = goToStep;
goToStep = (step) => {
    originalGoToStep(step);
    if (step === 3) runOptimizeStep();
};

function renderReviewStep() {
    document.getElementById('review-headline').value = wizardState.suggestions.headline;
    document.getElementById('review-about').value = wizardState.suggestions.about;
    goToStep(4);
}

async function regenerateWithFeedback() {
    const feedback = document.getElementById('ai-feedback').value;
    if (!feedback) return alert("Por favor, digite seu comentário.");
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "Regerando...";

    const model = document.getElementById('model-select').value;
    // We send current content + feedback
    const headline = document.getElementById('review-headline').value;
    const about = document.getElementById('review-about').value;

    try {
        const res = await fetchJSON('/api/profile/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                section: 'about', 
                content: `Feedback do usuário: ${feedback}\n\nConteúdo atual:\n${about}`, 
                model_name: model 
            })
        });

        if (res.ok) {
            document.getElementById('review-about').value = res.result;
            document.getElementById('ai-feedback').value = "";
        }
    } catch (e) {
        alert("Erro ao regerar: " + e.message);
    }

    btn.disabled = false;
    btn.textContent = "Regerar com Feedback";
}

async function applyToLinkedIn() {
    if (!confirm("Isso atualizará seu perfil real no LinkedIn. Confirmar?")) return;
    
    const headline = document.getElementById('review-headline').value;
    const about = document.getElementById('review-about').value;
    
    goToStep(5);
    
    const log = document.getElementById('apply-log');
    const bar = document.getElementById('apply-progress-bar');
    
    log.textContent = "Iniciando tarefa de atualização...";
    bar.style.width = "10%";

    try {
        const res = await fetchJSON('/api/profile/update-linkedin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ headline, about })
        });

        if (!res.ok) throw new Error(res.error);

        // Polling
        for (let i = 0; i < 60; i++) {
            await _sleep(2000);
            bar.style.width = `${20 + (i * 2)}%`;
            
            const statusRes = await fetchJSON('/api/task-status');
            if (statusRes.logs && statusRes.logs.length > 0) {
                log.textContent = statusRes.logs[statusRes.logs.length - 1].msg;
            }
            
            if (!statusRes.running && statusRes.task === 'Update LinkedIn Profile') {
                if (statusRes.error) throw new Error(statusRes.error);
                break;
            }
        }

        bar.style.width = "100%";
        document.getElementById('apply-title').textContent = "✅ Perfil Atualizado!";
        document.getElementById('completion-actions').style.display = 'block';

    } catch (e) {
        log.textContent = "Erro: " + e.message;
        document.getElementById('apply-title').textContent = "❌ Falha na Atualização";
    }
}
