document.addEventListener('DOMContentLoaded', () => {
    const importBtn = document.getElementById('import-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const statusText = document.getElementById('status-text');
    const loader = document.getElementById('loader');

    const updateUI = async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const { careerops_import_active, careerops_status } = await chrome.storage.local.get(['careerops_import_active', 'careerops_status']);
        
        const isLinkedIn = tab?.url?.includes('linkedin.com');

        if (careerops_import_active) {
            importBtn.disabled = true;
            importBtn.innerText = 'Processando...';
            statusText.innerText = careerops_status || 'Iniciando...';
            loader.style.display = 'block';
            cancelBtn.style.display = 'flex';
        } else {
            importBtn.disabled = false;
            cancelBtn.style.display = 'none';
            loader.style.display = 'none';

            if (isLinkedIn) {
                const isProfile = tab.url.includes('/in/');
                const isJob = tab.url.includes('/jobs/');
                const isSaved = tab.url.includes('/my-items/saved-jobs/');
                
                if (isProfile) importBtn.innerText = 'Importar Perfil LinkedIn';
                else if (isJob) importBtn.innerText = 'Importar Vaga LinkedIn';
                else if (isSaved) importBtn.innerText = 'Importar Vagas Salvas';
                else importBtn.innerText = 'Importar Página';
            } else {
                importBtn.innerText = 'Importar (Modo Universal)';
            }

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
        const isLinkedIn = tab.url.includes('linkedin.com');
        const isProfile = isLinkedIn && tab.url.includes('/in/');
        const isJob = isLinkedIn && tab.url.includes('/jobs/');

        await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Iniciando...', careerops_import_data: { step: 'start' } });
        await ensureContentScript(tab);

        if (isProfile) chrome.tabs.sendMessage(tab.id, { action: 'extractProfile' });
        else if (isJob) chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });
        else chrome.tabs.sendMessage(tab.id, { action: 'extractUniversal' });
    });

    cancelBtn.addEventListener('click', async () => {
        await chrome.storage.local.remove(['careerops_import_active', 'careerops_status', 'careerops_import_data']);
        updateUI();
    });
});
