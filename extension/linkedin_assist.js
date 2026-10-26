// CareerOps — LinkedIn assist: AI comment drafts on posts, AI invite notes on profiles, and scoring of the people
// listed on a page. Everything is drafted and filled in for you; the final click (Publicar / Enviar / Conectar) is
// always yours. Nothing is posted, sent, liked or followed by this script.
(() => {
    if (window.__careeropsAssist) return;
    window.__careeropsAssist = true;

    const ACCENT = '#6c5ce7';
    const api = (method, path, body) => new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: 'copilotApi', method, path, body }, (res) => {
            resolve(res || { ok: false, data: { detail: 'Sem resposta da extensão' } });
        });
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
        const t = document.createElement('div');
        t.textContent = msg;
        t.style.cssText = `position:fixed;right:16px;bottom:72px;z-index:2147483647;background:${ok ? '#00b894' : '#d63031'};color:#fff;
            padding:8px 12px;border-radius:8px;font:13px system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.2)`;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    }

    // Puts text into LinkedIn's editors: contenteditable (comment box) or textarea (invite note)
    function fill(el, text) {
        el.focus();
        if (el.isContentEditable) {
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, text);
        } else {
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    async function waitFor(fn, timeout = 4000) {
        const end = Date.now() + timeout;
        while (Date.now() < end) { const v = fn(); if (v) return v; await wait(150); }
        return null;
    }
    const byText = (root, selector, words) => [...root.querySelectorAll(selector)]
        .find((el) => words.some((w) => (el.innerText || el.getAttribute('aria-label') || '').toLowerCase().includes(w)));

    // ── 1. Posts: "✨ Comentário IA" ──────────────────────────────────────────────────────────────────
    const POST_SELECTOR = 'div[data-urn^="urn:li:activity"], div[data-id^="urn:li:activity"], article[data-urn^="urn:li:activity"]';

    function postInfo(post) {
        const urn = post.getAttribute('data-urn') || post.getAttribute('data-id') || '';
        const textEl = post.querySelector('.update-components-text, .feed-shared-inline-show-more-text, .feed-shared-update-v2__description, [data-test-id="main-feed-activity-card__commentary"]');
        const authorEl = post.querySelector('.update-components-actor__title span[aria-hidden="true"], .update-components-actor__name, .feed-shared-actor__name');
        const headlineEl = post.querySelector('.update-components-actor__description span[aria-hidden="true"], .update-components-actor__description');
        return {
            post_url: urn ? `https://www.linkedin.com/feed/update/${urn}/` : null,
            post_text: clean(textEl ? textEl.innerText : post.innerText).slice(0, 6000),
            author_name: authorEl ? clean(authorEl.innerText) : null,
            author_headline: headlineEl ? clean(headlineEl.innerText).slice(0, 300) : null,
        };
    }

    const EDITOR = '.ql-editor[contenteditable="true"], div[role="textbox"][contenteditable="true"]';
    const visibleEditor = (post) => [...post.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !el.closest('.careerops-card'));

    async function openCommentBox(post) {
        const open = visibleEditor(post);
        if (open) return open;
        const btn = [...post.querySelectorAll('button')].find((b) => !b.closest('.careerops-card') && !b.closest('.careerops-bar')
            && ['comentar', 'comment'].includes((b.getAttribute('aria-label') || b.innerText || '').trim().toLowerCase()));
        if (btn) btn.click();
        return waitFor(() => visibleEditor(post));
    }

    async function draftComment(post, anchor) {
        post.querySelectorAll('.careerops-card').forEach((c) => c.remove());
        const box = card('CareerOps · comentário');
        anchor.insertAdjacentElement('afterend', box);
        const status = line(box, 'Analisando o post…');
        const info = postInfo(post);
        if (info.post_text.length < 20) { status.textContent = 'Não encontrei o texto deste post.'; return; }
        const res = await api('POST', '/engagement', info);
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const item = res.data;
        status.textContent = `Relevância ${item.relevance ?? '?'} — ${item.reason || ''}`;
        if (item.status === 'skipped' || !item.comment_draft) {
            line(box, 'A IA sugere não comentar este post (pouco ligado aos seus mercados).', '#999');
            box.appendChild(button('Comentar mesmo assim', () => api('PATCH', `/engagement/${item.id}`, { status: 'pending' }).then(() => toast('Volta para a fila: rascunhe à mão')), false));
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
        actions.appendChild(button('Já comentei', () => api('PATCH', `/engagement/${item.id}`, { status: 'done', comment_draft: ta.value }).then(() => { toast('Registrado'); box.remove(); }), false));
        actions.appendChild(button('Pular', () => api('PATCH', `/engagement/${item.id}`, { status: 'skipped' }).then(() => box.remove()), false));
        box.appendChild(actions);
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

    function decoratePosts() {
        document.querySelectorAll(POST_SELECTOR).forEach((post) => {
            if (post.__careeropsBtn || post.closest('.careerops-card')) return;
            post.__careeropsBtn = true;
            const bar = document.createElement('div');
            bar.className = 'careerops-bar';
            bar.style.cssText = 'padding:4px 12px 0';
            bar.appendChild(button('✨ Comentário IA', () => draftComment(post, bar)));
            post.insertAdjacentElement('afterbegin', bar);
        });
    }

    // ── 2. Profile: "🤝 Convite IA" ───────────────────────────────────────────────────────────────────
    const isProfilePage = () => /^\/in\/[^/]+\/?$/.test(location.pathname);
    let profilePanel = null;

    function inviteTextarea() {
        const dialog = document.querySelector('div[role="dialog"], .artdeco-modal');
        return dialog && dialog.querySelector('textarea[name="message"], textarea#custom-message, textarea');
    }

    async function draftInvite() {
        if (profilePanel) profilePanel.remove();
        profilePanel = card('CareerOps · convite');
        profilePanel.style.cssText += ';position:fixed;right:16px;bottom:64px;width:360px;margin:0;z-index:2147483646';
        document.body.appendChild(profilePanel);
        const status = line(profilePanel, 'Avaliando o perfil…');
        const main = document.querySelector('main') || document.body;
        const name = clean((main.querySelector('h1') || {}).innerText || '');
        const headline = clean((main.querySelector('.text-body-medium') || {}).innerText || '');
        const res = await api('POST', '/prospects', {
            profile_url: location.origin + location.pathname, name: name || null, headline: headline || null,
            profile_text: clean(main.innerText).slice(0, 6000),
        });
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const p = res.data;
        status.textContent = `Encaixe ${p.fit ?? '?'} · ${p.market === 'br' ? 'Brasil' : p.market === 'intl' ? 'Exterior' : '—'} · ${p.segment || ''}`;
        if (p.reason) line(profilePanel, p.reason);
        if (p.status === 'skipped' || !p.note_draft) { line(profilePanel, 'A IA sugere não convidar (fora dos seus mercados).', '#999'); return; }
        const ta = editor(profilePanel, p.note_draft, 300);
        line(profilePanel, 'Clique em Conectar → Adicionar nota, depois em "Inserir na nota". O envio é com você.', '#777');
        const actions = document.createElement('div');
        actions.appendChild(button('Inserir na nota', () => {
            const target = inviteTextarea();
            if (!target) { toast('Abra Conectar → Adicionar nota primeiro', false); return; }
            fill(target, ta.value);
            toast('Nota inserida. Revise e clique em Enviar.');
        }));
        actions.appendChild(button('Copiar', () => navigator.clipboard.writeText(ta.value).then(() => toast('Copiado')), false));
        actions.appendChild(button('Convite enviado', () => api('PATCH', `/prospects/${p.id}`, { status: 'invited', note_draft: ta.value }).then(() => { toast('Registrado'); profilePanel.remove(); }), false));
        profilePanel.appendChild(actions);
        profilePanel.__prospectId = p.id;
        profilePanel.__note = ta;
    }

    // Clicking LinkedIn's "Enviar" in the invite dialog marks the prospect as invited
    document.addEventListener('click', (e) => {
        if (!profilePanel || !profilePanel.__prospectId) return;
        const b = e.target.closest('button');
        if (!b || !b.closest('div[role="dialog"], .artdeco-modal')) return;
        const label = (b.innerText || b.getAttribute('aria-label') || '').trim().toLowerCase();
        if (['enviar', 'send', 'enviar convite', 'send invitation', 'enviar sem nota', 'send without a note'].includes(label)) {
            api('PATCH', `/prospects/${profilePanel.__prospectId}`, { status: 'invited', note_draft: profilePanel.__note.value });
            toast('Convite registrado no CareerOps');
            profilePanel.remove();
            profilePanel = null;
        }
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
            seen.set(url, { url, anchor: a, container, text, name: lines[0] || '', headline: lines.slice(1, 4).join(' · ') });
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
        const people = visiblePeople();
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

    // ── Floating buttons, re-evaluated as LinkedIn navigates (single-page app) ─────────────────────────
    const fab = document.createElement('div');
    fab.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483645;display:flex;gap:6px';
    const inviteBtn = button('🤝 Convite IA', draftInvite);
    const scoreBtn = button('⭐ Avaliar pessoas da página', () => scorePage(scoreBtn));
    fab.append(inviteBtn, scoreBtn);
    document.documentElement.appendChild(fab);

    function refresh() {
        decoratePosts();
        inviteBtn.style.display = isProfilePage() ? '' : 'none';
        const listPage = /\/search\/results\/people|\/mynetwork/.test(location.pathname);
        scoreBtn.style.display = listPage ? '' : 'none';
    }
    new MutationObserver(() => { clearTimeout(refresh.t); refresh.t = setTimeout(refresh, 400); })
        .observe(document.documentElement, { childList: true, subtree: true });
    refresh();
})();
