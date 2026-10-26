// CareerOps Background Service Worker
// Backend addresses, tried in order. The HTTPS one (nginx on the homelab, port 5174) works from any machine on
// Tailscale; the HTTP ones only on the server itself. The first one that answers moves to the front.
const API_BASES = [
    'https://mpbflndsk201-wsl.tabby-broadnose.ts.net:5174/api',
    'http://100.109.242.35:8005/api',
    'http://127.0.0.1:8005/api',
    'http://localhost:8005/api'
];
const preferBase = (url) => {
    const i = API_BASES.findIndex((b) => url.startsWith(b));
    if (i > 0) API_BASES.unshift(API_BASES.splice(i, 1)[0]);
};
// Never let an unreachable address hang the worker: every request gives up after 8 s and the next address is tried.
const rawFetch = self.fetch.bind(self);
self.fetch = (url, opts = {}) => rawFetch(url, { signal: AbortSignal.timeout(8000), ...opts }).then((res) => { preferBase(String(url)); return res; });


chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'importProfile') {
        console.log('Background: Received profile data, attempting multi-IP sync...');
        
        const endpoints = API_BASES.map((b) => b + '/profile/import-extension');

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
        const endpoints = API_BASES.map((b) => b + '/jobs/import-extension');

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
        const endpoints = API_BASES.map((b) => b + '/jobs/import-universal');

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
        const endpoints = API_BASES.map((b) => b + '/jobs/mark-applied');

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

// ── LinkedIn Copilot: user-triggered capture (right-click → "Enviar ao CareerOps Copilot") ──
// Sends only what the user chose: the selected text (a post) or the current profile page.
// Nothing is liked, commented, followed or sent on LinkedIn — the backend only drafts.
const COPILOT_ENDPOINTS = API_BASES.map((b) => b + '/linkedin-copilot/capture');

chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'careerops-copilot-capture',
        title: 'Enviar ao CareerOps Copilot',
        contexts: ['selection', 'page', 'link'],
        documentUrlPatterns: ['https://www.linkedin.com/*']
    });
});

function setBadge(text, color) {
    chrome.action.setBadgeBackgroundColor({ color });
    chrome.action.setBadgeText({ text });
    setTimeout(() => chrome.action.setBadgeText({ text: '' }), 4000);
}

async function sendToCopilot(payload) {
    for (const url of COPILOT_ENDPOINTS) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) return await res.json();
            console.warn('Copilot capture rejected by', url, res.status, await res.text());
            return null;
        } catch (e) {
            console.warn('Copilot: failed to reach', url, e);
        }
    }
    return null;
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId !== 'careerops-copilot-capture' || !tab) return;
    let text = (info.selectionText || '').trim();
    let title = tab.title || '';
    if (!text) {
        // No selection: take the visible text of the page (used for profile pages).
        const [{ result }] = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => (document.querySelector('main') || document.body).innerText.slice(0, 6000)
        });
        text = (result || '').trim();
    }
    // A right-click on a post's timestamp/link gives its permalink; otherwise use the page URL.
    const url = info.linkUrl && info.linkUrl.includes('linkedin.com') ? info.linkUrl : tab.url;
    if (text.length < 20) { setBadge('?', '#ff6b6b'); return; }
    const result = await sendToCopilot({ url, text, title: title.replace(/\s*\|\s*LinkedIn\s*$/, '') });
    if (!result) { setBadge('ERR', '#ff6b6b'); return; }
    const skipped = result.item && (result.item.status === 'skipped');
    setBadge(result.kind === 'prospect' ? (skipped ? 'P-' : 'P+') : (skipped ? 'E-' : 'E+'), skipped ? '#888888' : '#00d4aa');
});

// ── Profile filler: field texts (EN + PT) from the CareerOps backend ──
const PROFILE_COPY_ENDPOINTS = API_BASES.map((b) => b + '/linkedin-copilot/profile-copy');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'getProfileCopy') return;
    (async () => {
        for (const url of PROFILE_COPY_ENDPOINTS) {
            try {
                const res = await fetch(url);
                if (res.ok) { sendResponse({ ok: true, data: await res.json() }); return; }
            } catch (e) {
                console.warn('Profile copy: failed to reach', url, e);
            }
        }
        sendResponse({ ok: false });
    })();
    return true; // keep the channel open for the async response
});

// ── Copilot API proxy for linkedin_assist.js (HTTPS pages cannot call the HTTP backend directly) ──

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'copilotApi') return;
    (async () => {
        for (const base of API_BASES.map((b) => b + '/linkedin-copilot')) {
            try {
                const res = await fetch(base + request.path, {
                    method: request.method || 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    body: request.body ? JSON.stringify(request.body) : undefined
                });
                const data = await res.json().catch(() => null);
                sendResponse({ ok: res.ok, status: res.status, data });
                return;
            } catch (e) {
                console.warn('Copilot API: failed to reach', base, e);
            }
        }
        sendResponse({ ok: false, status: 0, data: { detail: 'Backend do CareerOps indisponível — confira se o computador está no Tailscale e se o app abre em https://mpbflndsk201-wsl.tabby-broadnose.ts.net:5174' } });
    })();
    return true;
});

// ── Popup: which backend answers, how fast, and the server-side extension version ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'backendStatus') return;
    (async () => {
        for (const base of [...API_BASES]) {
            const started = Date.now();
            try {
                const res = await fetch(base + '/linkedin-copilot/status');
                if (!res.ok) continue;
                const status = await res.json();
                const info = await fetch(base + '/linkedin-copilot/extension/info').then((r) => (r.ok ? r.json() : null)).catch(() => null);
                sendResponse({ ok: true, base, ms: Date.now() - started, status, serverVersion: info && info.version, appUrl: base.replace(/\/api$/, '') });
                return;
            } catch (e) {
                console.warn('Status: failed', base, e);
            }
        }
        sendResponse({ ok: false });
    })();
    return true;
});

// ── Generic backend call (path under /api) with the JSON response, for content scripts ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'backendApi') return;
    (async () => {
        for (const base of [...API_BASES]) {
            try {
                const res = await fetch(base + request.path, {
                    method: request.method || 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    body: request.body ? JSON.stringify(request.body) : undefined
                });
                sendResponse({ ok: res.ok, status: res.status, data: await res.json().catch(() => null) });
                return;
            } catch (e) {
                console.warn('Backend API: failed', base, e);
            }
        }
        sendResponse({ ok: false, status: 0, data: { detail: 'Backend do CareerOps indisponível' } });
    })();
    return true;
});
