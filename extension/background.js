// CareerOps Background Service Worker — Stabilized Version 3.0

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'importProfile') {
        console.log('Background: Received profile data, attempting multi-IP sync...');
        
        const endpoints = [
            'http://127.0.0.1:8005/api/profile/import-extension',
            'http://localhost:8005/api/profile/import-extension',
            'http://100.109.242.35:8005/api/profile/import-extension',
            'http://192.168.1.4:8005/api/profile/import-extension'
        ];

        async function trySync() {
            for (const url of endpoints) {
                try {
                    console.log('Background: Trying endpoint:', url);
                    await fetch(url, {
                        method: 'POST',
                        mode: 'no-cors', // Bypass CORS preflight
                        body: JSON.stringify(request.data)
                    });
                    console.log('Background: Successfully sent data to:', url);
                    return true;
                } catch (e) {
                    console.warn(`Background: Failed to reach ${url}:`, e);
                }
            }
            return false;
        }

        trySync().then(success => {
            // Check if popup is still listening to avoid "Receiving end does not exist"
            chrome.runtime.sendMessage({
                action: 'importResult',
                success: success,
                error: success ? null : 'Nenhum servidor encontrado (verifique Docker/Rede)'
            }, () => {
                if (chrome.runtime.lastError) {
                    console.log('Background: Popup closed before result could be sent.');
                }
            });
        });

        return true; 
    } else if (request.action === 'importJob') {
        console.log('Background: Received job data...');
        const endpoints = [
            'http://127.0.0.1:8005/api/jobs/import-extension',
            'http://localhost:8005/api/jobs/import-extension',
            'http://100.109.242.35:8005/api/jobs/import-extension'
        ];

        async function trySyncJob() {
            for (const url of endpoints) {
                try {
                    await fetch(url, {
                        method: 'POST',
                        mode: 'no-cors',
                        body: JSON.stringify(request.data)
                    });
                    return true;
                } catch (e) {
                    console.warn(`Background: Job sync failed for ${url}`);
                }
            }
            return false;
        }

        trySyncJob().then(success => {
            chrome.runtime.sendMessage({
                action: 'importResult',
                success: success,
                error: success ? null : 'Erro ao sincronizar vaga'
            });
        });
        return true;
    } else if (request.action === 'importUniversal') {
        console.log('Background: Received universal job data...');
        const endpoints = [
            'http://127.0.0.1:8005/api/jobs/import-universal',
            'http://localhost:8005/api/jobs/import-universal',
            'http://100.109.242.35:8005/api/jobs/import-universal'
        ];

        async function trySyncUniversal() {
            for (const url of endpoints) {
                try {
                    await fetch(url, {
                        method: 'POST',
                        mode: 'no-cors',
                        body: JSON.stringify(request.data)
                    });
                    return true;
                } catch (e) {
                    console.warn(`Background: Universal sync failed for ${url}`);
                }
            }
            return false;
        }

        trySyncUniversal().then(success => {
            chrome.runtime.sendMessage({
                action: 'importResult',
                success: success,
                error: success ? null : 'Erro ao processar vaga universal'
            });
        });
        return true;
    } else if (request.action === 'markAsApplied') {
        console.log('Background: Marking job as applied:', request.jobId);
        const endpoints = [
            'http://127.0.0.1:8005/api/jobs/mark-applied',
            'http://localhost:8005/api/jobs/mark-applied',
            'http://100.109.242.35:8005/api/jobs/mark-applied'
        ];

        async function tryMarkApplied() {
            for (const url of endpoints) {
                try {
                    await fetch(url, {
                        method: 'POST',
                        mode: 'no-cors',
                        body: JSON.stringify({ jobId: String(request.jobId) })
                    });
                    return true;
                } catch (e) {
                    console.warn(`Background: Mark applied failed for ${url}`);
                }
            }
            return false;
        }
        tryMarkApplied();
        return true;
    }
});
