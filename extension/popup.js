document.addEventListener('DOMContentLoaded', () => {
    const $ = (id) => document.getElementById(id);
    const importBtn = $('import-btn');
    const cancelBtn = $('cancel-btn');
    const statusText = $('status-text');
    const loader = $('loader');
    const version = chrome.runtime.getManifest().version;
    $('version').textContent = `v${version}`;

    const send = (msg) => new Promise((resolve) => {
        chrome.runtime.sendMessage(msg, (res) => resolve(chrome.runtime.lastError ? null : res));
    });
    const newer = (a, b) => {          // is version a newer than b?
        const pa = String(a).split('.').map(Number), pb = String(b).split('.').map(Number);
        for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
            if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0);
        }
        return false;
    };

    // ── Header: backend and LinkedIn API indicators (details on hover), version with update notice, links ─────
    async function loadConnection() {
        const st = await send({ action: 'backendStatus' });
        if (!st || !st.ok) {
            $('conn-dot').className = 'dot bad';
            $('conn-chip').title = 'Backend inacessível — confira se o computador está no Tailscale e se o app abre no navegador.';
            $('pub-chip').title = 'Publicação no LinkedIn: sem backend';
            return null;
        }
        $('conn-dot').className = 'dot ok';
        $('conn-chip').title = `Conectado em ${st.ms} ms · ${st.base.replace(/^https?:\/\//, '').replace(/\/api$/, '')}`;
        const s = st.status || {};
        $('pub-dot').className = 'dot ' + (s.connected ? 'ok' : 'warn');
        $('pub-chip').title = 'Publicação no LinkedIn: ' + (s.connected ? `API conectada (${s.member_name || ''})` : 'manual — copiar e colar');
        // the app (frontend) lives behind the same HTTPS host; on the server itself it is :5173
        const app = st.appUrl.replace(':8005', ':5173');
        $('link-app').href = app + '/';
        $('link-copilot').href = app + '/linkedin-copilot';
        $('link-install').href = $('version').href = app + '/configuracoes?tab=extensao';
        if (st.serverVersion && newer(st.serverVersion, version)) {
            $('version').classList.add('new');
            $('version').textContent = `v${version} → v${st.serverVersion}`;
            $('version').title = `Versão nova disponível (v${st.serverVersion}): clique em Atualizar`;
        } else {
            $('version').title = `v${version} · atualizada`;
        }
        return st;
    }

    // ── Today's numbers (same as the app's Início) ───────────────────────────────────────────────
    async function loadStats() {
        const api = (path) => send({ action: 'copilotApi', method: 'GET', path });
        const [posts, eng, pros] = await Promise.all([api('/posts'), api('/engagement'), api('/prospects')]);
        if (posts && posts.ok) $('s-drafts').textContent = posts.data.posts.filter((p) => p.status === 'draft' || p.status === 'failed').length;
        if (eng && eng.ok) $('s-comments').textContent = `${eng.data.done_today}/${eng.data.daily_target}`;
        if (pros && pros.ok) $('s-invites').textContent = `${pros.data.invited_this_week}/${pros.data.weekly_target}`;
    }

    // ── Prospect check (accepted invites / replies): last result and a manual run ──────────────────
    const ago = (t) => { const m = Math.round((Date.now() - t) / 60000); return m < 60 ? `há ${m} min` : m < 1440 ? `há ${Math.round(m / 60)} h` : `há ${Math.round(m / 1440)} d`; };
    async function loadCheck() {
        const { prospectCheck: c } = await chrome.storage.local.get('prospectCheck');
        if (c) $('check-text').textContent = `Última verificação ${ago(c.at)}: ${c.summary || '—'}`;
    }
    $('check-btn').addEventListener('click', async () => {
        $('check-btn').disabled = true;
        const r = await send({ action: 'checkProspects' });
        $('check-text').textContent = r && r.ok ? 'Verificando numa aba em segundo plano (~1 min)…' : (r && r.detail) || 'Não consegui iniciar';
        setTimeout(() => { $('check-btn').disabled = false; }, 5000);
    });
    loadCheck();
    chrome.storage.onChanged.addListener((ch) => { if (ch.prospectCheck) loadCheck(); });

    // ── What can be done on the current page ─────────────────────────────────────────────────────
    let pageKind = 'other';
    let lockStatus = false;          // keeps the saved-jobs result visible over the 1 s refresh
    function describePage(tab) {
        const url = (tab && tab.url) || '';
        const li = url.includes('linkedin.com');
        const path = li ? new URL(url).pathname : '';
        let kind = 'other', title = 'Fora do LinkedIn', actions = ['Em páginas de vagas de outros sites: “Importar vaga (modo universal)”.'], btn = 'Importar vaga (modo universal)';
        if (li && (/^\/jobs\/view\//.test(path) || /[?&]currentJobId=/.test(url))) {
            kind = 'job'; title = 'Vaga do LinkedIn';
            actions = ['📥 CareerOps ao lado do botão Save — e clicar em Save já importa.', 'No Easy Apply: ✨ Preencher com IA no topo da janela.'];
            btn = 'Importar esta vaga';
        } else if (li && /^\/in\/[^/]+\/?$/.test(path)) {
            kind = 'profile'; title = 'Perfil de pessoa';
            actions = ['🤝 Conectar (CareerOps) ao lado do Conectar: avalia o encaixe e convida sem nota.', 'No seu próprio perfil: botão CareerOps · Perfil com os textos EN/PT.'];
            btn = 'Importar como MEU perfil (só no seu)';
        } else if (li && /^\/in\/[^/]+\/(details|edit)/.test(path)) {
            kind = 'profile-edit'; title = 'Edição do seu perfil';
            actions = ['CareerOps · Perfil (canto inferior esquerdo): clique no campo do LinkedIn e em “Inserir”.'];
            btn = 'Importar meu perfil';
        } else if (li && /^\/(my-items\/saved-jobs|jobs-tracker)/.test(path)) {
            kind = 'saved'; title = 'Suas vagas salvas';
            actions = ['📥 Importa as vagas da lista para o CareerOps (Vagas, status “new”), com a descrição de cada uma.', 'Até 25 por clique, uma a uma, sem clicar em nada da página. Role a lista para pegar mais.'];
            btn = 'Importar vagas salvas';
        } else if (li && /^\/(search\/results\/people|mynetwork)/.test(path)) {
            kind = 'people'; title = 'Lista de pessoas';
            actions = ['⭐ Avaliar pessoas da página (canto inferior direito): nota e mercado de cada um.'];
            btn = null;
        } else if (li && /^\/(feed|posts|feed\/update)/.test(path)) {
            kind = 'feed'; title = 'Feed / post';
            actions = ['✨ Comentário IA em cada post: rascunha e insere; você publica.', '📌 Salvar tema: vira inspiração para posts seus.'];
            btn = null;
        } else if (li) {
            kind = 'linkedin'; title = 'LinkedIn';
            actions = ['Abra o feed, um perfil, uma vaga ou uma busca de pessoas para ver as ações.'];
            btn = null;
        }
        pageKind = kind;
        $('page-kind').textContent = title;
        $('page-actions').innerHTML = '';
        actions.forEach((a) => { const li2 = document.createElement('li'); li2.textContent = a; $('page-actions').appendChild(li2); });
        importBtn.style.display = btn ? 'block' : 'none';
        if (btn) importBtn.dataset.label = btn;
    }

    // ── Import progress (profile / job), unchanged behaviour ─────────────────────────────────────
    const updateUI = async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const { careerops_import_active, careerops_status } = await chrome.storage.local.get(['careerops_import_active', 'careerops_status']);
        describePage(tab);
        if (careerops_import_active) {
            importBtn.disabled = true;
            importBtn.textContent = 'Processando…';
            statusText.textContent = careerops_status || 'Iniciando…';
            loader.style.display = 'block';
            cancelBtn.style.display = 'block';
        } else {
            if (!lockStatus) importBtn.disabled = false;
            importBtn.textContent = importBtn.dataset.label || 'Importar';
            cancelBtn.style.display = 'none';
            loader.style.display = 'none';
            if (!lockStatus) statusText.textContent = careerops_status && /✅|❌/.test(careerops_status) ? careerops_status : 'Pronto para agir';
        }
    };

    async function ensureContentScript(tab) {
        try {
            await chrome.tabs.sendMessage(tab.id, { action: 'ping' });
        } catch (e) {
            await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
            await new Promise((r) => setTimeout(r, 500));
        }
    }

    importBtn.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (pageKind === 'saved') {
            lockStatus = true;
            importBtn.disabled = true;
            statusText.textContent = 'Importando vagas salvas… (acompanhe o botão na página)';
            chrome.tabs.sendMessage(tab.id, { action: 'importSavedJobs' }, (res) => {
                importBtn.disabled = false;
                setTimeout(() => { lockStatus = false; }, 8000);
                statusText.textContent = chrome.runtime.lastError ? 'Recarregue a página do LinkedIn (F5) e tente de novo'
                    : res && res.ok ? `✅ ${res.imported} de ${res.total} vaga(s) importadas` : '❌ Nenhuma vaga visível na lista';
            });
            return;
        }
        await chrome.storage.local.set({ careerops_import_active: true, careerops_status: 'Iniciando…', careerops_import_data: { step: 'start' } });
        await ensureContentScript(tab);
        if (pageKind === 'profile' || pageKind === 'profile-edit') chrome.tabs.sendMessage(tab.id, { action: 'extractProfile' });
        else if (pageKind === 'job') chrome.tabs.sendMessage(tab.id, { action: 'extractJob' });
        else chrome.tabs.sendMessage(tab.id, { action: 'extractUniversal' });
    });

    cancelBtn.addEventListener('click', async () => {
        await chrome.storage.local.remove(['careerops_import_active', 'careerops_status', 'careerops_import_data']);
        updateUI();
    });

    updateUI();
    setInterval(updateUI, 1000);
    loadConnection().then((ok) => { if (ok) loadStats(); });
});
