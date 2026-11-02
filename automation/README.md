# Autopilot: você aprova, o sistema executa

Worker com o navegador no servidor (Chromium + extensão), rotina Claude no host e monitor de e-mail no backend. **Sobe desligado** (`mode = off`): nada acontece até você ligar em **Automação → Buscas e limites**.

## Stack de teste (já no ar neste servidor)

Para a conta de teste: banco `careerops_test`, sem dados da produção além do seu perfil e dos ajustes de IA. Nunca envia candidatura (`AUTOMATION_ALLOW_FINAL_SUBMIT` fixo em `false`). Definida em `test-stack/docker-compose.yml`, sem rótulos do Coolify.

| O quê | Onde |
|---|---|
| Tela Automação | `https://mpbflndsk201-wsl.tabby-broadnose.ts.net:6082/automacao` |
| Navegador (noVNC) | `https://mpbflndsk201-wsl.tabby-broadnose.ts.net:6081/vnc.html` |
| Senhas e tokens | `~/.config/careerops/test-stack.env`: `NGINX_USER`/`NGINX_PASSWORD` (site), `VNC_PASSWORD` (noVNC), `CAREEROPS_APPROVER_TOKEN` (Configurações → Chaves de IA → Acesso) |
| Rotina Claude | crontab, a cada 15 min; config em `~/.config/careerops/runner.env`; log em `~/backups/careerops/claude-runner.log` |

Recriar depois de mudar o código (`config/` e a extensão entram na imagem):

```bash
docker compose --env-file ~/.config/careerops/test-stack.env -f automation/test-stack/docker-compose.yml up -d --build
```

## Produção

Cada `git push` na `main` implanta pelo Coolify (auto-deploy). O serviço `automation` sobe junto, parado até ter token e modo ligado.

1. **Cadastre `CAREEROPS_APPROVER_TOKEN` no Coolify** (CareerOps → Environment Variables) com o valor de `~/.config/careerops/production.env`, faça um redeploy e digite o mesmo valor em Configurações → Chaves de IA → Acesso. Até lá, aprovar e publicar posts pela tela retorna 401; o que já foi aprovado continua saindo no horário.

   **Para ligar a automação na produção (F8):** cadastre também `CAREEROPS_WORKER_TOKEN`, `VNC_PASSWORD` e `AUTOMATION_ALLOW_FINAL_SUBMIT`, do mesmo arquivo, e faça um redeploy. Sem o token do worker, o serviço `automation` fica parado: não abre navegador nem visita o LinkedIn. Para o monitor de e-mail, `GMAIL_ADDRESS` e `GMAIL_APP_PASSWORD`.

2. O noVNC da produção já tem rota em `https://mpbflndsk201-wsl.tabby-broadnose.ts.net:6083/vnc.html`, com a mesma senha do site.

3. Para a rotina Claude atender à produção, troque `~/.config/careerops/runner.env`:

   ```text
   CAREEROPS_API_BASE=http://127.0.0.1:8005/api
   CAREEROPS_WORKER_TOKEN=<token do worker da produção>
   CAREEROPS_MCP_PORT_LINKEDIN=8931
   CAREEROPS_MCP_PORT_ATS=8932
   ```

4. O CLI precisa estar logado no servidor, senão cada execução da rotina termina em "Precisa de você":

   ```bash
   claude auth login
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
