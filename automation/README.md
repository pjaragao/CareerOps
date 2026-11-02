# Autopilot: você aprova, o sistema executa

Worker com o navegador no servidor (Chromium + extensão), rotina Claude no host e monitor de e-mail no backend. **Sobe desligado** (`mode = off`): nada acontece até você ligar em **Automação → Buscas e limites**.

## Colocar no ar

1. Gere e cadastre as variáveis no Coolify (ou em `linkedin-jobs/.env`):

   ```bash
   openssl rand -hex 32
   ```

   `CAREEROPS_APPROVER_TOKEN`, `CAREEROPS_WORKER_TOKEN` (valores diferentes), `VNC_PASSWORD`, `AUTOMATION_ALLOW_FINAL_SUBMIT=false`, `GMAIL_ADDRESS` e `GMAIL_APP_PASSWORD`.

   **Depois do deploy, aprovar e publicar posts passam a exigir o token:** digite-o em Configurações → Chaves de IA → Acesso.

2. Publique o noVNC pelo `nginx_secure`, com senha. O container só escuta em `127.0.0.1:6080`. Bloco para `nginx.conf`, igual aos existentes (crie o arquivo de senha com `htpasswd -c`):

   ```nginx
   server {
       listen 100.109.242.35:6081 ssl;
       server_name mpbflndsk201-wsl.tabby-broadnose.ts.net;
       auth_basic "CareerOps";
       auth_basic_user_file /etc/nginx/careerops.htpasswd;
       location / {
           proxy_pass http://127.0.0.1:6080;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_read_timeout 3600s;
       }
   }
   ```

3. Instale a rotina Claude no host:

   ```bash
   mkdir -p ~/.config/careerops && printf 'CAREEROPS_API_BASE=http://127.0.0.1:8005/api\nCAREEROPS_WORKER_TOKEN=<token do worker>\n' > ~/.config/careerops/runner.env && chmod 600 ~/.config/careerops/runner.env
   ```

   Linha do crontab:

   ```text
   */15 * * * * flock -n /tmp/careerops-claude.lock /usr/bin/python3 /home/paulojr/linkedin_resume/automation/claude_runner/run.py >> /home/paulojr/backups/careerops/claude-runner.log 2>&1
   ```

## Fases de ligação

| Etapa | O que fazer | Avança quando |
|---|---|---|
| **F1** | Conta de teste: abra "Ver navegador", faça login. Meça RAM, listas com mais de 10 itens, janelas em paralelo, sessão após reinício e redeploy. Repita com `BROWSER_MODE=headless`. | Você escolher modo e concorrência |
| **F3** | Conta de teste, modo **Ensaio**. Deixe as buscas rodarem 3 dias. Revise uma amostra acima e abaixo da nota 70. | Sem duplicatas, corte validado |
| **F4** | Conta de teste, modo **Ligada**, com alvos permitidos em `config/automation.yml → test_account.allowed_targets` (só o que é seu, ou de quem concordou). | 10 execuções de cada tipo |
| **F5** | Teste: 20 vagas até a tela final. Depois **conta principal**, `AUTOMATION_ALLOW_FINAL_SUBMIT=true`, 3 vagas reais com sua confirmação. | Dossiês corretos, as 3 confirmadas no LinkedIn |
| **F6** | Quebre um seletor de propósito e observe a rotina Claude. | Termina em `done` ou `needs_user` corretos |
| **F7** | `jobs.external_apply: true`, 5 externas assistidas. | Sem erro |
| **F8** | Conta principal, rampa dos limites. | 4 semanas sem alerta |

Conta de teste **nunca envia candidatura**, qualquer que seja a configuração. Na principal, o envio exige quatro condições ao mesmo tempo: modo Ligada, conta principal, permissão marcada no app e `AUTOMATION_ALLOW_FINAL_SUBMIT=true`.

## Testes

```bash
cd backend && pip install -r requirements-dev.txt && PYTHONPATH=. pytest tests
```

```bash
pytest automation/tests -q
```

```bash
node --test automation/tests/apply_rules.test.js automation/tests/post_text.test.js
```

Ponta a ponta, sem tocar no LinkedIn: backend, worker e extensão reais, em Chromium real, contra um site falso (`tests/e2e/fake_linkedin.py`) e um banco descartável. `--claude` usa a rotina de verdade, consumindo a sua assinatura. **Prova o fluxo, não que o LinkedIn real continua igual:** os seletores reais só são validados nas fases acima.

```bash
automation/tests/e2e/run.sh
```

## Onde está o quê

| O quê | Onde |
|---|---|
| Regras (limites, janela, estados) | `backend/app/services/automation_service.py`. O worker não decide nada |
| Execução na página | `extension/linkedin_assist.js`, seção 8; `extension/apply_copilot.js` |
| Olhar a página: alertas e prova | `automation/worker/safety.py`, `verify.py` |
| Rotina Claude | `automation/claude_runner/run.py` |
| Termos proibidos, janela, nota mínima, sites externos | `config/automation.yml` |
| Sessão do LinkedIn | volume `careerops_browser` (nunca exponha) |
