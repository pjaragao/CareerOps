// CareerOps — runs in the page's own JS world (manifest "world": "MAIN"). Read-only.
// The post id (urn:li:activity:…) is what makes a saved post's link. LinkedIn keeps it out of the HTML, so this
// bridge offers two sources that content scripts can't reach:
//  1. React's data: linkedin_assist.js marks a post with data-careerops-ask and fires "careerops-urn"; this answers
//     synchronously in data-careerops-urn. (A deeper walk of the props was tried and gave other posts' ids: no guess
//     is better than a wrong link.)
//  2. LinkedIn's own requests: opening a comment box or sending a comment sends the post's id. Each id seen is
//     published as a "careerops-net-urn" event; linkedin_assist.js only takes it right after you clicked Comment or
//     Publicar on a post, and drops it when two different ids arrive.
const POST_URN = /urn(?::|%3A)li(?::|%3A)(activity|ugcPost|share|groupPost)(?::|%3A)[\d-]+/gi;
const normUrn = (u) => decodeURIComponent(u);
// activity is the id of /feed/update/ links; prefer it over the share/ugcPost of the same post
const rank = (u) => (/:activity:/.test(u) ? 0 : /:ugcPost:/.test(u) ? 1 : /:share:/.test(u) ? 2 : 3);
const best = (urns) => [...new Set(urns.map(normUrn))].sort((a, b) => rank(a) - rank(b))[0] || null;

// a post id already given to another post on this page is someone else's (shared page data): never reuse it
const owners = new Map();   // urn -> post element
const ownedByOther = (urn, el) => { const o = owners.get(urn); return !!(o && o !== el && o.isConnected); };

document.addEventListener('careerops-urn', () => {
    for (const el of document.querySelectorAll('[data-careerops-ask]')) {
        el.removeAttribute('data-careerops-ask');
        const urn = nearestUrn(el);
        if (urn) { owners.set(urn, el); el.setAttribute('data-careerops-urn', urn); }
    }
});

// A: the first props on the way up from the post's first buttons that mention a post id (the post component itself)
function nearestUrn(el) {
    for (const start of [...el.querySelectorAll('button')].slice(0, 3).concat(el)) {
        const key = Object.keys(start).find((k) => k.startsWith('__reactFiber'));
        let f = key && start[key];
        for (let i = 0; i < 150 && f; i++, f = f.return) {
            const p = f.memoizedProps;
            if (!p || typeof p !== 'object') continue;
            let s;
            try { s = JSON.stringify(p, (k, v) => (v && typeof v === 'object' && (v.$$typeof || v instanceof Node)) ? undefined : v); } catch (e) { continue; }
            const m = s && s.match(POST_URN);
            if (m) {
                const urn = decodeURIComponent(m[0]);   // the first one, as before: in a repost, a later id is the original's
                if (!ownedByOther(urn, el)) return urn;
                break;   // this start leads to shared data: try the next one
            }
        }
    }
    return null;
}

// ── 2. Requests ────────────────────────────────────────────────────────────────────────────────────────────────
function announce(text) {
    const m = text && text.match(POST_URN);
    if (m) document.dispatchEvent(new CustomEvent('careerops-net-urn', { detail: best(m) }));
}
const bodyText = (b) => (typeof b === 'string' ? b : '');
try {
    const origFetch = window.fetch;
    window.fetch = function (input, init) {
        try { announce(`${(input && input.url) || input} ${bodyText(init && init.body)}`); } catch (e) { /* never break LinkedIn */ }
        return origFetch.apply(this, arguments);
    };
    const open = XMLHttpRequest.prototype.open;
    const send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) { this.__careeropsUrl = url; return open.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function (body) {
        try { announce(`${this.__careeropsUrl || ''} ${bodyText(body)}`); } catch (e) { /* never break LinkedIn */ }
        return send.apply(this, arguments);
    };
} catch (e) { /* page locked these down: React data and the page link still work */ }
