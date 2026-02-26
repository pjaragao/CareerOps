"""
Web UI — Flask interface for the LinkedIn Job Scraper.

Run: python web.py
Access: http://localhost:5050
"""
import json
import os
import threading
import time
from datetime import datetime, timezone
from flask import Flask, render_template_string, jsonify, request, send_from_directory

import db
from config import OUTPUT_DIR, SESSION_FILE, GEMINI_API_KEY

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------
task_status = {
    "running": False,
    "task": "",
    "progress": "",
    "logs": [],
    "error": None,
}
_task_lock = threading.Lock()


def _log(msg: str):
    """Thread-safe logging."""
    with _task_lock:
        task_status["logs"].append(
            {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg}
        )
        task_status["progress"] = msg
        # Keep only last 200 logs
        if len(task_status["logs"]) > 200:
            task_status["logs"] = task_status["logs"][-200:]


def _run_task(task_name: str, func, *args):
    """Run a task in background thread."""
    with _task_lock:
        if task_status["running"]:
            return False
        task_status["running"] = True
        task_status["task"] = task_name
        task_status["progress"] = "Starting..."
        task_status["logs"] = []
        task_status["error"] = None

    def worker():
        import builtins
        original_print = builtins.print

        def custom_print(*a, **kw):
            msg = " ".join(str(x) for x in a)
            _log(msg)
            original_print(*a, **kw)

        builtins.print = custom_print
        try:
            func(*args)
            _log(f"✅ {task_name} complete!")
        except Exception as e:
            _log(f"❌ Error: {e}")
            with _task_lock:
                task_status["error"] = str(e)
        finally:
            builtins.print = original_print
            with _task_lock:
                task_status["running"] = False

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat with Job</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-card: #16213e;
            --accent: #6c63ff;
            --text-primary: #e8e8f0;
            --text-secondary: #8888a8;
            --border: rgba(108, 99, 255, 0.15);
            --radius: 12px;
        }
        body { font-family: 'Inter', sans-serif; background: var(--bg-primary); color: var(--text-primary); margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: var(--bg-card); padding: 20px; border-radius: var(--radius); border: 1px solid var(--border); }
        h2 { margin-top: 0; font-size: 18px; color: var(--accent); }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; }
        textarea { width: 100%; height: 100px; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.2); color: var(--text-primary); font-family: inherit; font-size: 14px; box-sizing: border-box; }
        textarea:focus { outline: none; border-color: var(--accent); }
        button { background: var(--accent); color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; }
        button:hover { background: #7c74ff; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .answer-box { margin-top: 20px; padding: 15px; background: rgba(0,0,0,0.3); border-left: 4px solid var(--accent); border-radius: 4px; white-space: pre-wrap; display: none; }
        .loading { display: none; color: var(--accent); font-size: 14px; margin-top: 10px; }
        .controls { display: flex; gap: 15px; margin-bottom: 20px; }
        .control-group { flex: 1; }
        select { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-primary); color: var(--text-primary); }
    </style>
</head>
<body>
    <div class="container">
        <h2>💬 Assistente de Entrevista</h2>
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 20px;">
            Vaga: {{ job_title }} @ {{ company }}
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Tom da Resposta:</label>
                <select id="tone">
                    <option value="formal">Muito Formal</option>
                    <option value="semi-formal" selected>Semi-Formal (Equilibrado)</option>
                    <option value="informal">Informal, Direto e Amigável</option>
                </select>
            </div>
            <div class="control-group">
                <label>Modelo IA:</label>
                <select id="model-select">
                    <option value="gemini-3-flash-preview">gemini-3-flash-preview</option>
                </select>
            </div>
        </div>
        
        <div class="form-group">
            <label>Pergunta do Formulário / Empregador:</label>
            <textarea id="question" placeholder="Ex: Qual sua pretensão salarial? ou Why do you want to work here?"></textarea>
        </div>

        <div class="form-group">
            <label>Sua Orientação / Resposta curta (Opcional):</label>
            <textarea id="orientation" placeholder="Ex: Diga que é negociável, em torno de 5k. Mantenha profissional." style="height: 60px;"></textarea>
        </div>

        <button id="submitBtn" onclick="generateAnswer()">Gerar Resposta</button>
        <div id="loading" class="loading">⏳ Gerando resposta...</div>

        <div id="answerBox" class="answer-box">
            <label style="color:var(--accent)">Resposta:</label>
            <div id="answerText"></div>
            <button onclick="copyAnswer()" style="margin-top: 10px; padding: 6px 12px; font-size: 12px; background: rgba(255,255,255,0.1);">Copiar</button>
        </div>
    </div>

    <script>
        async function generateAnswer() {
            const question = document.getElementById('question').value.trim();
            const orientation = document.getElementById('orientation').value.trim();
            const tone = document.getElementById('tone').value;
            const modelName = document.getElementById('model-select').value;
            
            if (!question) { alert('Digite a pergunta.'); return; }

            const btn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const answerBox = document.getElementById('answerBox');
            
            btn.disabled = true;
            loading.style.display = 'block';
            answerBox.style.display = 'none';

            try {
                const res = await fetch('/api/chat/{{ job_id }}', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ question, orientation, tone, model_name: modelName })
                });
                const data = await res.json();
                
                if (data.ok) {
                    document.getElementById('answerText').textContent = data.answer;
                    answerBox.style.display = 'block';
                } else {
                    alert('Erro: ' + data.error);
                }
            } catch (e) {
                alert('Erro de conexão.');
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        }

        function copyAnswer() {
            const text = document.getElementById('answerText').textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('Copiado!');
            });
        }

        async function refreshModels() {
            try {
                const res = await fetch('/api/models');
                const data = await res.json();
                const selectElement = document.getElementById('model-select');
                if (data.models && data.models.length > 0) {
                    selectElement.innerHTML = data.models.map(m => `
                        <option value="${m}" ${m === 'gemini-3-flash-preview' ? 'selected' : ''}>${m}</option>
                    `).join('');
                }
            } catch (e) {
                console.error("Failed to load models list");
            }
        }
        
        refreshModels();
    </script>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinkedIn Job Scraper</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: #16213e;
            --bg-card-hover: #1c2a4a;
            --accent: #6c63ff;
            --accent-glow: rgba(108, 99, 255, 0.3);
            --accent-secondary: #00d4aa;
            --text-primary: #e8e8f0;
            --text-secondary: #8888a8;
            --text-muted: #555580;
            --border: rgba(108, 99, 255, 0.15);
            --success: #00d4aa;
            --warning: #ffb347;
            --error: #ff6b6b;
            --info: #54a0ff;
            --radius: 12px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        /* --- Header --- */
        .header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-bottom: 1px solid var(--border);
            padding: 20px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(20px);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent), var(--accent-secondary));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 700;
        }

        .header h1 {
            font-size: 16px;
            font-weight: 600;
            background: linear-gradient(135deg, var(--text-primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            white-space: nowrap;
        }

        .header-status {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s ease-in-out infinite;
        }

        .status-dot.error { background: var(--error); }
        .status-dot.warning { background: var(--warning); }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        /* --- Layout --- */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 32px;
        }

        /* --- Stats in Header --- */
        .header-stats {
            display: flex;
            gap: 24px;
            align-items: center;
            margin-left: 40px;
            padding-left: 40px;
            border-left: 1px solid rgba(255,255,255,0.1);
        }
        .h-stat { display: flex; flex-direction: column; }
        .h-label { font-size: 10px; text-transform: uppercase; color: var(--text-secondary); font-weight: 600; letter-spacing: 0.5px; }
        .h-val { font-size: 20px; font-weight: 700; color: var(--text-primary); margin-top: 2px; }
        .h-val.info { color: var(--info); }
        .h-val.warning { color: var(--warning); }
        .h-val.success { color: var(--success); }
        .h-val.error { color: var(--error); }

        /* --- Action buttons in Header --- */
        .actions-col {
            display: flex;
            align-items: center;
            gap: 16px;
            margin: 0 20px;
        }

        .action-group {
            display: flex;
            gap: 4px;
            align-items: center;
        }

        .action-divider {
            width: 1px;
            height: 20px;
            background: rgba(255,255,255,0.1);
            margin: 0 8px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 8px 14px;
            border: 1px solid transparent;
            border-radius: 8px;
            background: rgba(255,255,255,0.03);
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .btn:hover {
            color: var(--text-primary);
            background: rgba(255,255,255,0.1);
        }

        .btn:active { transform: scale(0.97); }

        .btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            pointer-events: none;
        }

        .btn.primary {
            background: var(--accent);
            color: white;
            box-shadow: 0 2px 8px var(--accent-glow);
        }

        .btn.primary:hover {
            background: #7c74ff;
            box-shadow: 0 4px 12px var(--accent-glow);
        }

        .btn.success { color: var(--success); background: rgba(0, 212, 170, 0.05); }
        .btn.success:hover { background: rgba(0, 212, 170, 0.15); }

        .btn.warning { color: var(--warning); }
        
        .btn.danger { color: var(--error); }
        .btn.danger:hover { background: rgba(255, 107, 107, 0.1); }

        .btn .icon { font-size: 14px; }

        /* --- Sections (two-column) --- */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 280px;
            gap: 20px;
        }

        @media (max-width: 1024px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }

        /* --- Jobs table --- */
        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }

        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }

        .panel-title {
            font-size: 15px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .panel-body {
            padding: 0;
            max-height: 600px;
            overflow-y: auto;
        }

        .panel-body::-webkit-scrollbar { width: 6px; }
        .panel-body::-webkit-scrollbar-track { background: transparent; }
        .panel-body::-webkit-scrollbar-thumb {
            background: var(--text-muted);
            border-radius: 3px;
        }

        .job-row {
            display: flex;
            align-items: center;
            padding: 14px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            transition: background 0.15s ease;
            gap: 12px;
        }

        .job-row:hover { background: rgba(108, 99, 255, 0.05); }

        .job-info {
            flex: 1;
            min-width: 0;
        }

        .job-title {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .job-company {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .job-meta {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-shrink: 0;
        }

        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .badge.new { background: rgba(84,160,255,0.15); color: var(--info); }
        .badge.scraped { background: rgba(255,179,71,0.15); color: var(--warning); }
        .badge.generating { background: rgba(108,99,255,0.15); color: var(--accent); }
        .badge.done { background: rgba(0,212,170,0.15); color: var(--success); }
        .badge.error { background: rgba(255,107,107,0.15); color: var(--error); }
        .badge.removed { background: rgba(85,85,128,0.15); color: var(--text-muted); }

        .badge.easy-apply {
            background: rgba(0,119,181,0.15);
            color: #0077b5;
            font-size: 10px;
            padding: 3px 8px;
        }

        .badge.remote {
            background: rgba(0,180,130,0.15);
            color: #00b482;
            font-size: 10px;
            padding: 3px 8px;
        }

        .job-download {
            color: var(--accent-secondary);
            text-decoration: none;
            font-size: 18px;
            transition: transform 0.2s;
        }

        .job-download:hover { transform: scale(1.2); }

        .job-container.expanded .job-row {
            position: sticky;
            top: 0;
            z-index: 10;
            background: var(--bg-card);
            border-bottom: 1px solid rgba(108,99,255,0.2);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .job-details {
            display: none;
            background: rgba(0,0,0,0.25);
            border-top: 1px solid rgba(255,255,255,0.05);
            font-size: 13px;
            color: var(--text-secondary);
            border-radius: 0 0 12px 12px;
            margin-bottom: 20px;
            animation: fadeIn 0.2s ease;
        }

        .job-details.active { display: block; }

        /* Detail tabs */
        .detail-tabs {
            display: flex;
            gap: 0;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid rgba(255,255,255,0.06);
            padding: 0 16px;
        }
        .detail-tab {
            padding: 10px 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            background: none;
            border: none;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .detail-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.03); }
        .detail-tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
            background: rgba(108,99,255,0.05);
        }
        .detail-tab .tab-count {
            font-size: 10px;
            background: rgba(108,99,255,0.2);
            color: var(--accent);
            padding: 1px 6px;
            border-radius: 10px;
        }

        .tab-panel {
            display: none;
            padding: 20px;
            max-height: 60vh;
            overflow-y: auto;
        }
        .tab-panel.active { display: block; }

        .details-content { 
            font-size: 13px; color: var(--text-secondary); 
            line-height: 1.6; white-space: pre-wrap;
        }
        .company-url { 
            color: var(--accent-secondary); 
            text-decoration: none; 
            font-size: 13px; 
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 12px;
        }
        .company-url:hover { text-decoration: underline; color: var(--accent); }
        .hiring-team-list { display: flex; flex-wrap: wrap; gap: 12px; }
        .hiring-person a { 
            display: flex; flex-direction: column; align-items: flex-start;
            padding: 12px 16px; background: rgba(255,255,255,0.03);
            border-radius: 10px; font-size: 13px; color: var(--text-primary);
            text-decoration: none; border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.2s; min-width: 180px;
        }
        .hiring-person a:hover { background: rgba(108,99,255,0.1); border-color: var(--accent); transform: translateY(-2px); }
        .hiring-person .person-name { display: flex; align-items: center; gap: 8px; font-weight: 600; }
        .hiring-person .person-title { font-size: 11px; color: var(--text-muted); margin-top: 4px; padding-left: 24px; }

        @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }

        .btn-icon {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 5px;
            border-radius: 4px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .btn-icon:hover {
            background: rgba(255,255,255,0.1);
            color: var(--text-primary);
        }

        .btn-icon.danger:hover {
            background: rgba(255,107,107,0.2);
            color: var(--error);
        }

        .btn-expand {
            font-size: 12px;
            margin-right: 5px;
        }

        .empty-state {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }

        .empty-state .icon { font-size: 40px; margin-bottom: 12px; }
        .empty-state p { font-size: 14px; }

        /* --- Log panel --- */
        .log-panel .panel-body {
            padding: 8px 12px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 11px;
            line-height: 1.5;
            max-height: 400px;
        }

        .log-entry {
            display: flex;
            gap: 10px;
            padding: 2px 0;
        }

        .log-time {
            color: var(--text-muted);
            flex-shrink: 0;
        }

        .log-msg {
            color: var(--text-secondary);
            word-break: break-word;
        }

        /* --- Task banner --- */
        .task-banner {
            background: linear-gradient(135deg, rgba(108,99,255,0.1), rgba(0,212,170,0.1));
            border: 1px solid var(--accent);
            border-radius: var(--radius);
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 20px;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .task-banner .spinner {
            width: 20px;
            height: 20px;
            border: 2px solid var(--accent-glow);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .task-banner-text {
            flex: 1;
            font-size: 14px;
            font-weight: 500;
        }

        .task-banner-detail {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        /* --- Config section --- */
        .config-grid {
            display: grid;
            gap: 6px;
            padding: 12px;
        }

        .config-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            font-size: 12px;
        }

        .config-label { color: var(--text-secondary); }
        .config-value { color: var(--text-primary); font-weight: 500; }
        .config-value.ok { color: var(--success); }
        .config-value.missing { color: var(--error); }

        /* Filter tabs */
        .filter-tabs {
            display: flex;
            gap: 4px;
            padding: 4px;
            background: var(--bg-primary);
            border-radius: 8px;
        }

        .filter-tab {
            padding: 6px 12px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }

        .filter-tab:hover { color: var(--text-primary); }
        .filter-tab.active {
            background: var(--accent);
            color: white;
        }

        /* --- Dropdown --- */
        .dropdown { position: relative; display: inline-block; }
        .dropdown-content {
            display: none; position: absolute; background-color: var(--bg-card);
            min-width: 140px; box-shadow: 0 8px 16px rgba(0,0,0,0.6); z-index: 1000;
            border: 1px solid var(--border); border-radius: 8px; padding: 4px 0;
            top: 100%; left: 0; margin-top: 5px;
        }
        .dropdown-content button {
            color: var(--text-primary); padding: 8px 14px; text-decoration: none;
            display: block; width: 100%; text-align: left; background: none; border: none;
            font-size: 11px; cursor: pointer; font-family: inherit; font-weight: 500;
        }
        .dropdown-content button:hover { background-color: var(--bg-card-hover); color: var(--accent); }
        .dropdown.show .dropdown-content { display: block; }

        /* --- Job Checkbox --- */
        .job-checkbox {
            appearance: none; background-color: rgba(255,255,255,0.05); margin: 0;
            color: currentColor; width: 18px; height: 18px; border: 1px solid var(--text-muted);
            border-radius: 4px; display: grid; place-content: center; cursor: pointer;
        }
        .job-checkbox::before {
            content: ""; width: 10px; height: 10px; transform: scale(0);
            transition: 120ms transform ease-in-out; background-color: var(--accent);
            transform-origin: center; clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
        }
        .job-checkbox:checked::before { transform: scale(1); }
        .job-checkbox:checked { border-color: var(--accent); background-color: rgba(108,99,255,0.1); }
        
        /* --- Modal --- */
        .modal {
            display: none; position: fixed; z-index: 2000; left: 0; top: 0;
            width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6);
        }
        .modal-content {
            background-color: var(--bg-card); margin: 5% auto; padding: 20px;
            border: 1px solid var(--border); width: 80%; max-width: 600px; border-radius: 12px;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { margin: 0; font-size: 18px; color: var(--text-primary); }
        .close { color: var(--text-secondary); font-size: 24px; font-weight: bold; cursor: pointer; }
        .close:hover { color: var(--text-primary); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-size: 12px; color: var(--text-secondary); }
        .form-group input, .form-group textarea {
            width: 100%; padding: 8px; border-radius: 6px; border: 1px solid var(--border);
            background: rgba(0,0,0,0.2); color: var(--text-primary); font-family: inherit; font-size: 13px;
            box-sizing: border-box;
        }
        .form-group textarea { height: 120px; resize: vertical; }
    </style>
</head>
<body>
    <div class="header" style="padding: 12px 24px;">
        <div class="header-left">
            <div class="logo">🎯</div>
            <h1>LinkedIn</h1>
            
            <div class="actions-col">
                <div class="action-group">
                    <button class="btn primary" onclick="openAddJobModal()" title="Add a job manually">
                        <span class="icon">➕</span> Add Job
                    </button>
                    <button class="btn secondary" onclick="runTask('pipeline')" id="btn-pipeline" title="Run full automated pipeline">
                        <span class="icon">🚀</span> Pipeline
                    </button>
                    <button class="btn" onclick="runTask('scrape')" id="btn-scrape" title="Scrape jobs">
                        <span class="icon">🔍</span> Scrape
                    </button>
                    <button class="btn" onclick="runTask('process')" id="btn-process" title="Process descriptions">
                        <span class="icon">⚙️</span> Process
                    </button>
                </div>
                
                <div class="action-divider"></div>
                
                <div class="action-group">
                    <select id="model-select" class="btn" style="padding: 7px 10px; max-width: 120px; outline: none;">
                        <option value="gemini-3-flash-preview">Loading...</option>
                    </select>
                    <div class="dropdown" id="generate-dropdown">
                        <button class="btn success" onclick="document.getElementById('generate-dropdown').classList.toggle('show')">
                            <span class="icon">📝</span> Generate <span style="font-size:8px; margin-left:2px; opacity:0.6">▼</span>
                        </button>
                        <div class="dropdown-content">
                            <button onclick="runGenerateTask('generate', false)">Resume (Scraped)</button>
                            <button onclick="runGenerateTask('generate', true)">Resume (Selected)</button>
                            <button onclick="runGenerateTask('generate_cover_letter', false)">Cover Letter (Scraped)</button>
                            <button onclick="runGenerateTask('generate_cover_letter', true)">Cover Letter (Selected)</button>
                        </div>
                    </div>
                    <button class="btn" onclick="runTask('retry')" id="btn-retry" title="Retry generation errors">
                        <span class="icon">🔄</span> Retry
                    </button>
                </div>

                <div class="action-divider"></div>

                <div class="action-group">
                    <button class="btn" onclick="runTask('login')" id="btn-login" style="color:#0077b5;">
                        <span class="icon">🔐</span> Login
                    </button>
                    <button class="btn danger" onclick="clearAllJobs()" id="btn-clear" title="Clear all scraped jobs">
                        <span class="icon">🧹</span> Clear
                    </button>
                </div>
            </div>
        </div>
        
        <div class="header-status">
            <div class="header-stats" id="header-stats" style="margin-left:auto; padding-left:0; border-left:none;">
                <div class="h-stat"><span class="h-label">Total</span><span class="h-val" id="stat-total">-</span></div>
                <div class="h-stat"><span class="h-label">Done</span><span class="h-val success" id="stat-done">-</span></div>
                <div class="h-stat"><span class="h-label">Err</span><span class="h-val error" id="stat-error">-</span></div>
            </div>
            <div style="width:1px; height:20px; background:rgba(255,255,255,0.1); margin:0 12px;"></div>
            <span id="header-status-text" style="font-size:13px;color:var(--text-secondary)">Ready</span>
            <div class="status-dot" id="status-dot"></div>
        </div>
    </div>

    <!-- Add Job Modal -->
    <div id="addJobModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>➕ Add Job Manually</h2>
                <span class="close" onclick="closeAddJobModal()">&times;</span>
            </div>
            <div class="form-group">
                <label>Job Title *</label>
                <input type="text" id="manual-job-title" placeholder="Software Engineer">
            </div>
            <div class="form-group">
                <label>Company *</label>
                <input type="text" id="manual-company" placeholder="Acme Corp">
            </div>
            <div class="form-group">
                <label>Location</label>
                <input type="text" id="manual-location" placeholder="Remote, Brazil">
            </div>
            <div class="form-group">
                <label>Job Post URL</label>
                <input type="text" id="manual-url" placeholder="https://...">
            </div>
            <div class="form-group">
                <label>Job Description *</label>
                <textarea id="manual-description" placeholder="Paste the full job description here..."></textarea>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px;">
                <button class="btn" onclick="closeAddJobModal()">Cancel</button>
                <button class="btn success" onclick="submitManualJob()">Save Job</button>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Task Progress Banner -->
        <div id="task-banner" class="task-banner" style="display:none;">
            <div class="spinner"></div>
            <div style="flex:1">
                <div class="task-banner-text" id="task-name">Running...</div>
                <div class="task-banner-detail" id="task-progress"></div>
            </div>
            <button class="btn success" id="btn-finish-login" style="padding:6px 16px;font-size:12px;display:none" onclick="finishLogin()">✅ Finish Login</button>
            <button class="btn danger" style="padding:6px 16px;font-size:12px" onclick="cancelTask()">✖ Cancel</button>
        </div>

        <!-- Main content -->
        <div class="main-grid">
            <!-- Jobs Panel -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        <span>📋</span> Job Listings
                        <span id="job-count" style="color:var(--text-muted);font-weight:400;font-size:13px"></span>
                    </div>
                    <div class="filter-tabs" id="filter-tabs">
                        <button class="filter-tab active" data-filter="all" onclick="setFilter('all', this)">All</button>
                        <button class="filter-tab" data-filter="new" onclick="setFilter('new', this)">New</button>
                        <button class="filter-tab" data-filter="scraped" onclick="setFilter('scraped', this)">Scraped</button>
                        <button class="filter-tab" data-filter="done" onclick="setFilter('done', this)">Done</button>
                        <button class="filter-tab" data-filter="error" onclick="setFilter('error', this)">Error</button>
                    </div>
                </div>
                <div class="panel-body" id="jobs-list">
                    <div class="empty-state">
                        <div class="icon">📭</div>
                        <p>No jobs yet. Click "Scrape Jobs" to start.</p>
                    </div>
                </div>
            </div>

            <!-- Right sidebar -->
            <div style="display:flex;flex-direction:column;gap:20px">
                <!-- Log Panel -->
                <div class="panel log-panel">
                    <div class="panel-header">
                        <div class="panel-title"><span>📟</span> Activity Log</div>
                        <button class="btn" style="padding:4px 12px;font-size:11px" onclick="clearLogs()">Clear</button>
                    </div>
                    <div class="panel-body" id="log-body">
                        <div class="empty-state" style="padding:20px">
                            <p style="color:var(--text-muted)">Waiting for activity...</p>
                        </div>
                    </div>
                </div>

                <!-- Config Panel -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title"><span>⚙️</span> Configuration</div>
                    </div>
                    <div class="config-grid" id="config-grid"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';
        let pollInterval = null;

        // --- API calls ---
        async function fetchJSON(url, opts) {
            const res = await fetch(url, opts);
            return res.json();
        }

        async function refreshStats() {
            const data = await fetchJSON('/api/stats');
            document.getElementById('stat-total').textContent = data.total || 0;
            document.getElementById('stat-new').textContent = data.new || 0;
            document.getElementById('stat-scraped').textContent = data.scraped || 0;
            document.getElementById('stat-done').textContent = data.done || 0;
            document.getElementById('stat-error').textContent = data.error || 0;
        }

        async function refreshJobs() {
            const data = await fetchJSON('/api/jobs?status=' + currentFilter);
            const list = document.getElementById('jobs-list');

            if (!data.jobs || data.jobs.length === 0) {
                list.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>No jobs found.</p></div>';
                document.getElementById('job-count').textContent = '';
                return;
            }

            document.getElementById('job-count').textContent = '(' + data.jobs.length + ')';

            list.innerHTML = data.jobs.map(j => {
                const title = esc(j.job_title || 'Untitled');
                const company = esc(j.company || '');
                const location = esc(j.location || '');
                const isRemote = (j.location || '').toLowerCase().includes('remote');
                const detailParts = [];
                if (company) detailParts.push('🏢 ' + company);
                if (location) detailParts.push('📍 ' + location);
                const detail = detailParts.join('  ·  ');

                const statusLabels = {
                    'new': '✨ NOVO',
                    'scraped': '📄 DETALHES OK',
                    'generating': '⏳ GERANDO',
                    'done': '✅ PRONTO',
                    'error': '⚠️ ERRO',
                    'removed': '🗑️ REMOVIDO'
                };
                const statusLabel = statusLabels[j.status] || j.status.toUpperCase();

                return `
                <div class="job-container" id="job-container-${j.id}">
                    <div class="job-row">
                        <div style="display:flex; align-items:center; margin-right: 10px; gap: 8px;">
                            <input type="checkbox" class="job-checkbox" data-id="${j.id}">
                            <button class="btn-icon btn-expand" onclick="toggleDetails(${j.id})" title="View Description">
                                ${j.description ? '▼' : '·'}
                            </button>
                        </div>
                        <div class="job-info">
                            <div class="job-title" title="${title}">${title}</div>
                            <div class="job-company">${detail}</div>
                        </div>
                        <div class="job-meta">
                            ${isRemote ? '<span class="badge remote">🌐 REMOTE</span>' : ''}
                            <span class="badge ${j.status}">${statusLabel}</span>
                            ${j.easy_apply ? '<span class="badge easy-apply">⚡ EASY APPLY</span>' : ''}
                            ${j.cover_letter ? `<button class="btn success" style="padding:4px 8px;font-size:10px" onclick="copyCL(${j.id})">CL Copy</button><a href="/download/cl/${j.id}" class="job-download" title="Download CL PDF" style="font-size: 16px; text-decoration: none;">⬇</a>` : ''}
                            ${j.file_name ? '<a href="/download/' + encodeURIComponent(j.file_name) + '" class="job-download" title="Download PDF">⬇</a>' : ''}
                            <a href="/chat/${j.id}" target="_blank" class="btn-icon" title="Chat Assistente" style="color:var(--accent)">💬</a>
                            <a href="${esc(j.url)}" target="_blank" class="btn-icon" title="Open on LinkedIn">🔗</a>
                            <button class="btn-icon danger" onclick="removeJob(${j.id})" title="Remove Job">🗑️</button>
                        </div>
                    </div>
                    <div class="job-details" id="details-${j.id}">
                        ${(() => {
                            const hasCompany = j.company_description || j.company_profile_url;
                            let team = [];
                            try { team = j.hiring_team_json ? JSON.parse(j.hiring_team_json) : []; } catch(e) {}
                            const hasTeam = team.length > 0;
                            return `
                            <div class="detail-tabs">
                                <button class="detail-tab active" onclick="switchTab(${j.id}, 'desc', this)">📄 Descrição</button>
                                ${hasCompany ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'company', this)">🏢 Empresa</button>` : ''}
                                ${hasTeam ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'team', this)">👥 Equipe <span class="tab-count">${team.length}</span></button>` : ''}
                                ${j.cover_letter ? `<button class="detail-tab" onclick="switchTab(${j.id}, 'cl', this)">📄 Cover Letter</button>` : ''}
                            </div>
                            <div class="tab-panel active" id="tab-desc-${j.id}">
                                <div class="details-content">${esc(j.description)}</div>
                            </div>
                            ${hasCompany ? `
                            <div class="tab-panel" id="tab-company-${j.id}">
                                ${j.company_profile_url ? `
                                    <a href="${esc(j.company_profile_url)}" target="_blank" class="company-url">
                                        Ver Perfil no LinkedIn ↗
                                    </a>
                                ` : ''}
                                <div class="details-content">${esc(j.company_description)}</div>
                            </div>
                            ` : ''}
                            ${hasTeam ? `
                            <div class="tab-panel" id="tab-team-${j.id}">
                                <div class="hiring-team-list">
                                    ${team.map(p => `
                                        <div class="hiring-person">
                                            <a href="${esc(p.url)}" target="_blank">
                                                <span class="person-name">👤 ${esc(p.name)}</span>
                                                ${p.title ? `<span class="person-title">${esc(p.title)}</span>` : ''}
                                            </a>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            ` : ''}
                            ${j.cover_letter ? `
                            <div class="tab-panel" id="tab-cl-${j.id}">
                                <div class="details-content" id="cl-content-${j.id}">${esc(j.cover_letter)}</div>
                            </div>
                            ` : ''}
                            `;
                        })()}
                    </div>
                </div>
            `}).join('');
        }

        async function refreshConfig() {
            const data = await fetchJSON('/api/config');
            const grid = document.getElementById('config-grid');
            grid.innerHTML = data.items.map(i => `
                <div class="config-item">
                    <span class="config-label">${esc(i.label)}</span>
                    <span class="config-value ${i.ok ? 'ok' : (i.ok === false ? 'missing' : '')}">${esc(i.value)}</span>
                </div>
            `).join('');
        }

        async function refreshTaskStatus() {
            const data = await fetchJSON('/api/task-status');
            const banner = document.getElementById('task-banner');
            const dot = document.getElementById('status-dot');
            const headerText = document.getElementById('header-status-text');

            if (data.running) {
                banner.style.display = 'flex';
                document.getElementById('task-name').textContent = data.task;
                document.getElementById('task-progress').textContent = data.progress;
                dot.className = 'status-dot warning';
                headerText.textContent = 'Running: ' + data.task;
                setButtons(true);
                // Disable model-select while running
                document.getElementById('model-select').disabled = true;
                // Show "Finish Login" button only during login tasks
                const finishBtn = document.getElementById('btn-finish-login');
                finishBtn.style.display = data.task.toLowerCase().includes('login') ? 'inline-flex' : 'none';
            } else {
                banner.style.display = 'none';
                dot.className = 'status-dot';
                headerText.textContent = 'Ready';
                setButtons(false);
                document.getElementById('model-select').disabled = false;

                if (pollInterval) {
                    clearInterval(pollInterval);
                    pollInterval = null;
                    refreshStats();
                    refreshJobs();
                }
            }

            // Update logs
            if (data.logs && data.logs.length > 0) {
                const logBody = document.getElementById('log-body');
                logBody.innerHTML = data.logs.map(l =>
                    `<div class="log-entry"><span class="log-time">${l.time}</span><span class="log-msg">${esc(l.msg)}</span></div>`
                ).join('');
                logBody.scrollTop = logBody.scrollHeight;
            }
        }

        async function runTask(task) {
            const modelName = document.getElementById('model-select').value;
            const res = await fetchJSON('/api/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task, model_name: modelName})
            });

            if (res.ok) {
                // Start polling
                refreshTaskStatus();
                pollInterval = setInterval(() => {
                    refreshTaskStatus();
                    refreshStats();
                }, 2000);
            } else {
                alert(res.error || 'Failed to start task');
            }
        }

        async function cancelTask() {
            await fetchJSON('/api/cancel', { method: 'POST' });
            if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
            refreshTaskStatus();
            refreshStats();
            refreshJobs();
        }

        async function finishLogin() {
            await fetchJSON('/api/finish-login', { method: 'POST' });
        }

        function toggleDetails(id) {
            const el = document.getElementById('details-' + id);
            const container = document.getElementById('job-container-' + id);
            if (el) {
                const isActive = el.classList.toggle('active');
                if (container) container.classList.toggle('expanded', isActive);
                // Scroll job row into view when expanding
                if (isActive && container) {
                    setTimeout(() => container.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
                }
            }
        }

        function switchTab(jobId, tab, btn) {
            // Hide all tab panels for this job
            const details = document.getElementById('details-' + jobId);
            details.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            details.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
            // Show selected
            const panel = document.getElementById('tab-' + tab + '-' + jobId);
            if (panel) panel.classList.add('active');
            btn.classList.add('active');
        }

        function copyCL(jobId) {
            const clElem = document.getElementById('cl-content-' + jobId);
            if (!clElem) return;
            navigator.clipboard.writeText(clElem.textContent).then(() => {
                alert("Cover Letter copiada para a área de transferência!");
            }).catch(err => {
                console.error("Erro ao copiar cover letter: ", err);
            });
        }

        async function removeJob(id) {
            if (!confirm('Remove this job?')) return;
            const res = await fetchJSON('/api/jobs/delete/' + id, { method: 'POST' });
            if (res.ok) {
                refreshJobs();
                refreshStats();
            }
        }

        async function clearAllJobs() {
            if (!confirm('Mark all non-Done jobs as removed?')) return;
            const res = await fetchJSON('/api/jobs/clear', { method: 'POST' });
            if (res.ok) {
                refreshJobs();
                refreshStats();
            }
        }

        function setFilter(filter, el) {
            currentFilter = filter;
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            refreshJobs();
        }

        function setButtons(disabled) {
            document.querySelectorAll('.actions-row .btn').forEach(b => b.disabled = disabled);
        }

        function clearLogs() {
            document.getElementById('log-body').innerHTML =
                '<div class="empty-state" style="padding:20px"><p style="color:var(--text-muted)">Waiting for activity...</p></div>';
        }

        function esc(str) {
            if (!str) return '';
            const d = document.createElement('div');
            d.textContent = str;
            return d.innerHTML;
        }

        // Close dropdown if clicked outside
        window.onclick = function(event) {
            if (!event.target.closest('.dropdown')) {
                const dropdowns = document.getElementsByClassName("dropdown");
                for (let i = 0; i < dropdowns.length; i++) {
                    const openDropdown = dropdowns[i];
                    if (openDropdown.classList.contains('show')) openDropdown.classList.remove('show');
                }
            }
        }

        async function runGenerateTask(taskType, onlySelected) {
            let jobIds = null;
            if (onlySelected) {
                const checkboxes = document.querySelectorAll('.job-checkbox:checked');
                if (checkboxes.length === 0) {
                    alert('Nenhuma vaga selecionada.');
                    return;
                }
                jobIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.id));
            }
            document.getElementById('generate-dropdown').classList.remove('show');
            
            const modelName = document.getElementById('model-select').value;
            const res = await fetchJSON('/api/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task: taskType, job_ids: jobIds, model_name: modelName})
            });

            if (res.ok) {
                refreshTaskStatus();
                pollInterval = setInterval(() => {
                    refreshTaskStatus();
                    refreshStats();
                }, 2000);
            } else {
                alert(res.error || 'Failed to start task');
            }
        }

        async function refreshModels() {
            try {
                const data = await fetchJSON('/api/models');
                const selectElement = document.getElementById('model-select');
                if (data.models && data.models.length > 0) {
                    selectElement.innerHTML = data.models.map(m => `
                        <option value="${esc(m)}" ${m === 'gemini-3-flash-preview' ? 'selected' : ''}>${esc(m)}</option>
                    `).join('');
                } else {
                    selectElement.innerHTML = '<option value="gemini-3-flash-preview">gemini-3-flash-preview</option>';
                }
            } catch (e) {
                console.error("Failed to load models list");
            }
        }

        async function submitManualJob() {
            const btn = document.querySelector('#addJobModal .btn.success');
            const data = {
                title: document.getElementById('manual-job-title').value.trim(),
                company: document.getElementById('manual-company').value.trim(),
                location: document.getElementById('manual-location').value.trim(),
                url: document.getElementById('manual-url').value.trim(),
                description: document.getElementById('manual-description').value.trim(),
            };
            if (!data.title || !data.company || !data.description) {
                alert("Please fill in Title, Company, and Description.");
                return;
            }
            btn.disabled = true;
            btn.textContent = "Saving...";
            try {
                const res = await fetchJSON('/api/jobs/manual', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if (res.ok) {
                    closeAddJobModal();
                    // Clear fields
                    document.getElementById('manual-job-title').value = '';
                    document.getElementById('manual-company').value = '';
                    document.getElementById('manual-location').value = '';
                    document.getElementById('manual-url').value = '';
                    document.getElementById('manual-description').value = '';
                    refreshJobs();
                } else {
                    alert('Error adding job: ' + res.error);
                }
            } catch (e) {
                alert('Connection error');
            } finally {
                btn.disabled = false;
                btn.textContent = "Save Job";
            }
        }
        
        function openAddJobModal() {
            document.getElementById('addJobModal').style.display = 'block';
        }
        function closeAddJobModal() {
            document.getElementById('addJobModal').style.display = 'none';
        }

        // --- Init ---
        refreshModels();
        refreshStats();
        refreshJobs();
        refreshConfig();
        // Check if task already running
        refreshTaskStatus();
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/models")
def api_models():
    from resume_generator import get_gemini_models
    return jsonify({"models": get_gemini_models()})

@app.route("/api/stats")
def api_stats():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) FROM public.job_listings
                GROUP BY status
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    stats = {}
    total = 0
    for status, count in rows:
        stats[status] = count
        total += count
    stats["total"] = total
    return jsonify(stats)


@app.route("/api/jobs")
def api_jobs():
    status_filter = request.args.get("status", "all")
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            if status_filter == "all":
                cur.execute("""
                    SELECT id, linkedin_job_id, url, status, job_title, company,
                           location, language, file_name, easy_apply, created_at, updated_at,
                           (description IS NOT NULL AND length(description) > 50) as has_details,
                           description, cover_letter, company_description, company_profile_url, hiring_team_json
                    FROM public.job_listings
                    ORDER BY created_at DESC
                    LIMIT 200
                """)
            else:
                cur.execute("""
                    SELECT id, linkedin_job_id, url, status, job_title, company,
                           location, language, file_name, easy_apply, created_at, updated_at,
                           (description IS NOT NULL AND length(description) > 50) as has_details,
                           description, cover_letter, company_description, company_profile_url, hiring_team_json
                    FROM public.job_listings
                    WHERE status = %s
                    ORDER BY created_at DESC
                    LIMIT 200
                """, (status_filter,))

            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()

    jobs = []
    for row in rows:
        job = dict(zip(columns, row))
        # Convert datetimes to string
        for key in ("created_at", "updated_at"):
            if job.get(key):
                job[key] = job[key].isoformat()
        jobs.append(job)

    return jsonify({"jobs": jobs})


@app.route("/api/config")
def api_config():
    session_ok = SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 100
    gemini_ok = bool(GEMINI_API_KEY and GEMINI_API_KEY != "COLE_SUA_GEMINI_API_KEY_AQUI")

    # Check gotenberg
    import requests as req
    try:
        from config import GOTENBERG_URL
        r = req.get(f"{GOTENBERG_URL}/health", timeout=3)
        gotenberg_ok = r.status_code == 200
    except Exception:
        gotenberg_ok = False

    # Check DB
    try:
        conn = db.get_connection()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    items = [
        {"label": "Database", "value": "Connected" if db_ok else "Not connected", "ok": db_ok},
        {"label": "LinkedIn Session", "value": "Active" if session_ok else "Not logged in", "ok": session_ok},
        {"label": "Gemini API", "value": "Configured" if gemini_ok else "Missing API key", "ok": gemini_ok},
        {"label": "Gotenberg", "value": "Running" if gotenberg_ok else "Not available", "ok": gotenberg_ok},
        {"label": "Output Dir", "value": str(OUTPUT_DIR), "ok": None},
    ]
    return jsonify({"items": items})


@app.route("/api/task-status")
def api_task_status():
    with _task_lock:
        return jsonify({
            "running": task_status["running"],
            "task": task_status["task"],
            "progress": task_status["progress"],
            "logs": task_status["logs"][-50:],  # return last 50
            "error": task_status["error"],
        })


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json() or {}
    task = data.get("task", "")

    with _task_lock:
        if task_status["running"]:
            return jsonify({"ok": False, "error": "A task is already running."})

    if task == "pipeline":
        m_name = data.get("model_name", "gemini-3-flash-preview")
        def full_pipeline(m_name=m_name):
            from scraper import scrape_saved_jobs
            from processor import process_new_jobs
            from resume_generator import generate_resumes
            scrape_saved_jobs(max_jobs=100)
            process_new_jobs()
            generate_resumes(model_name=m_name)
        started = _run_task("Full Pipeline", full_pipeline)
    elif task == "scrape":
        from scraper import scrape_saved_jobs
        started = _run_task("Scrape Jobs", scrape_saved_jobs, 100)
    elif task == "process":
        from processor import process_new_jobs
        started = _run_task("Process Jobs", process_new_jobs)
    elif task == "generate":
        from resume_generator import generate_resumes
        job_ids = data.get("job_ids")
        m_name = data.get("model_name", "gemini-3-flash-preview")
        started = _run_task("Generate Resumes", generate_resumes, job_ids, m_name)
    elif task == "generate_cover_letter":
        from resume_generator import generate_cover_letters
        job_ids = data.get("job_ids")
        m_name = data.get("model_name", "gemini-3-flash-preview")
        started = _run_task("Generate Cover Letters", generate_cover_letters, job_ids, m_name)
    elif task == "retry":
        m_name = data.get("model_name", "gemini-3-flash-preview")
        def retry_errors(m_name=m_name):
            from resume_generator import generate_resumes
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.job_listings SET status = 'scraped'
                        WHERE status = 'error' AND description IS NOT NULL
                            AND length(description) > 50
                    """)
                    count = cur.rowcount
                conn.commit()
                print(f"🔄 Reset {count} error jobs to 'scraped'.")
            finally:
                conn.close()
            generate_resumes(model_name=m_name)
        started = _run_task("Retry Errors", retry_errors)
    elif task == "login":
        from scraper import login as linkedin_login
        started = _run_task("LinkedIn Login", linkedin_login)
    else:
        return jsonify({"ok": False, "error": f"Unknown task: {task}"})

    return jsonify({"ok": started})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    """Force-reset the task status so a new task can be started."""
    with _task_lock:
        was_running = task_status["running"]
        task_status["running"] = False
        task_status["error"] = "Cancelled by user" if was_running else None
    _log("⛔ Task cancelled by user.")
    return jsonify({"ok": True, "was_running": was_running})


@app.route("/api/finish-login", methods=["POST"])
def api_finish_login():
    """Signal the login process to save session and close browser."""
    from scraper import finish_login
    finish_login()
    _log("🏁 Finish Login signal sent — saving session...")
    return jsonify({"ok": True})


@app.route("/api/jobs/delete/<int:job_id>", methods=["POST"])
def api_delete_job(job_id):
    """Hard delete a job."""
    db.delete_job(job_id)
    _log(f"🗑️ Job {job_id} deleted.")
    return jsonify({"ok": True})


@app.route("/api/jobs/clear", methods=["POST"])
def api_clear_jobs():
    """Clear all non-Done jobs."""
    db.clear_all_jobs()
    _log("🧹 All non-Done jobs marked as removed.")
    return jsonify({"ok": True})


@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(str(OUTPUT_DIR), filename, as_attachment=True)


@app.route("/download/cl/<int:job_id>")
def download_cl(job_id):
    import io
    from flask import send_file
    from resume_generator import _convert_to_pdf, _safe_filename
    
    jobs = db.get_jobs_by_ids([job_id])
    if not jobs or not jobs[0].get("cover_letter"):
        return "Cover letter not found", 404
        
    job = jobs[0]
    title = job.get("job_title", "Unknown")
    company = job.get("company", "Unknown")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; white-space: pre-wrap; }}
        </style>
    </head>
    <body>{job.get("cover_letter")}</body>
    </html>
    """
    
    try:
        pdf_bytes = _convert_to_pdf(html)
        date_str = datetime.now().strftime("%Y%m%d")
        file_name = f"CL_{_safe_filename(company)}_{_safe_filename(title)}_{date_str}.pdf"
        
        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=file_name,
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"Error generating PDF: {str(e)}", 500


@app.route("/chat/<int:job_id>")
def chat_page(job_id):
    jobs = db.get_jobs_by_ids([job_id])
    if not jobs:
        return "Job not found", 404
    job = jobs[0]
    
    html = CHAT_TEMPLATE.replace("{{ job_id }}", str(job["id"]))
    html = html.replace("{{ job_title }}", job.get("job_title", "Unknown"))
    html = html.replace("{{ company }}", job.get("company", "Unknown"))
    return render_template_string(html)

@app.route("/api/chat/<int:job_id>", methods=["POST"])
def api_chat(job_id):
    data = request.get_json()
    if not data or not data.get("question"):
        return jsonify({"ok": False, "error": "Question is required."})
        
    jobs = db.get_jobs_by_ids([job_id])
    if not jobs:
        return jsonify({"ok": False, "error": "Job not found."})
        
    job = jobs[0]
    question = data["question"]
    orientation = data.get("orientation", "")
    tone = data.get("tone", "semi-formal")
    model_name = data.get("model_name", "gemini-3-flash-preview")
    
    from resume_generator import chat_with_job
    answer = chat_with_job(job, question, orientation, tone=tone, model_name=model_name)
    
    return jsonify({"ok": True, "answer": answer})

@app.route("/api/jobs/manual", methods=["POST"])
def api_add_manual_job():
    data = request.get_json()
    title = data.get("title", "").strip()
    company = data.get("company", "").strip()
    location = data.get("location", "").strip()
    url = data.get("url", "").strip()
    description = data.get("description", "").strip()
    
    if not title or not company or not description:
        return jsonify({"ok": False, "error": "Title, Company, and Description are required."})
        
    success = db.insert_manual_job(title, company, location, url, description)
    if success:
        _log(f"➕ Manual job added: {title} @ {company}")
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "Database error while adding job."})

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🌐 Starting LinkedIn Job Scraper Web UI...")
    print("   → http://localhost:5050\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
