// CareerOps LinkedIn Profile Extractor — Clean Version 5.0
// Robust segmented extraction using header-based section discovery.

console.log('CareerOps: Extension content script loaded.');

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function expandAllButtons(container = document) {
    const selectors = [
        '.inline-show-more-text__button', 
        '.lt-line-clamp__more', 
        'button[aria-label*="see more"]', 
        'button[aria-label*="exibir mais"]',
        'button[aria-label*="ver mais"]',
        'a[href*="/details/experience/"]',
        'a[href*="/details/education/"]',
        'a[href*="/details/skills/"]'
    ];
    const buttons = container.querySelectorAll(selectors.join(', '));
    for (const btn of buttons) {
        if (btn.offsetParent !== null) {
            // If it's a link to a "details" page, we don't want to navigate away.
            // But we can try to trigger a click if it's an overlay button.
            if (btn.tagName === 'A') continue; 
            btn.click();
            await wait(300);
        }
    }
}

async function captureContactInfo() {
    console.log('CareerOps: Capturing contact info modal...');
    const contactInfoLink = document.querySelector('#top-card-text-details-contact-info, a[href*="/overlay/contact-info/"]');
    if (!contactInfoLink) return {};

    contactInfoLink.click();
    await wait(1500);
    
    const modal = document.querySelector('.pv-contact-info, .artdeco-modal');
    if (!modal) return {};

    const email = modal.querySelector('section.ci-email .pv-contact-info__contact-item, a[href^="mailto:"]')?.innerText?.trim() || '';
    const phone = modal.querySelector('section.ci-phone .pv-contact-info__contact-item')?.innerText?.trim() || '';
    const linkedin = modal.querySelector('section.ci-linkedin .pv-contact-info__contact-item')?.innerText?.trim() || '';

    const closeBtn = modal.querySelector('button[aria-label*="Dismiss"], button[aria-label*="Fechar"], .artdeco-modal__dismiss');
    if (closeBtn) closeBtn.click();
    await wait(300);

    return { email, phone, linkedin };
}

function findSectionByKeywords(keywords) {
    // Try h2 headers first
    const headers = Array.from(document.querySelectorAll('h2'));
    for (const h of headers) {
        const text = h.innerText.toLowerCase();
        if (keywords.some(k => text.includes(k))) {
            return h.closest('section') || h.parentElement;
        }
    }
    // Fallback to section IDs
    for (const k of keywords) {
        const el = document.getElementById(k);
        if (el) return el.closest('section') || el;
    }
    return null;
}

async function getSegmentedData() {
    const segments = {
        about_raw: '',
        experience_raw: '',
        education_raw: '',
        skills_raw: ''
    };

    const mapping = {
        about_raw: ['sobre', 'about', 'summary'],
        experience_raw: ['experiência', 'experience', 'work history'],
        education_raw: ['formação', 'educação', 'education'],
        skills_raw: ['competências', 'skills', 'habilidades']
    };

    for (const [key, keywords] of Object.entries(mapping)) {
        const section = findSectionByKeywords(keywords);
        if (section) {
            console.log(`CareerOps: Found section for ${key}`);
            await expandAllButtons(section);
            segments[key] = section.innerText;
        } else {
            console.log(`CareerOps: Optional section missing: ${key}`);
        }
    }

    return segments;
}

async function updateVisualStatus(message, isError = false) {
    console.log(`CareerOps: ${message}`);
    await chrome.storage.local.set({ careerops_status: message });
}

async function performFullExtraction() {
    try {
        const url = window.location.href;
        let { careerops_import_data } = await chrome.storage.local.get('careerops_import_data');
        if (!careerops_import_data) careerops_import_data = { step: 'start' };

        // Stage 1: Main Profile Page (Start or Language Switch)
        if (url.includes('/in/') && !url.includes('/details/')) {
            const profileSlug = url.split('/in/')[1].split('/')[0];

            if (careerops_import_data.step === 'start') {
                updateVisualStatus('Fase 1: Analizando Perfil (PT)...');
                await wait(2000);
                careerops_import_data.name = document.querySelector('h1')?.innerText?.trim() || document.querySelector('.text-heading-xlarge')?.innerText?.trim() || '';
                careerops_import_data.headline = document.querySelector('.text-body-medium')?.innerText?.trim() || '';
                careerops_import_data.about = (document.querySelector('section.pv-about-section, #about')?.parentElement?.innerText || '') + '\n' + (document.querySelector('.pv-about-section__top-skills')?.innerText || '');
                careerops_import_data.url = url.split('?')[0];
                careerops_import_data.step = 'go_to_exp';
                await chrome.storage.local.set({ careerops_import_data, careerops_import_active: true });
                window.location.href = `https://www.linkedin.com/in/${profileSlug}/details/experience/`;
                return;
            }

            if (careerops_import_data.step === 'switch_lang') {
                updateVisualStatus('Fase 2: Trocando para Inglês...');
                const langButtons = document.querySelectorAll('.pv-about-section--secondary-languages button, .artdeco-pill, .pv-profile-section__language-pill');
                let found = false;
                for (const btn of langButtons) {
                    const txt = btn.innerText.toLowerCase();
                    if ((txt.includes('english') || txt.includes('inglês')) && !btn.classList.contains('active')) {
                        btn.click();
                        found = true;
                        await wait(3000);
                        break;
                    }
                }
                careerops_import_data.step = 'go_to_exp_en';
                await chrome.storage.local.set({ careerops_import_data });
                window.location.href = `https://www.linkedin.com/in/${profileSlug}/details/experience/`;
                return;
            }
        }

        // Stage 2: Experience
        if (url.includes('/details/experience/')) {
            updateVisualStatus(`Capturando Experiências (${careerops_import_data.step.includes('en') ? 'EN' : 'PT'})...`);
            await wait(2500);
            const expText = document.querySelector('main')?.innerText || '';
            careerops_import_data.experience_raw = (careerops_import_data.experience_raw || '') + '\n' + expText;
            
            careerops_import_data.step = careerops_import_data.step.includes('en') ? 'go_to_edu_en' : 'go_to_edu';
            await chrome.storage.local.set({ careerops_import_data });
            const profileSlug = url.split('/in/')[1].split('/')[0];
            window.location.href = `https://www.linkedin.com/in/${profileSlug}/details/education/`;
            return;
        }

        // Stage 3: Education
        if (url.includes('/details/education/')) {
            updateVisualStatus(`Capturando Formação (${careerops_import_data.step.includes('en') ? 'EN' : 'PT'})...`);
            await wait(2500);
            const eduText = document.querySelector('main')?.innerText || '';
            careerops_import_data.education_raw = (careerops_import_data.education_raw || '') + '\n' + eduText;
            
            careerops_import_data.step = careerops_import_data.step.includes('en') ? 'go_to_skills_en' : 'go_to_skills';
            await chrome.storage.local.set({ careerops_import_data });
            const profileSlug = url.split('/in/')[1].split('/')[0];
            window.location.href = `https://www.linkedin.com/in/${profileSlug}/details/skills/`;
            return;
        }

        // Stage 4: Skills & Finalization
        if (url.includes('/details/skills/')) {
            updateVisualStatus(`Capturando Competências (${careerops_import_data.step.includes('en') ? 'EN' : 'PT'})...`);
            await wait(2500);
            const skillsText = document.querySelector('main')?.innerText || '';
            careerops_import_data.skills_raw = (careerops_import_data.skills_raw || '') + '\n' + skillsText;
            
            if (careerops_import_data.step === 'go_to_skills') {
                careerops_import_data.step = 'switch_lang';
                await chrome.storage.local.set({ careerops_import_data });
                const profileSlug = url.split('/in/')[1].split('/')[0];
                window.location.href = `https://www.linkedin.com/in/${profileSlug}/`;
                return;
            }

            updateVisualStatus('✅ Sincronizando Perfil Global...');
            careerops_import_data.full_page_text = document.documentElement.outerHTML;
            chrome.runtime.sendMessage({ action: 'importProfile', data: careerops_import_data });
            await chrome.storage.local.remove(['careerops_import_active', 'careerops_import_data']);
            
            setTimeout(() => {
                const profileSlug = url.split('/in/')[1].split('/')[0];
                window.location.href = `https://www.linkedin.com/in/${profileSlug}/`;
            }, 3000);
        }
    } catch (e) {
        console.error('CareerOps: Extraction failed:', e);
        await chrome.storage.local.remove(['careerops_import_active', 'careerops_import_data']);
        updateVisualStatus('❌ Falha na captura', true);
    }
}

async function performJobExtraction() {
    try {
        updateVisualStatus('Capturando detalhes da vaga...');
        
        // 1. Capture Title
        const title = document.querySelector('.job-details-jobs-unified-top-card__job-title')?.innerText?.trim() || 
                      document.querySelector('h1')?.innerText?.trim() || '';
        
        // 2. Capture Company
        const company = document.querySelector('.job-details-jobs-unified-top-card__company-name')?.innerText?.trim() || 
                        document.querySelector('.jobs-unified-top-card__company-name')?.innerText?.trim() || '';
        
        // 3. Capture Location
        const location = document.querySelector('.job-details-jobs-unified-top-card__bullet')?.innerText?.trim() || 
                         document.querySelector('.jobs-unified-top-card__bullet')?.innerText?.trim() || '';
        
        // 4. Capture Description
        const descriptionEl = document.querySelector('.jobs-description__container') || 
                              document.querySelector('#job-details');
        const description = descriptionEl?.innerText?.trim() || '';

        // 5. Smart URL Construction
        let finalUrl = window.location.href;
        const urlParams = new URLSearchParams(window.location.search);
        const jobId = urlParams.get('currentJobId') || window.location.pathname.match(/\/view\/(\d+)/)?.[1];
        
        if (jobId) {
            finalUrl = `https://www.linkedin.com/jobs/view/${jobId}/`;
        } else {
            // Fallback: search for data-job-id on the active card
            const activeCard = document.querySelector('.jobs-search-results-list__list-item--active, [data-job-id]');
            const fallbackId = activeCard?.getAttribute('data-job-id');
            if (fallbackId) {
                finalUrl = `https://www.linkedin.com/jobs/view/${fallbackId}/`;
            }
        }

        const jobData = {
            url: finalUrl,
            title,
            company,
            location,
            description,
            timestamp: new Date().toISOString()
        };

        if (!title || !description) {
            updateVisualStatus('❌ Erro: Não consegui ler os dados da vaga', true);
            return;
        }

        updateVisualStatus('✅ Sincronizando vaga...');
        chrome.runtime.sendMessage({ action: 'importJob', data: jobData });
        
        setTimeout(() => {
            chrome.storage.local.remove(['careerops_import_active', 'careerops_status']);
        }, 3000);
    } catch (e) {
        console.error('CareerOps: Job extraction failed:', e);
        updateVisualStatus('❌ Falha na captura da vaga', true);
    }
}

async function performUniversalExtraction() {
    try {
        updateVisualStatus('Capturando conteúdo universal...');
        const rawText = document.body.innerText;
        const url = window.location.href;

        updateVisualStatus('✅ Enviando para IA processar...');
        chrome.runtime.sendMessage({ 
            action: 'importUniversal', 
            data: { raw_text: rawText, url: url } 
        });

        setTimeout(() => {
            chrome.storage.local.remove(['careerops_import_active', 'careerops_status']);
        }, 3000);
    } catch (e) {
        console.error('CareerOps: Universal extraction failed:', e);
        updateVisualStatus('❌ Falha na captura universal', true);
    }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'ping') {
        sendResponse({status: 'ok'});
    } else if (request.action === 'extractProfile') {
        performFullExtraction();
        sendResponse({status: 'started'});
    } else if (request.action === 'extractJob') {
        performJobExtraction();
        sendResponse({status: 'started'});
    } else if (request.action === 'extractUniversal') {
        performUniversalExtraction();
        sendResponse({status: 'started'});
    }
    return true;
});

// Auto-resume if middle of an import
window.addEventListener('load', async () => {
    const { careerops_import_active } = await chrome.storage.local.get('careerops_import_active');
    if (careerops_import_active) {
        console.log('CareerOps: Resuming smart navigation...');
        setTimeout(performFullExtraction, 2000);
    }
});
