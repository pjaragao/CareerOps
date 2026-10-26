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
// AI calls take 10–60 s, so real requests may run up to 3 min. Reachability is decided separately and fast:
// apiBase() probes each address with a 6 s limit and remembers the one that answers for 5 minutes.
const rawFetch = self.fetch.bind(self);
self.fetch = (url, opts = {}) => rawFetch(url, { signal: AbortSignal.timeout(180000), ...opts }).then((res) => { preferBase(String(url)); return res; });

let cachedBase = null;
let cachedAt = 0;
let probeErrors = [];
async function apiBase(force = false) {
    if (!force && cachedBase && Date.now() - cachedAt < 300000) return cachedBase;
    probeErrors = [];
    for (const base of [...API_BASES]) {
        try {
            const res = await rawFetch(base + '/linkedin-copilot/extension/info', { signal: AbortSignal.timeout(6000) });
            if (res.ok) { cachedBase = base; cachedAt = Date.now(); preferBase(base); return base; }
            probeErrors.push(`${base.split('/')[2]} → HTTP ${res.status}`);
        } catch (e) {
            probeErrors.push(`${base.split('/')[2]} → ${e.name}`);
        }
    }
    cachedBase = null;
    return null;
}

// One request to the reachable backend (no retry on other addresses, so an AI call never runs twice)
async function callBackend(path, method, body) {
    const base = await apiBase();
    if (!base) return { ok: false, status: 0, data: { detail: 'Backend do CareerOps indisponível. Detalhes: ' + probeErrors.join(' | ') } };
    try {
        const res = await fetch(base + path, {
            method: method || 'GET',
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined
        });
        return { ok: res.ok, status: res.status, data: await res.json().catch(() => null) };
    } catch (e) {
        cachedBase = null;   // next call probes again
        return { ok: false, status: 0, data: { detail: e.name === 'TimeoutError' ? 'A IA demorou mais de 3 minutos — tente de novo' : `Falha de rede: ${e.message}` } };
    }
}


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
    const r = await callBackend('/linkedin-copilot/capture', 'POST', payload);
    return r.ok ? r.data : null;
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

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'getProfileCopy') return;
    callBackend('/linkedin-copilot/profile-copy', 'GET').then((r) => sendResponse(r.ok ? { ok: true, data: r.data } : { ok: false }));
    return true; // keep the channel open for the async response
});

// ── Copilot API proxy for linkedin_assist.js (HTTPS pages cannot call the HTTP backend directly) ──

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'copilotApi') return;
    callBackend('/linkedin-copilot' + request.path, request.method, request.body).then(sendResponse);
    return true;
});

// ── Popup: which backend answers, how fast, and the server-side extension version ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'backendStatus') return;
    (async () => {
        const started = Date.now();
        const base = await apiBase(true);
        if (!base) { sendResponse({ ok: false, errors: probeErrors }); return; }
        const ms = Date.now() - started;
        const status = await rawFetch(base + '/linkedin-copilot/status', { signal: AbortSignal.timeout(8000) }).then((r) => r.json()).catch(() => ({}));
        const info = await rawFetch(base + '/linkedin-copilot/extension/info', { signal: AbortSignal.timeout(8000) }).then((r) => r.json()).catch(() => null);
        sendResponse({ ok: true, base, ms, status, serverVersion: info && info.version, appUrl: base.replace(/\/api$/, '') });
    })();
    return true;
});

// ── Generic backend call (path under /api) with the JSON response, for content scripts ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== 'backendApi') return;
    callBackend(request.path, request.method, request.body).then(sendResponse);
    return true;
});
