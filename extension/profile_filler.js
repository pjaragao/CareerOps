// CareerOps — LinkedIn profile filler (English + Portuguese).
// Shows a side panel with the approved texts (from the CareerOps backend) for each profile field.
// "Inserir" puts a text into the field you clicked last in LinkedIn's edit form; YOU review and click Save.
// Nothing is submitted, saved or clicked on LinkedIn by this script.
(() => {
    if (window.__careeropsFiller) return;
    window.__careeropsFiller = true;

    const STORE_KEY = 'careeropsFillerDone';
    const MONTHS = {
        en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        pt: ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'],
    };
    const UI = {
        en: { present: 'Present', headline: 'Headline', about: 'About', positions: 'Experience', projects: 'Projects',
              skills: 'Skills', remove: 'Remove / fix', education: 'Education', licenses: 'Licenses & certifications', languages: 'Languages', degree: 'Degree', field: 'Field of study', copy: 'Copy', insert: 'Insert', title: 'Title', description: 'Description',
              hint: 'Click a field in LinkedIn\'s edit form, then “Insert”. Review and click Save on LinkedIn.',
              noField: 'Click the LinkedIn field first, then “Insert”.', optional: 'optional', top: 'Top 5', all: 'Add these',
              howto: 'English profile: Profile → “Add profile in another language” → English. Fill name, headline, About and each position title/description.' },
        pt: { present: 'o momento', headline: 'Título', about: 'Sobre', positions: 'Experiência', projects: 'Projetos',
              skills: 'Competências', remove: 'Apagar / corrigir', education: 'Formação acadêmica', licenses: 'Licenças e certificados', languages: 'Idiomas', degree: 'Diploma', field: 'Área de estudo', copy: 'Copiar', insert: 'Inserir', title: 'Cargo', description: 'Descrição',
              hint: 'Clique num campo do formulário de edição do LinkedIn e depois em “Inserir”. Revise e clique em Salvar no LinkedIn.',
              noField: 'Clique primeiro no campo do LinkedIn e depois em “Inserir”.', optional: 'opcional', top: 'Top 5', all: 'Adicionar',
              howto: 'Perfil principal em português. As competências e os projetos são únicos para os dois idiomas: cadastre em inglês.' },
    };

    let data = null;
    let lang = 'en';
    let done = {};
    let lastField = null;

    // Remember the last editable field the user focused on LinkedIn (outside our panel).
    document.addEventListener('focusin', (e) => {
        const el = e.target;
        if (host && host.contains(el)) return;
        if (el.matches && (el.matches('textarea, input[type="text"], input:not([type])') || el.isContentEditable)) lastField = el;
    }, true);

    function insertInto(el, text) {
        el.focus();
        if (el.isContentEditable) {
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, text);
            return;
        }
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);   // works with framework-controlled inputs
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    const fmtDate = (ym, l) => {
        if (!ym) return UI[l].present;
        const [y, m] = ym.split('-');
        return `${MONTHS[l][Number(m) - 1]} ${y}`;
    };

    // ── UI (shadow DOM, so LinkedIn's CSS does not leak in) ─────────────
    const host = document.createElement('div');
    host.id = 'careerops-filler';
    const root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { all: initial; }
        .panel { position: fixed; left: 16px; bottom: 16px; width: 420px; max-height: 78vh; overflow: auto; z-index: 2147483647;
                 background: #14141c; color: #e8e8f0; border: 1px solid #2c2c3a; border-radius: 14px; padding: 14px;
                 font: 13px/1.45 system-ui, sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,.4); display: none; }
        .panel.open { display: block; }
        .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .tabs button, .btn { background: #262636; color: #e8e8f0; border: 1px solid #3a3a4e; border-radius: 8px; padding: 4px 10px; cursor: pointer; font: inherit; }
        .tabs button.on { background: #6c5ce7; border-color: #6c5ce7; }
        .btn.primary { background: #6c5ce7; border-color: #6c5ce7; }
        h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: #9a9ab0; margin: 14px 0 6px; }
        .item { background: #1c1c28; border: 1px solid #2a2a3a; border-radius: 10px; padding: 8px 10px; margin-bottom: 8px; }
        .item.done { opacity: .5; }
        .meta { color: #9a9ab0; font-size: 12px; }
        .text { white-space: pre-wrap; max-height: 110px; overflow: auto; margin: 6px 0; color: #d6d6e2; font-size: 12px; }
        .row { display: flex; gap: 6px; align-items: center; justify-content: flex-end; flex-wrap: wrap; }
        .row label { margin-right: auto; color: #9a9ab0; font-size: 12px; display: flex; gap: 4px; align-items: center; }
        .hint { color: #9a9ab0; font-size: 12px; margin-bottom: 6px; }
        .err { color: #ff8a8a; }
        .chips span { display: inline-block; background: #262636; border-radius: 6px; padding: 2px 6px; margin: 2px; font-size: 12px; }
        .toast { position: fixed; left: 16px; top: 72px; z-index: 2147483647; background: #00b894; color: #fff; padding: 8px 12px;
                 border-radius: 8px; font: 13px system-ui, sans-serif; display: none; }
      </style>
      <div class="panel"></div>
      <div class="toast"></div>`;
    const panel = root.querySelector('.panel');
    const toast = root.querySelector('.toast');

    function say(msg, ok = true) {
        toast.textContent = msg;
        toast.style.background = ok ? '#00b894' : '#d63031';
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 2500);
    }

    const key = (id) => `${lang}:${id}`;

    function textBlock(id, label, text, meta) {
        const isDone = !!done[key(id)];
        const div = document.createElement('div');
        div.className = 'item' + (isDone ? ' done' : '');
        div.innerHTML = `<div><strong></strong> <span class="meta"></span></div><div class="text"></div>
          <div class="row"><label><input type="checkbox"> ok</label>
          <button class="btn" data-a="copy"></button><button class="btn primary" data-a="insert"></button></div>`;
        div.querySelector('strong').textContent = label;
        div.querySelector('.meta').textContent = meta || `${text.length} car.`;
        div.querySelector('.text').textContent = text;
        div.querySelector('[data-a="copy"]').textContent = UI[lang].copy;
        div.querySelector('[data-a="insert"]').textContent = UI[lang].insert;
        const cb = div.querySelector('input');
        cb.checked = isDone;
        cb.addEventListener('change', () => {
            done[key(id)] = cb.checked;
            chrome.storage.local.set({ [STORE_KEY]: done });
            div.classList.toggle('done', cb.checked);
        });
        div.querySelector('[data-a="copy"]').addEventListener('click', async () => {
            try { await navigator.clipboard.writeText(text); say(UI[lang].copy + ' ✓'); } catch { say('Clipboard bloqueado', false); }
        });
        div.querySelector('[data-a="insert"]').addEventListener('click', () => {
            if (!lastField || !document.contains(lastField)) { say(UI[lang].noField, false); return; }
            insertInto(lastField, text);
            say(UI[lang].insert + ' ✓ — ' + (lang === 'en' ? 'review and Save' : 'revise e salve'));
        });
        return div;
    }

    function render() {
        const t = UI[lang];
        panel.innerHTML = '';
        const top = document.createElement('div');
        top.className = 'top';
        top.innerHTML = `<strong>CareerOps — LinkedIn</strong><div class="tabs"><button data-l="en">EN</button> <button data-l="pt">PT</button> <button data-l="x">✕</button></div>`;
        top.querySelectorAll('button').forEach((b) => {
            if (b.dataset.l === lang) b.classList.add('on');
            b.addEventListener('click', () => {
                if (b.dataset.l === 'x') { panel.classList.remove('open'); return; }
                lang = b.dataset.l; render();
            });
        });
        panel.appendChild(top);
        if (!data) {
            const p = document.createElement('div');
            p.className = 'err';
            p.textContent = 'Backend do CareerOps indisponível (porta 8005). Suba o backend e reabra o painel.';
            panel.appendChild(p);
            return;
        }
        const hint = document.createElement('div');
        hint.className = 'hint';
        hint.textContent = `${t.hint} ${t.howto}`;
        panel.appendChild(hint);

        const section = (title) => { const h = document.createElement('h3'); h.textContent = title; panel.appendChild(h); };

        section(t.headline);
        panel.appendChild(textBlock('headline', t.headline, data[lang].headline, `${data[lang].headline.length}/220`));
        section(t.about);
        panel.appendChild(textBlock('about', t.about, data[lang].about, `${data[lang].about.length}/2600`));

        section(t.positions);
        for (const p of data.positions) {
            const when = `${p.company} · ${fmtDate(p.start, lang)} – ${fmtDate(p.end, lang)}${p.optional ? ` · (${t.optional})` : ''}`;
            panel.appendChild(textBlock(`${p.id}:title`, `${t.title}`, p[lang].title, when));
            panel.appendChild(textBlock(`${p.id}:desc`, `${t.description} — ${p[lang].title}`, p[lang].description,
                `${p[lang].description.length}/2000`));
        }

        section(t.projects);
        for (const p of data.projects) {
            const when = `${fmtDate(p.start, lang)} – ${fmtDate(p.end, lang)}`;
            panel.appendChild(textBlock(`${p.id}:title`, t.title, p[lang].title, when));
            panel.appendChild(textBlock(`${p.id}:desc`, `${t.description} — ${p[lang].title}`, p[lang].description));
        }

        section(t.education);
        for (const e of data.education || []) {
            const when = `${e.school} · ${e.start}–${e.end}`;
            panel.appendChild(textBlock(`${e.id}:degree`, t.degree, e[lang].degree, when));
            panel.appendChild(textBlock(`${e.id}:field`, t.field, e[lang].field, when));
            panel.appendChild(textBlock(`${e.id}:desc`, `${t.description} — ${e[lang].field}`, e[lang].description));
        }

        section(t.licenses);
        for (const l of data.licenses || []) {
            panel.appendChild(textBlock(`${l.id}:name`, t.title, l[lang].name, `${l.issuer} · ${l.credential_id}`));
        }

        section(t.languages);
        for (const [i, l] of (data.languages || []).entries()) {
            panel.appendChild(textBlock(`lang:${i}`, t.languages, l[lang]));
        }

        section(t.skills);
        const sk = document.createElement('div');
        sk.className = 'item chips';
        sk.innerHTML = `<div class="meta">${t.top}</div>${data.skills_top.map((s) => `<span>${s}</span>`).join('')}
          <div class="meta" style="margin-top:6px">${t.all}</div>${data.skills.map((s) => `<span>${s}</span>`).join('')}`;
        panel.appendChild(sk);

        section(t.remove);
        for (const [i, r] of data.remove.entries()) {
            const div = document.createElement('div');
            div.className = 'item' + (done[key(`remove:${i}`)] ? ' done' : '');
            div.innerHTML = '<div class="row" style="justify-content:flex-start"><label style="margin-right:0"><input type="checkbox"></label><span></span></div>';
            div.querySelector('span').textContent = r[lang];
            const cb = div.querySelector('input');
            cb.checked = !!done[key(`remove:${i}`)];
            cb.addEventListener('change', () => { done[key(`remove:${i}`)] = cb.checked; chrome.storage.local.set({ [STORE_KEY]: done }); div.classList.toggle('done', cb.checked); });
            panel.appendChild(div);
        }
    }

    function load() {
        chrome.runtime.sendMessage({ action: 'getProfileCopy' }, (res) => {
            data = res && res.ok ? res.data : null;
            render();
        });
    }

    // Your own profile: LinkedIn shows the edit controls ("Add profile section", the pencils) only there
    const isOwnProfile = () => /^\/in\/[^/]+\/(details|edit)/.test(location.pathname)
        || (/^\/in\//.test(location.pathname) && [...document.querySelectorAll('main button, main a')].some((b) =>
            /add profile section|adicionar se[cç][aã]o|open to|dispon[ií]vel para|enhance profile|aprimorar perfil/i.test(b.innerText || b.getAttribute('aria-label') || '')));

    // Opened from the extension popup ("Textos do meu perfil"), only on your own profile — no floating button
    chrome.runtime.onMessage.addListener((req, _sender, sendResponse) => {
        if (req.action === 'fillerAvailable') { sendResponse({ own: isOwnProfile() }); return; }
        if (req.action !== 'openProfileFiller') return;
        panel.classList.add('open');
        load();
        sendResponse({ ok: true });
    });

    chrome.storage.local.get(STORE_KEY, (v) => { done = v[STORE_KEY] || {}; });
    document.documentElement.appendChild(host);
})();
