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
    const HEADINGS = 'h2, h3, h4, h5, legend, [role="heading"]';
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
        const sec = sectionOf(el);
        return sec && !label.toLowerCase().includes(sec.toLowerCase()) ? `${sec} › ${label}` : label;
    };

    // Workday-style dropdowns: a button that opens a list of options (not a <select>)
    const DROPDOWN = 'button[aria-haspopup="listbox"], [role="combobox"][aria-haspopup="listbox"]:not(input)';
    const OPTION = '[role="listbox"] [role="option"], [data-automation-id="promptOption"]';
    const visibleOptions = () => [...document.querySelectorAll(OPTION)].filter((o) => visible(o) && !o.closest('#careerops-apply-copilot'));
    // search-and-pick inputs ("How did you hear about us?"): typing shows options to click
    const isSearchPick = (el) => el.tagName === 'INPUT' && (el.getAttribute('role') === 'combobox' || /searchbox/i.test(el.getAttribute('data-automation-id') || ''));

    function collect() {
        const fields = [];
        const seen = new Set();
        document.querySelectorAll(DROPDOWN).forEach((el, i) => {
            if (el.closest('#careerops-apply-copilot') || el.disabled || !visible(el)) return;
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
                f.current = el.value || null;
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
    const closeList = (el) => { el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); document.body.click(); };

    // Opens a dropdown and reads its options (long lists are scrolled to load all of them), then closes it
    async function readOptions(f) {
        const el = f.els[0];
        el.click();
        const first = await until(() => visibleOptions().length && visibleOptions(), 2000);
        if (!first) { closeList(el); return []; }
        const names = new Set(first.map((o) => clean(o.innerText)));
        const list = first[0].closest('[role="listbox"]') || first[0].parentElement;
        for (let k = 0; k < 30 && list && list.scrollHeight > list.clientHeight + 5; k++) {
            const before = names.size;
            list.scrollTop += list.clientHeight;
            await wait(120);
            visibleOptions().forEach((o) => names.add(clean(o.innerText)));
            if (names.size === before && list.scrollTop + list.clientHeight >= list.scrollHeight - 2) break;
        }
        closeList(el);
        await wait(150);
        return [...names].filter((t) => t && !PLACEHOLDER.test(t) && !/^select one$/i.test(t)).slice(0, 300);
    }

    // Picks an option in a dropdown or a search-and-pick box; false when no option matches
    async function choose(f, value) {
        const el = f.els[0];
        if (f.searchPick) typeText(el, value); else el.click();
        const list = await until(() => visibleOptions().length && visibleOptions(), 2500);
        if (!list) { closeList(el); return false; }
        let opt = pick(list, value);
        const box = list[0].closest('[role="listbox"]') || list[0].parentElement;
        for (let k = 0; !opt && box && k < 30; k++) {   // virtualised lists: scroll until it shows up
            box.scrollTop += box.clientHeight;
            await wait(120);
            opt = pick(visibleOptions(), value);
        }
        if (!opt) { closeList(el); return false; }
        opt.scrollIntoView({ block: 'nearest' });
        opt.click();
        await wait(250);
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
    const attached = new WeakSet();
    async function attachFiles(manual = false) {
        const inputs = [...document.querySelectorAll('input[type="file"]')].filter((el) => !el.disabled && !attached.has(el));
        if (!inputs.length) { if (manual) status('Não encontrei campo de arquivo nesta etapa.'); return 0; }
        let n = 0;
        for (const el of inputs) {
            const ctx = `${labelOf(el)} ${el.name} ${el.id} ${(el.closest('div, section, fieldset') || {}).innerText || ''}`.slice(0, 400);
            const kind = COVER.test(ctx) && !RESUME.test(labelOf(el)) ? 'cover' : RESUME.test(ctx) || inputs.length === 1 ? 'resume' : null;
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
        const empty = all.filter((f) => !f.current);
        await attachFiles(false);
        if (!empty.length) { if (manual) status('Nada vazio para preencher nesta etapa.'); return; }
        busy = true;
        todo('');   // the previous step's list
        // what is already filled in the same block helps the AI ("Work Experience 2: Job Title = Engineer" → Company)
        const bySection = new Map();
        for (const f of all) {
            const sec = f.label.includes(' › ') ? f.label.split(' › ')[0] : '';
            if (sec && f.current) bySection.set(sec, [...(bySection.get(sec) || []), `${f.label.split(' › ').slice(1).join(' › ')} = ${String(f.current).slice(0, 60)}`]);
        }
        for (const f of empty) {
            const sec = f.label.includes(' › ') ? f.label.split(' › ')[0] : '';
            if (sec && bySection.get(sec)) f.label = `${f.label} [same block already has: ${bySection.get(sec).slice(0, 4).join('; ')}]`.slice(0, 300);
        }
        for (const f of empty.filter((x) => x.dropdown).slice(0, 15)) {
            status(`Lendo as opções de "${f.label.slice(0, 40)}"…`);
            f.options = await readOptions(f);
        }
        let filled = 0;
        const pending = [];
        const toAsk = [];
        for (const f of empty) {
            if (f.type === 'textarea' && COVER.test(f.label) && prep.cover_letter) { await apply(f, prep.cover_letter); mark(f, '#00b894'); filled++; continue; }
            if (DEMOGRAPHIC.test(f.label)) { mark(f, '#e17055'); pending.push(f.label); continue; }
            toAsk.push(f);
        }
        status(`Preenchendo ${toAsk.length} campo(s) com IA…`);
        for (let i = 0; i < toAsk.length; i += 25) {
            const chunk = toAsk.slice(i, i + 25);
            const res = await copilot('POST', '/easy-apply/answers', {
                // a dropdown whose options could not be read goes as text: the answer is then matched to the options when picked
                job: prep.job, fields: chunk.map(({ key, type, label, options, current }) => ({ key, type: type === 'select' && !options.length ? 'text' : type, label, options, current })),
            });
            if (!res.ok) { status(errText(res)); busy = false; return; }
            const sugg = res.data.suggestions || {};
            for (const f of chunk) {
                if (await apply(f, res.data.answers[f.key])) { mark(f, '#00b894'); filled++; continue; }
                const sg = sugg[f.key];
                if (sg && await apply(f, sg.value)) { mark(f, '#fdcb6e'); pending.push(`${f.label} (sugestão: ${sg.value} — confirme)`); continue; }
                mark(f, '#e17055');
                pending.push(f.label || f.key);
            }
        }
        busy = false;
        status(`✓ ${filled} campo(s) preenchido(s) em verde. Revise e clique em enviar/avançar — o envio é seu.`);
        todo(pending.length ? `Com você (laranja/amarelo):\n• ${pending.slice(0, 8).map((p) => p.split(' [same block')[0].slice(0, 90)).join('\n• ')}` : '');
        // the form moved to another step while the AI answered: fill the new one
        const now = collect();
        if (ui.auto && ui.auto.checked && now.map((x) => x.key).join('|') !== lastSignature && now.some((x) => !x.current)) fillPage(false);
    }

    // New step of a multi-page form (Workday, Gupy…): fill it too
    const observer = new MutationObserver(() => {
        clearTimeout(observer.t);
        observer.t = setTimeout(() => {
            if (!ui.auto || !ui.auto.checked || busy) return;
            const sig = collect().map((f) => f.key).join('|');
            if (sig && sig !== lastSignature && collect().some((f) => !f.current)) fillPage(false);
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
