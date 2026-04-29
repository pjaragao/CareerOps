document.addEventListener('DOMContentLoaded', () => {
    const importBtn = document.getElementById('import-btn');
    const statusText = document.getElementById('status-text');
    const loader = document.getElementById('loader');

    const updateUI = async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const { careerops_import_active, careerops_status } = await chrome.storage.local.get(['careerops_import_active', 'careerops_status']);
        
        // Detect Page Context
        const isLinkedIn = tab?.url?.includes('linkedin.com');
        const isProfile = isLinkedIn && tab?.url?.includes('/in/');
        const isJob = isLinkedIn && tab?.url?.includes('/jobs/');

        if (careerops_import_active) {
            importBtn.disabled = true;
            importBtn.innerText = 'Processando...';
            statusText.innerText = careerops_status || 'Iniciando...';
            loader.style.display = 'block';
        } else {
            importBtn.disabled = false;
            loader.style.display = 'none';

            if (isProfile) {
                importBtn.innerText = 'Importar Perfil LinkedIn';
                importBtn.style.background = '#38bdf8';
            } else if (isJob) {
                importBtn.innerText = 'Importar Vaga LinkedIn';
                importBtn.style.background = '#22c55e';
            } else {
                importBtn.innerText = 'Importar Vaga (Universal)';
                importBtn.style.background = '#a855f7'; // Purple for universal
                importBtn.disabled = false;
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

    importBtn.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const isLinkedIn = tab.url.includes('linkedin.com');
        const isProfile = isLinkedIn && tab.url.includes('/in/');
        const isJob = isLinkedIn && tab.url.includes('/jobs/');

        try {
            await chrome.storage.local.remove(['careerops_import_data', 'careerops_status']);
            await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Iniciando...' });
            
            // Inject content script if needed
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });

            if (isProfile) {
                chrome.tabs.sendMessage(tab.id, { action: 'extractProfile' });
            } else if (isJob) {
                chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });
            } else {
                chrome.tabs.sendMessage(tab.id, { action: 'extractUniversal' });
            }
        } catch (err) {
            // If already injected
            if (isProfile) chrome.tabs.sendMessage(tab.id, { action: 'extractProfile' });
            else if (isJob) chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });
            else chrome.tabs.sendMessage(tab.id, { action: 'extractUniversal' });
        }
    });
});
