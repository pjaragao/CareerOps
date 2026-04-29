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
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

import db
from config import OUTPUT_DIR, SESSION_FILE, GEMINI_API_KEY, AI_PROVIDER, AI_MODEL, AI_BASE_URL, load_profile, save_profile, AI_PROVIDER, AI_MODEL, AI_BASE_URL, load_profile, save_profile

app = Flask(__name__)
CORS(app)

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

# CHAT_TEMPLATE moved to templates/chat.html

# HTML_TEMPLATE moved to templates/index.html


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("profile.html")

@app.route("/config")
def config_page():
    return render_template("config.html")

@app.route("/jobs")
def jobs_index():
    return render_template("index.html")

@app.route("/api/strategies", methods=["GET"])
def api_get_strategies():
    strategies = db.get_search_strategies(active_only=False)
    return jsonify(strategies)

@app.route("/api/strategies", methods=["POST"])
def api_add_strategy():
    data = request.json
    success = db.upsert_search_strategy(
        title=data.get("title"),
        keywords=data.get("keywords", []),
        locations=data.get("locations", []),
        remote_only=data.get("remote_only", True)
    )
    return jsonify({"ok": success})

@app.route("/api/outreach/email", methods=["POST"])
def api_outreach_email():
    data = request.json
    from services.email_sender import send_email
    success = send_email(data.get("email"), "Job Application Inquiry", data.get("body"))
    return jsonify({"ok": success})

@app.route("/api/strategies/delete/<int:id>", methods=["POST"])
def api_delete_strategy(id):
    success = db.delete_search_strategy(id)
    return jsonify({"ok": success})

@app.route("/api/jobs/<int:id>/skill-gaps", methods=["GET", "POST"])
def api_job_skill_gaps(id):
    if request.method == "POST":
        from services.skill_analyzer import analyze_job_gaps
        # Run in background or wait? Since it's fast-ish, I'll wait or use _run_task
        # User might want to see result immediately. I'll run sync for now or background.
        # Background is safer for web.
        if _run_task("Analyze Skill Gaps", analyze_job_gaps, id):
            return jsonify({"ok": True, "message": "Analysis started"})
        return jsonify({"ok": False, "error": "Task already running"})
    
    gaps = db.get_skill_gaps(id)
    return jsonify(gaps)

@app.route("/api/chat/<int:id>/simulate", methods=["POST"])
def api_chat_simulate(id):
    data = request.json
    user_answer = data.get("answer", "")
    history = data.get("history", [])
    
    job = db.get_job_by_id(id)
    profile = db.get_user_profile()
    
    from ai_provider import get_provider
    provider = get_provider()
    
    prompt = f"""
    Você é um Simulador de Entrevistas para a vaga de {job.get('title')} na {job.get('company')}.
    
    PERFIL DO CANDIDATO:
    {json.dumps(profile, indent=2)}
    
    DESCRIÇÃO DA VAGA:
    {job.get('description')}
    
    HISTÓRICO DA SIMULAÇÃO:
    {json.dumps(history, indent=2)}
    
    RESPOSTA DO USUÁRIO: "{user_answer}"
    
    INSTRUÇÕES:
    - Se o histórico estiver vazio, apresente-se como o recrutador e faça a primeira pergunta técnica ou comportamental.
    - Se o usuário respondeu, dê um feedback rápido e profissional sobre a resposta dele e faça a PRÓXIMA pergunta.
    - Se achar que a simulação deve acabar, defina "is_over": true.
    
    RETORNE APENAS JSON:
    {{
      "feedback": "Feedback sobre a resposta anterior (vazio se for a primeira)",
      "next_question": "A próxima pergunta para o candidato",
      "is_over": false
    }}
    """
    
    try:
        result = provider.generate_json(prompt)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/models")
def api_models():
    from ai_provider import get_available_models
    models = get_available_models()
    return jsonify({"models": models})

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
            base_query = """
                SELECT j.id, j.linkedin_job_id, j.url, j.status, j.job_title, j.company,
                       j.location, j.language, j.file_name, j.easy_apply, j.created_at, j.updated_at,
                       (j.description IS NOT NULL AND length(j.description) > 50) as has_details,
                       j.description, j.cover_letter, j.company_description, j.company_profile_url, j.hiring_team_json,
                       (EXISTS (SELECT 1 FROM public.applications a WHERE a.job_id = j.id)) as has_application,
                       e.overall_score, e.match_score, e.north_star_score, e.comp_score, e.cultural_score, e.red_flags,
                       e.analysis, e.archetype
                FROM public.job_listings j
                LEFT JOIN public.job_evaluations e ON j.id = e.job_id
            """

            if status_filter == "all":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed'
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            elif status_filter == "easy_apply":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed' AND j.easy_apply = true
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            elif status_filter == "not_applied":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed' AND NOT EXISTS (SELECT 1 FROM public.applications a WHERE a.job_id = j.id)
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            elif status_filter == "score_high":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed' AND e.overall_score >= 4
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            elif status_filter == "score_medium":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed' AND e.overall_score >= 3 AND e.overall_score < 4
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            elif status_filter == "score_low":
                cur.execute(f"""
                    {base_query}
                    WHERE j.status != 'removed' AND e.overall_score > 0 AND e.overall_score < 3
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """)
            else:
                cur.execute(f"""
                    {base_query}
                    WHERE j.status = %s
                    ORDER BY j.created_at DESC
                    LIMIT 200
                """, (status_filter,))
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            
            jobs = []
            for row in rows:
                job = dict(zip(columns, row))
                for key in ("created_at", "updated_at"):
                    if job.get(key):
                        job[key] = job[key].isoformat()
                if job.get("overall_score") is not None:
                    job["evaluation"] = {
                        "overall_score": job["overall_score"],
                        "match_score": job["match_score"],
                        "north_star_score": job["north_star_score"],
                        "comp_score": job["comp_score"],
                        "cultural_score": job["cultural_score"],
                        "red_flags": job["red_flags"],
                        "analysis": job["analysis"],
                        "archetype": job["archetype"]
                    }
                jobs.append(job)
                
            return jsonify({"jobs": jobs})
    finally:
        conn.close()

@app.route("/api/profile/config/prompts", methods=["GET"])
def api_get_prompts():
    import profile_prompts
    return jsonify(profile_prompts.load_prompts())

@app.route("/api/profile/config/prompts", methods=["POST"])
def api_save_prompts():
    import profile_prompts
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No data provided"})
    profile_prompts.save_prompts(data)
    return jsonify({"ok": True})


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

    if task == "generate":
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
        
        # Save to output dir so it's accessible from Windows Explorer
        pdf_path = OUTPUT_DIR / file_name
        pdf_path.write_bytes(pdf_bytes)
        
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
    
    return render_template(
        "chat.html",
        job_id=job["id"],
        job_title=job.get("job_title", "Unknown"),
        company=job.get("company", "Unknown")
    )

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

@app.route("/api/jobs/import", methods=["POST"])
def api_jobs_import():
    data = request.get_json()
    title = data.get("title", "").strip()
    company = data.get("company", "").strip()
    location = data.get("location", "").strip()
    url = data.get("url", "").strip()
    description = data.get("description", "").strip()
    
    if not title or not company:
        return jsonify({"ok": False, "error": "Title and Company are required."})
        
    success = db.insert_manual_job(title, company, location, url, description)
    if success:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Database error"})

# ---------------------------------------------------------------------------
# Applications API
# ---------------------------------------------------------------------------
@app.route("/api/applications")
def api_get_applications():
    apps = db.get_applications()
    for a in apps:
        for key in ("created_at", "updated_at"):
            if a.get(key):
                a[key] = a[key].isoformat()
    return jsonify({"applications": apps})

@app.route("/api/applications", methods=["POST"])
def api_post_application():
    data = request.get_json()
    job_id = data.get("job_id")
    company = data.get("company", "").strip()
    job_title = data.get("job_title", "").strip()
    apply_method = data.get("apply_method", "").strip()
    status = data.get("status", "Applied").strip()
    notes = data.get("notes", "").strip()
    
    if not company or not job_title:
        return jsonify({"ok": False, "error": "Company and Job Title required."})
        
    success = db.insert_application(
        job_id=int(job_id) if job_id else None,
        company_name=company,
        job_title=job_title,
        apply_method=apply_method,
        status=status,
        notes=notes
    )
    return jsonify({"ok": success})

@app.route("/api/applications/update/<int:app_id>", methods=["POST"])
def api_update_application(app_id):
    data = request.get_json()
    status = data.get("status")
    apply_method = data.get("apply_method")
    notes = data.get("notes")
    company_name = data.get("company")
    job_title = data.get("job_title")
    
    success = db.update_application(
        app_id=app_id,
        status=status,
        apply_method=apply_method,
        notes=notes,
        company_name=company_name,
        job_title=job_title
    )
    return jsonify({"ok": success})

@app.route("/api/applications/delete/<int:app_id>", methods=["POST"])
def api_delete_application(app_id):
    success = db.delete_application(app_id)
    return jsonify({"ok": success})

def auto_recover_hung_jobs():
    """Reset jobs that were left in broken states due to previous interruptions or failed scrapes."""
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            # 1. Reset jobs that were stuck while building PDF back to 'scraped' so they can be generated again
            cur.execute("UPDATE public.job_listings SET status = 'scraped' WHERE status IN ('generating', 'processing')")
            rowcount1 = cur.rowcount
            
            # 2. Reset jobs that were marked 'scraped' or 'error' but actually lack a real description back to 'new'
            cur.execute("UPDATE public.job_listings SET status = 'new' WHERE status IN ('scraped', 'error') AND (description IS NULL OR LENGTH(description) < 50)")
            rowcount2 = cur.rowcount
            
            if rowcount1 > 0 or rowcount2 > 0:
                print(f"   ♻️  Auto-recovered {rowcount1} stalled generations and {rowcount2} failed scrapes.")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Could not run auto-recovery: {e}")

# ---------------------------------------------------------------------------
# Profile Optimizer API
# ---------------------------------------------------------------------------
@app.route("/api/profile/resume")
def api_get_resume():
    from config import PROJECT_DIR
    resume_path = PROJECT_DIR / "resume_base.md"
    if not resume_path.exists():
        return jsonify({"ok": False, "error": "Resume file not found."})
    return jsonify({"ok": True, "content": resume_path.read_text()})

@app.route("/api/profile/optimize", methods=["POST"])
def api_profile_optimize():
    data = request.get_json()
    section = data.get("section")
    content = data.get("content")
    model_name = data.get("model_name", "gemini-3-flash-preview")
    
    import profile_optimizer
    if section == "headline":
        result = profile_optimizer.optimize_headline(content, model_name=model_name)
    elif section == "about":
        result = profile_optimizer.optimize_about(content, model_name=model_name)
    elif section == "experience":
        result = profile_optimizer.rewrite_experience_car(content, model_name=model_name)
    elif section == "analyze":
        result = profile_optimizer.analyze_profile(content, model_name=model_name)
    else:
        return jsonify({"ok": False, "error": f"Unknown section: {section}"})
    
    return jsonify({"ok": True, "result": result})

@app.route("/api/profile/ssi", methods=["POST"])
def api_profile_ssi():
    data = request.get_json()
    content = data.get("content")
    model_name = data.get("model_name", "gemini-3-flash-preview")
    import profile_optimizer
    result = profile_optimizer.generate_ssi_plan(content, model_name=model_name)
    return jsonify({"ok": True, "result": result})



@app.route("/api/profile/score", methods=["POST"])
def api_profile_score():
    data = request.get_json()
    profile_md = data.get("content")
    model_name = data.get("model_name", "gemini-3-flash-preview")
    
    import profile_optimizer
    result = profile_optimizer.get_profile_score(profile_md, model_name=model_name)
    
    # Save score to DB
    db.upsert_profile_stats(score=result.get("score"), analysis=result.get("reason"), current_data={"md": profile_md})
    
    return jsonify({"ok": True, "result": result})


@app.route("/api/profile/status", methods=["GET"])
def api_profile_status():
    stats = db.get_latest_profile_stats()
    if stats:
        for key in ("scraped_at", "last_optimized_at", "updated_at"):
            if stats.get(key):
                stats[key] = stats[key].isoformat()
    return jsonify({"ok": True, "stats": stats})


@app.route("/api/profile/update-linkedin", methods=["POST"])
def api_profile_update_linkedin():
    # Deprecated: Auto-updating LinkedIn was too fragile.
    return jsonify({"ok": False, "error": "Auto-update is disabled. Please update your profile manually on LinkedIn."})


# ---------------------------------------------------------------------------
# AI Provider API
# ---------------------------------------------------------------------------
@app.route("/api/ai/providers")
def api_ai_providers():
    from ai_provider import get_provider_info, get_available_models, VALID_PROVIDERS, DEFAULT_MODELS, NVIDIA_MODELS, ALIBABA_MODELS, OLLAMA_MODELS
    info = get_provider_info()
    info["valid_providers"] = VALID_PROVIDERS
    info["default_models"] = DEFAULT_MODELS
    info["provider_models"] = {
        "nvidia": NVIDIA_MODELS,
        "alibaba": ALIBABA_MODELS,
        "ollama": OLLAMA_MODELS,
    }
    return jsonify(info)

@app.route("/api/ai/models")
def api_ai_models():
    from ai_provider import get_available_models
    provider = request.args.get("provider")
    models = get_available_models(provider)
    return jsonify({"models": models})

@app.route("/api/ai/test", methods=["POST"])
def api_ai_test():
    from ai_provider import create_provider
    data = request.get_json() or {}
    provider_type = data.get("provider", AI_PROVIDER)
    api_key = data.get("api_key", "")
    base_url = data.get("base_url", "")
    model = data.get("model", "")
    try:
        provider = create_provider(provider_type, api_key, base_url, model)
        success, message = provider.test_connection()
        return jsonify({"ok": success, "message": message})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)})

@app.route("/api/ai/config", methods=["POST"])
def api_ai_config():
    data = request.get_json() or {}
    provider = data.get("provider", AI_PROVIDER)
    model = data.get("model", "")
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    
    if api_key:
        import os
        os.environ["AI_API_KEY"] = api_key
    if provider:
        import os
        os.environ["AI_PROVIDER"] = provider
    if model:
        import os
        os.environ["AI_MODEL"] = model
    if base_url:
        import os
        os.environ["AI_BASE_URL"] = base_url
    
    from ai_provider import get_provider
    get_provider(refresh=True)
    
    db.save_ai_config(provider, model, base_url)
    return jsonify({"ok": True, "message": "AI provider configuration saved."})

# ---------------------------------------------------------------------------
# Job Evaluation / Scoring API
# ---------------------------------------------------------------------------
@app.route("/api/jobs/<int:job_id>/evaluate", methods=["POST"])
def api_evaluate_job(job_id):
    from job_evaluator import evaluate_job
    jobs = db.get_jobs_by_ids([job_id])
    if not jobs:
        return jsonify({"ok": False, "error": "Job not found."})
    job = jobs[0]
    result = evaluate_job(job_id, job)
    if "error" in result:
        return jsonify({"ok": False, "error": result["error"]})
    return jsonify({"ok": True, "evaluation": result})

@app.route("/api/jobs/evaluate-batch", methods=["POST"])
def api_evaluate_batch():
    from job_evaluator import evaluate_batch
    data = request.get_json() or {}
    job_ids = data.get("job_ids")
    
    def _do_evaluate():
        results = evaluate_batch(job_ids)
        _log(f"✅ Evaluated {len(results)} jobs.")
    
    started = _run_task("Evaluate Jobs", _do_evaluate)
    if not started:
        return jsonify({"ok": False, "error": "A task is already running."})
    return jsonify({"ok": True, "message": "Evaluation started."})

@app.route("/api/jobs/<int:job_id>/evaluation", methods=["GET"])
def api_get_evaluation(job_id):
    evaluation = db.get_job_evaluation(job_id)
    if not evaluation:
        return jsonify({"ok": False, "error": "No evaluation found."})
    for key in ("evaluated_at",):
        if evaluation.get(key):
            evaluation[key] = evaluation[key].isoformat()
    return jsonify({"ok": True, "evaluation": evaluation})

@app.route("/api/evaluations", methods=["GET"])
def api_all_evaluations():
    evals = db.get_all_evaluations()
    for e in evals:
        if e.get("evaluated_at"):
            e["evaluated_at"] = e["evaluated_at"].isoformat()
    return jsonify({"evaluations": evals})

# ---------------------------------------------------------------------------
# Interview Stories API
# ---------------------------------------------------------------------------
@app.route("/api/stories", methods=["GET"])
def api_get_stories():
    tags = request.args.get("tags")
    archetypes = request.args.get("archetypes")
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    arch_list = [a.strip() for a in archetypes.split(",")] if archetypes else None
    stories = db.get_interview_stories(tags=tag_list, archetypes=arch_list)
    for s in stories:
        if s.get("created_at"):
            s["created_at"] = s["created_at"].isoformat()
        if s.get("updated_at"):
            s["updated_at"] = s["updated_at"].isoformat()
    return jsonify({"stories": stories})

@app.route("/api/stories", methods=["POST"])
def api_create_story():
    data = request.get_json() or {}
    story_id = db.insert_interview_story(
        title=data.get("title", ""),
        situation=data.get("situation", ""),
        task=data.get("task", ""),
        action=data.get("action", ""),
        result=data.get("result", ""),
        reflection=data.get("reflection", ""),
        tags=data.get("tags", []),
        archetypes=data.get("archetypes", []),
    )
    return jsonify({"ok": True, "id": story_id})

@app.route("/api/stories/<int:story_id>", methods=["DELETE"])
def api_delete_story(story_id):
    success = db.delete_interview_story(story_id)
    return jsonify({"ok": success})

@app.route("/api/stories/generate/<int:job_id>", methods=["POST"])
def api_generate_stories(job_id):
    from job_evaluator import generate_interview_stories
    jobs = db.get_jobs_by_ids([job_id])
    if not jobs:
        return jsonify({"ok": False, "error": "Job not found."})
    story_ids = generate_interview_stories(jobs[0])
    return jsonify({"ok": True, "story_ids": story_ids})

# ---------------------------------------------------------------------------
# User Profile API
# ---------------------------------------------------------------------------
@app.route("/api/profile/settings", methods=["GET"])
def api_get_profile_settings():
    profile = load_profile()
    return jsonify({"ok": True, "profile": profile})

@app.route("/api/profile/settings", methods=["POST"])
def api_save_profile_settings():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No data provided."})
    save_profile(data)
    return jsonify({"ok": True, "message": "Profile saved."})

# ---------------------------------------------------------------------------
# Pipeline API
# ---------------------------------------------------------------------------
@app.route("/api/pipeline", methods=["GET"])
def api_get_pipeline():
    status = request.args.get("status", "pending")
    urls = db.get_pipeline_urls(status)
    for u in urls:
        for key in ("created_at", "processed_at"):
            if u.get(key):
                u[key] = u[key].isoformat()
    return jsonify({"urls": urls})

@app.route("/api/pipeline", methods=["POST"])
def api_add_pipeline_url():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    source = data.get("source", "manual")
    if not url:
        return jsonify({"ok": False, "error": "URL is required."})
    success = db.insert_pipeline_url(url, source)
    return jsonify({"ok": success})

@app.route("/api/pipeline/<int:pipeline_id>", methods=["POST"])
def api_update_pipeline(pipeline_id):
    data = request.get_json() or {}
    status = data.get("status", "done")
    error = data.get("error_message")
    db.update_pipeline_url(pipeline_id, status, error)
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Health / Integrity API
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def api_health():
    from ai_provider import get_provider_info
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.job_listings WHERE status != 'removed'")
            active_jobs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM public.job_evaluations")
            total_evals = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM public.interview_stories")
            total_stories = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM public.applications")
            total_apps = cur.fetchone()[0]
    finally:
        conn.close()

    provider_info = get_provider_info()
    return jsonify({
        "ok": True,
        "active_jobs": active_jobs,
        "total_evaluations": total_evals,
        "total_stories": total_stories,
        "total_applications": total_apps,
        "ai_provider": provider_info["provider"],
        "ai_model": provider_info["model"],
    })


# ---------------------------------------------------------------------------
# V3 End-to-End Onboarding & Strategy API
# ---------------------------------------------------------------------------

@app.route("/onboarding")
def onboarding_page():
    return render_template("onboarding.html")

@app.route("/api/user-profile", methods=["GET"])
def api_get_user_profile():
    profile = db.get_user_profile()
    if profile:
        for key in ("created_at", "updated_at"):
            if profile.get(key):
                profile[key] = profile[key].isoformat()
    return jsonify({"ok": True, "profile": profile})

@app.route("/api/user-profile", methods=["POST"])
def api_save_user_profile():
    data = request.get_json() or {}
    full_data = data.get("full_data", {})
    base_resume_md = data.get("base_resume_md", "")
    
    success = db.upsert_user_profile(full_data, base_resume_md)
    if success:
        return jsonify({"ok": True, "message": "Profile saved successfully."})
    return jsonify({"ok": False, "error": "Failed to save profile."})

@app.route("/api/profile/upload-resume", methods=["POST"])
def api_upload_resume():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "No file part"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": "No selected file"})
    
    filename = file.filename.lower()
    text = ""
    
    try:
        if filename.endswith(".md") or filename.endswith(".txt"):
            text = file.read().decode("utf-8")
        elif filename.endswith(".pdf"):
            from pypdf import PdfReader
            import io
            pdf = PdfReader(io.BytesIO(file.read()))
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        elif filename.endswith(".docx"):
            import docx
            import io
            doc = docx.Document(io.BytesIO(file.read()))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            return jsonify({"ok": False, "error": "Unsupported file format. Use .md, .pdf or .docx"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error reading file: {str(e)}"})

    if not text.strip():
        return jsonify({"ok": False, "error": "Could not extract text from file."})

    # AI Analysis
    model_name = request.form.get("model_name", "gemini-3-flash-preview")
    from ai_provider import create_provider
    try:
        provider = create_provider(model=model_name)
        prompt = f"""
Você é um especialista em recrutamento técnico sênior. Analise o seguinte currículo e extraia todas as informações para preenchimento de perfil.
Retorne APENAS um JSON válido no formato abaixo. Seja preciso e não invente dados que não existam no texto.

CURRÍCULO:
{text}

FORMATO JSON:
{{
  "personal": {{
    "name": "Nome Completo",
    "email": "e-mail",
    "phone": "telefone",
    "country": "país de residência",
    "linkedin": "url do linkedin",
    "github": "url do github ou portfolio"
  }},
  "legal": {{
    "work_authorization": "Yes se tiver autorização para US/EU, caso contrário No",
    "sponsorship": "Yes se precisar de visto, No se não precisar",
    "disability": "No (padrão) ou Yes se mencionado",
    "veteran": "No (padrão) ou Yes se mencionado",
    "race": "Hispanic/Latino, White, Black, Asian ou Decline"
  }},
  "preferences": {{
    "work_model": "Remote, Hybrid, Onsite ou Any",
    "salary_expectation": "valor se mencionado",
    "notice_period": "aviso prévio se mencionado"
  }},
  "base_resume_md": "O conteúdo do currículo integral convertido para Markdown de alta qualidade"
}}
        """
        response = provider.generate_text(prompt, model=model_name)
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            profile_data = json.loads(json_match.group(0))
            return jsonify({"ok": True, "profile_data": profile_data})
        else:
            # Fallback if no JSON found
            return jsonify({"ok": False, "error": "AI could not generate structured data. Try a different model or check the file content."})
    except Exception as e:
        return jsonify({"ok": False, "error": f"AI Error: {str(e)}"})

@app.route("/api/strategy/generate", methods=["POST"])
def api_generate_strategy():
    data = request.get_json() or {}
    profile_data = data.get("profile_data", {})
    model_name = data.get("model_name", "gemini-3-flash-preview")
    
    import resume_generator
    try:
        # Simplistic generation logic calling LLM
        provider = resume_generator.create_provider(model_name=model_name)
        prompt = f"""
Você é um estrategista de carreira sênior. Baseado neste perfil de candidato:
{json.dumps(profile_data, indent=2)}

Sua tarefa é sugerir uma Estratégia de Busca de Vagas (Search Strategy).
Retorne APENAS um JSON válido no seguinte formato:
{{
  "title": "Ex: Senior AI Engineer - Remote US",
  "keywords": ["AI Engineer", "LLM", "Python", "Machine Learning"],
  "locations": ["Remote", "United States", "Europe"],
  "remote_only": true,
  "ai_suggestions": "Foque em startups Series B+ que utilizam agentes ReAct."
}}
        """
        response = provider.generate(prompt)
        # Parse JSON
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            strategy = json.loads(json_match.group(0))
            db.upsert_search_strategy(
                title=strategy.get("title", "New Strategy"),
                keywords=strategy.get("keywords", []),
                locations=strategy.get("locations", []),
                remote_only=strategy.get("remote_only", True),
                ai_suggestions=strategy.get("ai_suggestions", "")
            )
            return jsonify({"ok": True, "strategy": strategy})
        else:
            return jsonify({"ok": False, "error": "Failed to parse AI response as JSON."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🌐 Starting LinkedIn Job Scraper + Profile Optimizer...")
    try:
        db.run_migration()
        print("   ✅ Database migrations applied.")
    except Exception as e:
        print(f"   ❌ Migration error: {e}")
        
    auto_recover_hung_jobs()
    print("   → http://localhost:5050 (Profile Optimizer)")
    print("   → http://localhost:5050/jobs (Job Scraper)\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
