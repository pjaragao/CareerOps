document.addEventListener('DOMContentLoaded', () => {
    const importBtn = document.getElementById('import-btn');
    const importJobBtn = document.getElementById('import-job-btn');
    const bulkBtn = document.getElementById('bulk-jobs-btn');
    const statusText = document.getElementById('status-text');
    const loader = document.getElementById('loader');

    const updateUI = async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const { careerops_import_active, careerops_status } = await chrome.storage.local.get(['careerops_import_active', 'careerops_status']);
        
        const isLinkedIn = tab?.url?.includes('linkedin.com');
        const isSearch = isLinkedIn && tab?.url?.includes('/jobs/search');

        if (careerops_import_active) {
            importBtn.disabled = true;
            importJobBtn.disabled = true;
            bulkBtn.disabled = true;
            statusText.innerText = careerops_status || 'Iniciando...';
            loader.style.display = 'block';
        } else {
            importBtn.disabled = false;
            importJobBtn.disabled = false;
            bulkBtn.disabled = !isSearch;
            loader.style.display = 'none';

            if (careerops_status && (careerops_status.includes('✅') || careerops_status.includes('❌'))) {
                statusText.innerText = careerops_status;
            } else {
                statusText.innerText = 'Pronto para agir';
            }
        }
    };

    setInterval(updateUI, 1000);
    updateUI();

    async function ensureContentScript(tab) {
        try {
            await chrome.tabs.sendMessage(tab.id, { action: 'ping' });
        } catch (e) {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });
            await new Promise(r => setTimeout(r, 500));
        }
    }

    importBtn.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Importando Perfil...' });
        await ensureContentScript(tab);
        chrome.tabs.sendMessage(tab.id, { action: 'extractProfile' });
    });

    importJobBtn.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Importando Vaga...' });
        await ensureContentScript(tab);
        
        const isLinkedIn = tab.url.includes('linkedin.com');
        const isJob = isLinkedIn && (tab.url.includes('/jobs/view/') || tab.url.includes('/jobs/search/'));
        
        if (isJob) {
            chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });
        } else {
            chrome.tabs.sendMessage(tab.id, { action: 'extractUniversal' });
        }
    });

    bulkBtn.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Iniciando captura em massa...' });
        await ensureContentScript(tab);
        chrome.tabs.sendMessage(tab.id, { action: 'bulkCapture' });
    });
});
