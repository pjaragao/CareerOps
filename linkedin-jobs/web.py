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

# CHAT_TEMPLATE moved to templates/chat.html

# HTML_TEMPLATE moved to templates/index.html


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

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
                    WHERE status != 'removed'
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
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🌐 Starting LinkedIn Job Scraper Web UI...")
    auto_recover_hung_jobs()
    print("   → http://localhost:5050\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
