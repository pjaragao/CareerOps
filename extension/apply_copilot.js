// CareerOps — Auto Apply copilot for application pages outside LinkedIn (Greenhouse, Lever, Workday, Gupy, …).
// Active only in a tab that CareerOps opened for a job (marker #careerops-apply=<id>, or a tab opened from it).
// It attaches the tailored resume, fills the fields it can with your data and AI, and lists what is left for you.
// It never clicks the final submit button: you review and send.
(() => {
    if (window.__careeropsApply) return;
    const inFrame = window.top !== window;   // forms embedded in an iframe (e.g. Greenhouse on a company site)
    window.__careeropsApply = true;

    const send = (msg) => new Promise((resolve) => {
        try { chrome.runtime.sendMessage(msg, (res) => { void chrome.runtime.lastError; resolve(res); }); } catch (e) { resolve(null); }
    });
    const marker = !inFrame && location.hash.match(/careerops-apply=(\d+)/);
    const started = marker ? send({ action: 'applyStart', jobId: Number(marker[1]) }) : Promise.resolve();
    if (location.hostname.endsWith('linkedin.com')) return;   // LinkedIn: linkedin_assist.js drives Easy Apply

    const ready = () => new Promise((r) => (document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', r, { once: true }) : r()));
    const backend = (method, path, body) => send({ action: 'backendApi', method, path, body }).then((r) => r || { ok: false, data: { detail: 'Sem resposta da extensão' } });
    const copilot = (method, path, body) => send({ action: 'copilotApi', method, path, body }).then((r) => r || { ok: false, data: { detail: 'Sem resposta da extensão' } });
    const errText = (res) => (res && res.data && res.data.detail) || 'Falha ao falar com o CareerOps';
    const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));

    const DEMOGRAPHIC = /race|ra[cç]a|etnia|ethnic|veteran|disab|defici[eê]ncia|pcd|orienta[cç][aã]o sexual|sexual orientation|pronoun|pronome|religi|gender|g[eê]nero|sexo\b/i;
    const PLACEHOLDER = /^(selecione|select|escolha|choose|--|please select)/i;
    const COVER = /cover letter|carta de apresenta|motivation|motiva[cç][aã]o/i;
    const RESUME = /resume|r[eé]sum[eé]|\bcv\b|curr[ií]cul/i;

    // ── Panel (shadow DOM: the site's CSS can't touch it) ──
    let root, ui = {};
    function panel(job) {
        const host = document.createElement('div');
        host.id = 'careerops-apply-copilot';
        host.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647';
        root = host.attachShadow({ mode: 'open' });
        root.innerHTML = `<style>
            .box{font:13px/1.45 system-ui,sans-serif;width:330px;background:#fff;color:#222;border:1px solid #6c5ce7;border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.25);padding:12px}
            .head{display:flex;justify-content:space-between;align-items:center;gap:8px}
            strong{color:#6c5ce7} .job{color:#555;font-size:12px;margin:2px 0 8px}
            .st{font-size:12px;color:#333;margin:6px 0;white-space:pre-line} .todo{font-size:12px;color:#c0392b;white-space:pre-line}
            button{font:600 12px system-ui,sans-serif;border-radius:14px;padding:5px 10px;cursor:pointer;margin:2px;border:1px solid #c9c9d6;background:#fff;color:#333}
            button.p{background:#6c5ce7;border-color:#6c5ce7;color:#fff} label{font-size:12px;color:#555;display:flex;gap:4px;align-items:center;margin-top:6px}
            .min{display:none} .box.small .body{display:none} .box.small .min{display:inline}
        </style>
        <div class="box"><div class="head"><strong>🚀 CareerOps · Candidatura</strong>
            <span><button class="tog" title="Minimizar">–</button><button class="end" title="Encerrar o Auto Apply nesta aba">✕</button></span></div>
            <div class="body">
            <div class="job"></div><div class="st">Preparando…</div><div class="todo"></div>
            <div><button class="p fill">✨ Preencher com IA</button><button class="cv">📎 Anexar CV</button></div>
            <div><button class="cl">📋 Copiar carta</button><button class="cvt">📋 Copiar CV (texto)</button><button class="done">✓ Enviei</button></div>
            <label><input type="checkbox" class="auto" checked> preencher sozinho cada nova etapa</label>
            </div></div>`;
        document.documentElement.appendChild(host);
        const $ = (s) => root.querySelector(s);
        ui = { box: $('.box'), st: $('.st'), todo: $('.todo'), auto: $('.auto') };
        $('.job').textContent = `${job.title || ''} · ${job.company || ''}`;
        $('.tog').onclick = () => ui.box.classList.toggle('small');
        $('.end').onclick = async () => { await send({ action: 'applyStop' }); host.remove(); observer.disconnect(); };
        $('.fill').onclick = () => fillPage(true);
        $('.cv').onclick = () => attachFiles(true);
        $('.cl').onclick = () => copy(prep.cover_letter, 'Carta copiada');
        $('.cvt').onclick = () => copy(prep.resume_markdown, 'CV copiado');
        $('.done').onclick = async () => {
            const r = await backend('PATCH', `/jobs/${jobId}/status`, { status: 'applied' });
            status(r.ok ? '✓ Marcada como "Candidatado" no CareerOps.' : errText(r));
            if (r.ok) { await send({ action: 'applyStop' }); observer.disconnect(); }
        };
    }
    const status = (t) => { if (ui.st) ui.st.textContent = t; };
    const todo = (t) => { if (ui.todo) ui.todo.textContent = t; };
    const copy = (text, msg) => (text ? navigator.clipboard.writeText(text).then(() => status(msg)) : status('Ainda não gerado no CareerOps'));

    // ── Form fields ──
    const visible = (el) => el.offsetParent !== null || el.getClientRects().length > 0;
    function labelOf(el) {
        const byFor = el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (byFor) return clean(byFor.innerText);
        const ids = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
        if (ids.length) { const t = ids.map((i) => (document.getElementById(i) || {}).innerText || '').join(' '); if (clean(t)) return clean(t); }
        if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
        const wrap = el.closest('label');
        if (wrap) return clean(wrap.innerText);
        const fs = el.closest('fieldset');
        if (fs && fs.querySelector('legend')) return clean(fs.querySelector('legend').innerText);
        let box = el.parentElement;
        for (let k = 0; k < 4 && box; k++, box = box.parentElement) {
            const t = clean(box.innerText);
            if (t && t.length < 200) return t;
        }
        return clean(el.placeholder || el.name || '');
    }

    // The heading a field sits under ("Work Experience 2", "Education 1", "Address"): the same label repeats in each
    // block of a multi-entry form, and without it the AI can't tell which job a "Company" belongs to
    // (a fieldset legend such as "From*" names a group inside a block, not the block: it goes between block and label)
    const HEADINGS = 'h2, h3, h4, h5, h6, [role="heading"]';
    function sectionOf(el) {
        let last = null;
        for (const h of document.querySelectorAll(HEADINGS)) {
            if (h.closest('#careerops-apply-copilot') || !visible(h)) continue;
            if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) last = h; else break;
        }
        const t = last ? clean(last.innerText) : '';
        return t.length > 1 && t.length < 80 ? t : '';
    }
    const withSection = (el, label) => {
        const fs = el.closest('fieldset');
        const legend = fs && fs.querySelector('legend') ? clean(fs.querySelector('legend').innerText).replace(/\*$/, '') : '';
        if (legend && !label.toLowerCase().includes(legend.toLowerCase())) label = `${legend} › ${label}`;
        const sec = sectionOf(el);
        return sec && !label.toLowerCase().includes(sec.toLowerCase()) ? `${sec} › ${label}` : label;
    };

    // Workday-style dropdowns: a button that opens a list of options (not a <select>)
    const DROPDOWN = 'button[aria-haspopup="listbox"], [role="combobox"][aria-haspopup="listbox"]:not(input)';
    const OPTION = '[role="option"], [data-automation-id="promptOption"]';
    // Workday shows what is already chosen in a search box as items built like options: never take them for a list
    const SELECTED = '[data-automation-id="selectedItemList"], [data-automation-id="selectedItem"]';
    // the options of THIS control: the list its aria-controls points to; else any open list except those seen before
    function optionsFor(el, before) {
        const ctrl = el.getAttribute('aria-controls');
        const root = ctrl && document.getElementById(ctrl);
        const pool = root ? root.querySelectorAll(OPTION) : document.querySelectorAll(`[role="listbox"] [role="option"], [data-automation-id="promptOption"]`);
        return [...pool].filter((o) => visible(o) && !o.closest(SELECTED) && !o.closest('#careerops-apply-copilot') && !(before && before.has(o)));
    }
    // search-and-pick inputs ("How did you hear about us?", phone country code): typing shows options to click
    const isSearchPick = (el) => el.tagName === 'INPUT' && (el.getAttribute('role') === 'combobox' || /searchbox/i.test(el.getAttribute('data-automation-id') || '')
        || el.getAttribute('data-uxi-widget-type') === 'selectinput' || !!el.closest('[data-automation-id="multiselectInputContainer"]'));
    const pickedIn = (el) => {   // what a search-and-pick box already has chosen
        const box = el.closest('[data-automation-id="multiSelectContainer"]') || el.parentElement;
        return [...box.querySelectorAll('[data-automation-id="selectedItem"]')].map((i) => clean(i.innerText)).filter(Boolean).join(', ') || null;
    };
    // the form only: the site's own header menus (language, settings) are dropdowns too
    const inForm = (el) => !el.closest('header, nav, [role="banner"], [role="navigation"]');

    function collect() {
        const fields = [];
        const seen = new Set();
        document.querySelectorAll(DROPDOWN).forEach((el, i) => {
            if (el.closest('#careerops-apply-copilot') || el.disabled || !visible(el) || !inForm(el)) return;
            const key = el.id || el.getAttribute('data-automation-id') || el.name || `dd${i}`;
            if (seen.has(key)) return;
            seen.add(key);
            const text = clean(el.innerText || el.getAttribute('aria-label') || '');
            const label = labelOf(el).replace(text, '').trim() || labelOf(el);
            fields.push({ key, type: 'select', label: withSection(el, label).slice(0, 300), options: [], current: text && !PLACEHOLDER.test(text) && !/^select one$/i.test(text) ? text : null, els: [el], dropdown: true });
        });
        document.querySelectorAll('form input, form textarea, form select, [role="form"] input, main input, main textarea, main select').forEach((el, i) => {
            if (el.closest('#careerops-apply-copilot') || el.disabled || el.readOnly || !visible(el) || el.closest(DROPDOWN)) return;
            const type = el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea'
                : el.type === 'radio' ? 'radio' : el.type === 'checkbox' ? 'checkbox' : el.type === 'number' ? 'number'
                : ['text', 'tel', 'email', 'url', 'date', ''].includes(el.type) ? 'text' : null;
            if (!type) return;
            const key = type === 'radio' ? `radio:${el.name || i}` : (el.id || el.name || `f${i}`);
            if (seen.has(key)) return;
            seen.add(key);
            if (!inForm(el)) return;
            const f = { key, type, label: withSection(el, labelOf(el)).slice(0, 300), options: [], current: null, els: [el], searchPick: isSearchPick(el) };
            if (type === 'select') {
                f.options = [...el.options].map((o) => o.text.trim()).filter((t) => t && !PLACEHOLDER.test(t));
                const sel = el.options[el.selectedIndex];
                f.current = sel && sel.value && !PLACEHOLDER.test(sel.text.trim()) ? sel.text.trim() : null;
            } else if (type === 'radio') {
                f.els = [...document.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`)];
                f.label = withSection(el, labelOf(el.closest('fieldset, [role="radiogroup"]') || el)).slice(0, 300);
                f.options = f.els.map((r) => labelOf(r) || r.value);
                const on = f.els.find((r) => r.checked);
                f.current = on ? f.options[f.els.indexOf(on)] : null;
            } else if (type === 'checkbox') {
                f.current = el.checked ? 'true' : null;
            } else {
                f.current = el.value || (f.searchPick ? pickedIn(el) : null);
            }
            fields.push(f);
        });
        return fields;
    }

    function setValue(el, text) {
        el.focus();
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
        // date segments (Workday's month/year) and other key-driven widgets ignore a set value: type it instead
        if (el.getAttribute('role') !== 'spinbutton' || el.tagName === 'SELECT') {
            Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);   // React-controlled inputs need the native setter
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (el.tagName !== 'SELECT' && el.value !== text) typeText(el, text);
        el.blur();
    }
    // like the user typing: the page's own key handlers see each insertion
    function typeText(el, text) {
        el.focus();
        if (el.select) el.select();
        document.execCommand('insertText', false, text);
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    const norm = (t) => clean(t).toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    const pick = (options, value) => {
        const v = norm(value);
        return options.find((o) => norm(o.innerText) === v) || options.find((o) => norm(o.innerText).startsWith(v))
            || options.find((o) => v.length > 3 && norm(o.innerText).includes(v));
    };
    const key = (target, k, code) => target.dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, keyCode: code, bubbles: true }));
    // A dropdown button closes its list when clicked again (Workday ignores Escape once focus is in the list);
    // search boxes close on a click outside them
    const press = (target) => { for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) target.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })); };
    const clickOutside = () => {
        press(document.querySelector('main h2, main h3, h2, h3') || document.body);
    };
    const closeList = async (el) => {
        if (el.tagName === 'BUTTON' && el.getAttribute('aria-expanded') === 'true') el.click();
        else if (el.tagName === 'INPUT') clickOutside();
        else key(document.activeElement || el, 'Escape', 27);
        await wait(300);
        if (el.getAttribute('aria-expanded') === 'true') { key(el, 'Escape', 27); await wait(200); }
    };

    // Opens a dropdown and reads its options (long lists are scrolled to load all of them), then closes it
    async function readOptions(f) {
        const el = f.els[0];
        const before = new Set(optionsFor(el));
        el.click();
        const first = await until(() => optionsFor(el, before).length && optionsFor(el, before), 2500);
        if (!first) { await closeList(el); return []; }
        const names = new Set(first.map((o) => clean(o.innerText)));
        const list = first[0].closest('[role="listbox"]') || first[0].parentElement;
        for (let k = 0; k < 80 && list && list.scrollHeight > list.clientHeight + 5; k++) {
            const size = names.size;
            list.scrollTop += list.clientHeight;
            await wait(120);
            optionsFor(el, before).forEach((o) => names.add(clean(o.innerText)));
            if (names.size === size && list.scrollTop + list.clientHeight >= list.scrollHeight - 2) break;
        }
        await closeList(el);
        return [...names].filter((t) => t && !PLACEHOLDER.test(t) && !/^select one$/i.test(t)).slice(0, 400);
    }

    // Picks an option in a dropdown or a search-and-pick box; false when no option matches
    async function choose(f, value) {
        const el = f.els[0];
        if (f.searchPick && f.current) {   // replacing a wrong pick: remove what is there first
            const box = el.closest('[data-automation-id="multiSelectContainer"]') || el.parentElement;
            for (const del of box.querySelectorAll('[data-automation-id="DELETE_charm"]')) { del.click(); await wait(250); }
        }
        const before = new Set(optionsFor(el));
        el.click();   // Workday's search boxes list every option on click; typing does not filter them
        const list = await until(() => optionsFor(el, before).length && optionsFor(el, before), 3000);
        if (!list) { await closeList(el); return false; }
        let opt = pick(list, value);
        const box = list[0].closest('[role="listbox"]') || list[0].parentElement;
        for (let k = 0; !opt && box && k < 80; k++) {   // virtualised lists: scroll until it shows up (or the end)
            if (box.scrollTop + box.clientHeight >= box.scrollHeight - 2) break;
            box.scrollTop += box.clientHeight;
            await wait(120);
            opt = pick(optionsFor(el, before), value);
        }
        if (!opt) { await closeList(el); return false; }
        opt.scrollIntoView({ block: 'nearest' });
        // Workday's search-box options are checkboxes inside the option: a bare click() is ignored, the full
        // pointer sequence on the inner node is what selects
        press(opt.querySelector('[data-automation-id="promptLeafNode"]') || opt);
        await wait(400);
        if (f.searchPick) await closeList(el);   // multi-select boxes stay open after a pick
        return true;
    }
    async function until(fn, timeout) {
        const end = Date.now() + timeout;
        while (Date.now() < end) { const v = fn(); if (v) return v; await wait(100); }
        return null;
    }

    async function apply(f, value) {
        if (value === undefined || value === null || value === '') return false;
        if (!f.els[0].isConnected) return false;   // the form moved to another step meanwhile
        value = String(value);
        if (f.searchPick && (f.options || []).length < 20 && /[,;]/.test(value)) {   // free multi-select (skills…): one pick per item
            let any = false;
            for (const item of value.split(/[,;]/).map((x) => x.trim()).filter(Boolean).slice(0, 10)) any = (await choose(f, item)) || any;
            return any;
        }
        if (f.dropdown || f.searchPick) return choose(f, value);
        if (f.type === 'select') {
            const opt = [...f.els[0].options].find((o) => o.text.trim().toLowerCase() === value.toLowerCase());
            if (!opt) return false;
            setValue(f.els[0], opt.value);
        } else if (f.type === 'radio') {
            const idx = f.options.findIndex((o) => o.toLowerCase() === value.toLowerCase());
            if (idx < 0) return false;
            f.els[idx].click();
        } else if (f.type === 'checkbox') {
            if ((value === 'true') !== f.els[0].checked) f.els[0].click();
        } else {
            setValue(f.els[0], value);
        }
        return true;
    }

    const mark = (f, color) => f.els.forEach((el) => { (el.type === 'radio' || el.type === 'checkbox' ? el.parentElement : el).style.outline = `2px solid ${color}`; });

    // ── Files: tailored resume (and cover letter) PDFs from CareerOps ──
    // Which document a file input wants. The text around an input often names both ("Resume/CV … Cover letter"), and
    // the resume used to win: the input's own attributes decide first, then the closest text that names only one.
    function fileKind(el, inputs) {
        const own = `${el.id} ${el.name} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('data-automation-id') || ''} ${el.getAttribute('data-qa') || ''}`;
        if (/cover|carta|motivation/i.test(own)) return 'cover';
        if (/resume|r[eé]sum[eé]|\bcv\b|curr[ií]cul/i.test(own)) return 'resume';
        if (inputs.length === 1) {
            // one upload on the step: the resume, unless its own short label asks for a letter (never page-wide text,
            // which includes the job description)
            for (let box = el.parentElement, k = 0; box && k < 3; box = box.parentElement, k++) {
                const t = (box.innerText || '');
                if (t.length > 300) break;
                if (COVER.test(t) && !RESUME.test(t)) return 'cover';
            }
            return 'resume';
        }
        for (let box = el.parentElement, k = 0; box && k < 8; box = box.parentElement, k++) {
            const t = (box.innerText || '').slice(0, 600);
            const cover = COVER.test(t), resume = RESUME.test(t);
            if (cover && !resume) return 'cover';
            if (resume && !cover) return 'resume';
            if (cover && resume) {
                // both in this box: the one named nearest before the input (the field's own heading)
                let last = null;
                const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
                for (let n = walker.nextNode(); n; n = walker.nextNode()) {
                    if (!(n.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) break;
                    if (COVER.test(n.textContent)) last = 'cover'; else if (RESUME.test(n.textContent)) last = 'resume';
                }
                if (last) return last;
                break;
            }
        }
        return inputs.length === 1 ? 'resume' : null;
    }
    const attached = new WeakSet();
    async function attachFiles(manual = false) {
        const inputs = [...document.querySelectorAll('input[type="file"]')].filter((el) => !el.disabled && !attached.has(el));
        if (!inputs.length) { if (manual) status('Não encontrei campo de arquivo nesta etapa.'); return 0; }
        let n = 0;
        for (const el of inputs) {
            const kind = fileKind(el, inputs);
            if (!kind || (kind === 'resume' && !prep.resume_markdown) || (kind === 'cover' && !prep.cover_letter)) continue;
            const file = await send({ action: 'backendFile', path: `/jobs/${jobId}/document.pdf?kind=${kind}` });
            if (!file || !file.ok) { status(`Não consegui baixar o ${kind === 'resume' ? 'CV' : 'carta'}: ${(file && file.detail) || ''}`); continue; }
            const bytes = Uint8Array.from(atob(file.b64), (c) => c.charCodeAt(0));
            const dt = new DataTransfer();
            dt.items.add(new File([bytes], file.name, { type: file.type }));
            el.files = dt.files;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            attached.add(el);
            n++;
        }
        if (manual || n) status(n ? `📎 ${n} arquivo(s) anexado(s) (CV personalizado em PDF).` : 'Nenhum campo de CV/carta reconhecido — anexe à mão.');
        return n;
    }

    // ── Fill: cover-letter boxes get the letter; the rest goes to the AI with your data (config + CV) ──
    let busy = false;
    let lastSignature = '';
    async function fillPage(manual = false) {
        if (busy) return;
        const all = collect();
        lastSignature = all.map((f) => f.key).join('|');
        await attachFiles(false);
        if (!all.length) { if (manual) status('Nenhum campo nesta etapa.'); return; }
        busy = true;
        todo('');   // the previous step's list
        let filled = 0;
        const pending = [];
        const fixed = [];
        const toAsk = [];
        for (const f of all) {
            if (DEMOGRAPHIC.test(f.label)) { if (!f.current) { mark(f, '#e17055'); pending.push(f.label); } continue; }
            if (!f.current && f.type === 'textarea' && COVER.test(f.label) && prep.cover_letter) { await apply(f, prep.cover_letter); mark(f, '#00b894'); filled++; continue; }
            toAsk.push(f);   // empty ones are filled; filled ones are checked against the CV (sites prefill from a parsed resume, often wrongly)
        }
        // options of every list on the step (filled ones too: a correction must be an option that exists); the same
        // list repeated in each block ("Field of Study", language levels) is read once
        const lists = new Map();
        for (const f of toAsk.filter((x) => x.dropdown || x.searchPick).slice(0, 40)) {
            const name = f.label.split(' › ').pop();
            if (!lists.has(name)) {
                status(`Lendo as opções de "${name.slice(0, 40)}"…`);
                lists.set(name, await readOptions(f));
            }
            f.options = lists.get(name);
        }
        status(`Preenchendo ${toAsk.filter((f) => !f.current).length} campo(s) e conferindo ${toAsk.filter((f) => f.current).length} com o CV…`);
        // one call for the whole step: the AI sees every block complete (Work Experience 1…n, Education 1…n)
        const res = await copilot('POST', '/easy-apply/answers', {
            // a dropdown whose options could not be read goes as text: the answer is then matched to the options when picked
            job: prep.job, fields: toAsk.slice(0, 100).map(({ key, type, label, options, current, searchPick }) => ({
                key, label, current,
                // a list read whole is a choice among its options; a search box that lists only a few (Skills) is free search, left to you
                type: (searchPick && options.length >= 20) ? 'select' : (type === 'select' && !options.length ? 'text' : type),
                options: searchPick && options.length < 20 ? [] : options,
            })),
        });
        if (!res.ok) { status(errText(res)); busy = false; return; }
        const sugg = res.data.suggestions || {};
        const corrections = res.data.corrections || {};
        for (const f of toAsk) {
            if (f.current) {
                const c = corrections[f.key];
                if (c && c.value !== undefined && String(c.value) !== String(f.current) && await apply(f, c.value)) {
                    mark(f, '#0984e3');
                    fixed.push(`${f.label.split(' › ').slice(0, 1).concat(f.label.split(' › ').slice(-1)).join(' › ')}: ${String(f.current).slice(0, 30)} → ${String(c.value).slice(0, 40)}`);
                }
                continue;
            }
            if (await apply(f, res.data.answers[f.key])) { mark(f, '#00b894'); filled++; continue; }
            const sg = sugg[f.key];
            if (sg && await apply(f, sg.value)) { mark(f, '#fdcb6e'); pending.push(`${f.label} (sugestão: ${sg.value} — confirme)`); continue; }
            if (f.type === 'checkbox') continue;   // left unchecked is an answer too ("I currently work here" on a past job)
            mark(f, '#e17055');
            pending.push(f.label || f.key);
        }
        busy = false;
        status(`✓ ${filled} preenchido(s) em verde${fixed.length ? `, ${fixed.length} corrigido(s) em azul (diferiam do CV)` : ''}. Revise e clique em enviar/avançar — o envio é seu.`);
        todo([
            fixed.length ? `Corrigidos pelo CV (azul):\n• ${fixed.slice(0, 8).join('\n• ')}` : '',
            pending.length ? `Com você (laranja/amarelo):\n• ${pending.slice(0, 8).map((p) => p.slice(0, 90)).join('\n• ')}` : '',
        ].filter(Boolean).join('\n'));
        // the form moved to another step while the AI answered: fill the new one
        const now = collect();
        if (ui.auto && ui.auto.checked && now.map((x) => x.key).join('|') !== lastSignature && now.length) fillPage(false);
    }

    // New step of a multi-page form (Workday, Gupy…): fill it too
    const observer = new MutationObserver(() => {
        clearTimeout(observer.t);
        observer.t = setTimeout(() => {
            if (!ui.auto || !ui.auto.checked || busy) return;
            const sig = collect().map((f) => f.key).join('|');
            if (sig && sig !== lastSignature) fillPage(false);
        }, 1200);
    });

    let jobId = null;
    let prep = {};
    (async () => {
        await started;
        await ready();
        const pending = await send({ action: 'applyPending' });
        if (!pending) return;
        jobId = pending.jobId;
        await wait(1500);   // let the application form render
        if (inFrame && collect().length < 3) return;   // only frames that hold the form get a panel
        if (!inFrame && collect().length < 2 && document.querySelector('iframe')) {
            await wait(2500);
            if (collect().length < 2 && [...document.querySelectorAll('iframe')].some((f) => f.offsetHeight > 300)) return;   // the form is in a frame: its panel runs there
        }
        const res = await backend('POST', `/jobs/${jobId}/auto-apply/prepare`, {});
        prep = res.ok ? res.data : { job: {} };
        panel(prep.job || {});
        if (!res.ok) { status(errText(res)); return; }
        await fillPage(false);
        observer.observe(document.body, { childList: true, subtree: true });
    })();
})();
