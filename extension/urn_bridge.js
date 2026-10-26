// CareerOps — runs in the page's own JS world (manifest "world": "MAIN"). LinkedIn's new feed keeps the post id
// (urn:li:activity:…) only in React's data, which content scripts can't see. linkedin_assist.js marks a post with
// data-careerops-ask and fires "careerops-urn"; this answers synchronously in data-careerops-urn. Read-only.
document.addEventListener('careerops-urn', () => {
    for (const el of document.querySelectorAll('[data-careerops-ask]')) {
        el.removeAttribute('data-careerops-ask');
        // climb React's tree from a button inside the post: the post component (with its urn) is on the way up
        for (const start of [...el.querySelectorAll('button')].slice(0, 3).concat(el)) {
            const urn = urnAbove(start);
            if (urn) { el.setAttribute('data-careerops-urn', urn); break; }
        }
    }
});

function urnAbove(node) {
    const key = Object.keys(node).find((k) => k.startsWith('__reactFiber'));
    let f = key && node[key];
    for (let i = 0; i < 150 && f; i++, f = f.return) {
        const p = f.memoizedProps;
        if (!p || typeof p !== 'object') continue;
        let s;
        try { s = JSON.stringify(p, (k, v) => (v && typeof v === 'object' && (v.$$typeof || v instanceof Node)) ? undefined : v); } catch (e) { continue; }
        const m = s && s.match(/urn:li:(activity|ugcPost|share):\d+/);
        if (m) return m[0];
    }
    return null;
}
