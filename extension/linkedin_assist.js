// CareerOps — LinkedIn assist: AI comment and reply drafts on posts, connect-without-note on profiles, and scoring of
// the people listed on a page. In your own browser everything is drafted and filled in for you and the final click
// (Publicar / Responder / Conectar) is yours; the only things done for you follow from that click: liking the post or
// comment you just answered (a pre-checked option you can turn off) and the invite you asked for with "Conectar".
// On the server (managed mode, section 8) it executes what you approved in the app, and only that: an action exists in
// the backend, was handed to this tab with its nonce, and goes up to the final click unless the backend allows it.
(() => {
    if (window.__careeropsAssist) return;
    window.__careeropsAssist = true;

    const ACCENT = '#6c5ce7';
    const api = (method, path, body) => new Promise((resolve) => {
        try {
            chrome.runtime.sendMessage({ action: 'copilotApi', method, path, body }, (res) => {
                const err = chrome.runtime.lastError;
                resolve(res || { ok: false, data: { detail: err ? `Extensão: ${err.message} — recarregue a extensão e a página` : 'Sem resposta da extensão' } });
            });
        } catch (e) {
            // the extension was reloaded/updated while this tab was open: the page needs a refresh
            resolve({ ok: false, data: { detail: 'A extensão foi atualizada — recarregue esta página (F5)' } });
        }
    });
    const errText = (res) => (res && res.data && (res.data.detail || res.data.error)) || 'Falha ao falar com o CareerOps';
    const clean = (t) => (t || '').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

    // ── Small UI kit (inline styles; LinkedIn CSS is huge and unpredictable) ─────────────────────────
    function button(label, onClick, primary = true) {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = label;
        b.style.cssText = `font:600 12px system-ui,sans-serif;border-radius:14px;padding:4px 10px;cursor:pointer;margin:2px;
            border:1px solid ${primary ? ACCENT : '#c9c9d6'};background:${primary ? ACCENT : '#fff'};color:${primary ? '#fff' : '#333'}`;
        b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); onClick(e); });
        return b;
    }

    function card(title) {
        const box = document.createElement('div');
        box.className = 'careerops-card';
        box.style.cssText = `font:13px/1.45 system-ui,sans-serif;background:#fff;color:#222;border:1px solid ${ACCENT};border-radius:10px;
            padding:10px 12px;margin:8px 12px;box-shadow:0 4px 14px rgba(0,0,0,.12);position:relative;z-index:5`;
        const head = document.createElement('div');
        head.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px';
        head.innerHTML = `<strong style="color:${ACCENT}"></strong>`;
        head.querySelector('strong').textContent = title;
        head.appendChild(button('✕', () => box.remove(), false));
        box.appendChild(head);
        return box;
    }

    function line(box, text, color = '#555') {
        const p = document.createElement('div');
        p.style.cssText = `color:${color};font-size:12px;margin:2px 0`;
        p.textContent = text;
        box.appendChild(p);
        return p;
    }

    function editor(box, text, max) {
        const ta = document.createElement('textarea');
        ta.value = text || '';
        ta.rows = 4;
        ta.style.cssText = 'width:100%;box-sizing:border-box;font:13px system-ui,sans-serif;border:1px solid #ccc;border-radius:8px;padding:6px;margin:6px 0';
        box.appendChild(ta);
        if (max) {
            const c = line(box, '');
            const upd = () => { if (ta.value.length > max) ta.value = ta.value.slice(0, max); c.textContent = `${ta.value.length}/${max}`; };
            ta.addEventListener('input', upd); upd();
        }
        return ta;
    }

    function toast(msg, ok = true) {
        remember(msg);
        const t = document.createElement('div');
        t.textContent = msg;
        t.style.cssText = `position:fixed;right:16px;bottom:72px;z-index:2147483647;background:${ok ? '#00b894' : '#d63031'};color:#fff;
            padding:8px 12px;border-radius:8px;font:13px system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.2)`;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    }

    // Puts text into LinkedIn's editors: contenteditable (comment box) or textarea (invite note)
    function fill(el, text, append = false) {
        writing = true;
        try { fillText(el, text, append); } finally { writing = false; }
    }
    function fillText(el, text, append) {
        el.focus();
        if (el.isContentEditable) {
            if (append && clean(el.innerText)) {
                // reply boxes start with LinkedIn's @mention of the person: keep it and write after it
                const sel = window.getSelection();
                sel.selectAllChildren(el);
                sel.collapseToEnd();
                document.execCommand('insertText', false, ' ' + text);
                return;
            }
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, text);
        } else {
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    // ── Status and pause: what the extension is doing now (bar at the top), and ⏸ Pausar to hold every automatic
    // action (filling, clicking Avançar/Enviar, imports, checks) at its next step until ▶ Continuar. Shared by every
    // tab and the company-site copilot (chrome.storage). A field you typed into is never overwritten, paused or not.
    let paused = false;
    let writing = false;   // our own fill in progress (its input events are not yours)
    const touched = new WeakSet();
    const mine = (e) => { if (e.isTrusted && !writing && e.target instanceof Element) touched.add(e.target); };
    document.addEventListener('input', mine, true);
    document.addEventListener('change', mine, true);
    const typedByYou = (f) => f.els.some((el) => touched.has(el));

    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    async function gate() { while (paused) await sleep(300); }
    const wait = async (ms) => { await sleep(ms); await gate(); };
    async function waitFor(fn, timeout = 4000) {
        const end = Date.now() + timeout;
        while (Date.now() < end) { const v = fn(); if (v) return v; await sleep(150); }
        return null;
    }

    const hud = { el: null, log: [], text: '', hide: null };
    const clock = () => new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    function remember(text) {
        if (!text || hud.log[0] && hud.log[0].text === text) return;
        hud.log.unshift({ at: clock(), text });
        hud.log.length = Math.min(hud.log.length, 12);
        if (hud.el && hud.el.__list.style.display !== 'none') renderLog();
    }
    function renderLog() {
        hud.el.__list.replaceChildren(...hud.log.map((l) => {
            const d = document.createElement('div');
            d.style.cssText = 'padding:2px 0;border-top:1px solid #eee;color:#444';
            d.textContent = `${l.at} · ${l.text}`;
            return d;
        }));
        if (!hud.log.length) hud.el.__list.textContent = 'Nada feito ainda nesta aba.';
    }
    function buildHud() {
        const el = document.createElement('div');
        el.className = 'careerops-card careerops-hud';
        el.style.cssText = `position:fixed;top:56px;left:50%;transform:translateX(-50%);z-index:2147483647;font:12px/1.4 system-ui,sans-serif;
            background:#fff;color:#222;border:1px solid ${ACCENT};border-radius:14px;box-shadow:0 4px 14px rgba(0,0,0,.2);padding:4px 6px 4px 10px;
            width:min(520px,92vw);box-sizing:border-box;display:none`;
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:6px';
        const dot = document.createElement('span');
        dot.style.cssText = 'width:8px;height:8px;border-radius:50%;flex:0 0 auto';
        const text = document.createElement('span');
        text.style.cssText = 'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
        const list = document.createElement('div');
        list.style.cssText = 'display:none;max-height:180px;overflow:auto;margin-top:4px;font-size:11px';
        const more = button('▾', () => { const open = list.style.display === 'none'; list.style.display = open ? 'block' : 'none'; if (open) renderLog(); }, false);
        more.title = 'O que foi feito nesta aba';
        const toggle = button('⏸ Pausar', () => setPaused(!paused));
        toggle.title = 'Segura tudo que a extensão faz sozinha (preencher, avançar, enviar, importar) até você continuar';
        const close = button('✕', () => { el.style.display = 'none'; }, false);
        close.title = 'Esconder (volta na próxima ação)';
        row.append(dot, text, more, toggle, close);
        el.append(row, list);
        Object.assign(el, { __dot: dot, __text: text, __list: list, __toggle: toggle });
        document.documentElement.appendChild(el);
        return el;
    }
    function renderHud() {
        if (!hud.el) hud.el = buildHud();
        const el = hud.el;
        el.__dot.style.background = paused ? '#fdcb6e' : ACCENT;
        el.__text.textContent = paused ? `⏸ Pausado — nada é preenchido nem clicado até você continuar${hud.text ? ` · parado em: ${hud.text}` : ''}` : (hud.text || 'Pronto');
        el.__text.title = el.__text.textContent;
        el.__toggle.textContent = paused ? '▶ Continuar' : '⏸ Pausar';
        el.__toggle.style.background = paused ? '#00b894' : ACCENT;
        el.__toggle.style.borderColor = paused ? '#00b894' : ACCENT;
    }
    // what is happening now: shown in the bar (hidden again after a while, unless paused or an Auto Apply is running)
    function activity(text) {
        if (!text) return;
        hud.text = text;
        remember(text);
        renderHud();
        hud.el.style.display = 'block';
        clearTimeout(hud.hide);
        hud.hide = setTimeout(() => { if (!paused && !(autopilot && !autopilot.done)) hud.el.style.display = 'none'; }, 15000);
    }
    function setPaused(v) {
        try { chrome.storage.local.set({ careeropsPaused: !!v }); } catch (e) { /* extension reloaded */ }
        applyPaused(v);
    }
    function applyPaused(v) {
        const was = paused;
        paused = !!v;
        if (was === paused && hud.el) return;
        if (paused || hud.el) { renderHud(); if (paused) hud.el.style.display = 'block'; }
        if (was !== paused) remember(paused ? 'Pausado por você' : 'Continuando');
        if (was && !paused) { activity('Continuando…'); setTimeout(refresh, 0); }   // steps that appeared meanwhile
    }
    try {
        chrome.storage.local.get('careeropsPaused', (v) => applyPaused(v && v.careeropsPaused));
        chrome.storage.onChanged.addListener((c, area) => { if (area === 'local' && c.careeropsPaused) applyPaused(c.careeropsPaused.newValue); });
    } catch (e) { /* extension reloaded */ }
    const byText = (root, selector, words) => [...root.querySelectorAll(selector)]
        .find((el) => words.some((w) => (el.innerText || el.getAttribute('aria-label') || '').toLowerCase().includes(w)));

    // ── 1. Posts: "✨ Comentário IA" ──────────────────────────────────────────────────────────────────
    const POST_SELECTOR = 'div[data-urn^="urn:li:activity"], div[data-id^="urn:li:activity"], article[data-urn^="urn:li:activity"]';
    // LinkedIn's feed markup changes often; every post, however, has an action bar with Repost/Compartilhar.
    const REPOST = /^(repost|republicar|compartilhar|share)$/i;
    const label = (el) => clean(el.innerText || el.getAttribute('aria-label') || '').split('\n')[0];
    const CONTROL_MENU = /control menu for post|menu de controle|op[cç][oõ]es da publica[cç][aã]o|more actions for post/i;
    const isRepostButton = (b) => REPOST.test(label(b)) || /^(repost|republicar|compartilhar)\b/i.test(b.getAttribute('aria-label') || '')
        || CONTROL_MENU.test(b.getAttribute('aria-label') || '');

    const anchorKind = (b) => (CONTROL_MENU.test(b.getAttribute('aria-label') || '') ? 'menu' : 'repost');

    function findPosts() {
        const posts = new Set(document.querySelectorAll(POST_SELECTOR));
        for (const btn of document.querySelectorAll('main button, main [role="button"]')) {
            if (btn.closest('.careerops-card, .careerops-bar, .careerops-actions') || !isRepostButton(btn)) continue;
            // climb until the parent holds more than one post (i.e. the feed list): the current element is the post
            const kind = anchorKind(btn);
            let el = btn;
            while (el.parentElement && el.parentElement.tagName !== 'MAIN' && el.parentElement !== document.body) {
                // the list item is the whole card; above it, a post alone on the page takes in the page's footer
                if (el.getAttribute('role') === 'listitem' && (el.innerText || '').length > 40) break;
                const parent = el.parentElement;
                const count = [...parent.querySelectorAll('button, [role="button"]')].filter((b) => isRepostButton(b) && anchorKind(b) === kind).length;
                if (count > 1) break;
                el = parent;
            }
            if (el !== btn && (el.innerText || '').length > 40) posts.add(el);
        }
        return [...posts].filter((p) => ![...posts].some((o) => o !== p && o.contains(p)));
    }

    // Post author in the new feed: the first named /in/ or /company/ link that isn't social context ("X likes this")
    const { SOCIAL, cardText } = globalThis.careeropsPostText;
    const META = /^(•.*|\d+\s*(s|m|min|h|d|w|sem|mo|yrs?|y|a)\b.*|\+?\s*follow|following|seguir|seguindo|promoted|promovido|verified|premium|feed post|publicação no feed|.*•\s*(1st|2nd|3rd\+?|1º|2º|3º\+?))$/i;
    function actorOf(post) {
        for (const a of post.querySelectorAll('a[href*="/in/"], a[href*="/company/"]')) {
            if (a.closest('.careerops-card, .careerops-bar, .careerops-actions, .comments-comments-list, [class*="comments-list"]')) continue;
            const name = clean(a.innerText).split('\n')[0].replace(/\s*•.*$/, '').trim();
            if (!name || name.length > 80 || /^(view|ver)\b/i.test(name)) continue;
            const ctx = clean((a.parentElement && a.parentElement.innerText) || '');
            if (ctx.length < 160 && SOCIAL.test(ctx.replace(name, ''))) continue;
            const lines = clean(post.innerText).split('\n').map((l) => l.trim()).filter(Boolean);
            const i = lines.indexOf(name);
            const headline = i < 0 ? null : lines.slice(i + 1, i + 5).find((l) => l !== name && !META.test(l) && l.length > 2) || null;
            return { name, headline };
        }
        return null;
    }

    // Post id from React's data, through urn_bridge.js (page world)
    function reactUrn(post) {
        post.setAttribute('data-careerops-ask', '1');
        document.dispatchEvent(new CustomEvent('careerops-urn'));
        post.removeAttribute('data-careerops-ask');
        return post.getAttribute('data-careerops-urn');
    }

    // ── The post's link: several independent sources, the first that answers wins ──────────────────────────────
    // 1. the HTML (data-urn / data-id on the card or its wrappers, links to /feed/update/… or /posts/…-activity-…)
    // 2. React's data (urn_bridge.js)
    // 3. LinkedIn's own request when you open the comment box or send a comment on that post (urn_bridge.js)
    // 4. the page address, when the page shows one post (/feed/update/…, /posts/…)
    // and when all fail, the backend keeps the post and the extension fills the link the next time the post shows up.
    const URN = /urn:li:(activity|ugcPost|share|groupPost):[\d-]+/;
    const urnFromValue = (v) => {
        const m = decodeURIComponent(v || '').match(URN);
        if (m) return m[0];
        const a = (v || '').match(/activity[-:](\d{16,})/);
        return a ? `urn:li:activity:${a[1]}` : null;
    };
    function htmlUrn(post) {
        const els = [post, ...post.querySelectorAll('[data-urn], [data-id], a[href*="urn:li:"], a[href*="/feed/update/"], a[href*="/posts/"]')];
        for (let a = post.parentElement, k = 0; a && k < 6; a = a.parentElement, k++) els.push(a);
        for (const el of els) {
            if (el !== post && el.closest && el.closest('.careerops-card')) continue;
            for (const attr of ['data-urn', 'data-id', 'href']) {
                const urn = urnFromValue(el.getAttribute && el.getAttribute(attr));
                if (urn) return urn;
            }
        }
        return null;
    }
    // 3: the post you clicked Comment / Publicar on in the last seconds gets the id LinkedIn sends right after;
    // two different ids in that window are ambiguous and both are dropped
    let armed = null;   // { post, at }
    const ARM = /^(comment|comentar|post|publicar|reply|responder)$/i;
    document.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('button, [role="button"]');
        if (!b || own(b)) return;
        if (!(ARM.test(label(b)) || ARM.test(b.getAttribute('aria-label') || '') || b.className.includes('comments-comment-box__submit-button'))) return;
        const post = findPosts().find((p) => p.contains(b));
        if (post) armed = { post, at: Date.now() };
    }, true);
    document.addEventListener('careerops-net-urn', (e) => {
        if (!armed || Date.now() - armed.at > 4000 || !e.detail) return;
        const post = armed.post;
        if (!post.dataset.careeropsNetUrn) post.dataset.careeropsNetUrn = e.detail;
        else if (post.dataset.careeropsNetUrn !== e.detail && !post.dataset.careeropsNetUrn.startsWith('?')) post.dataset.careeropsNetUrn = '?';
    });
    function pageUrn() {
        if (!/^\/(feed\/update|posts)\//.test(location.pathname) || findPosts().length !== 1) return null;
        return urnFromValue(location.pathname);
    }
    function postUrn(post) {
        const net = post.dataset.careeropsNetUrn;
        return htmlUrn(post) || reactUrn(post) || (net && net !== '?' ? net : null) || pageUrn();
    }
    const postUrl = (urn) => (urn ? `https://www.linkedin.com/feed/update/${urn}/` : null);

    function postInfo(post) {
        const textEl = post.querySelector('.update-components-text, .feed-shared-inline-show-more-text, .feed-shared-update-v2__description, [data-test-id="main-feed-activity-card__commentary"]');
        const authorEl = post.querySelector('.update-components-actor__title span[aria-hidden="true"], .update-components-actor__name, .feed-shared-actor__name');
        const headlineEl = post.querySelector('.update-components-actor__description span[aria-hidden="true"], .update-components-actor__description');
        let text;
        let comments = '';
        const listEl = post.querySelector('.comments-comments-list, .comments-comment-list, [class*="comments-list"]');
        if (listEl) comments = listEl.innerText;
        if (textEl) {
            text = textEl.innerText;
        } else {
            // read the post without our own bar/cards, cut before reactions/comments, drop the author header
            const copy = post.cloneNode(true);
            copy.querySelectorAll(`.careerops-bar, .careerops-actions, .careerops-card, .careerops-badge, ${EDITOR}`).forEach((el) => el.remove());
            document.body.appendChild(copy);
            copy.style.cssText = 'position:absolute;left:-99999px;top:0;width:600px';
            const card = cardText(copy.innerText || '', actorOf(post));
            copy.remove();
            if (!comments) comments = card.tail;
            text = card.body;
        }
        const who = authorEl ? { name: clean(authorEl.innerText).split('\n')[0], headline: headlineEl ? clean(headlineEl.innerText) : null } : actorOf(post);
        return {
            post_url: postUrl(postUrn(post)),
            post_text: clean(text).slice(0, 6000),
            author_name: who ? who.name : null,
            author_headline: who && who.headline ? who.headline.slice(0, 300) : null,
            other_comments: clean(comments).slice(0, 3000) || null,
        };
    }

    const EDITOR = '.ql-editor[contenteditable="true"], div[role="textbox"][contenteditable="true"]';
    const visibleEditor = (post) => [...post.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !el.closest('.careerops-card'));

    async function openCommentBox(post) {
        const open = visibleEditor(post);
        if (open) return open;
        const btn = [...post.querySelectorAll('button')].find((b) => !own(b)
            && ['comentar', 'comment'].includes((b.getAttribute('aria-label') || b.innerText || '').trim().toLowerCase()));
        if (btn) btn.click();
        return waitFor(() => visibleEditor(post));
    }

    // Draft card under the anchor (the post's action bar). opts.instruction = your request for this comment;
    // opts.regenerate = a new draft even if this post already has one.
    async function draftComment(post, anchor, opts = {}) {
        post.querySelectorAll('.careerops-card').forEach((c) => c.remove());
        const box = card('CareerOps · comentário');
        anchor.insertAdjacentElement('afterend', box);
        const status = line(box, opts.instruction ? `Gerando com o seu pedido: “${opts.instruction}”…` : 'Analisando o post…');
        const info = postInfo(post);
        if (info.post_text.length < 20) { status.textContent = 'Não encontrei o texto deste post.'; return; }
        const res = await api('POST', '/engagement', { ...info, instruction: opts.instruction || null, regenerate: !!opts.regenerate, angle: opts.angle || null });
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const item = res.data;
        status.textContent = `Relevância ${item.relevance ?? '?'} — ${item.reason || ''}`;
        const again = (instruction, angle = opts.angle) => draftComment(post, anchor, { instruction, angle, regenerate: true });
        if (item.status === 'skipped' || !item.comment_draft) {
            line(box, 'A IA sugere não comentar este post (pouco ligado aos seus mercados).', '#999');
            box.appendChild(button('Gerar mesmo assim', () => again('Write the comment anyway.'), false));
            return;
        }
        const ta = editor(box, item.comment_draft);
        const actions = document.createElement('div');
        actions.appendChild(button('Inserir no comentário', async () => {
            const ed = await openCommentBox(post);
            if (!ed) { toast('Não achei a caixa de comentário — use Copiar', false); return; }
            fill(ed, ta.value);
            toast('Inserido. Revise e clique em Publicar.');
            watchCommentSubmit(post, item.id, ta);
        }));
        actions.appendChild(button('Copiar', () => navigator.clipboard.writeText(ta.value).then(() => toast('Copiado')), false));
        actions.appendChild(button('🔄 Gerar outro', () => again(opts.instruction), false));
        actions.appendChild(button('Já comentei', () => api('PATCH', `/engagement/${item.id}`, { status: 'done', comment_draft: ta.value }).then(() => { toast('Registrado'); box.remove(); saveCommented(post, ta.value); }), false));
        actions.appendChild(button('Pular', () => api('PATCH', `/engagement/${item.id}`, { status: 'skipped' }).then(() => box.remove()), false));
        box.appendChild(actions);
        angleRow(box, opts.angle || 'tecnico', (a) => again(opts.instruction, a));
        likeToggle(box, 'Curtir o post ao comentar');
        promptRow(box, 'Refazer com um pedido (ex.: mais curto, discorde com educação)', again);
    }

    // Kind of comment: one chip per angle (backend COMMENT_ANGLES); a click writes a new draft with that angle
    const COMMENT_ANGLES = [
        ['tecnico', 'Técnico'], ['elogio', 'Elogio + problema'], ['pergunta', 'Pergunta'],
        ['contraponto', 'Contraponto'], ['complemento', 'Complemento'], ['experiencia', 'Minha experiência'],
    ];
    function angleRow(box, current, onPick) {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;font:12px system-ui,sans-serif';
        for (const [key, label] of COMMENT_ANGLES) {
            const b = button(label, () => onPick(key), key === current);
            b.title = 'Gerar outro comentário neste estilo';
            row.appendChild(b);
        }
        box.appendChild(row);
    }

    // Text field + "Gerar": your own request for the comment
    function promptRow(box, placeholder, onGo) {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;gap:4px;align-items:center;margin-top:6px';
        const inp = document.createElement('input');
        inp.placeholder = placeholder;
        inp.style.cssText = 'flex:1;min-width:0;font:13px system-ui,sans-serif;border:1px solid #ccc;border-radius:8px;padding:6px';
        const go = () => { const v = inp.value.trim(); if (v) onGo(v); };
        inp.addEventListener('keydown', (e) => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); go(); } });
        row.appendChild(inp);
        row.appendChild(button('✨ Gerar', go));
        box.appendChild(row);
        return inp;
    }

    function promptCard(post, anchor) {
        post.querySelectorAll('.careerops-card').forEach((c) => c.remove());
        const box = card('CareerOps · comentário com pedido');
        anchor.insertAdjacentElement('afterend', box);
        line(box, 'Diga o que quer no comentário: ângulo, tom, um ponto a citar, concordar ou discordar…');
        promptRow(box, 'Ex.: elogie a solução e diga que problema de escala ela resolve', (v) => draftComment(post, anchor, { instruction: v, regenerate: true })).focus();
    }

    // When you click LinkedIn's own submit button in this post, the queue item is marked as done
    function watchCommentSubmit(post, id, ta) {
        if (post.__careeropsWatch) return;
        post.__careeropsWatch = true;
        post.addEventListener('click', (e) => {
            const b = e.target.closest('button');
            if (!b) return;
            const label = (b.innerText || b.getAttribute('aria-label') || '').toLowerCase();
            if (b.className.includes('comments-comment-box__submit-button') || ['publicar', 'post', 'comentar', 'comment'].includes(label.trim())) {
                api('PATCH', `/engagement/${id}`, { status: 'done', comment_draft: ta.value });
                post.querySelectorAll('.careerops-card').forEach((c) => c.remove());
                toast('Comentário registrado no CareerOps');
            }
        }, true);
    }

    // ── Posts you comment on become saved topics (📌) automatically, with your comment as your angle ──
    const SUBMIT = /^(post|publicar|comment|comentar|reply|responder)$/i;

    // People around a saved post (its author and the commenters in view) are scored and queued as prospects:
    // whoever engages with a topic you follow is a natural person to invite
    const COMMENTS = '.comments-comments-list, .comments-comment-list, [class*="comments-list"], article[class*="comments-comment"]';
    const MORE = /^(load more comments|ver mais coment[aá]rios|carregar mais coment[aá]rios|show more comments|see previous comments|ver coment[aá]rios anteriores)/i;

    // Commenters only exist in the page once the comments are open: open them and load a few more batches
    async function openComments(post) {
        if (!post.querySelector(COMMENTS)) {
            const btn = [...post.querySelectorAll('button')].find((b) => !own(b) && COMMENT_BTN.test((b.getAttribute('aria-label') || b.innerText || '').trim()));
            if (btn) btn.click();
            await waitFor(() => post.querySelector(COMMENTS));
        }
        for (let k = 0; k < 3; k++) {
            const more = [...post.querySelectorAll('button')].find((b) => !own(b) && MORE.test(label(b)));
            if (!more) break;
            more.click();
            await new Promise((r) => setTimeout(r, 1200));
        }
    }

    // Badges LinkedIn glues to names in the accessible text ("Ana Lima Verified Profile 3rd+", "Paulo … You")
    const BADGE = /\s*(•|verified profile|premium profile|perfil verificado|perfil premium|author|autor|you|voc[eê]|1st|2nd|3rd\+?|1º|2º|3º\+?|\(he\/him\)|\(she\/her\)|\(ele\/dele\)|\(ela\/dela\))\s*$/i;
    function personName(raw) {
        let n = clean(raw).split('\n')[0].replace(/\s*•.*$/, '').trim();
        for (let k = 0; k < 6 && BADGE.test(n); k++) n = n.replace(BADGE, '').trim();
        return n;
    }
    // "Ana Lima • 1st" / "1º": already a connection, never a prospect to invite
    const FIRST_DEGREE = /(^|[\s•·])(1st|1º)(\s|$)/i;
    const isFirstDegree = (text) => clean(text).split('\n').slice(0, 4).some((l) => FIRST_DEGREE.test(l));
    // Tells the backend these people are connections: matching prospects move to "aceitou" (no AI call)
    function markConnected(people) {
        if (people.length) api('POST', '/prospects/check', { connections: people, sent: [], conversations: [] });
    }
    const isSelf = (raw) => /(^|\s)(you|voc[eê])\s*$/i.test(clean(raw).split('\n')[0]);
    const NOT_HEADLINE = /^(like|gostei|reply|responder|curtir|author|autor|you|voc[eê]|verified profile|premium profile|perfil verificado|edited|editado|see more|ver mais|…|\d+\s*(likes?|reactions?|curtidas|rea[cç][oõ]es|replies|respostas)?)$/i;

    async function harvestPeople(post, info) {
        await openComments(post);
        const seen = new Map(), connected = new Map();
        post.querySelectorAll('a[href*="/in/"]').forEach((a) => {
            if (own(a)) return;
            const m = a.href.match(/https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
            if (!m || m[1] === 'me' || (seen.has(m[0]) && (!seen.get(m[0]) || seen.get(m[0]).headline))) return;
            const raw = a.innerText || a.getAttribute('aria-label') || '';
            const name = personName(raw);
            if (!name || name.length > 80 || /^(view|ver)\b/i.test(name)) return;
            if (isSelf(raw)) { seen.set(m[0], null); return; }
            if (isFirstDegree(raw) || isFirstDegree((a.parentElement || a).innerText || '')) { connected.set(m[0], { profile_url: m[0], name }); seen.set(m[0], null); return; }
            // LinkedIn's classes are obfuscated: climb from the link to the largest block that is still only about this
            // person (no link to anyone else) and take the first line after the name that reads like a headline
            let headline = null;
            for (let el = a.parentElement, k = 0; el && el !== post && k < 10 && !headline; el = el.parentElement, k++) {
                const others = [...el.querySelectorAll('a[href*="/in/"]')].some((x) => {
                    const id = (x.href.match(/\/in\/([^/?#]+)/) || [])[1];
                    return id && id !== m[1];
                });
                if (others) break;
                const lines = clean(el.innerText).split('\n').map((l) => l.trim()).filter(Boolean);
                const i = lines.findIndex((l) => personName(l) === name);
                if (i < 0) continue;
                headline = lines.slice(i + 1, i + 6).find((l) => personName(l) !== name && !META.test(l) && !NOT_HEADLINE.test(l) && l.length > 3) || null;
            }
            if (!headline && info.author_name && personName(info.author_name) === name) headline = info.author_headline;
            seen.set(m[0], { profile_url: m[0], name, headline: headline ? headline.slice(0, 300) : null });
        });
        markConnected([...connected.values()]);
        const found = [...seen.values()].filter(Boolean);
        const people = found.filter((p) => p.headline).slice(0, 25);
        if (!people.length) {
            if (found.length) toast(`Achei ${found.length} pessoa(s) neste post, mas não consegui ler o cargo delas`, false);
            return;
        }
        api('POST', '/prospects/batch', { people, topic: info.post_text.slice(0, 500) }).then((res) => {
            if (!res.ok) return;
            const good = res.data.items.filter((i) => i.status !== 'skipped').length;
            if (good) toast(`🤝 ${good} pessoa${good > 1 ? 's' : ''} deste post para convidar — veja em Prospecção`);
        });
    }

    async function saveCommented(post, comment) {
        if (post.__careeropsSaved) return;
        post.__careeropsSaved = true;
        let info = postInfo(post);
        if (info.post_text.length < 20) { post.__careeropsSaved = false; return; }
        // no id yet: the request that sends your comment carries it — give it a moment
        if (!info.post_url) {
            const url = await waitFor(() => postUrl(postUrn(post)), 2500);
            if (url) info = { ...info, post_url: url };
        }
        const note = comment ? `Você comentou: ${comment}`.slice(0, 2000) : null;
        api('POST', '/inspirations', { ...info, note }).then((res) => {
            if (res.ok) { toast('📌 Tema salvo — você comentou neste post'); harvestPeople(post, info); } else post.__careeropsSaved = false;
        });
    }

    // LinkedIn's own comment submit (with or without our draft): read the comment before LinkedIn clears the box
    document.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('button');
        if (!b || own(b) || !(b.className.includes('comments-comment-box__submit-button') || SUBMIT.test(label(b)))) return;
        if (isReplyAction(b)) return;   // a comment's "Responder" only opens the reply box
        let ed = null;
        let box = b.closest('form') || b.parentElement;
        for (let k = 0; k < 4 && box && !ed; k++, box = box.parentElement) ed = [...box.querySelectorAll(EDITOR)].find((el) => !own(el));
        const text = ed ? clean(ed.innerText) : '';
        if (text.length < 2) return;
        const post = findPosts().find((p) => p.contains(b));
        if (!post) return;
        // a reply goes under the comment whose "Responder" you clicked last; anything else is a comment on the post
        const target = lastReply && lastReply.post === post && lastReply.block.isConnected && ed
            && (threadOf(lastReply.block, post).contains(ed) || lastReply.block.parentElement.contains(ed)) ? lastReply.block : null;
        const draft = target && lastReply.draft;
        lastReply = null;
        if (likeOnComment) setTimeout(() => likeAfterSend(post, target), 700);
        if (!target) saveCommented(post, text);
        // a reply you sent joins your line of thought, with your request and the AI's reading when it came from a draft
        else api('POST', '/voice', {
            kind: 'reply', text, context: textOf(target).slice(0, 2000), post_url: postInfo(post).post_url || null,
            instruction: (draft && draft.instruction) || null, topic: (draft && draft.topic) || null, stance: (draft && draft.stance) || null,
        });
    }, true);

    // ── 👍 Like what you answer (pre-checked; remembered per browser) ────────────────────────────────────
    let likeOnComment = true;
    try { chrome.storage.local.get('likeOnComment', (v) => { if (v && v.likeOnComment === false) likeOnComment = false; }); } catch (e) { /* extension reloaded */ }
    function likeToggle(box, text) {
        const row = document.createElement('label');
        row.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:12px;color:#444;margin:4px 0;cursor:pointer';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = likeOnComment;
        cb.addEventListener('change', () => { likeOnComment = cb.checked; chrome.storage.local.set({ likeOnComment: cb.checked }); });
        row.append(cb, document.createTextNode(`👍 ${text}`));
        box.appendChild(row);
        return cb;
    }
    const LIKE_LABEL = /^(like|gostei|curtir)$/i;
    const LIKE_ARIA = /^(react like|reagir com gostei|like |gostei |curtir )/i;
    const LIKED = /unlike|remover|desfazer|liked|curtido/i;
    // Current markup (2026-10): no "Like" text; the button (post) or its icon (comment, a div role=button) carries
    // "Reaction button state: no reaction" before you react and "Reaction button state: Like" (or another reaction) after
    const STATE = /(reaction button state|estado do bot[aã]o de rea[cç][aã]o|bot[aã]o de rea[cç][aã]o)\s*:\s*(.*)$/i;
    const NO_REACTION = /^(no reaction|sem rea[cç][aã]o|nenhuma rea[cç][aã]o|none)\b/i;
    const reactionState = (b) => {
        for (const el of [b, ...b.querySelectorAll('[aria-label]')]) {
            const m = (el.getAttribute('aria-label') || '').match(STATE);
            if (m) return m[2].trim();
        }
        return null;
    };
    const isLike = (b) => !own(b) && (reactionState(b) !== null || LIKE_LABEL.test(label(b)) || LIKE_ARIA.test(b.getAttribute('aria-label') || ''));
    function pressLike(btn) {
        if (!btn) return false;
        const state = reactionState(btn);
        if (state !== null && !NO_REACTION.test(state)) return false;   // already reacted
        if (btn.getAttribute('aria-pressed') === 'true' || LIKED.test(btn.getAttribute('aria-label') || '')) return false;
        btn.click();
        return true;
    }
    function likeAfterSend(post, commentBlock) {
        let btn = null;
        if (commentBlock) {
            btn = [...commentBlock.querySelectorAll('button, [role="button"]')].find(isLike);
        } else {
            const bar = actionBar(post);
            btn = bar && [...bar.querySelectorAll('button, [role="button"]')].find(isLike);
        }
        if (pressLike(btn)) toast(commentBlock ? '👍 Comentário curtido' : '👍 Post curtido');
    }

    // ── ↩ Replies: "✨ Responder" on every comment; the AI continues the discussion or thanks and closes it ──
    const REPLY = /^(reply|responder)$/i;
    // the comment's own "Responder" (opens the reply box), not the send button of a reply box
    const isReplyAction = (b) => !own(b) && REPLY.test(label(b)) && !b.closest('form')
        && !(b.parentElement && b.parentElement.parentElement && b.parentElement.parentElement.querySelector(EDITOR));
    let lastReply = null;   // { post, block, draft? }: the comment you are answering (draft = the AI reply you inserted)
    document.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('button, [role="button"]');
        if (!b || !isReplyAction(b)) return;
        const post = findPosts().find((p) => p.contains(b));
        if (post) lastReply = { post, block: commentBlock(b, post) };
    }, true);

    // The comment around a "Responder" button: the largest block that holds only this one reply action
    function commentBlock(replyBtn, post) {
        let el = replyBtn;
        while (el.parentElement && el.parentElement !== post
            && [...el.parentElement.querySelectorAll('button, [role="button"]')].filter(isReplyAction).length === 1) el = el.parentElement;
        return el;
    }
    // The thread: the smallest block above the comment that also holds other comments (parent + replies)
    function threadOf(block, post) {
        let el = block.parentElement;
        while (el && el !== post && [...el.querySelectorAll('button, [role="button"]')].filter(isReplyAction).length < 2) el = el.parentElement;
        return el && el !== post ? el : block;
    }
    const textOf = (el) => {
        const copy = el.cloneNode(true);
        copy.querySelectorAll('.careerops-card, .careerops-reply, button, ' + EDITOR).forEach((x) => x.remove());
        return clean(copy.innerText);
    };
    function authorOf(block) {
        const a = [...block.querySelectorAll('a[href*="/in/"]')].find((x) => personName(x.innerText || x.getAttribute('aria-label') || ''));
        return a ? { name: personName(a.innerText || a.getAttribute('aria-label') || ''), self: isSelf(a.innerText || '') } : { name: null, self: false };
    }

    async function draftReply(replyBtn, post, opts = {}) {
        const block = commentBlock(replyBtn, post);
        const thread = threadOf(block, post);
        block.parentElement.querySelectorAll(':scope > .careerops-card').forEach((c) => c.remove());
        const box = card('CareerOps · resposta');
        block.insertAdjacentElement('afterend', box);
        const status = line(box, opts.instruction ? `Gerando com o seu pedido: “${opts.instruction}”…` : 'Lendo a conversa…');
        const who = authorOf(block);
        // your comment in this thread (the one being answered, usually)
        const mineBtn = [...thread.querySelectorAll('button, [role="button"]')].filter(isReplyAction)
            .map((b) => commentBlock(b, post)).find((bl) => bl !== block && authorOf(bl).self);
        const me = mineBtn ? authorOf(mineBtn).name : null;
        const info = postInfo(post);
        const res = await api('POST', '/engagement/reply', {
            post_text: info.post_text || '(post text not found)', author_name: info.author_name, post_url: undefined,
            target_text: textOf(block).slice(0, 2000), target_author: who.name, thread: textOf(thread).slice(0, 4000),
            my_comment: mineBtn ? textOf(mineBtn).slice(0, 2000) : null, my_name: me,
            instruction: opts.instruction || null, previous_draft: opts.previous || null,
        });
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const r = res.data;
        status.textContent = r.kind === 'close' ? '🙏 Agradecer e encerrar' : '💬 Continuar a conversa';
        status.style.fontWeight = '600';
        if (r.reason) line(box, r.reason, '#777');
        const ta = editor(box, r.reply);
        const like = likeToggle(box, 'Curtir o comentário ao responder');
        const again = (instruction) => draftReply(replyBtn, post, { instruction, previous: ta.value });
        const actions = document.createElement('div');
        actions.appendChild(button('Inserir na resposta', async () => {
            replyBtn.click();
            lastReply = { post, block, draft: { instruction: opts.instruction, topic: r.topic, stance: r.stance } };
            const ed = await waitFor(() => [...thread.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !own(el))
                || [...block.parentElement.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !own(el)));
            if (!ed) { toast('Não achei a caixa de resposta — use Copiar', false); return; }
            const tagged = await ensureMention(ed, who.name);
            fill(ed, tagged ? dropLeadingName(ta.value, who.name) : ta.value, true);
            likeOnComment = like.checked;
            toast('Inserido. Revise e clique em Responder.');
            box.remove();
        }));
        actions.appendChild(button('Copiar', () => navigator.clipboard.writeText(ta.value).then(() => toast('Copiado')), false));
        actions.appendChild(button(r.kind === 'close' ? '💬 Continuar em vez disso' : '🙏 Só agradecer', () =>
            again(r.kind === 'close' ? 'Continue the discussion: answer their point with substance.' : 'Just thank them warmly and close the exchange.'), false));
        actions.appendChild(button('🔄 Outra', () => again(opts.instruction), false));
        box.appendChild(actions);
        promptRow(box, 'Refazer com um pedido (ex.: discorde com educação, cite um exemplo)', again);
    }

    // ── @mention of the person you answer: LinkedIn usually puts it in the reply box by itself (sometimes a moment
    // later); when it doesn't, type "@Name" and pick the person in LinkedIn's suggestion list, like you would
    const MENTION = 'a, .ql-mention, [data-entity-urn], [data-mention], [class*="mention"]';
    const OPTION = '[role="listbox"] [role="option"], [class*="typeahead"] [role="option"], [class*="typeahead"] li';
    const plain = (t) => (t || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    const hasMention = (ed, name) => !!ed.querySelector(MENTION) || (name && plain(ed.innerText).includes(plain(name)));
    async function ensureMention(ed, name) {
        if (!name) return false;
        if (await waitFor(() => hasMention(ed, name), 1500)) return true;
        const words = name.split(/\s+/).filter(Boolean);
        const typed = '@' + words.slice(0, 2).join(' ');
        writing = true;
        try {
            ed.focus();
            const sel = window.getSelection();
            sel.selectAllChildren(ed);
            sel.collapseToStart();
            document.execCommand('insertText', false, typed);
        } finally { writing = false; }
        const [first, last] = [plain(words[0]), plain(words[words.length - 1])];
        const option = await waitFor(() => [...document.querySelectorAll(OPTION)]
            .find((o) => o.offsetParent !== null && plain(o.innerText).includes(first) && plain(o.innerText).includes(last)), 3500);
        if (option) {
            option.click();
            if (await waitFor(() => ed.querySelector(MENTION), 1500)) return true;
        }
        // no suggestion list: take the typed "@Name" back out and reply without the tag
        writing = true;
        try {
            ed.focus();
            const sel = window.getSelection();
            sel.selectAllChildren(ed);
            sel.collapseToStart();
            for (let k = 0; k < typed.length; k++) sel.modify('extend', 'forward', 'character');
            if (sel.toString() === typed) document.execCommand('delete');
        } finally { writing = false; }
        toast('Não consegui marcar a pessoa — marque com @ antes de enviar', false);
        return false;
    }
    // with the @mention in front, an opening "Ahmed," / "Ahmed —" would repeat the name
    function dropLeadingName(text, name) {
        const first = (name || '').split(/\s+/)[0];
        if (!first) return text;
        const m = text.match(new RegExp(`^\\s*${first.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}])\\s*[,—–:-]?\\s*`, 'iu'));
        if (!m || !m[0].trim()) return text;
        const rest = text.slice(m[0].length);
        return rest.charAt(0).toUpperCase() + rest.slice(1);
    }

    // ▾ next to "✨ Responder": you say what you want in the reply, then the AI writes it
    function replyPromptCard(replyBtn, post) {
        const block = commentBlock(replyBtn, post);
        block.parentElement.querySelectorAll(':scope > .careerops-card').forEach((c) => c.remove());
        const box = card('CareerOps · resposta com pedido');
        block.insertAdjacentElement('afterend', box);
        line(box, 'Diga o que quer na resposta: seu ponto, tom, concordar ou discordar, um exemplo a citar…');
        promptRow(box, 'Ex.: concorde sobre o lock-in e cite a migração de ERP que conduzi', (v) => { box.remove(); draftReply(replyBtn, post, { instruction: v }); }).focus();
    }

    // Adds "✨ Responder" next to each comment's Responder; highlights replies to your own comments
    function decorateReplies() {
        findPosts().forEach((post) => {
            [...post.querySelectorAll('button, [role="button"]')].filter(isReplyAction).forEach((rb) => {
                if (rb.dataset.careeropsSeen && (rb.dataset.careeropsSeen === 'self' || (rb.nextElementSibling && rb.nextElementSibling.classList.contains('careerops-reply')))) return;
                const block = commentBlock(rb, post);
                const who = authorOf(block);
                if (who.self) { rb.dataset.careeropsSeen = 'self'; return; }   // your own comment: nothing to answer
                rb.dataset.careeropsSeen = '1';
                const thread = threadOf(block, post);
                const toMe = thread !== block && [...thread.querySelectorAll('a[href*="/in/"]')].some((a) => !block.contains(a) && isSelf(a.innerText || ''));
                // [✨ Responder | ▾] like the post's [✨ IA | ▾]: the arrow lets you say what you want in the reply
                const split = document.createElement('span');
                split.className = 'careerops-reply';
                split.style.cssText = 'display:inline-flex;margin-left:6px;vertical-align:middle';
                const b = button(toMe ? '✨ Responder (para você)' : '✨ Responder', () => draftReply(rb, post), toMe);
                b.title = 'Rascunho de resposta com IA: continua a conversa ou agradece e encerra';
                b.style.cssText += ';font-size:11px;padding:2px 8px;margin:0;border-radius:14px 0 0 14px';
                const arrow = button('▾', () => replyPromptCard(rb, post), toMe);
                arrow.title = 'Responder com um pedido seu (o que dizer, tom, concordar ou discordar)';
                arrow.style.cssText += `;font-size:11px;padding:2px 7px;margin:0;border-radius:0 14px 14px 0;border-left:1px solid ${toMe ? 'rgba(255,255,255,.45)' : '#c9c9d6'}`;
                if (!toMe) arrow.style.borderLeftWidth = '0';
                split.append(b, arrow);
                rb.insertAdjacentElement('afterend', split);
            });
        });
    }

    const COMMENT_BTN = /^(comment|comentar)$/i;
    const own = (el) => el.closest('.careerops-card, .careerops-bar, .careerops-actions, .careerops-reply');

    // LinkedIn now draws its dialogs (the invite one, late 2026) inside the shadow root of #interop-outlet, where
    // document.querySelectorAll does not look. Closed or open, the extension can reach it.
    function shadowRoots() {
        const host = document.querySelector('#interop-outlet, [data-testid="interop-shadowdom"]');
        if (!host) return [];
        const root = host.shadowRoot || (chrome.dom && chrome.dom.openOrClosedShadowRoot ? chrome.dom.openOrClosedShadowRoot(host) : null);
        return root ? [root] : [];
    }
    const deepAll = (selector) => [document, ...shadowRoots()].flatMap((r) => [...r.querySelectorAll(selector)]);

    // The post's action bar (Like · Comment · Repost · Send): the smallest element holding its Comment and Repost buttons
    function actionBar(post) {
        const btns = [...post.querySelectorAll('button, [role="button"]')].filter((b) => !own(b));
        const repost = btns.find((b) => isRepostButton(b) && anchorKind(b) === 'repost');
        if (!repost) return null;
        for (let el = repost.parentElement; el && el !== post; el = el.parentElement) {
            if ([...el.querySelectorAll('button, [role="button"]')].some((b) => COMMENT_BTN.test(label(b)) || COMMENT_BTN.test(b.getAttribute('aria-label') || ''))) return el;
        }
        return null;
    }

    function savePost(post) {
        return async () => {
            const info = postInfo(post);
            if (info.post_text.length < 20) { toast('Não encontrei o texto deste post', false); return; }
            const res = await api('POST', '/inspirations', info);
            toast(res.ok ? 'Tema salvo — gere um post seu sobre ele no Copilot' : errText(res), res.ok);
            if (res.ok) harvestPeople(post, info);
        };
    }

    // Compact buttons for the action bar: [✨ IA | ▾] split button + 📌
    function barButton(text, title, onClick, css) {
        const b = button(text, onClick);
        b.title = title;
        b.style.cssText = `font:600 13px system-ui,sans-serif;cursor:pointer;border:1px solid ${ACCENT};height:30px;margin:0;${css}`;
        return b;
    }

    function postActions(post, bar) {
        const g = document.createElement('div');
        g.className = 'careerops-actions';
        g.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin-left:auto;padding:0 6px;flex:0 0 auto';
        const split = document.createElement('div');
        split.style.cssText = 'display:inline-flex';
        split.appendChild(barButton('✨ IA', 'Gerar comentário com IA', () => draftComment(post, bar),
            `background:${ACCENT};color:#fff;border-radius:15px 0 0 15px;padding:0 10px`));
        split.appendChild(barButton('▾', 'Gerar com um pedido seu (ângulo, tom, ponto a citar)', () => promptCard(post, bar),
            `background:${ACCENT};color:#fff;border-left:1px solid rgba(255,255,255,.45);border-radius:0 15px 15px 0;padding:0 7px`));
        g.appendChild(split);
        g.appendChild(barButton('📌', 'Salvar tema deste post (para um post seu no Copilot)', savePost(post),
            `background:#fff;color:${ACCENT};border-radius:15px;padding:0 9px`));
        return g;
    }

    // ── Saved posts that still have no link: filled in when the post shows up again (feed, search, the post page) ──
    const plainKey = (t) => (t || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '');
    let missing = { at: 0, items: [], loading: false };
    async function repairLinks(posts) {
        if (Date.now() - missing.at > 10 * 60 * 1000 && !missing.loading) {
            missing.loading = true;
            const res = await api('GET', '/inspirations/missing-links');
            missing = { at: Date.now(), items: res.ok ? res.data.items : [], loading: false };
        }
        if (!missing.items.length) return;
        for (const post of posts) {
            if (post.__careeropsKeyChecked) continue;
            const key = plainKey((post.innerText || '').slice(0, 3000));   // the whole card: header, author, then the text
            if (key.length < 20) continue;
            post.__careeropsKeyChecked = true;
            const item = missing.items.find((i) => key.includes(i.key));
            if (!item) continue;
            const url = postUrl(postUrn(post));
            if (!url) { post.__careeropsKeyChecked = false; continue; }   // try again later (e.g. after you click Comment)
            missing.items = missing.items.filter((i) => i !== item);
            const res = await api('PATCH', `/inspirations/${item.id}/link`, { post_url: url });
            if (res.ok) toast('🔗 Link do post salvo no CareerOps');
        }
    }

    function decoratePosts() {
        const posts = findPosts();
        repairLinks(posts);
        posts.forEach((post) => {
            if (post.closest('.careerops-card')) return;
            const bar = actionBar(post);
            if (bar) {
                // LinkedIn re-renders the bar; put the buttons back when they disappear
                if (bar.querySelector(':scope > .careerops-actions')) return;
                post.querySelectorAll('.careerops-bar, .careerops-actions').forEach((el) => el.remove());
                bar.appendChild(postActions(post, bar));
                post.__careeropsBtn = true;
                return;
            }
            if (post.__careeropsBtn) return;
            post.__careeropsBtn = true;
            // fallback (no recognizable action bar): a row at the top of the card
            const top = document.createElement('div');
            top.className = 'careerops-bar';
            top.style.cssText = 'padding:8px 16px 0;display:flex;gap:4px;flex-wrap:wrap';
            top.appendChild(button('✨ Comentário IA', () => draftComment(post, top)));
            top.appendChild(button('✍️ Com pedido', () => promptCard(post, top), false));
            top.appendChild(button('📌 Salvar tema', savePost(post), false));
            // LinkedIn wraps each card in zero-height containers: put the bar inside the visible card itself
            let host = post;
            for (let k = 0; k < 6; k++) {
                const kids = [...host.children].filter((c) => !c.classList.contains('careerops-bar') && !c.classList.contains('careerops-card'));
                const h = host.getBoundingClientRect().height;
                if (kids.length === 1 && (h < 2 || kids[0].getBoundingClientRect().height >= h - 2)) host = kids[0]; else break;
            }
            host.insertAdjacentElement('afterbegin', top);
        });
    }

    // ── 2. Profile: "🤝 Conectar" ───────────────────────────────────────────────────────────────────
    const isProfilePage = () => /^\/in\/[^/]+\/?$/.test(location.pathname);
    let profilePanel = null;

    // Connection requests go out WITHOUT a note (the free plan only allows a few personalized ones per month).
    const CONNECT = /^\+?\s*(conectar|connect)$/i;
    const SEND_NO_NOTE = ['enviar sem nota', 'send without a note', 'send without note'];
    const SEND = ['enviar', 'send', 'enviar convite', 'send invitation'];
    const dialogs = () => deepAll('div[role="dialog"], .artdeco-modal, [aria-modal="true"], dialog[open]')
        .filter((d) => (d.offsetParent !== null || d.getClientRects().length) && !own(d));
    const NO_NOTE = /^(send without( a)? note|enviar sem( uma)? nota)$/i;
    // "Send without a note" anywhere in the open dialogs, else "Send". A note asking for the person's e-mail does not
    // stop the invite; when LinkedIn really needs the e-mail, it keeps Send disabled and nothing is found here.
    function sendButton(open) {
        for (const d of open) {
            const btns = [...d.querySelectorAll('button')].filter((b) => (b.offsetParent !== null || b.getClientRects().length) && !b.disabled);
            const noNote = btns.find((b) => NO_NOTE.test(btnLabel(b)) || NO_NOTE.test(clean(b.getAttribute('aria-label') || '')));
            if (noNote) return noNote;
            const send = btns.find((b) => SEND.includes(btnLabel(b)));
            if (send) return send;
        }
        return null;
    }
    const btnLabel = (b) => clean(b.innerText || b.getAttribute('aria-label') || '').split('\n')[0].toLowerCase();

    // Only the profile's own top card counts. <main> also holds "People you may know" / "More profiles for you", whose
    // Connect buttons invite THAT person straight away (no dialog) — a wrong match there invites a stranger.
    const isMoreButton = (b) => /^(mais|more)$/i.test(btnLabel(b)) || /mais a[cç][oõ]es|more actions/i.test(b.getAttribute('aria-label') || '');
    const PENDING = /^(pendente|pending)$/i;
    // The name heading: <h1> in the old layout; now an <h2> — sometimes inside the link to this same profile, sometimes
    // not, so it is also recognised by matching the tab title ("Ana Lima | LinkedIn")
    const titleName = () => clean(document.title.replace(/^\(\d+\)\s*/, '').split(' | ')[0]).toLowerCase();
    const profileSlug = () => decodeURIComponent((location.pathname.match(/^\/in\/([^/]+)/) || [])[1] || '').toLowerCase();
    const linkSlug = (a) => decodeURIComponent((a.pathname.match(/^\/in\/([^/]+)/) || [])[1] || '').toLowerCase();
    function profileHeading() {
        return document.querySelector('main h1')
            || [...document.querySelectorAll('main h2')].find((h) => titleName() && clean(h.innerText).toLowerCase() === titleName())
            || [...document.querySelectorAll('main a[href*="/in/"] h2')].find((h) => linkSlug(h.closest('a')) === profileSlug()) || null;
    }
    // From the name up to the block that holds its action row (always has "More", "Connect" or "Pending"), never
    // far enough to take in a card about somebody else (a link to another /in/ profile)
    function profileTopCard() {
        const head = profileHeading();
        const visible = (el) => [...el.querySelectorAll('button, a, [role="button"]')].filter((b) => b.offsetParent !== null);
        const hasRow = (el) => visible(el).some((b) => isMoreButton(b) || CONNECT.test(btnLabel(b)) || PENDING.test(btnLabel(b)));
        const other = (el) => [...el.querySelectorAll('a[href*="/in/"]')].some((a) => linkSlug(a) && linkSlug(a) !== profileSlug());
        let el = head;
        while (el && !hasRow(el) && el.parentElement && el.parentElement.tagName !== 'MAIN' && !other(el.parentElement)) el = el.parentElement;
        return el && el !== head && hasRow(el) ? el : null;
    }
    const profileName = () => clean((profileHeading() || {}).innerText || '').toLowerCase() || titleName();
    // "Invite Ana Lima to connect" must name this profile; any other aria-label naming someone else is rejected
    function invitesThisPerson(el) {
        const labels = [el, ...el.querySelectorAll('[aria-label]')].map((e) => e.getAttribute('aria-label') || '').filter((l) => /(invite|convidar|convide)\b/i.test(l));
        const words = profileName().split(',')[0].trim().split(/\s+/);   // "ahmed elkadi, phd" → first + last name
        return labels.every((l) => words[0] && l.toLowerCase().includes(words[0]) && l.toLowerCase().includes(words[words.length - 1]));
    }
    const CANDIDATES = 'button, a, [role="button"], [role="menuitem"], div[aria-label]';
    const isConnect = (el) => el.offsetParent !== null && !el.closest('.careerops-card') && invitesThisPerson(el)
        && (CONNECT.test(btnLabel(el)) || /^(convidar|invite) .*(conectar|connect)/i.test(el.getAttribute('aria-label') || ''));

    // "Connect" is either a button in the top card's action row (older layout, most 2nd-degree profiles) or an item of
    // its "More" menu (rendered outside <main>). Menu items are told apart by appearing only after "More" is clicked.
    async function findConnect(card) {
        let el = [...card.querySelectorAll(CANDIDATES)].find(isConnect);
        if (el) return el;
        const more = [...card.querySelectorAll('button, [role="button"]')].find((b) => b.offsetParent !== null && isMoreButton(b));
        if (!more) return null;
        const before = new Set([...document.querySelectorAll(CANDIDATES)].filter((e) => e.offsetParent !== null));
        more.click();
        el = await waitFor(() => [...document.querySelectorAll(CANDIDATES)].find((e) => !before.has(e) && isConnect(e)) || null, 2500);
        if (!el) more.click();   // close the menu again
        return el;
    }

    // Returns 'sent' | 'pending' | 'connected' | 'unavailable' | 'needs_user'
    // beforeSend (managed mode) runs right before the click that sends; false stops it there
    async function connectNoNote(beforeSend) {
        const card = profileTopCard();
        if (!card) return 'unavailable';
        const actions = () => [...card.querySelectorAll('button, a')].filter((b) => b.offsetParent !== null).map(btnLabel);
        if (actions().some((l) => PENDING.test(l))) return 'pending';
        const target = await findConnect(card);
        if (!target) return actions().some((l) => /^(mensagem|message)$/.test(l)) ? 'connected' : 'unavailable';
        const before = new Set(dialogs());
        target.click();
        // The invite dialog is the one that opens now, not one already on the page (the messaging overlay is a
        // dialog too): look for its send button in every dialog that is open, newest first
        const btn = await waitFor(() => sendButton(dialogs().sort((x, y) => before.has(x) - before.has(y))), 5000);
        if (!btn) {
            // some profiles send at once, without a dialog: the button turns into "Pending"
            if (await waitFor(() => actions().some((l) => PENDING.test(l)), 1500)) return 'sent';
            return 'needs_user';   // e.g. LinkedIn asks for the person's email: that one is yours
        }
        if (beforeSend && !(await beforeSend())) return 'needs_user';
        btn.click();
        await wait(800);
        return 'sent';
    }

    // Saves the profile as a prospect (scored), then connects on your click
    async function ensureProspect() {
        const main = document.querySelector('main') || document.body;
        const name = clean((profileHeading() || {}).innerText || '');
        const headline = clean((main.querySelector('.text-body-medium') || {}).innerText || '');
        return api('POST', '/prospects', {
            profile_url: location.origin + location.pathname, name: name || null, headline: headline || null,
            profile_text: clean(main.innerText).slice(0, 6000),
        });
    }

    async function runConnect(prospectId) {
        activity('Conectando (sem nota) com este perfil…');
        await gate();
        const result = await connectNoNote();
        const msg = {
            sent: ['Convite enviado (sem nota) e registrado no CareerOps', true],
            pending: ['Já existe um convite pendente para esta pessoa', true],
            connected: ['Vocês já estão conectados', true],
            unavailable: ['Não achei o botão Conectar neste perfil', false],
            needs_user: ['O LinkedIn pediu algo a mais (ex.: e-mail): termine o convite manualmente', false],
        }[result];
        if (prospectId && ['sent', 'pending'].includes(result)) await api('PATCH', `/prospects/${prospectId}`, { status: 'invited' });
        if (prospectId && result === 'connected') await api('PATCH', `/prospects/${prospectId}`, { status: 'accepted' });
        toast(msg[0], msg[1]);
        return result;
    }

    async function draftInvite() {
        if (profilePanel) profilePanel.remove();
        profilePanel = card('CareerOps · conectar');
        profilePanel.style.cssText += ';position:fixed;right:16px;bottom:64px;width:340px;margin:0;z-index:2147483646';
        document.body.appendChild(profilePanel);
        const status = line(profilePanel, 'Avaliando o perfil…');
        const res = await ensureProspect();
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const p = res.data;
        status.textContent = `Encaixe ${p.fit ?? '?'} · ${p.market === 'br' ? 'Brasil' : p.market === 'intl' ? 'Exterior' : '—'} · ${p.segment || ''}`;
        if (p.reason) line(profilePanel, p.reason);
        if (p.status === 'skipped') line(profilePanel, 'A IA sugere não convidar (fora dos seus mercados).', '#999');
        const actions = document.createElement('div');
        actions.appendChild(button('Conectar sem nota', async () => { profilePanel.remove(); profilePanel = null; await runConnect(p.id); }));
        profilePanel.appendChild(actions);
    }

    // Opened from the CareerOps app ("Conectar"): <profile>#careerops-connect=<prospect id> connects and tells the app
    async function autoConnectFromApp() {
        const m = location.hash.match(/careerops-connect=(\d+)/);
        if (!m || !isProfilePage()) return;
        history.replaceState(null, '', location.pathname + location.search);
        await waitFor(profileHeading, 10000);
        await wait(1200);   // let the action row finish rendering
        await runConnect(Number(m[1]));
    }

    // Clicking LinkedIn's own "Enviar" in the invite dialog (manual connect) marks the prospect as invited
    document.addEventListener('click', (e) => {
        const hit = e.composedPath()[0];   // a click inside LinkedIn's shadow-root dialog reaches here retargeted to its host
        const b = hit && hit.closest ? hit.closest('button') : null;
        if (!b || !b.closest('div[role="dialog"], .artdeco-modal')) return;
        if (![...SEND_NO_NOTE, ...SEND].includes(btnLabel(b)) || !isProfilePage()) return;
        ensureProspect().then((res) => { if (res.ok) api('PATCH', `/prospects/${res.data.id}`, { status: 'invited' }); });
        toast('Convite registrado no CareerOps');
    }, true);

    // ── 3. Lists of people: "⭐ Avaliar pessoas da página" ─────────────────────────────────────────────
    function visiblePeople() {
        const seen = new Map();
        document.querySelectorAll('main a[href*="/in/"]').forEach((a) => {
            const m = a.href.match(/https:\/\/www\.linkedin\.com\/in\/[^/?#]+/);
            if (!m || location.href.startsWith(m[0])) return;
            const url = m[0];
            const container = a.closest('li, .entity-result, .discover-entity-type-card, .artdeco-card, div[data-view-name]') || a.parentElement;
            const text = clean(container ? container.innerText : a.innerText);
            if (!text || text.length < 5) return;
            const lines = text.split('\n').map((s) => s.trim()).filter(Boolean)
                .filter((s) => !/^(conectar|connect|seguir|follow|mensagem|message|ver perfil|view profile|•|\d+º|\d+(st|nd|rd|th))$/i.test(s));
            const prev = seen.get(url);
            if (prev && prev.text.length >= text.length) return;
            seen.set(url, { url, anchor: a, container, text, name: lines[0] || '', headline: lines.slice(1, 4).join(' · '), first: isFirstDegree(text) });
        });
        return [...seen.values()].slice(0, 25);
    }

    function badge(person, item) {
        const host = person.container || person.anchor;
        if (!host || host.querySelector('.careerops-badge')) return;
        const fit = item.fit ?? 0;
        const good = item.status !== 'skipped';
        const b = document.createElement('div');
        b.className = 'careerops-badge';
        b.title = `${item.reason || ''}${item.note_draft ? '\n\nNota: ' + item.note_draft : ''}`;
        b.style.cssText = `display:inline-block;margin:4px 0;padding:2px 8px;border-radius:10px;font:600 11px system-ui,sans-serif;
            background:${good ? (fit >= 75 ? '#00b894' : '#fdcb6e') : '#dfe6e9'};color:${good ? '#fff' : '#636e72'}`;
        b.textContent = `CareerOps ${fit} · ${item.market === 'br' ? 'BR' : item.market === 'intl' ? 'EXT' : '—'}${good ? '' : ' · pular'}`;
        host.appendChild(b);
    }

    async function scorePage(btn) {
        const all = visiblePeople();
        markConnected(all.filter((p) => p.first).map((p) => ({ profile_url: p.url, name: p.name })));
        const people = all.filter((p) => !p.first);
        if (!people.length) { toast('Nenhuma pessoa visível nesta página', false); return; }
        btn.disabled = true;
        btn.textContent = `Avaliando ${people.length}…`;
        const res = await api('POST', '/prospects/batch', { people: people.map((p) => ({ profile_url: p.url, name: p.name, headline: p.headline })) });
        btn.disabled = false;
        btn.textContent = '⭐ Avaliar pessoas da página';
        if (!res.ok) { toast(errText(res), false); return; }
        const byUrl = new Map(res.data.items.map((i) => [i.profile_url, i]));
        people.forEach((p) => { const item = byUrl.get(p.url); if (item) badge(p, item); });
        const top = res.data.items.filter((i) => i.status !== 'skipped').length;
        toast(`${top} de ${res.data.items.length} pessoas com bom encaixe — salvas em Prospecção com a nota pronta`);
    }

    // ── 4. Easy Apply: "✨ Preencher com IA" (fills each step; you review, click Next and Submit) ────────
    // Gender goes to the backend, which answers it only from config/easy_apply.yml; these stay with the user
    const DEMOGRAPHIC = /race|ra[cç]a|etnia|ethnic|veteran|disab|defici[eê]ncia|pcd|orienta[cç][aã]o sexual|sexual orientation|pronoun|pronome|religi/i;
    const PLACEHOLDER = /^(selecione|select|escolha|choose)/i;

    // LinkedIn's apply form: the old modal (div role=dialog) or the native <dialog> it uses now (top layer: no
    // offsetParent, so visibility is checked with getClientRects)
    const shown = (el) => el.offsetParent !== null || el.getClientRects().length > 0;
    function easyApplyModal() {
        return deepAll('.jobs-easy-apply-modal, div[role="dialog"], dialog[open]')
            .find((d) => shown(d) && (d.classList.contains('jobs-easy-apply-modal')
                || /candidatura simplificada|easy apply|apply to |candidatar-se|candidatura para/i.test(d.innerText.slice(0, 400))));
    }

    // ── CV and cover letter generated for this job, attached in the form ──
    // A file input already in the step is filled directly. LinkedIn's current form has none: "Upload resume" creates one
    // and opens the system dialog; urn_bridge.js skips that dialog while <html data-careerops-pick-file> is set.
    const UPLOAD = { resume: /^(upload resume|carregar curr[ií]culo|enviar curr[ií]culo|fazer upload do curr[ií]culo|upload cv)/i,
                     cover: /^(upload cover letter|carregar carta|enviar carta|fazer upload da carta)/i };
    const KIND_TEXT = { resume: /resume|r[eé]sum[eé]|\bcv\b|curr[ií]cul/i, cover: /cover letter|carta de apresenta|motivation letter/i };
    async function careeropsJob(say) {
        const id = currentJobId();
        if (!id) return null;
        let res = await backend('GET', `/jobs/linkedin/${id}`);
        if (!res.ok && res.status === 404) {   // not imported yet: import it, then look again
            say('Importando a vaga para o CareerOps…');
            let job = jobFromPage(id);
            if (!job.description) { const extra = await jobPosting(id); job = { ...job, ...Object.fromEntries(Object.entries(extra).filter(([, v]) => v)) }; }
            await backend('POST', '/jobs/import-extension', { title: job.title, company: job.company, location: job.location, description: job.description,
                url: `https://www.linkedin.com/jobs/view/${id}/`, linkedin_job_id: id, status: 'new', hiringTeam: hiringTeamFromPage() });
            res = await backend('GET', `/jobs/linkedin/${id}`);
        }
        return res.ok ? res.data : null;
    }
    async function putFile(modal, kind, file) {
        const bytes = Uint8Array.from(atob(file.b64), (c) => c.charCodeAt(0));
        const dt = new DataTransfer();
        dt.items.add(new File([bytes], file.name, { type: file.type }));
        const set = (input) => { input.files = dt.files; input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); };
        const inputs = [...modal.querySelectorAll('input[type="file"]')];
        const direct = inputs.find((i) => KIND_TEXT[kind].test(`${i.id} ${i.name} ${i.getAttribute('aria-label') || ''} ${(i.closest('label, div') || {}).innerText || ''}`.slice(0, 300)));
        if (direct || (kind === 'resume' && inputs.length === 1)) { set(direct || inputs[0]); return true; }
        const btn = [...modal.querySelectorAll('button, [role="button"], label')].find((b) => !own(b) && UPLOAD[kind].test(label(b)));
        if (!btn) return false;
        const before = new Set(document.querySelectorAll('input[type="file"]'));
        document.documentElement.setAttribute('data-careerops-pick-file', '');
        try {
            btn.click();
            const input = await waitFor(() => [...document.querySelectorAll('input[type="file"]')].find((i) => !before.has(i)), 3000);
            if (!input) return false;
            set(input);
            return true;
        } finally {
            setTimeout(() => document.documentElement.removeAttribute('data-careerops-pick-file'), 500);
        }
    }
    // the step asks for a CV / cover letter: attach the ones generated for this job (once per form)
    async function attachDocuments(modal, say) {
        const wants = ['resume', 'cover'].filter((k) => !(modal.__careeropsDocs || {})[k]
            && ([...modal.querySelectorAll('button, [role="button"], label')].some((b) => !own(b) && UPLOAD[k].test(label(b)))
                || [...modal.querySelectorAll('input[type="file"]')].length && KIND_TEXT[k].test(modal.innerText)));
        if (!wants.length) return [];
        modal.__careeropsDocs = modal.__careeropsDocs || {};
        const job = await careeropsJob(say);
        if (!job) { say('Vaga não encontrada no CareerOps: anexe o CV à mão.'); return []; }
        if ((wants.includes('resume') && !job.has_resume) || (wants.includes('cover') && !job.has_cover)) {
            say('Gerando o CV e a carta para esta vaga (≈1 min)…');
            await backend('POST', `/jobs/${job.id}/auto-apply/prepare`, {});
        }
        const done = [];
        for (const kind of wants) {
            const file = await message({ action: 'backendFile', path: `/jobs/${job.id}/document.pdf?kind=${kind}` });
            if (!file || !file.ok) { say(`Não consegui baixar o ${kind === 'resume' ? 'CV' : 'carta'}: ${(file && file.detail) || ''}`); continue; }
            if (await putFile(modal, kind, file)) {
                modal.__careeropsDocs[kind] = true;
                done.push(file.name);
                await wait(2500);   // LinkedIn uploads it and adds it to the list
                // the uploaded file must be the one chosen (LinkedIn keeps the last CV used, often another job's)
                const radio = [...modal.querySelectorAll('input[type="radio"]')].find((r) => (r.closest('label, li, div') || {}).innerText && r.closest('li, div').innerText.includes(file.name.replace(/\.pdf$/i, '')));
                if (radio && !radio.checked) radio.click();
            }
        }
        return done;
    }

    // Late-2026 form: the question is a <p> right before the fieldset (ending in "*" when required), every input repeats it
    // in aria-label, and the <label for> is empty. The older form (label / legend / .fb-dash-form-element) is still read.
    const questionBlock = (el) => el.closest('[componentkey^="easyApplyFieldFocus"]') || (el.closest('fieldset') || {}).parentElement || null;
    const blockTitle = (el) => { const b = questionBlock(el); return b ? clean(b.innerText).split('\n')[0].trim() : ''; };

    function labelFor(el, modal) {
        if (el.id) { const l = modal.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l && clean(l.innerText)) return clean(l.innerText); }
        const fs = el.closest('fieldset');
        if (fs && fs.querySelector('legend') && clean(fs.querySelector('legend').innerText)) return clean(fs.querySelector('legend').innerText);
        // the question in aria-label: on the input, or (some radio groups) on the div[role=radio] around it
        const aria = el.getAttribute('aria-label') || (el.closest('[role="radio"], [role="checkbox"]') || { getAttribute: () => '' }).getAttribute('aria-label');
        if (aria) return clean(aria) + (/\*$/.test(blockTitle(el)) ? ' *' : '');
        // the <p> heading the question's block, when nothing else names it
        if (el.closest('[componentkey^="easyApplyFieldFocus"]') && blockTitle(el)) return blockTitle(el).replace(/\s*\*$/, ' *');
        const wrap = el.closest('.fb-dash-form-element, .jobs-easy-apply-form-element, .artdeco-text-input, div');
        return wrap ? clean(wrap.innerText).split('\n')[0] : '';
    }

    function collectFields(modal) {
        const fields = [];
        const seen = new Set();
        modal.querySelectorAll('input, textarea, select').forEach((el, i) => {
            if (el.closest('.careerops-card') || !shown(el) || el.disabled) return;
            const type = el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea'
                : el.type === 'radio' ? 'radio' : el.type === 'checkbox' ? 'checkbox' : el.type === 'number' ? 'number'
                : ['text', 'tel', 'email', 'url', ''].includes(el.type) ? 'text' : null;
            if (!type) return;
            const key = type === 'radio' ? `radio:${el.name || i}` : (el.id || el.name || `f${i}`);
            if (seen.has(key)) return;
            seen.add(key);
            const label = labelFor(el, modal).slice(0, 300);
            const f = { key, type, label, options: [], current: null, els: [el] };
            if (type === 'select') {
                f.options = [...el.options].map((o) => o.text.trim()).filter((t) => t && !PLACEHOLDER.test(t));
                const sel = el.options[el.selectedIndex];
                f.current = sel && !PLACEHOLDER.test(sel.text.trim()) ? sel.text.trim() : null;
            } else if (type === 'radio') {
                f.els = [...modal.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`)];
                // the option's text: its label, or (late-2026 form, empty label) the text next to the radio's own box
                f.options = f.els.map((r) => clean((modal.querySelector(`label[for="${CSS.escape(r.id)}"]`) || {}).innerText || '')
                    || clean(r.parentElement.innerText) || clean((r.parentElement.parentElement || {}).innerText || '') || r.value);
                const on = f.els.find((r) => r.checked);
                f.current = on ? f.options[f.els.indexOf(on)] : null;
            } else if (type === 'checkbox') {
                f.current = el.checked ? 'true' : null;
            } else {
                f.current = el.value ? el.value : null;
            }
            fields.push(f);
        });
        return fields;
    }

    function applyAnswer(f, value) {
        if (f.type === 'select') {
            const el = f.els[0];
            const opt = [...el.options].find((o) => o.text.trim().toLowerCase() === value.toLowerCase());
            if (!opt) return false;
            el.value = opt.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        } else if (f.type === 'radio') {
            const idx = f.options.findIndex((o) => o.toLowerCase() === value.toLowerCase());
            if (idx < 0) return false;
            f.els[idx].click();
        } else if (f.type === 'checkbox') {
            if ((value === 'true') !== f.els[0].checked) f.els[0].click();
        } else {
            fill(f.els[0], value);
        }
        return true;
    }

    // LinkedIn marks required questions on the input or with a "*" / "required" / "obrigatório" in the label
    const isRequired = (f) => f.els.some((el) => el.required || el.getAttribute('aria-required') === 'true' || /\*$/.test(blockTitle(el)))
        || /\*\s*$|\b(required|obrigat[oó]rio)\b/i.test(f.label || '');

    const mark = (f, color) => f.els.forEach((el) => { (el.type === 'radio' || el.type === 'checkbox' ? el.parentElement : el).style.outline = `2px solid ${color}`; });

    function jobContext() {
        const q = (sel) => clean((document.querySelector(sel) || {}).innerText || '');
        return {
            title: q('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .t-24.job-details-jobs-unified-top-card__job-title, h1'),
            company: q('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name'),
            location: q('.job-details-jobs-unified-top-card__primary-description-container, .jobs-unified-top-card__bullet'),
            description: q('#job-details, .jobs-description__content, .jobs-description-content__text').slice(0, 5000),
            linkedin_job_id: currentJobId() || null,   // the backend uses the CV generated for this job
        };
    }

    let applyBusy = false;
    // one notice line under the status, replaced at each step (the bar never grows)
    function note(panel, text, color = '#555') {
        let el = panel.querySelector('.careerops-apply-note');
        if (!el) { el = line(panel, ''); el.className = 'careerops-apply-note'; }
        el.textContent = text;
        el.style.color = color;
        return el;
    }

    async function fillStep(modal, panel) {
        if (applyBusy) return null;
        const all = collectFields(modal);
        const fields = all.filter((f) => !f.current);
        const statusEl = panel.querySelector('.careerops-apply-status');
        const status = { style: statusEl.style, set textContent(t) { statusEl.textContent = t; activity(`Easy Apply: ${t}`); } };
        note(panel, '');   // the previous step's notice
        const attached = await attachDocuments(modal, (t) => { status.textContent = t; });
        if (attached.length) note(panel, `📎 Anexado: ${attached.join(', ')} (gerado para esta vaga).`, '#00b894');
        if (!fields.length) { status.textContent = attached.length ? 'Anexado. Revise e clique em Avançar.' : 'Nada para preencher nesta etapa. Revise e clique em Avançar.'; return { filled: 0, pending: 0 }; }
        const demographic = fields.filter((f) => DEMOGRAPHIC.test(f.label));
        const send = fields.filter((f) => !DEMOGRAPHIC.test(f.label));
        demographic.forEach((f) => mark(f, '#e17055'));
        // In managed mode a voluntary demographic question stays blank (only the required ones stop the application)
        const requiredDemographic = managedRun ? demographic.filter(isRequired) : demographic;
        const blocking = (list) => list.map((f) => ({ key: f.key, label: f.label, type: f.type, options: f.options }));
        if (!send.length) {
            status.textContent = 'Só há perguntas pessoais/demográficas nesta etapa — responda você.';
            return { filled: 0, pending: requiredDemographic.length, questions: blocking(requiredDemographic) };
        }
        applyBusy = true;
        status.textContent = `Preenchendo ${send.length} campo(s)…`;
        const res = await api('POST', '/easy-apply/answers', {
            job: jobContext(), fields: send.map(({ key, type, label, options, current }) => ({ key, type, label, options, current })),
        });
        applyBusy = false;
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return null; }
        await gate();   // paused while the AI answered: apply nothing until you continue
        let filled = 0;
        const pending = [];
        const toConfirm = [];
        const unanswered = [...requiredDemographic];
        const sugg = res.data.suggestions || {};
        for (const f of send) {
            if (typedByYou(f)) continue;   // you answered it meanwhile
            const v = res.data.answers[f.key];
            if (v !== undefined && applyAnswer(f, v)) {
                mark(f, '#00b894'); filled++;
                if (managedRun) managedRun.fields.push({ label: f.label || f.key, value: String(v).slice(0, 500) });
                continue;
            }
            const sg = sugg[f.key];
            if (sg && applyAnswer(f, sg.value)) { mark(f, '#fdcb6e'); toConfirm.push(`${f.label || f.key}: ${sg.value}${sg.basis ? ` (${sg.basis})` : ''}`); unanswered.push(f); continue; }
            mark(f, '#e17055');
            if (managedRun && !isRequired(f)) continue;   // optional and unknown: stays blank, which is an answer too
            pending.push(f.label || f.key); unanswered.push(f);
        }
        requiredDemographic.forEach((f) => pending.push(f.label));
        status.style.color = '#555';
        status.textContent = `${filled} preenchido(s) em verde. ` + (pending.length ? `Para você (laranja): ${pending.slice(0, 6).join(' · ')}` : 'Revise e clique em Avançar.');
        if (toConfirm.length) note(panel, `Confirme ou altere (amarelo) — sugestão de mercado estimada pela IA: ${toConfirm.join(' · ')}`, '#b7791f');
        if (res.data.notes) note(panel, res.data.notes, '#777');
        return { filled, pending: pending.length, toConfirm: toConfirm.length, questions: blocking(unanswered) };
    }

    let applyPanel = null;
    // The panel goes right above the area that scrolls the form (inside the same column), never as a loose child of
    // the dialog: LinkedIn's <dialog> lays its children out in a row, and a panel there squeezed the form into a
    // narrow column
    function placeApplyPanel(modal, panel) {
        const field = [...modal.querySelectorAll('input, select, textarea, h3, label')].find((el) => !own(el) && shown(el));
        let scroller = null;
        for (let el = field && field.parentElement; el && el !== modal; el = el.parentElement) {
            if (/(auto|scroll)/.test(getComputedStyle(el).overflowY)) { scroller = el; break; }
        }
        const parent = scroller && scroller.parentElement;
        const rowLayout = parent && getComputedStyle(parent).display.includes('flex') && !getComputedStyle(parent).flexDirection.startsWith('column');
        if (scroller && parent && !rowLayout) parent.insertBefore(panel, scroller);
        else if (scroller) scroller.insertAdjacentElement('afterbegin', panel);   // inside the scrolling area
        else modal.insertAdjacentElement('afterbegin', panel);
    }

    function decorateEasyApply() {
        const modal = easyApplyModal();
        if (!modal) { applyPanel = null; return; }
        if (!modal.querySelector('.careerops-apply')) {
            // a compact bar: button, auto-fill switch and one status line; the colour legend is the tooltip
            applyPanel = card('CareerOps · Easy Apply');
            applyPanel.classList.add('careerops-apply');
            applyPanel.style.cssText += ';margin:6px 16px;padding:8px 12px;flex:0 0 auto;box-shadow:none';
            applyPanel.title = 'A IA preenche com seus dados (config/easy_apply.yml + o CV gerado para a vaga). Verde: preenchido · Amarelo: sugestão, confirme · Laranja: com você.';
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap';
            const fillBtn = button('✨ Preencher com IA', () => fillStep(modal, applyPanel));
            fillBtn.classList.add('careerops-fill');
            const auto = document.createElement('label');
            auto.style.cssText = 'font-size:12px;color:#555;display:flex;gap:4px;align-items:center;margin:0;cursor:pointer';
            auto.innerHTML = '<input type="checkbox" checked> cada nova etapa';
            applyPanel.__auto = auto.querySelector('input');
            row.append(fillBtn, auto);
            applyPanel.appendChild(row);
            const status = line(applyPanel, '');
            status.className = 'careerops-apply-status';
            placeApplyPanel(modal, applyPanel);
        }
        // Auto: when a new step shows empty fields, fill them (the user still clicks Next/Submit)
        const panel = modal.querySelector('.careerops-apply');
        const signature = collectFields(modal).map((f) => f.key).join('|');
        if (!paused && panel.__auto && panel.__auto.checked && panel.__filledOnce && signature && signature !== panel.__lastStep) {
            panel.__lastStep = signature;
            fillStep(modal, panel);
        }
        if (!panel.__filledOnce) {
            panel.querySelector('.careerops-fill').addEventListener('click', () => { panel.__filledOnce = true; panel.__lastStep = signature; }, { once: true });
        }
    }

    // ── 5. Saved jobs: "📥 Importar vagas salvas" (my-items/saved-jobs) ───────────────────────────────
    // Reads the list on screen (no clicks) and fetches each job's public posting, one at a time, slowly.
    const backend = (method, path, body) => new Promise((resolve) => {
        try {
            chrome.runtime.sendMessage({ action: 'backendApi', method, path, body }, (res) => resolve(res || { ok: false, data: { detail: (chrome.runtime.lastError || {}).message || 'Sem resposta' } }));
        } catch (e) { resolve({ ok: false, data: { detail: 'A extensão foi atualizada — recarregue esta página (F5)' } }); }
    });
    const isSavedJobsPage = () => /\/my-items\/saved-jobs|\/jobs-tracker/.test(location.pathname);

    // The job tracker (/jobs-tracker/, late 2026; the old address goes there) has no list items: the card's first link holds
    // its lines (the title ending in "(Verified job)", the title again, "Company · Place", "Posted 2w ago"). The old page
    // (my-items/saved-jobs) has li / entity-result boxes with the title, the company and the place.
    const VERIFIED = /\s*\((verified job|vaga verificada)\)\s*$/i;
    function savedJobsOnScreen() {
        const jobs = new Map();
        document.querySelectorAll('main a[href*="/jobs/view/"]').forEach((a) => {
            const m = a.href.match(/\/jobs\/view\/(\d+)/);
            if (!m || jobs.has(m[1])) return;
            const box = a.closest('li, .entity-result, div[data-chameleon-result-urn], .reusable-search__result-container');
            const lines = clean(box ? box.innerText : a.innerText).split('\n').map((l) => l.trim().replace(VERIFIED, '')).filter(Boolean);
            if (!lines.length) return;
            const title = lines[0];
            const rest = lines[1] === title ? lines.slice(2) : lines.slice(1);
            const [company, location] = / · /.test(rest[0] || '') ? rest[0].split(' · ', 2) : [rest[0], rest[1]];
            jobs.set(m[1], { id: m[1], title, company: company || '', location: location || '',
                             easy_apply: /easy apply|candidatura simplificada/i.test(box ? box.innerText : (a.parentElement || a).innerText) });
        });
        return [...jobs.values()].slice(0, 25);
    }

    // The next page of the list: the tracker's button (data-testid), the old artdeco one, or a button that says so
    const savedNextButton = () => [...document.querySelectorAll('button, a')].find((b) => !b.closest('.careerops-card, .careerops-bar, .careerops-actions')
        && (b.matches('[data-testid^="pagination-controls-next-button"], .artdeco-pagination__button--next') || /^(next|pr[oó]xima)$/i.test(label(b)))
        && !b.disabled && b.getAttribute('aria-disabled') !== 'true' && b.offsetParent !== null);

    // Text of a parsed (not rendered) HTML block, keeping paragraphs and bullets: innerText doesn't work there
    function htmlText(el) {
        if (!el) return '';
        const c = el.cloneNode(true);
        c.querySelectorAll('br').forEach((b) => b.replaceWith('\n'));
        c.querySelectorAll('li').forEach((li) => li.prepend('• '));
        c.querySelectorAll('p, div, li, h1, h2, h3, h4, h5, h6, ul, ol').forEach((b) => b.append('\n'));
        return c.textContent.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    }

    async function jobPosting(id) {
        try {
            const html = await fetch(`/jobs-guest/jobs/api/jobPosting/${id}`, { credentials: 'include' }).then((r) => (r.ok ? r.text() : ''));
            if (!html) return {};
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const q = (sel) => clean((doc.querySelector(sel) || {}).textContent || '');
            return {
                title: q('.top-card-layout__title, .topcard__title'),
                company: q('.topcard__org-name-link, .topcard__flavor a, .topcard__flavor'),
                location: q('.topcard__flavor--bullet'),
                description: htmlText(doc.querySelector('.show-more-less-html__markup, .description__text')),
            };
        } catch (e) { return {}; }
    }

    async function importSavedJobs(btn) {
        const jobs = savedJobsOnScreen();
        if (!jobs.length) { toast('Nenhuma vaga salva visível — role a lista e tente de novo', false); return { ok: false, imported: 0 }; }
        let imported = 0, noDesc = 0;
        for (let i = 0; i < jobs.length; i++) {
            const j = jobs[i];
            if (btn) btn.textContent = `Importando ${i + 1}/${jobs.length}…`;
            activity(`Importando vaga salva ${i + 1}/${jobs.length}: ${j.title || j.id}`);
            await gate();
            const extra = await jobPosting(j.id);
            if (!extra.description) noDesc++;
            const res = await backend('POST', '/jobs/import-extension', {
                title: extra.title || j.title, company: extra.company || j.company, location: extra.location || j.location,
                url: `https://www.linkedin.com/jobs/view/${j.id}/`, linkedin_job_id: j.id,
                description: extra.description || '', status: 'new',
            });
            if (res.ok) imported++;
            await wait(1500 + Math.random() * 1000);   // slow and steady
        }
        if (btn) btn.textContent = '📥 Importar vagas salvas';
        toast(`${imported} de ${jobs.length} vaga(s) salvas no CareerOps (Vagas)` + (noDesc ? ` · ${noDesc} sem descrição` : ''), imported > 0);
        return { ok: true, imported, total: jobs.length };
    }

    // ── 6. Job pages: "📥 CareerOps" next to LinkedIn's Save, and Save imports automatically ─────────
    const SAVE = /^(save|salvar)$/i;
    const SAVED = /^(saved|salva|salvo|unsave|remover dos salvos)$/i;
    const currentJobId = () => new URLSearchParams(location.search).get('currentJobId') || (location.pathname.match(/\/jobs\/view\/(\d+)/) || [])[1];

    function jobFromPage(id) {
        const q = (sel) => clean((document.querySelector(sel) || {}).innerText || '');
        return {
            title: q('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .jobs-details h1, main h1'),
            company: q('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name'),
            location: q('.job-details-jobs-unified-top-card__primary-description-container, .jobs-unified-top-card__bullet'),
            description: q('#job-details, .jobs-description__content, .jobs-description-content__text, .jobs-box__html-content'),
            id,
        };
    }

    // "Meet the hiring team" / "Conheça a equipe de contratação": the people who posted or own the job, when LinkedIn
    // shows them. Found by the heading text (class names change), then every profile link inside that section.
    const HIRING_HEAD = /^(meet the hiring team|conhe[cç]a a equipe de contrata[cç][aã]o|equipe de contrata[cç][aã]o|job poster|anunciante da vaga)$/i;
    function hiringTeamFromPage() {
        const head = [...document.querySelectorAll('main h1, main h2, main h3, main h4, main span, main div, main p')]
            .find((el) => el.children.length <= 1 && HIRING_HEAD.test(clean(el.innerText || '')));
        if (!head) return [];
        let box = head;
        for (let k = 0; k < 6 && box.parentElement && !box.querySelector('a[href*="/in/"]'); k++) box = box.parentElement;
        const people = new Map();
        for (const a of box.querySelectorAll('a[href*="/in/"]')) {
            const link = a.href.split('?')[0].replace(/\/$/, '');
            const lines = clean(a.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean);
            // the card around the link holds the name, the headline and badges ("2nd", "Job poster")
            const card = a.closest('li, div') || a;
            const all = (card.innerText || '').split('\n').map((s) => s.trim()).filter((s) => s && !/^(·|\d(st|nd|rd|º)|job poster|anunciante da vaga|message|mensagem|connect|conectar|verified|•)/i.test(s));
            const name = (lines[0] || all[0] || '').replace(/\s*(verified profile|perfil verificado).*$/i, '');
            if (!name || people.has(link)) continue;
            const title = all.find((s) => s !== name && !s.startsWith(name) && s.length > 3) || '';
            people.set(link, { name, title, link });
        }
        return [...people.values()].slice(0, 5);
    }

    const jobState = new Map();   // job id -> imported in this tab
    const setJobButtons = (id, text) => document.querySelectorAll(`.careerops-jobbtn[data-job="${id}"]`).forEach((b) => { b.textContent = text; });

    async function importCurrentJob(btn, auto = false) {
        const id = currentJobId();
        if (!id) { toast('Não encontrei a vaga aberta', false); return; }
        setJobButtons(id, 'Importando…');
        let job = jobFromPage(id);
        if (!job.description || !job.title) {
            const extra = await jobPosting(id);
            job = { ...job, title: job.title || extra.title, company: job.company || extra.company,
                    location: job.location || extra.location, description: job.description || extra.description || '' };
        }
        const res = await backend('POST', '/jobs/import-extension', {
            title: job.title, company: job.company, location: job.location, description: job.description,
            url: `https://www.linkedin.com/jobs/view/${id}/`, linkedin_job_id: id, status: 'new',
            hiringTeam: hiringTeamFromPage(),
        });
        if (res.ok) jobState.set(id, true);
        setJobButtons(id, res.ok ? '✓ No CareerOps' : '📥 CareerOps');
        toast(res.ok ? (auto ? 'Vaga salva também no CareerOps' : 'Vaga importada para o CareerOps (Vagas)') : errText(res), res.ok);
    }

    // Every visible Save of the job pane gets our button — including the sticky header LinkedIn shows on scroll
    function decorateJobSave() {
        const id = currentJobId();
        if (!id) return;
        const saves = [...document.querySelectorAll('main button, header button, div[class*="sticky"] button')]
            .filter((b) => !b.closest('.careerops-card, .careerops-bar, .careerops-actions') && (SAVE.test(label(b)) || SAVED.test(label(b)))
                && b.offsetParent !== null && !b.closest('li') && b.__careeropsJob !== id);
        for (const saveBtn of saves) {
            saveBtn.__careeropsJob = id;
            const mine = button(jobState.get(id) ? '✓ No CareerOps' : '📥 CareerOps', () => importCurrentJob(mine));
            mine.classList.add('careerops-jobbtn');
            mine.title = 'Importar esta vaga para o CareerOps';
            // same height as LinkedIn's pill buttons, never overlapping them
            mine.style.cssText += ';position:static;flex:0 0 auto;align-self:center;height:32px;padding:0 14px;margin:0 0 0 8px;white-space:nowrap;border-radius:16px';
            mine.dataset.job = id;
            // Save sits inside its own fixed-size wrapper: climb to the element that shares a parent with the Apply
            // button of the same bar and add ours as a separate item of that row
            // climb until the parent also holds an Apply button: that parent is this Save's own row
            const isApply = (b) => /^(apply|candidatar|candidatar-se|easy apply|candidatura simplificada)\b/i.test(label(b)) && b.offsetParent !== null;
            let anchor = saveBtn;
            let foundRow = false;
            for (let k = 0; k < 6 && anchor.parentElement && anchor.parentElement.tagName !== 'MAIN'; k++) {
                const parent = anchor.parentElement;
                if ([...parent.querySelectorAll('button, a')].some((b) => isApply(b) && !anchor.contains(b))) { foundRow = true; break; }
                anchor = parent;
            }
            if (!foundRow) anchor = saveBtn.parentElement && saveBtn.parentElement.children.length === 1 ? saveBtn.parentElement : saveBtn;
            anchor.insertAdjacentElement('afterend', mine);
            if (anchor.parentElement && !getComputedStyle(anchor.parentElement).display.includes('flex')) {
                mine.style.display = 'inline-flex';
                mine.style.alignItems = 'center';
                mine.style.verticalAlign = 'middle';
            }
            // clicking LinkedIn's Save (not Unsave) also imports the job
            saveBtn.addEventListener('click', () => { if (SAVE.test(label(saveBtn))) importCurrentJob(mine, true); }, true);
        }
    }

    // ── 7. Auto Apply (started from a job in CareerOps): drives Easy Apply step by step, or hands off to the
    // company site (apply_copilot.js continues there). The final "Submit application" is yours unless you tick
    // "enviar sozinho no final".
    const message = (msg) => new Promise((resolve) => {
        try { chrome.runtime.sendMessage(msg, (res) => { void chrome.runtime.lastError; resolve(res); }); } catch (e) { resolve(null); }
    });
    const EASY = /^(easy apply|candidatura simplificada)/i;
    const APPLY_EXT = /^(apply|candidatar-se|candidatar)\b/i;
    const NEXT = /^(next|continue|review|avançar|continuar|revisar|próximo|revisar candidatura)\b/i;
    const SUBMIT_APP = /^(submit application|submit|enviar candidatura|enviar)$/i;
    const SENT = /application (was )?sent|application submitted|candidatura (foi )?enviada|sua candidatura foi enviada/i;
    let autopilot = null;
    let applyCheckedFor = null;   // the job id last checked for a pending Auto Apply (LinkedIn changes jobs without reloading)

    function apStatus(text, color = '#333') {
        if (autopilot) { autopilot.status.textContent = text; autopilot.status.style.color = color; }
        activity(`Auto Apply: ${text}`);
    }

    async function startAutopilot() {
        const jobOnPage = String(currentJobId());
        applyCheckedFor = jobOnPage;
        // the tab CareerOps just opened registers itself (apply_copilot.js) at about the same time: give it a moment
        const marked = /careerops-apply=/.test(location.hash);
        let pending = await message({ action: 'applyPending' });
        for (let k = 0; marked && k < 20 && !(pending && String(pending.linkedinJobId) === jobOnPage); k++) {
            await sleep(150);
            pending = await message({ action: 'applyPending' });
        }
        if (!pending || autopilot) return;
        // only on the job it was started for (other jobs and pages opened later in this tab are not applied to)
        if (pending.linkedinJobId ? String(pending.linkedinJobId) !== jobOnPage : !/careerops-apply=/.test(location.hash)) return;
        const box = card('🚀 CareerOps · Auto Apply');
        box.style.cssText += ';position:fixed;left:16px;bottom:16px;width:330px;margin:0;z-index:2147483646';
        const status = line(box, 'Preparando CV e carta…');
        const opts = document.createElement('label');
        opts.style.cssText = 'font-size:12px;color:#555;display:flex;gap:4px;align-items:center;margin:4px 0';
        opts.innerHTML = '<input type="checkbox"> enviar sozinho no final (sem revisão)';
        const autoSubmit = opts.querySelector('input');
        chrome.storage.local.get('autoSubmit', (v) => { autoSubmit.checked = !!(v && v.autoSubmit); });
        autoSubmit.addEventListener('change', () => chrome.storage.local.set({ autoSubmit: autoSubmit.checked }));
        const stop = button('Parar', () => closeAutopilot('Auto Apply encerrado'), false);
        const pause = button('⏸ Pausar', () => setPaused(!paused), false);
        pause.classList.add('careerops-pause');
        box.append(opts, pause, stop);
        document.documentElement.appendChild(box);
        const ap = autopilot = { jobId: pending.jobId, linkedinJobId: jobOnPage, box, status, autoSubmit, prep: {}, uploaded: false, lastSig: '', running: false, done: false, steps: 0 };
        const res = await backend('POST', `/jobs/${pending.jobId}/auto-apply/prepare`, {});
        if (ap.done) return;   // closed meanwhile (Parar, or you left the job)
        if (!res.ok) { apStatus(errText(res), '#d63031'); managedStuck(res.status === 422 ? 'content_blocked' : 'documents_failed', errText(res)); return; }
        ap.prep = res.data;
        const btn = await waitFor(() => [...document.querySelectorAll('main button, main a')].find((b) => !own(b) && b.offsetParent !== null
            && (EASY.test(label(b)) || APPLY_EXT.test(label(b)))), 12000);
        if (ap.done) return;
        if (!btn) {
            apStatus('Não achei o botão de candidatura nesta página (vaga encerrada ou já candidatado?).', '#d63031');
            const page = ((document.querySelector('main') || {}).innerText || '');
            if (ALREADY_APPLIED.test(page)) managedStuck('already_applied', 'A página mostra candidatura já enviada');
            else if (JOB_CLOSED.test(page)) managedStuck('job_closed', 'Vaga encerrada');
            else managedStuck('selector_not_found', 'Botão de candidatura não encontrado');
            return;
        }
        if (EASY.test(label(btn))) {
            apStatus('Abrindo o Easy Apply…');
            btn.click();
            // a click before LinkedIn has wired the button does nothing (2026-11-03): try again, then say so instead of
            // waiting for a form that never comes
            for (let k = 0; k < 2 && !(await waitFor(easyApplyModal, 10000)); k++) {
                if (ap.done) return;
                const again = [...document.querySelectorAll('main button, main a')].find((b) => !own(b) && b.offsetParent !== null && EASY.test(label(b)));
                if (again) { apStatus('O Easy Apply não abriu: clicando de novo…'); again.click(); }
            }
            if (!ap.done && !easyApplyModal()) {
                apStatus('O formulário do Easy Apply não abriu.', '#d63031');
                managedStuck('step_stuck', 'O formulário do Easy Apply não abriu depois de 3 cliques');
            }
        } else if (managedRun) {
            // The worker catches the tab this click opens and passes its address to the backend
            apStatus('Candidatura no site da empresa: passando o endereço ao sistema…');
            await managedApi('POST', `/automation/actions/${managedRun.id}/events`, { source: 'extension', event: 'external_apply_click', data: {} });
            btn.click();
        } else {
            apStatus('Esta vaga é no site da empresa: abrindo… o painel CareerOps continua lá (anexa o CV e preenche).');
            await message({ action: 'applyHandoff' });
            btn.click();
        }
    }

    function closeAutopilot(text) {
        autopilot.done = true;
        autopilot.box.remove();
        autopilot = null;
        message({ action: 'applyStop' });
        activity(text);
    }

    async function finishApplied() {
        autopilot.done = true;
        if (managedRun) {   // the backend marks the job once the worker has seen it on the page
            await message({ action: 'applyStop' });
            apStatus('Candidatura enviada: conferindo…', '#00b894');
            return;
        }
        const r = await backend('PATCH', `/jobs/${autopilot.jobId}/status`, { status: 'applied' });
        await message({ action: 'applyStop' });
        apStatus(r.ok ? '✓ Candidatura enviada — vaga marcada como "Candidatado" no CareerOps.' : `Enviada. ${errText(r)}`, '#00b894');
    }

    const FIELD_ERROR = /this field is required|please (make a selection|enter a valid)|campo (é )?obrigat[oó]rio|selecione uma op[cç][aã]o|dieses feld ist erforderlich|este campo es obligatorio/i;

    async function driveAutopilot() {
        const ap = autopilot;
        if (ap && ap.box) { const b = ap.box.querySelector('.careerops-pause'); if (b) b.textContent = paused ? '▶ Continuar' : '⏸ Pausar'; }
        if (!ap || ap.done || ap.running || !ap.prep.job || paused) return;   // paused: this step is looked at when you continue
        if (deepAll('div[role="dialog"], .artdeco-modal, dialog[open]').some((d) => shown(d) && SENT.test(d.innerText))) { finishApplied(); return; }
        const modal = easyApplyModal();
        if (!modal) return;
        const panel = modal.querySelector('.careerops-apply');
        if (!panel) return;   // nothing was filled or checked on this step yet: looked at again once the panel is there
        const footer = [...modal.querySelectorAll('button')].filter((b) => !own(b) && b.offsetParent !== null && !b.disabled);
        const sig = collectFields(modal).map((f) => f.key).join('|') + '#' + footer.map(label).join('|') + '#' + (modal.querySelector('h3, h2') || {}).innerText;
        if (sig === ap.lastSig) return;   // same step: waiting for you or for LinkedIn
        ap.lastSig = sig;
        ap.running = true;
        try {
            await wait(800);
            const result = await fillStep(modal, panel);
            const clear = globalThis.careeropsApplyRules.stepClear(result);
            const buttons = [...modal.querySelectorAll('button')].filter((b) => !own(b) && b.offsetParent !== null && !b.disabled);
            const submit = buttons.find((b) => SUBMIT_APP.test(label(b)));
            if (submit) {
                if (managedRun) { await managedFinalStep(ap, submit, result, clear); return; }
                if (ap.autoSubmit.checked && clear) {
                    apStatus('Enviando a candidatura…');
                    await wait(800);
                    if (!ap.done && submit.isConnected) submit.click();
                    return;
                }
                submit.style.outline = '3px solid #00b894';
                apStatus('✓ Tudo preenchido. Revise e clique em "Enviar candidatura" — eu marco a vaga como candidatada.', '#00b894');
                return;
            }
            if (!clear) {
                apStatus('Complete os campos em laranja/amarelo e clique em Avançar — continuo na próxima etapa.', '#b7791f');
                managedQuestions(result);
                return;
            }
            const next = buttons.find((b) => NEXT.test(label(b)));
            if (!next) {
                apStatus('Não achei o botão Avançar — siga você; continuo quando a etapa mudar.', '#b7791f');
                managedStuck('step_stuck', 'Botão Avançar não encontrado nesta etapa');
                return;
            }
            ap.steps++;
            apStatus(`Etapa ${ap.steps} preenchida — avançando…`);
            await wait(700 + Math.random() * 600);   // a pause here holds the click until you continue
            if (ap.done || !next.isConnected) return;
            next.click();
            await wait(1800);
            // the old form's error classes, or (late 2026, hashed classes) the message itself / aria-invalid
            if (modal.querySelector('.artdeco-inline-feedback--error, [data-test-form-element-error-messages], [aria-invalid="true"]')
                || FIELD_ERROR.test(modal.innerText || '')) {
                // same step stays marked: wait for you (no retry loop); the next step changes the signature
                apStatus('O LinkedIn marcou campos nesta etapa: corrija e clique em Avançar — continuo depois.', '#b7791f');
                managedQuestions({ questions: collectFields(modal).filter((f) => !f.current).map((f) => ({ key: f.key, label: f.label, type: f.type, options: f.options })) }, 'O LinkedIn recusou uma resposta nesta etapa');
            }
        } finally {
            ap.running = false;
        }
    }

    // ── 8. Managed execution (browser on the server): what you approved in the app, opened by the worker at
    // <url>#careerops-run=<action>.<nonce>. The backend says what may be done; without its answer nothing happens. Every
    // outcome is reported: the worker looks at the page before a write counts as done.
    const ALREADY_APPLIED = /\b(applied \d|application submitted|you applied|candidatou-se|candidatura enviada|voc[eê] se candidatou)\b/i;
    const JOB_CLOSED = /no longer accepting applications|n[aã]o (est[aá] mais )?aceita(ndo)? candidaturas|vaga (foi )?encerrada/i;
    const FOLLOW = /^(\+\s*)?(follow|seguir)\b/i;
    const FOLLOWING = /^(following|seguindo)\b/i;
    const INVITE_LIMIT = /weekly invitation limit|limite semanal de convites/i;
    let managedRun = null;
    let managedStarted = false;

    const managedApi = (method, path, body) => backend(method, path, body);
    const managedReady = async () => !!(await chrome.storage.local.get('careeropsManaged')).careeropsManaged;

    function managedStuck(code, text, questions) {
        if (!managedRun || managedRun.closed) return;
        managedRun.closed = true;
        managedApi('POST', `/automation/actions/${managedRun.id}/escalate`, { code, text: String(text || '').slice(0, 1900), questions: questions || [] });
        activity(`Automação: ${code}`);
    }

    function managedQuestions(result, text) {
        if (!managedRun) return;
        const questions = (result && result.questions) || [];
        managedStuck(questions.length ? 'unknown_required_question' : 'step_stuck', text || 'Perguntas sem resposta nesta etapa', questions);
    }

    // Said BEFORE the final click, never after: the page may reload right away and this script with it. From here on the
    // action is never clicked again; the worker looks at the page to tell whether it went out. No answer, no click.
    async function managedExecuted(data) {
        if (!managedRun || managedRun.closed) return false;
        managedRun.closed = true;
        const res = await managedApi('POST', `/automation/actions/${managedRun.id}/complete`, { outcome: 'executed', data: data || {} });
        if (!res.ok) activity('Automação: o sistema não confirmou: nada foi clicado');
        return res.ok;
    }
    function managedDry(data) {
        if (!managedRun || managedRun.closed) return Promise.resolve();
        managedRun.closed = true;
        return managedApi('POST', `/automation/actions/${managedRun.id}/complete`, { outcome: 'dry_run', data: data || {} });
    }
    function managedRead(data) {
        if (!managedRun || managedRun.closed) return Promise.resolve();
        managedRun.closed = true;
        return managedApi('POST', `/automation/actions/${managedRun.id}/complete`, { outcome: 'read', data: data || {} });
    }

    // Last screen of the form. Nothing unanswered, permission from the backend, and your click on the first ones.
    async function managedFinalStep(ap, submit, result, clear) {
        if (!clear) { managedQuestions(result); return; }
        if (!managedRun.info.allow_final) {
            apStatus('Modo de teste: tudo preenchido, sem enviar.', '#00b894');
            await managedDry({ fields: managedRun.fields, reached_final_step: true });
            return;
        }
        if (managedRun.info.confirm_required) {
            apStatus('Aguardando sua confirmação no app…', '#b7791f');
            await managedApi('POST', `/automation/actions/${managedRun.id}/ready`, { fields: managedRun.fields });
            for (;;) {
                await sleep(4000);
                const r = await managedApi('GET', `/automation/actions/${managedRun.id}/run?nonce=${encodeURIComponent(managedRun.nonce)}`);
                if (r.ok && r.data.confirmed) break;
                if (!r.ok || r.data.status !== 'awaiting_confirm' || r.data.halted) { apStatus('Envio não confirmado: parado.', '#d63031'); return; }
            }
        }
        await gate();
        if (ap.done || !submit.isConnected) { managedStuck('step_stuck', 'O botão de envio saiu da tela'); return; }
        apStatus('Enviando a candidatura…');
        if (await managedExecuted({ fields: managedRun.fields })) submit.click();
    }

    async function managedConnect() {
        const card = await waitFor(profileTopCard, 15000);
        if (!card) { managedStuck('selector_not_found', 'Perfil não carregou'); return; }
        await wait(1200);   // let the action row finish rendering
        const actions = () => [...card.querySelectorAll('button, a')].filter((b) => b.offsetParent !== null).map(btnLabel);
        if (actions().some((l) => PENDING.test(l))) { managedStuck('already_pending', 'Convite já pendente'); return; }
        if (!managedRun.info.allow_final) {
            const target = await findConnect(card);
            if (!target) { managedStuck(actions().some((l) => /^(mensagem|message)$/.test(l)) ? 'already_connected' : 'selector_not_found', 'Sem botão Conectar'); return; }
            await managedDry({ found: 'connect' });
            return;
        }
        const result = await connectNoNote(() => managedExecuted({ connect: 'sent' }));
        if (document.body && INVITE_LIMIT.test(document.body.innerText)) { managedRun.closed = false; managedStuck('weekly_invite_limit', 'O LinkedIn avisou do limite semanal de convites'); return; }
        const route = {
            sent: () => managedExecuted({ connect: 'sent' }),   // no dialog on this profile: it went out with the first click
            pending: () => managedStuck('already_pending', 'Convite já pendente'),
            connected: () => managedStuck('already_connected', 'Já conectados'),
            unavailable: () => managedStuck('selector_not_found', 'Botão Conectar não encontrado'),
            needs_user: () => managedStuck('invite_needs_email', 'O LinkedIn pediu algo a mais (ex.: e-mail)'),
        }[result];
        await route();
    }

    async function managedFollow() {
        const root = /\/in\//.test(location.pathname) ? await waitFor(profileTopCard, 15000) : await waitFor(() => document.querySelector('main'), 15000);
        if (!root) { managedStuck('selector_not_found', 'Página não carregou'); return; }
        await wait(1200);
        const visible = (selector) => [...root.querySelectorAll(selector)].filter((b) => b.offsetParent !== null && !own(b));
        const top = /\/company\//.test(location.pathname) ? (root.querySelector('section') || root) : root;
        const buttonsIn = (box) => [...box.querySelectorAll('button, [role="button"]')].filter((b) => b.offsetParent !== null && !own(b));
        if (buttonsIn(top).some((b) => FOLLOWING.test(btnLabel(b)))) { managedStuck('already_following', 'Já segue'); return; }
        let btn = buttonsIn(top).find((b) => FOLLOW.test(btnLabel(b)));
        if (!btn) {   // on many profiles it sits in the "More" menu
            const more = visible('button, [role="button"]').find(isMoreButton);
            if (more) {
                more.click();
                btn = await waitFor(() => [...document.querySelectorAll('[role="menuitem"], [role="button"], button, div[aria-label]')]
                    .find((e) => e.offsetParent !== null && FOLLOW.test(btnLabel(e))), 2500);
                if (!btn) { const again = buttonsIn(document).find((b) => FOLLOWING.test(btnLabel(b))); if (again) { managedStuck('already_following', 'Já segue'); return; } more.click(); }
            }
        }
        if (!btn) { managedStuck('selector_not_found', 'Botão Seguir não encontrado'); return; }
        if (!managedRun.info.allow_final) { await managedDry({ found: 'follow' }); return; }
        await gate();
        if (await managedExecuted({ follow: true })) btn.click();
    }

    // The comment goes on the post that was approved and with the approved text, or not at all
    async function managedComment() {
        const { text, post_head: head } = managedRun.info.payload;
        const post = await waitFor(() => findPosts()[0], 15000);
        if (!post) {
            const page = ((document.querySelector('main') || document.body).innerText || '');
            managedStuck(/this (post|page) (cannot|can't|doesn't)|n[aã]o (est[aá] dispon[ií]vel|existe)|content isn.t available/i.test(page) ? 'post_deleted' : 'selector_not_found', 'Post não encontrado na página');
            return;
        }
        await wait(800);
        const key = (t) => (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 60);
        if (head && key(postInfo(post).post_text).slice(0, 40) !== key(head).slice(0, 40)) {
            managedStuck('unexpected_layout', 'O post desta página não é o que foi aprovado');
            return;
        }
        // a page with one post may keep its comment box outside the post's card (LinkedIn's layout of late 2026)
        const single = /^\/(feed\/update|posts)\//.test(location.pathname) && findPosts().length === 1;
        const ed = await openCommentBox(post) || (single && await openCommentBox(document.querySelector('main') || document.body));
        if (!ed) { managedStuck('selector_not_found', 'Caixa de comentário não encontrada'); return; }
        await gate();
        fill(ed, text);
        await wait(700);
        const words = (t) => (t || '').replace(/\s+/g, ' ').trim();   // the box may break lines its own way
        if (words(ed.innerText) !== words(text)) { managedStuck('step_stuck', 'O texto digitado saiu diferente do aprovado: não publiquei'); return; }
        if (!managedRun.info.allow_final) { await managedDry({ typed: true }); return; }
        // the nearest button up from the box: the post's own "Comentar" (which only opens the box) is further away
        const nearestSubmit = () => {
            for (let box = ed.parentElement, k = 0; box && k < 8; box = box.parentElement, k++) {
                const b = [...box.querySelectorAll('button')].find((x) => !own(x) && x.offsetParent !== null && !x.disabled
                    && (x.className.includes('comments-comment-box__submit-button') || SUBMIT.test(label(x))));
                if (b) return b;
            }
            return null;
        };
        const submit = await waitFor(nearestSubmit, 4000);
        if (!submit) { managedStuck('selector_not_found', 'Botão Publicar não encontrado'); return; }
        await gate();
        if (await managedExecuted({ commented: true })) submit.click();
    }

    const searchCards = () => {
        const cards = new Map();
        // late 2026 (/jobs/search-results/): no links per card; each one is a div[role=button] keyed by the job id, its lines
        // the title (twice, the first may end in "(Verified job)"), the company and the place
        document.querySelectorAll('[role="button"][componentkey^="job-card-component-ref-"]').forEach((el) => {
            const id = (el.getAttribute('componentkey').match(/(\d+)$/) || [])[1];
            if (!id || cards.has(id)) return;
            const text = el.innerText || '';
            const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
            const title = (lines[0] || '').replace(/\s*\((verified job|vaga verificada)\)\s*$/i, '');
            const rest = lines[1] === title ? lines.slice(2) : lines.slice(1);
            cards.set(id, {
                id, title, company: rest[0] || '', location: rest[1] || '',
                easy_apply: /easy apply|candidatura simplificada/i.test(text),
                posted: (text.match(/(\d+\s*(minutes?|hours?|days?|weeks?|months?)\s*ago|h[aá]\s*\d+\s*(minutos?|horas?|dias?|semanas?|m[eê]s(es)?)|just now|agora mesmo)/i) || [])[0] || '',
            });
        });
        document.querySelectorAll('[data-job-id], a[href*="/jobs/view/"], a[href*="currentJobId="]').forEach((el) => {
            const id = el.getAttribute('data-job-id') || ((el.href || '').match(/\/jobs\/view\/(\d+)/) || [])[1] || ((el.href || '').match(/currentJobId=(\d+)/) || [])[1];
            if (!id || !/^\d+$/.test(id) || cards.has(id)) return;
            const box = el.closest('li, [data-occludable-job-id], .job-card-container, .jobs-search-results__list-item') || el;
            const text = box.innerText || '';
            const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
            cards.set(id, {
                id, title: lines[0] || '', company: lines[1] || '', location: lines[2] || '',
                easy_apply: /easy apply|candidatura simplificada/i.test(text),
                posted: (box.querySelector('time') || {}).innerText || (text.match(/(\d+\s*(minutes?|hours?|days?|weeks?|months?)\s*ago|h[aá]\s*\d+\s*(minutos?|horas?|dias?|semanas?|m[eê]s(es)?)|just now|agora mesmo)/i) || [])[0] || '',
            });
        });
        return [...cards.values()].slice(0, 25);
    };

    async function managedSearch() {
        await waitFor(() => searchCards().length, 20000);
        await wait(1500);
        const cards = searchCards();
        if (!cards.length) {
            const page = (document.querySelector('main') || document.body).innerText || '';
            if (/no matching jobs|nenhuma vaga|no results|sem resultados/i.test(page)) { await managedRead({ cards: 0, added: 0 }); return; }
            managedStuck('unexpected_layout', 'Lista de vagas não reconhecida');
            return;
        }
        const seen = await managedApi('POST', '/automation/discovered/unseen', { ids: cards.map((c) => c.id) });
        if (!seen.ok) { managedStuck('unexpected_layout', errText(seen)); return; }
        const fresh = cards.filter((c) => seen.data.unseen.includes(c.id)).slice(0, Math.max(seen.data.budget, 0));
        const jobs = [];
        for (const c of fresh) {
            await gate();
            const extra = await jobPosting(c.id);
            if (extra.description) jobs.push({ linkedin_job_id: c.id, title: extra.title || c.title, company: extra.company || c.company, location: extra.location || c.location, description: extra.description, posted: c.posted, easy_apply: c.easy_apply });
            await wait(1500 + Math.random() * 1000);
        }
        const added = jobs.length ? await managedApi('POST', '/automation/discovered', { jobs, search: managedRun.info.payload.search || null }) : { ok: true, data: { added: 0 } };
        await managedRead({ cards: cards.length, unseen: fresh.length, added: added.ok ? added.data.added : 0 });
    }

    // Your saved jobs, every page of the list (at most 5): the new ones are read from their public ad and go in as "new",
    // like the import button does. Nothing is clicked but the list's own "Next".
    const NO_SAVED = /no saved jobs|nenhuma vaga salva|you haven.t saved|voc[eê] ainda n[aã]o salvou|\bsaved\s*·\s*0\b|\bsalvas?\s*·\s*0\b/i;
    async function managedSavedImport() {
        const cards = new Map();
        let pages = 0;
        await waitFor(() => savedJobsOnScreen().length || NO_SAVED.test((document.querySelector('main') || document.body).innerText || ''), 20000);
        for (; pages < 5; pages++) {
            await wait(1500);
            const onScreen = savedJobsOnScreen();
            onScreen.forEach((j) => cards.has(j.id) || cards.set(j.id, j));
            const next = onScreen.length && savedNextButton();
            if (!next) { pages++; break; }
            const first = onScreen[0].id;
            await gate();
            next.click();
            if (!(await waitFor(() => { const now = savedJobsOnScreen(); return now.length && now[0].id !== first; }, 15000))) { pages++; break; }
        }
        if (!cards.size) {
            if (NO_SAVED.test((document.querySelector('main') || document.body).innerText || '')) { await managedRead({ cards: 0, known: 0, added: 0, promoted: 0 }); return; }
            managedStuck('unexpected_layout', 'Lista de vagas salvas não reconhecida');
            return;
        }
        const all = [...cards.values()];
        const seen = await managedApi('POST', '/automation/discovered/unseen', { ids: all.map((c) => c.id).slice(0, 100) });
        if (!seen.ok) { managedStuck('unexpected_layout', errText(seen)); return; }
        const fresh = all.filter((c) => seen.data.unseen.includes(c.id)).slice(0, 40);
        const jobs = [];
        for (const c of fresh) {
            await gate();
            const extra = await jobPosting(c.id);
            if (extra.description) jobs.push({ linkedin_job_id: c.id, title: extra.title || c.title, company: extra.company || c.company, location: extra.location || c.location, description: extra.description, easy_apply: !!c.easy_apply });
            await wait(1500 + Math.random() * 1000);
        }
        const res = await managedApi('POST', '/automation/saved-jobs', { jobs, ids: all.map((c) => c.id).slice(0, 200) });
        if (!res.ok) { managedStuck('unexpected_layout', errText(res)); return; }
        await managedRead({ cards: all.length, pages, known: all.length - fresh.length, unseen: fresh.length, no_text: fresh.length - jobs.length,
                            added: res.data.added, promoted: res.data.promoted });
    }

    async function managedFeedScan() {
        await waitFor(() => findPosts().length, 20000);
        for (let k = 0; k < 4; k++) { window.scrollBy(0, window.innerHeight); await wait(1500 + Math.random() * 800); }
        const limit = managedRun.info.payload.limit || 8;
        let added = 0;
        for (const post of findPosts().slice(0, limit)) {
            await gate();
            const info = postInfo(post);
            if (info.post_text.length < 40 || !info.post_url) continue;
            const res = await api('POST', '/engagement', info);
            if (res.ok && res.data.status !== 'skipped') added++;
            await wait(1000);
        }
        await managedRead({ added });
    }

    async function managedFollowScan() {
        const { mode, why, market } = managedRun.info.payload;
        const pattern = mode === 'company' ? /\/company\/[^/?#]+/ : /\/in\/[^/?#]+/;
        await waitFor(() => document.querySelector(`main a[href*="/${mode === 'company' ? 'company' : 'in'}/"]`), 20000);
        await wait(1500);
        const targets = new Map();
        document.querySelectorAll('main a[href]').forEach((a) => {
            const m = (a.href || '').match(pattern);
            const name = clean(a.innerText).split('\n')[0];
            if (!m || !name || targets.has(m[0])) return;
            targets.set(m[0], { url: `https://www.linkedin.com${m[0]}`, name: name.slice(0, 200), why: why || '', market: market || null });
        });
        const list = [...targets.values()].slice(0, mode === 'company' ? 1 : 3);
        const res = list.length ? await managedApi('POST', '/automation/follow-targets', { targets: list }) : { ok: true, data: { proposed: 0 } };
        await managedRead({ proposed: res.ok ? res.data.proposed : 0 });
    }

    async function managedStart() {
        const m = location.hash.match(/careerops-run=(\d+)\.([\w-]+)/);
        if (!m || managedStarted || !(await managedReady())) return;
        managedStarted = true;
        const nonce = m[2];
        const res = await managedApi('GET', `/automation/actions/${m[1]}/run?nonce=${encodeURIComponent(nonce)}`);
        if (!res.ok) { activity('Automação: ação não reconhecida pelo sistema'); return; }   // nothing happens without the backend's word
        const info = res.data;
        if (info.status !== 'running_ext' || info.halted) return;
        managedRun = { id: info.id, nonce, info, fields: [], closed: false };
        history.replaceState(null, '', location.pathname + location.search);
        activity(`Automação: ${info.kind}`);
        const run = { apply: managedApply, connect: managedConnect, follow: managedFollow, comment: managedComment, search: managedSearch, check: managedCheck, feed_scan: managedFeedScan, follow_scan: managedFollowScan, saved_import: managedSavedImport }[info.kind];
        try {
            await run();
        } catch (e) {
            managedStuck('unexpected_layout', e && e.message);
        }
    }

    async function managedApply() {
        const job = currentJobId();
        await message({ action: 'applyStart', jobId: managedRun.info.target_id, linkedinJobId: job });
        applyCheckedFor = null;
        await startAutopilot();
        if (autopilot) autopilot.autoSubmit.checked = false;   // the final click is decided in managedFinalStep, never by the checkbox
    }

    // Reads the three lists like the 12-hourly check does, and tells the queue when it ends
    async function managedCheck() {
        setCheckState({ step: 'connections', background: true, managedRun: managedRun.id });
        if (!/^\/mynetwork\/invite-connect\/connections/.test(location.pathname)) { location.href = CONNECTIONS_URL; return; }
        runProspectCheck();
    }

    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action !== 'importSavedJobs') return;
        importSavedJobs(savedBtn).then(sendResponse);
        return true;
    });

    // ── 5. Prospect check: who accepted / replied (reads two lists, opens no profile, clicks nothing on people) ──
    // Started by <connections page>#careerops-check (from the app, the popup or the 12 h alarm in background.js).
    // Step 1 reads My Network → Connections (newest first), step 2 the pending Sent invitations (also the ones sent from
    // LinkedIn itself, which the extension never saw), step 3 the Messaging list; the backend matches all three against
    // the prospects. The step survives the page changes in sessionStorage (same tab only).
    const CHECK_KEY = 'careeropsProspectCheck';
    const CONNECTIONS_URL = 'https://www.linkedin.com/mynetwork/invite-connect/connections/';
    const SENT_URL = 'https://www.linkedin.com/mynetwork/invitation-manager/sent/';
    const checkState = () => { try { return JSON.parse(sessionStorage.getItem(CHECK_KEY) || 'null'); } catch (e) { return null; } };
    const setCheckState = (v) => { try { v ? sessionStorage.setItem(CHECK_KEY, JSON.stringify(v)) : sessionStorage.removeItem(CHECK_KEY); } catch (e) { /* private mode */ } };
    let checkPanel = null;
    const checkStatus = (text, color = '#555') => {
        if (!checkPanel) {
            checkPanel = card('CareerOps · verificar prospecção');
            checkPanel.style.cssText += ';position:fixed;right:16px;top:72px;width:340px;margin:0;z-index:2147483646';
            document.documentElement.appendChild(checkPanel);
            checkPanel.__status = line(checkPanel, '');
        }
        checkPanel.__status.textContent = text;
        checkPanel.__status.style.color = color;
        activity(`Verificação de prospecção: ${text}`);
    };

    // Both lists scroll inside their own box (Connections: <main>, Messaging: the conversation <ul>), not the window
    function scrollParent(el) {
        for (; el && el !== document.body; el = el.parentElement) {
            if (/(auto|scroll)/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
        }
        return document.scrollingElement;
    }

    // Waits until a list stops growing on its own (first render), up to ~6 s
    async function settle(count) {
        let last = -1;
        for (let i = 0; i < 12 && count() !== last; i++) { last = count(); await wait(500); }
    }

    // Lists load more as you scroll (or with "Show more results"): a few rounds, stopping after two that bring nothing.
    // The scroll box is looked up each round from an item: right after the first items appear the box is not
    // scrollable yet, and scrolling the window instead loads nothing.
    async function loadMore(count, item, rounds = 6) {
        await settle(count);
        let last = count(), idle = 0;
        for (let i = 0; i < rounds && idle < 2; i++) {
            const scroller = scrollParent(item());
            scroller.scrollTop = scroller.scrollHeight;
            const more = [...document.querySelectorAll('main button')].find((b) => b.offsetParent !== null
                && /^(mostrar mais resultados|exibir mais resultados|show more results|load more|carregar mais)$/i.test(label(b)));
            if (more) more.click();
            await wait(1800);
            idle = count() > last ? 0 : idle + 1;
            last = count();
        }
    }

    function readConnections() {
        const seen = new Map();
        document.querySelectorAll('main a[href*="/in/"]').forEach((a) => {
            const m = a.href.match(/https:\/\/www\.linkedin\.com\/in\/[^/?#]+/);
            if (!m) return;
            const name = clean(a.innerText).split('\n').map((s) => s.trim()).find((s) => s && !/^(membro do linkedin|linkedin member)$/i.test(s));
            if (name && (!seen.get(m[0]) || !seen.get(m[0]).name)) seen.set(m[0], { profile_url: m[0], name: name.slice(0, 200) });
            else if (!seen.has(m[0])) seen.set(m[0], { profile_url: m[0], name: null });
        });
        return [...seen.values()];
    }

    // Sent invitations: the profile links carry no text; the name is the first line of the card (the block holding "Withdraw")
    function readSent() {
        const seen = new Map();
        document.querySelectorAll('main a[href*="/in/"]').forEach((a) => {
            const m = a.href.match(/https:\/\/www\.linkedin\.com\/in\/[^/?#]+/);
            if (!m || seen.has(m[0])) return;
            let card = a;
            while (card.parentElement && card.parentElement.tagName !== 'MAIN' && !/\b(withdraw|retirar)\b/i.test(card.innerText || '')) card = card.parentElement;
            const name = /\b(withdraw|retirar)\b/i.test(card.innerText || '') ? clean(card.innerText).split('\n')[0] : '';
            seen.set(m[0], { profile_url: m[0], name: name.slice(0, 200) || null });
        });
        return [...seen.values()];
    }

    const CONVO = '.msg-conversation-listitem, .msg-conversations-container__convo-item, li[class*="conversation-listitem"]';
    function readConversations() {
        return [...document.querySelectorAll(CONVO)].filter((li) => !li.parentElement.closest(CONVO)).map((li) => {
            const q = (sel) => clean((li.querySelector(sel) || {}).innerText || '');
            const name = q('.msg-conversation-listitem__participant-names, .msg-conversation-card__participant-names, h3') || clean(li.innerText).split('\n')[0];
            const snippet = q('.msg-conversation-card__message-snippet, [class*="message-snippet"], p');
            const link = li.querySelector('a[href*="/in/"]');
            return {
                name: name.slice(0, 200),
                profile_url: link ? (link.href.match(/https:\/\/www\.linkedin\.com\/in\/[^/?#]+/) || [null])[0] : null,
                // the list shows the last message: "Você: …" / "You: …" when it was yours; "Sponsored • …" is an ad
                replied: !!snippet && !/^\s*(voc[eê]|you)\s*(:|enviou|sent)/i.test(snippet)
                    && !/^\s*(sponsored|patrocinad[ao]|linkedin offer|inmail)\b/i.test(snippet),
            };
        }).filter((c) => c.name && !c.name.includes(','));   // group conversations: no single person to match
    }

    async function runProspectCheck() {
        const state = checkState();
        if (!state) return;
        if (document.hidden) state.hidden = true;   // carried by the next steps' saved state
        if (state.step === 'connections') {
            if (!/^\/mynetwork\/invite-connect\/connections/.test(location.pathname)) return;
            checkStatus('Lendo suas conexões mais recentes…');
            const first = await waitFor(() => document.querySelector('main a[href*="/in/"]'), 20000);
            if (first) await loadMore(() => document.querySelectorAll('main a[href*="/in/"]').length, () => document.querySelector('main a[href*="/in/"]'), 8);
            const connections = readConnections();
            setCheckState({ ...state, step: 'sent', connections });
            checkStatus(`${connections.length} conexões lidas. Abrindo os convites enviados…`);
            await wait(800);
            location.href = SENT_URL;
            return;
        }
        if (state.step === 'sent') {
            if (!/^\/mynetwork\/invitation-manager\/sent/.test(location.pathname)) return;
            checkStatus('Lendo os convites enviados…');
            const first = await waitFor(() => document.querySelector('main a[href*="/in/"]')
                || /(no pending|nenhum convite|n[aã]o h[aá] convites)/i.test((document.querySelector('main') || {}).innerText || ''), 20000);
            if (first instanceof Element) await loadMore(() => document.querySelectorAll('main a[href*="/in/"]').length, () => document.querySelector('main a[href*="/in/"]'), 8);
            const sent = readSent();
            // the tab header says how many are pending ("People (11)" / "Pessoas (11)"): tells if the list came in whole
            const total = Number((((document.querySelector('main') || {}).innerText || '').match(/(?:people|pessoas)\s*\((\d+)\)/i) || [])[1]) || null;
            setCheckState({ ...state, step: 'messaging', sent, sentTotal: total });
            checkStatus(`${sent.length} convites pendentes lidos. Abrindo as mensagens…`);
            await wait(800);
            location.href = 'https://www.linkedin.com/messaging/';
            return;
        }
        if (state.step !== 'messaging' || !/^\/messaging/.test(location.pathname)) return;
        setCheckState(null);   // whatever happens next, the check ends on this page
        checkStatus('Lendo a lista de conversas…');
        const first = await waitFor(() => document.querySelector(CONVO), 20000);
        if (first) await loadMore(() => document.querySelectorAll(CONVO).length, () => document.querySelector(CONVO), 3);
        if (first) await settle(() => document.querySelectorAll(CONVO).length);
        const conversations = first ? readConversations() : [];
        const res = await api('POST', '/prospects/check', { connections: state.connections || [], sent: state.sent || [], conversations });
        let summary;
        if (!res.ok) {
            summary = errText(res);
            checkStatus(summary, '#d63031');
        } else {
            const d = res.data;
            const names = (list) => list.map((p) => p.name || '?').join(', ');
            summary = `${d.accepted.length} aceitaram, ${d.replied.length} responderam · ${d.waiting} convite(s) pendentes`
                + (d.invited.length ? ` (${d.invited.length} marcados agora como convidados)` : '');
            checkStatus(summary, d.accepted.length || d.replied.length || d.invited.length ? '#00b894' : '#555');
            if (d.invited.length) line(checkPanel, `Já convidados: ${names(d.invited)}`);
            if (d.accepted.length) line(checkPanel, `Aceitaram: ${names(d.accepted)}`);
            if (d.replied.length) line(checkPanel, `Responderam: ${names(d.replied)}`);
            if (!first) line(checkPanel, 'Não reconheci a lista de mensagens (o LinkedIn pode ter mudado): só as conexões foram verificadas.', '#b7791f');
            line(checkPanel, `Lidos: ${d.read.connections} conexões, ${d.read.sent}${state.sentTotal ? ` de ${state.sentTotal}` : ''} convites enviados, ${d.read.conversations} conversas.`, '#999');
            if (state.sentTotal && d.read.sent < state.sentTotal) line(checkPanel, `Faltaram ${state.sentTotal - d.read.sent} convites enviados (a lista não carregou toda)${state.hidden ? ': a aba ficou oculta — o Chrome não carrega listas em abas de fundo; deixe-a visível durante a verificação' : ''}.`, '#b7791f');
        }
        try { chrome.runtime.sendMessage({ action: 'prospectCheckDone', ok: res.ok, result: res.data, summary, background: !!state.background, managedRun: state.managedRun || null }, () => { void chrome.runtime.lastError; }); } catch (e) { /* extension reloaded */ }
    }

    function startProspectCheck() {
        const m = location.hash.match(/careerops-check(-bg)?/);
        if (!m) return;
        history.replaceState(null, '', location.pathname + location.search);
        setCheckState({ step: 'connections', background: !!m[1] });
        if (!/^\/mynetwork\/invite-connect\/connections/.test(location.pathname)) { location.href = CONNECTIONS_URL; return; }
        runProspectCheck();
    }

    // ── Floating buttons, re-evaluated as LinkedIn navigates (single-page app) ─────────────────────────
    const fab = document.createElement('div');
    fab.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483645;display:flex;gap:6px';
    // Invite button: placed in the profile's own action row (next to Connect/Message); if that row is not found it
    // floats at the top right, below LinkedIn's nav — the bottom right is covered by the messaging dock
    const inviteBtn = button('🤝 Conectar (CareerOps)', draftInvite);
    inviteBtn.style.cssText += ';font-size:14px;padding:8px 16px;border-radius:20px;margin:0 0 0 8px;white-space:nowrap;flex:0 0 auto';
    const inviteFloat = 'position:fixed;top:72px;right:16px;z-index:2147483646;margin:0;box-shadow:0 4px 14px rgba(0,0,0,.3)';
    function placeInvite() {
        if (!isProfilePage()) { inviteBtn.remove(); return; }
        const main = document.querySelector('main');
        const isAction = (b) => /^(conectar|connect|mensagem|message|seguir|follow|pendente|pending)\b/i.test(label(b)) && b.offsetParent !== null;
        const anchor = main && [...main.querySelectorAll('button, a')].find(isAction);
        if (anchor) {
            // climb to the item that sits in the row holding several actions
            let item = anchor;
            while (item.parentElement && item.parentElement !== main && item.parentElement.children.length < 2) item = item.parentElement;
            if (inviteBtn.previousElementSibling !== item) item.insertAdjacentElement('afterend', inviteBtn);
            inviteBtn.style.position = 'static';
            inviteBtn.style.boxShadow = 'none';
            inviteBtn.style.margin = '0 0 0 8px';
        } else if (inviteBtn.parentElement !== document.documentElement) {
            document.documentElement.appendChild(inviteBtn);
            inviteBtn.style.cssText += ';' + inviteFloat;
        }
    }
    // Visiting a connection's profile (degree "1st"/"1º" on the top card) marks them accepted in Prospecção
    let degreeCheckedFor = null;
    function checkProfileDegree() {
        if (!isProfilePage() || degreeCheckedFor === location.pathname) return;
        const head = profileHeading();
        const card = head && profileTopCard();
        if (!card) return;
        degreeCheckedFor = location.pathname;
        if (isFirstDegree(clean(card.innerText).split('\n').slice(0, 6).join('\n')) || [...card.querySelectorAll('span')].some((sp) => /^[·•]?\s*(1st|1º)$/i.test(clean(sp.innerText)))) {
            markConnected([{ profile_url: location.origin + (location.pathname.match(/^\/in\/[^/]+/) || [location.pathname])[0], name: clean(head.innerText) }]);
        }
    }
    const scoreBtn = button('⭐ Avaliar pessoas da página', () => scorePage(scoreBtn));
    const savedBtn = button('📥 Importar vagas salvas', () => importSavedJobs(savedBtn));
    fab.append(scoreBtn, savedBtn);
    document.documentElement.appendChild(fab);

    function refresh() {
        decoratePosts();
        decorateReplies();
        decorateEasyApply();
        decorateJobSave();
        if (currentJobId() && applyCheckedFor !== String(currentJobId())) startAutopilot();
        // left the job (feed, another job): this tab's Auto Apply ends, the company-site tab it opened goes on
        if (autopilot && String(currentJobId()) !== autopilot.linkedinJobId) closeAutopilot('Auto Apply encerrado: você saiu da vaga');
        driveAutopilot();
        // the job pane is reused when another job is opened: reset our button for the new job
        document.querySelectorAll('.careerops-jobbtn').forEach((b) => { if (b.dataset.job !== String(currentJobId())) b.remove(); });
        placeInvite();
        checkProfileDegree();
        const listPage = /\/search\/results\/people|\/mynetwork/.test(location.pathname);
        scoreBtn.style.display = listPage ? '' : 'none';
        savedBtn.style.display = isSavedJobsPage() ? '' : 'none';
    }
    const watcher = new MutationObserver(() => { clearTimeout(refresh.t); refresh.t = setTimeout(refresh, 400); });
    watcher.observe(document.documentElement, { childList: true, subtree: true });
    // changes inside LinkedIn's shadow-root dialogs are not seen from the document: watch that root too (it can be redrawn)
    let watchedRoot = null;
    setInterval(() => {
        const [root] = shadowRoots();
        if (root && root !== watchedRoot) { watcher.observe(root, { childList: true, subtree: true }); watchedRoot = root; }
    }, 1000);
    refresh();
    // pages that rewrite their address while loading (the new job search) lose the #fragment: the worker puts it back
    window.addEventListener('hashchange', () => { if (!managedRun && /careerops-run=/.test(location.hash)) managedStart(); });
    if (/careerops-run=/.test(location.hash)) {
        managedStart();
    } else {
        autoConnectFromApp();
        if (/careerops-check/.test(location.hash)) startProspectCheck(); else runProspectCheck();
    }
})();
