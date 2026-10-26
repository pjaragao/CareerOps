// CareerOps — LinkedIn assist: AI comment and reply drafts on posts, connect-without-note on profiles, and scoring of
// the people listed on a page. Everything is drafted and filled in for you; the final click (Publicar / Responder /
// Conectar) is always yours. The only things done for you follow from that click: liking the post or comment you just
// answered (a pre-checked option you can turn off) and the invite you asked for with "Conectar".
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
        const t = document.createElement('div');
        t.textContent = msg;
        t.style.cssText = `position:fixed;right:16px;bottom:72px;z-index:2147483647;background:${ok ? '#00b894' : '#d63031'};color:#fff;
            padding:8px 12px;border-radius:8px;font:13px system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.2)`;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    }

    // Puts text into LinkedIn's editors: contenteditable (comment box) or textarea (invite note)
    function fill(el, text, append = false) {
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
                const parent = el.parentElement;
                const count = [...parent.querySelectorAll('button, [role="button"]')].filter((b) => isRepostButton(b) && anchorKind(b) === kind).length;
                if (count > 1) break;
                el = parent;
            }
            if (el !== btn && (el.innerText || '').length > 40) posts.add(el);
        }
        return [...posts].filter((p) => ![...posts].some((o) => o !== p && o.contains(p)));
    }

    const CUT = /\n(add a comment|adicionar um coment[aá]rio|most relevant|mais relevantes|\d[\d.,]*\s*(reactions?|rea[cç][oõ]es|comments?|coment[aá]rios)\b|like\ncomment|gostei\ncomentar)/i;

    // Post author in the new feed: the first named /in/ or /company/ link that isn't social context ("X likes this")
    const SOCIAL = /\b(likes?|loves?|celebrates?|supports?|finds?|commented|reposted|follows?|curtiu|gostou|comentou|republicou|celebrou|apoiou|amou|achou)\b/i;
    const META = /^(•.*|\d+\s*(s|m|min|h|d|w|sem|mo|y|a)\b.*|\+?\s*follow|following|seguir|seguindo|promoted|promovido|verified|premium|feed post|publicação no feed|.*•\s*(1st|2nd|3rd\+?|1º|2º|3º\+?))$/i;
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

    function postInfo(post) {
        const urnHolder = [post, ...post.querySelectorAll('[data-urn], [data-id], a[href*="urn:li:"]')]
            .map((el) => (el.getAttribute('data-urn') || el.getAttribute('data-id') || el.getAttribute('href') || ''))
            .concat(Array.from({ length: 6 }, (_, k) => { let a = post; for (let n = 0; n <= k && a; n++) a = a.parentElement; return a ? (a.getAttribute('data-urn') || '') : ''; }))
            .map((v) => (v.match(/urn:li:(activity|ugcPost|share):\d+/) || [])[0]).find(Boolean);
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
            text = copy.innerText || '';
            copy.remove();
            const m = text.match(CUT);
            if (m) { if (!comments) comments = text.slice(m.index); text = text.slice(0, m.index); }
            const HEADER = /^(\d+\s*(s|m|min|h|d|w|sem|mo|y|a)\b.*|(following|seguindo|follow|seguir)\b.*|…|\.\.\.|•.*|.*•\s*(1st|2nd|3rd\+?|1º|2º|3º\+?)|promoted|promovido|edited|editado|feed post|publicação no feed)$/i;
            let lines = text.split('\n').map((l) => l.replace(/[\u200b-\u200d\ufeff]/g, '').trim()).filter((l) => l && !/^(show translation|ver tradução|traduzir|see translation)$/i.test(l));
            let last = -1;
            lines.slice(0, 8).forEach((l, k) => { if (HEADER.test(l)) last = k; });
            if (last >= 0) lines = lines.slice(last + 1);
            lines = lines.map((l) => l.replace(/\s*…\s*(see more|ver mais|more|mais)$/i, '')).filter((l) => l && !HEADER.test(l));
            // the actor block (name, headline, followers) goes before the text; carousel/counter leftovers at the end
            const who = actorOf(post);
            if (who) {
                const i = lines.slice(0, 8).indexOf(who.name);
                if (i >= 0) lines = lines.slice(i + 1).filter((l, k) => !(k < 3 && (l === who.headline || /^[\d.,]+\s*(followers|seguidores)$/i.test(l))));
            }
            while (lines.length && /^([\d\s/.,]+|\d+\s*(pages?|páginas?))$/i.test(lines[lines.length - 1])) {
                if (/pages?|páginas?/i.test(lines.pop()) && lines.length) lines.pop();   // "Title / 8 pages": drop the title too
            }
            text = lines.join('\n');
        }
        const who = authorEl ? { name: clean(authorEl.innerText).split('\n')[0], headline: headlineEl ? clean(headlineEl.innerText) : null } : actorOf(post);
        const urn = urnHolder || reactUrn(post);
        return {
            post_url: urn ? `https://www.linkedin.com/feed/update/${urn}/` : null,
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
        const res = await api('POST', '/engagement', { ...info, instruction: opts.instruction || null, regenerate: !!opts.regenerate });
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return; }
        const item = res.data;
        status.textContent = `Relevância ${item.relevance ?? '?'} — ${item.reason || ''}`;
        const again = (instruction) => draftComment(post, anchor, { instruction, regenerate: true });
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
        likeToggle(box, 'Curtir o post ao comentar');
        promptRow(box, 'Refazer com um pedido (ex.: mais curto, discorde com educação)', again);
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
        promptRow(box, 'Ex.: concorde e cite a experiência com concessões de saneamento', (v) => draftComment(post, anchor, { instruction: v, regenerate: true })).focus();
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
    const isSelf = (raw) => /(^|\s)(you|voc[eê])\s*$/i.test(clean(raw).split('\n')[0]);
    const NOT_HEADLINE = /^(like|gostei|reply|responder|curtir|author|autor|you|voc[eê]|verified profile|premium profile|perfil verificado|edited|editado|see more|ver mais|…|\d+\s*(likes?|reactions?|curtidas|rea[cç][oõ]es|replies|respostas)?)$/i;

    async function harvestPeople(post, info) {
        await openComments(post);
        const seen = new Map();
        post.querySelectorAll('a[href*="/in/"]').forEach((a) => {
            if (own(a)) return;
            const m = a.href.match(/https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
            if (!m || m[1] === 'me' || (seen.has(m[0]) && (!seen.get(m[0]) || seen.get(m[0]).headline))) return;
            const raw = a.innerText || a.getAttribute('aria-label') || '';
            const name = personName(raw);
            if (!name || name.length > 80 || /^(view|ver)\b/i.test(name)) return;
            if (isSelf(raw)) { seen.set(m[0], null); return; }
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

    function saveCommented(post, comment) {
        if (post.__careeropsSaved) return;
        const info = postInfo(post);
        if (info.post_text.length < 20) return;
        post.__careeropsSaved = true;
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
        lastReply = null;
        if (likeOnComment) setTimeout(() => likeAfterSend(post, target), 700);
        if (!target) saveCommented(post, text);
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
    const isLike = (b) => !own(b) && (LIKE_LABEL.test(label(b)) || LIKE_ARIA.test(b.getAttribute('aria-label') || ''));
    function pressLike(btn) {
        if (!btn) return false;
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
    let lastReply = null;   // { post, block }: the comment you are answering
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
            lastReply = { post, block };
            const ed = await waitFor(() => [...thread.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !own(el))
                || [...block.parentElement.querySelectorAll(EDITOR)].find((el) => el.offsetParent !== null && !own(el)));
            if (!ed) { toast('Não achei a caixa de resposta — use Copiar', false); return; }
            fill(ed, ta.value, true);
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
                const b = button(toMe ? '✨ Responder (para você)' : '✨ Responder', () => draftReply(rb, post), toMe);
                b.classList.add('careerops-reply');
                b.title = 'Rascunho de resposta com IA: continua a conversa ou agradece e encerra';
                b.style.cssText += ';font-size:11px;padding:2px 8px;margin-left:6px';
                rb.insertAdjacentElement('afterend', b);
            });
        });
    }

    const COMMENT_BTN = /^(comment|comentar)$/i;
    const own = (el) => el.closest('.careerops-card, .careerops-bar, .careerops-actions, .careerops-reply');

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

    function decoratePosts() {
        findPosts().forEach((post) => {
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
    const CONNECT = /^(conectar|connect)$/i;
    const SEND_NO_NOTE = ['enviar sem nota', 'send without a note', 'send without note'];
    const SEND = ['enviar', 'send', 'enviar convite', 'send invitation'];
    const inDialog = () => document.querySelector('div[role="dialog"], .artdeco-modal');
    const btnLabel = (b) => clean(b.innerText || b.getAttribute('aria-label') || '').split('\n')[0].toLowerCase();

    // "Connect" sits in the profile's action row or, for some profiles, inside the "More" menu
    async function findConnect(main) {
        const find = () => [...main.querySelectorAll('button, a, [role="button"], [role="menuitem"], div[aria-label]')]
            .find((el) => el.offsetParent !== null && !el.closest('.careerops-card')
                && (CONNECT.test(btnLabel(el)) || /^(convidar|invite) .*(conectar|connect)/i.test(el.getAttribute('aria-label') || '')));
        let el = find();
        if (el) return el;
        const more = [...main.querySelectorAll('button')].find((b) => b.offsetParent !== null && /^(mais|more)$/i.test(btnLabel(b)) || /mais a[cç][oõ]es|more actions/i.test(b.getAttribute('aria-label') || ''));
        if (more) { more.click(); el = await waitFor(() => find() || null, 2000); }
        return el;
    }

    // Returns 'sent' | 'pending' | 'connected' | 'unavailable' | 'needs_user'
    async function connectNoNote() {
        const main = document.querySelector('main') || document.body;
        const actions = [...main.querySelectorAll('button, a')].map(btnLabel);
        if (actions.some((l) => /^(pendente|pending)$/.test(l))) return 'pending';
        const target = await findConnect(main);
        if (!target) return actions.some((l) => /^(mensagem|message)$/.test(l)) ? 'connected' : 'unavailable';
        target.click();
        const dlg = await waitFor(inDialog, 4000);
        if (!dlg) return 'needs_user';
        const btn = await waitFor(() => [...dlg.querySelectorAll('button')].find((b) => SEND_NO_NOTE.includes(btnLabel(b)))
            || [...dlg.querySelectorAll('button')].find((b) => SEND.includes(btnLabel(b)) && !dlg.querySelector('input[type="email"], input[name="email"]')), 3000);
        if (!btn) return 'needs_user';   // e.g. LinkedIn asks for the person's email: that one is yours
        btn.click();
        await wait(800);
        return 'sent';
    }

    // Saves the profile as a prospect (scored), then connects on your click
    async function ensureProspect() {
        const main = document.querySelector('main') || document.body;
        const name = clean((main.querySelector('h1') || {}).innerText || '');
        const headline = clean((main.querySelector('.text-body-medium') || {}).innerText || '');
        return api('POST', '/prospects', {
            profile_url: location.origin + location.pathname, name: name || null, headline: headline || null,
            profile_text: clean(main.innerText).slice(0, 6000),
        });
    }

    async function runConnect(prospectId) {
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
        await waitFor(() => document.querySelector('main h1'), 10000);
        await wait(1200);   // let the action row finish rendering
        await runConnect(Number(m[1]));
    }

    // Clicking LinkedIn's own "Enviar" in the invite dialog (manual connect) marks the prospect as invited
    document.addEventListener('click', (e) => {
        const b = e.target.closest('button');
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

    // ── 4. Easy Apply: "✨ Preencher com IA" (fills each step; you review, click Next and Submit) ────────
    // Gender goes to the backend, which answers it only from config/easy_apply.yml; these stay with the user
    const DEMOGRAPHIC = /race|ra[cç]a|etnia|ethnic|veteran|disab|defici[eê]ncia|pcd|orienta[cç][aã]o sexual|sexual orientation|pronoun|pronome|religi/i;
    const PLACEHOLDER = /^(selecione|select|escolha|choose)/i;

    function easyApplyModal() {
        return [...document.querySelectorAll('.jobs-easy-apply-modal, div[role="dialog"]')]
            .find((d) => d.offsetParent !== null && (d.classList.contains('jobs-easy-apply-modal')
                || /candidatura simplificada|easy apply|apply to |candidatar-se/i.test(d.innerText.slice(0, 400))));
    }

    function labelFor(el, modal) {
        if (el.id) { const l = modal.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clean(l.innerText); }
        const fs = el.closest('fieldset');
        if (fs && fs.querySelector('legend')) return clean(fs.querySelector('legend').innerText);
        if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
        const wrap = el.closest('.fb-dash-form-element, .jobs-easy-apply-form-element, .artdeco-text-input, div');
        return wrap ? clean(wrap.innerText).split('\n')[0] : '';
    }

    function collectFields(modal) {
        const fields = [];
        const seen = new Set();
        modal.querySelectorAll('input, textarea, select').forEach((el, i) => {
            if (el.closest('.careerops-card') || el.offsetParent === null || el.disabled) return;
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
                f.options = f.els.map((r) => clean((modal.querySelector(`label[for="${CSS.escape(r.id)}"]`) || r.parentElement).innerText) || r.value);
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

    const mark = (f, color) => f.els.forEach((el) => { (el.type === 'radio' || el.type === 'checkbox' ? el.parentElement : el).style.outline = `2px solid ${color}`; });

    function jobContext() {
        const q = (sel) => clean((document.querySelector(sel) || {}).innerText || '');
        return {
            title: q('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .t-24.job-details-jobs-unified-top-card__job-title, h1'),
            company: q('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name'),
            location: q('.job-details-jobs-unified-top-card__primary-description-container, .jobs-unified-top-card__bullet'),
            description: q('#job-details, .jobs-description__content, .jobs-description-content__text').slice(0, 5000),
        };
    }

    let applyBusy = false;
    async function fillStep(modal, panel) {
        if (applyBusy) return null;
        const all = collectFields(modal);
        const fields = all.filter((f) => !f.current);
        const status = panel.querySelector('.careerops-apply-status');
        if (!fields.length) { status.textContent = 'Nada para preencher nesta etapa. Revise e clique em Avançar.'; return { filled: 0, pending: 0 }; }
        const demographic = fields.filter((f) => DEMOGRAPHIC.test(f.label));
        const send = fields.filter((f) => !DEMOGRAPHIC.test(f.label));
        demographic.forEach((f) => mark(f, '#e17055'));
        if (!send.length) { status.textContent = 'Só há perguntas pessoais/demográficas nesta etapa — responda você.'; return { filled: 0, pending: demographic.length }; }
        applyBusy = true;
        status.textContent = `Preenchendo ${send.length} campo(s)…`;
        const res = await api('POST', '/easy-apply/answers', {
            job: jobContext(), fields: send.map(({ key, type, label, options, current }) => ({ key, type, label, options, current })),
        });
        applyBusy = false;
        if (!res.ok) { status.textContent = errText(res); status.style.color = '#d63031'; return null; }
        let filled = 0;
        const pending = [];
        const toConfirm = [];
        const sugg = res.data.suggestions || {};
        for (const f of send) {
            const v = res.data.answers[f.key];
            if (v !== undefined && applyAnswer(f, v)) { mark(f, '#00b894'); filled++; continue; }
            const sg = sugg[f.key];
            if (sg && applyAnswer(f, sg.value)) { mark(f, '#fdcb6e'); toConfirm.push(`${f.label || f.key}: ${sg.value}${sg.basis ? ` (${sg.basis})` : ''}`); continue; }
            mark(f, '#e17055'); pending.push(f.label || f.key);
        }
        demographic.forEach((f) => pending.push(f.label));
        status.style.color = '#555';
        status.textContent = `${filled} preenchido(s) em verde. ` + (pending.length ? `Para você (laranja): ${pending.slice(0, 6).join(' · ')}` : 'Revise e clique em Avançar.');
        if (toConfirm.length) line(panel, `Confirme ou altere (amarelo) — sugestão de mercado estimada pela IA: ${toConfirm.join(' · ')}`, '#b7791f');
        if (res.data.notes) line(panel, res.data.notes, '#777');
        return { filled, pending: pending.length };
    }

    let applyPanel = null;
    function decorateEasyApply() {
        const modal = easyApplyModal();
        if (!modal) { applyPanel = null; return; }
        if (!modal.querySelector('.careerops-apply')) {
            applyPanel = card('CareerOps · Easy Apply');
            applyPanel.classList.add('careerops-apply');
            line(applyPanel, 'A IA preenche com seus dados (config/easy_apply.yml + CV). Verde: preenchido · Amarelo: salário sugerido, confirme · Laranja: com você.', '#777');
            const status = line(applyPanel, '');
            status.className = 'careerops-apply-status';
            const auto = document.createElement('label');
            auto.style.cssText = 'font-size:12px;color:#555;display:flex;gap:4px;align-items:center;margin:4px 0';
            auto.innerHTML = '<input type="checkbox" checked> preencher cada nova etapa automaticamente';
            applyPanel.__auto = auto.querySelector('input');
            const fillBtn = button('✨ Preencher com IA', () => fillStep(modal, applyPanel));
            fillBtn.classList.add('careerops-fill');
            applyPanel.append(fillBtn, auto);
            modal.insertAdjacentElement('afterbegin', applyPanel);
        }
        // Auto: when a new step shows empty fields, fill them (the user still clicks Next/Submit)
        const panel = modal.querySelector('.careerops-apply');
        const signature = collectFields(modal).map((f) => f.key).join('|');
        if (panel.__auto && panel.__auto.checked && panel.__filledOnce && signature && signature !== panel.__lastStep) {
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

    function savedJobsOnScreen() {
        const jobs = new Map();
        document.querySelectorAll('main a[href*="/jobs/view/"]').forEach((a) => {
            const m = a.href.match(/\/jobs\/view\/(\d+)/);
            if (!m || jobs.has(m[1])) return;
            const box = a.closest('li, .entity-result, div[data-chameleon-result-urn], .reusable-search__result-container') || a.parentElement;
            const lines = clean(box ? box.innerText : a.innerText).split('\n').map((l) => l.trim()).filter(Boolean);
            jobs.set(m[1], { id: m[1], title: clean(a.innerText) || lines[0] || '', company: lines[1] || '', location: lines[2] || '' });
        });
        return [...jobs.values()].slice(0, 25);
    }

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
    let applyChecked = false;

    function apStatus(text, color = '#333') { if (autopilot) { autopilot.status.textContent = text; autopilot.status.style.color = color; } }

    async function startAutopilot() {
        applyChecked = true;
        const pending = await message({ action: 'applyPending' });
        if (!pending) return;
        const box = card('🚀 CareerOps · Auto Apply');
        box.style.cssText += ';position:fixed;left:16px;bottom:16px;width:330px;margin:0;z-index:2147483646';
        const status = line(box, 'Preparando CV e carta…');
        const opts = document.createElement('label');
        opts.style.cssText = 'font-size:12px;color:#555;display:flex;gap:4px;align-items:center;margin:4px 0';
        opts.innerHTML = '<input type="checkbox"> enviar sozinho no final (sem revisão)';
        const autoSubmit = opts.querySelector('input');
        chrome.storage.local.get('autoSubmit', (v) => { autoSubmit.checked = !!(v && v.autoSubmit); });
        autoSubmit.addEventListener('change', () => chrome.storage.local.set({ autoSubmit: autoSubmit.checked }));
        const stop = button('Parar', async () => { autopilot.done = true; await message({ action: 'applyStop' }); box.remove(); }, false);
        box.append(opts, stop);
        document.documentElement.appendChild(box);
        autopilot = { jobId: pending.jobId, box, status, autoSubmit, prep: {}, uploaded: false, lastSig: '', running: false, done: false, steps: 0 };
        const res = await backend('POST', `/jobs/${pending.jobId}/auto-apply/prepare`, {});
        if (!res.ok) { apStatus(errText(res), '#d63031'); return; }
        autopilot.prep = res.data;
        const btn = await waitFor(() => [...document.querySelectorAll('main button, main a')].find((b) => !own(b) && b.offsetParent !== null
            && (EASY.test(label(b)) || APPLY_EXT.test(label(b)))), 12000);
        if (!btn) { apStatus('Não achei o botão de candidatura nesta página (vaga encerrada ou já candidatado?).', '#d63031'); return; }
        if (EASY.test(label(btn))) {
            apStatus('Abrindo o Easy Apply…');
            btn.click();
        } else {
            apStatus('Esta vaga é no site da empresa: abrindo… o painel CareerOps continua lá (anexa o CV e preenche).');
            btn.click();
        }
    }

    async function uploadResume(modal) {
        const input = modal.querySelector('input[type="file"]');
        if (!input || autopilot.uploaded || !autopilot.prep.resume_markdown) return false;
        if (!/resume|curr[ií]culo|\bcv\b/i.test(modal.innerText)) return false;
        const file = await message({ action: 'backendFile', path: `/jobs/${autopilot.jobId}/document.pdf?kind=resume` });
        if (!file || !file.ok) { apStatus(`Não consegui baixar o CV: ${(file && file.detail) || ''} — sigo com o CV já salvo no LinkedIn.`, '#b7791f'); autopilot.uploaded = true; return false; }
        const bytes = Uint8Array.from(atob(file.b64), (c) => c.charCodeAt(0));
        const dt = new DataTransfer();
        dt.items.add(new File([bytes], file.name, { type: file.type }));
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        autopilot.uploaded = true;
        apStatus(`📎 CV personalizado enviado (${file.name}).`);
        await wait(3000);
        return true;
    }

    async function finishApplied() {
        autopilot.done = true;
        const r = await backend('PATCH', `/jobs/${autopilot.jobId}/status`, { status: 'applied' });
        await message({ action: 'applyStop' });
        apStatus(r.ok ? '✓ Candidatura enviada — vaga marcada como "Candidatado" no CareerOps.' : `Enviada. ${errText(r)}`, '#00b894');
    }

    async function driveAutopilot() {
        const ap = autopilot;
        if (!ap || ap.done || ap.running || !ap.prep.job) return;
        if ([...document.querySelectorAll('div[role="dialog"], .artdeco-modal')].some((d) => d.offsetParent !== null && SENT.test(d.innerText))) { finishApplied(); return; }
        const modal = easyApplyModal();
        if (!modal) return;
        const footer = [...modal.querySelectorAll('button')].filter((b) => !own(b) && b.offsetParent !== null && !b.disabled);
        const sig = collectFields(modal).map((f) => f.key).join('|') + '#' + footer.map(label).join('|') + '#' + (modal.querySelector('h3, h2') || {}).innerText;
        if (sig === ap.lastSig) return;   // same step: waiting for you or for LinkedIn
        ap.lastSig = sig;
        ap.running = true;
        try {
            await wait(800);
            await uploadResume(modal);
            const panel = modal.querySelector('.careerops-apply');
            const result = panel ? await fillStep(modal, panel) : { pending: 0 };
            const buttons = [...modal.querySelectorAll('button')].filter((b) => !own(b) && b.offsetParent !== null && !b.disabled);
            const submit = buttons.find((b) => SUBMIT_APP.test(label(b)));
            if (submit) {
                if (ap.autoSubmit.checked && result && !result.pending) { apStatus('Enviando a candidatura…'); await wait(800); submit.click(); return; }
                submit.style.outline = '3px solid #00b894';
                apStatus('✓ Tudo preenchido. Revise e clique em "Enviar candidatura" — eu marco a vaga como candidatada.', '#00b894');
                return;
            }
            if (!result || result.pending) {
                apStatus('Complete os campos em laranja/amarelo e clique em Avançar — continuo na próxima etapa.', '#b7791f');
                return;
            }
            const next = buttons.find((b) => NEXT.test(label(b)));
            if (!next) { apStatus('Não achei o botão Avançar — siga você; continuo quando a etapa mudar.', '#b7791f'); return; }
            ap.steps++;
            apStatus(`Etapa ${ap.steps} preenchida — avançando…`);
            await wait(700 + Math.random() * 600);
            next.click();
            await wait(1800);
            if (modal.querySelector('.artdeco-inline-feedback--error, [data-test-form-element-error-messages]')) {
                // same step stays marked: wait for you (no retry loop); the next step changes the signature
                apStatus('O LinkedIn marcou campos nesta etapa: corrija e clique em Avançar — continuo depois.', '#b7791f');
            }
        } finally {
            ap.running = false;
        }
    }

    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action !== 'importSavedJobs') return;
        importSavedJobs(savedBtn).then(sendResponse);
        return true;
    });

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
    const scoreBtn = button('⭐ Avaliar pessoas da página', () => scorePage(scoreBtn));
    const savedBtn = button('📥 Importar vagas salvas', () => importSavedJobs(savedBtn));
    fab.append(scoreBtn, savedBtn);
    document.documentElement.appendChild(fab);

    function refresh() {
        decoratePosts();
        decorateReplies();
        decorateEasyApply();
        decorateJobSave();
        if (!applyChecked && currentJobId()) startAutopilot();
        driveAutopilot();
        // the job pane is reused when another job is opened: reset our button for the new job
        document.querySelectorAll('.careerops-jobbtn').forEach((b) => { if (b.dataset.job !== String(currentJobId())) b.remove(); });
        placeInvite();
        const listPage = /\/search\/results\/people|\/mynetwork/.test(location.pathname);
        scoreBtn.style.display = listPage ? '' : 'none';
        savedBtn.style.display = isSavedJobsPage() ? '' : 'none';
    }
    new MutationObserver(() => { clearTimeout(refresh.t); refresh.t = setTimeout(refresh, 400); })
        .observe(document.documentElement, { childList: true, subtree: true });
    refresh();
    autoConnectFromApp();
})();
