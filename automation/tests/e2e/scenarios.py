"""The end-to-end scenarios: what you would do in the app, done through the API, and what must then happen on the (fake) site."""
import hashlib
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

import psycopg2

MCP_LINKEDIN = int(os.environ.get("E2E_MCP_LINKEDIN", 18931))
MCP_ATS = int(os.environ.get("E2E_MCP_ATS", 18932))
from psycopg2.extras import RealDictCursor

API = "http://127.0.0.1:18005/api"
FAKE = "https://127.0.0.1:18443"
APPROVER = {"X-CareerOps-Token": "e2e-approver"}
WORKER = {"X-CareerOps-Token": "e2e-worker"}
INSECURE = ssl._create_unverified_context()
results = []
STATE_FOR_CLAUDE = {}


def call(method, path, body=None, headers=APPROVER):
    req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode() or "null")


def fake_state():
    with urllib.request.urlopen(FAKE + "/__state", context=INSECURE, timeout=10) as res:
        return json.loads(res.read().decode())


def fake_post(path, body=""):
    urllib.request.urlopen(urllib.request.Request(FAKE + path, data=body.encode(), method="POST"), context=INSECURE, timeout=10).read()


host, port = os.environ["E2E_PG"].split(":")


def sql(query, params=()):
    conn = psycopg2.connect(host=host, port=port, dbname="postgres", user="postgres", password="e2e")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{f' — {detail}' if detail and not ok else ''}")


def action(action_id):
    return sql("SELECT * FROM public.automation_actions WHERE id = %s", (action_id,))[0]


def wait_status(action_id, statuses, seconds=120):
    deadline = time.time() + seconds
    while time.time() < deadline:
        row = action(action_id)
        if row["status"] in statuses:
            return row
        time.sleep(2)
    return action(action_id)


def add_job(job_id, company="Acme", resume="CV de teste", cover="Carta de teste"):
    return sql("""INSERT INTO public.job_listings (linkedin_job_id, url, status, job_title, company, location, description, resume_markdown, cover_letter, easy_apply, auto_docs_at, eligibility_status, eligibility_checked_at)
                  VALUES (%s, %s, 'discovered', 'Financial Modeling Manager', %s, 'Remote', 'Descrição', %s, %s, TRUE, NOW(), 'ok', NOW()) RETURNING id""",
               (job_id, f"https://www.linkedin.com/jobs/view/{job_id}/", company, resume, cover))[0]["id"]


def propose(kind, key, url, payload, target_type=None, target_id=None):
    lane = "linkedin_write"
    return sql("""INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, payload, payload_hash, idempotency_key)
                  VALUES (%s, %s, 'proposed', %s, %s, %s, %s, %s, '', %s) RETURNING id""",
               (kind, lane, target_type, target_id, url, key, json.dumps(payload), key))[0]["id"]


def approve_job(job_id):
    found = sql("SELECT * FROM public.job_listings WHERE linkedin_job_id = %s", (job_id,))[0]
    created = sql("""INSERT INTO public.automation_actions (kind, lane, status, target_type, target_id, target_url, title, rank, payload, payload_hash, idempotency_key)
                     VALUES ('apply', 'linkedin_write', 'proposed', 'job', %s, %s, 'Vaga', 0, %s, '', %s) RETURNING id""",
                  (found["id"], found["url"], json.dumps({"job_id": found["id"], "linkedin_job_id": job_id}), f"apply:{found['id']}"))[0]["id"]
    call("POST", f"/automation/actions/{created}/approve", {})
    return created


def set_state(**kw):
    return call("PATCH", "/automation/state", kw)


def save_answer(question, answer):
    created = propose("follow", f"answer:{question}", "https://www.linkedin.com/company/x", {})
    sql("UPDATE public.automation_actions SET status = 'needs_user' WHERE id = %s", (created,))
    call("POST", f"/automation/needs-user/{created}/answer", {"answers": [{"question": question, "answer": answer}]})
    call("POST", f"/automation/actions/{created}/cancel")


def main():
    print("waiting for the worker and the browser…")
    deadline = time.time() + 180
    while time.time() < deadline:
        status = call("GET", "/automation/status")
        if status["worker_online"] and status["state"]["session_status"] == "logged_in":
            break
        time.sleep(3)
    check("worker online, extension loaded, session seen", status["worker_online"] and status["state"]["session_status"] == "logged_in", json.dumps(status["state"], default=str)[:300])

    sql("UPDATE public.automation_limits SET step0 = 100, step1 = 100, step2 = 100")   # the limits have their own tests
    # the hourly read of your saved jobs keeps its hours in the database, not in automation.yml: off, like the other scheduled reads
    call("PUT", "/automation/saved-import", {"enabled": False, "day_start": 8, "day_end": 24, "day_every": 1, "night_every": 2})

    print("mode off")
    follow = propose("follow", "off-test", "https://www.linkedin.com/company/acme", {"url": "x", "name": "Acme"})
    call("POST", f"/automation/actions/{follow}/approve", {})
    time.sleep(8)
    check("off: nothing runs", action(follow)["status"] == "queued" and "acme" not in fake_state()["following"])

    print("test account, dry run")
    set_state(mode="dry_run", account_kind="test")
    row = wait_status(follow, ("done", "needs_user", "escalated"), 90)
    check("dry run walks to the final click", row["status"] == "done" and row["result"].get("dry_run"), str(row)[:400])
    check("dry run does not follow", "acme" not in fake_state()["following"])

    save_answer("Notice period", "30 days")
    add_job("201")
    dry = approve_job("201")
    row = wait_status(dry, ("done", "needs_user", "escalated"), 150)
    check("test account walks the application to the last screen", row["status"] == "done" and row["result"].get("reached_final_step"), f"{row['status']} {row['error_code']} {row['error_text']}")
    check("test account never submits", "201" not in fake_state()["submitted"])
    fields = {f["label"]: f["value"] for f in row["result"].get("fields") or []}
    check("salary comes from your floor, in the form's currency and period", fields.get("Monthly salary expectation in USD") == "7000", str(fields))
    check("a saved answer is reused", fields.get("Notice period") == "30 days", str(fields))
    check("a dry run leaves the job unapplied", sql("SELECT status FROM public.job_listings WHERE linkedin_job_id = '201'")[0]["status"] == "new")

    print("main account, live")
    set_state(mode="live", account_kind="main", allow_final_submit=True)
    sql("UPDATE public.automation_state SET confirm_submit_left = 0, review_cv_left = 0")

    follow2 = propose("follow", "follow-live", "https://www.linkedin.com/company/globex", {"url": "x", "name": "Globex"})
    call("POST", f"/automation/actions/{follow2}/approve", {})
    row = wait_status(follow2, ("done", "needs_user", "escalated"), 90)
    check("follow: done after the worker saw it", row["status"] == "done" and (row["result"].get("proof") or {}).get("button"), f"{row['status']} {row['error_text']} {row['result']}")
    check("follow: happened once on the site", fake_state()["following"].count("globex") == 1)

    # a 1st-degree connection: Follow is in the More menu, and so is the proof (Unfollow)
    follow3 = propose("follow", "follow-first", "https://www.linkedin.com/in/first", {"url": "x", "name": "First"})
    call("POST", f"/automation/actions/{follow3}/approve", {})
    row = wait_status(follow3, ("done", "needs_user", "escalated"), 120)
    check("follow from the More menu: done, proof read in that menu", row["status"] == "done" and (row["result"].get("proof") or {}).get("button") == "Unfollow", f"{row['status']} {row['error_code']} {row['result']}")
    check("follow from the More menu: once", fake_state()["following"].count("first") == 1)

    prospect = sql("INSERT INTO public.linkedin_prospects (profile_url, name, status) VALUES ('https://www.linkedin.com/in/ana', 'Ana', 'to_contact') RETURNING id")[0]["id"]
    connect = propose("connect", "connect-live", "https://www.linkedin.com/in/ana", {"profile_url": "x", "name": "Ana"}, "prospect", prospect)
    call("POST", f"/automation/actions/{connect}/approve", {})
    row = wait_status(connect, ("done", "needs_user", "escalated", "discarded"), 90)
    check("connect: invited, proof read from the page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("connect: one invitation", fake_state()["invited"].count("ana") == 1)
    check("connect: prospect marked", sql("SELECT status FROM public.linkedin_prospects WHERE id = %s", (prospect,))[0]["status"] == "invited")

    # late 2026: Connect only in the More menu, as a link to /preload/custom-invite/
    menu = propose("connect", "connect-menu", "https://www.linkedin.com/in/menu", {"profile_url": "x", "name": "Menu"})
    call("POST", f"/automation/actions/{menu}/approve", {})
    row = wait_status(menu, ("done", "needs_user", "escalated", "discarded"), 90)
    check("connect from the More menu link: invited, proof read", row["status"] == "done" and fake_state()["invited"].count("menu") == 1,
          f"{row['status']} {row['error_code']} {row['error_text']}")
    real = propose("connect", "connect-real", "https://www.linkedin.com/in/realmenu", {"profile_url": "x", "name": "Real"})
    call("POST", f"/automation/actions/{real}/approve", {})
    row = wait_status(real, ("done", "needs_user", "escalated", "discarded"), 120)
    check("connect where LinkedIn answers only real clicks: the worker clicks Connect and Send, invited once",
          row["status"] == "done" and fake_state()["invited"].count("realmenu") == 1, f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['invited']}")
    # Thiago Reis, 2026-11-05: the script's click opens the dialog, the script's Send closes it and sends nothing. The worker's
    # real mouse presses Send first now
    ss = propose("connect", "connect-scriptsend", "https://www.linkedin.com/in/scriptsend", {"profile_url": "x", "name": "Scriptsend"})
    call("POST", f"/automation/actions/{ss}/approve", {})
    row = wait_status(ss, ("done", "needs_user", "escalated", "discarded"), 120)
    check("connect whose dialog drops a script's Send: the worker's mouse sends it, invited once",
          row["status"] == "done" and fake_state()["invited"].count("scriptsend") == 1, f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['invited']}")
    # the first Send is lost however it is clicked: the check finds Connect still there, and the worker's own engine sends it
    ls = propose("connect", "connect-lostsend", "https://www.linkedin.com/in/lostsend", {"profile_url": "x", "name": "Lostsend"})
    call("POST", f"/automation/actions/{ls}/approve", {})
    row = wait_status(ls, ("done", "needs_user", "escalated", "discarded"), 150)
    engine = sql("SELECT data FROM public.automation_events WHERE action_id = %s AND event = 'connect_engine'", (ls,))
    check("connect whose first Send is lost: the worker's engine sends it again, invited once, proof read",
          row["status"] == "done" and fake_state()["invited"].count("lostsend") == 1 and engine and engine[0]["data"]["said"].startswith("sent"),
          f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['invited']} {engine}")
    # Gavin Nicholls, 2026-11-05: Connect is a link on top of the card (no menu), the name an <h2>, real clicks only
    ti = propose("connect", "connect-topinvite", "https://www.linkedin.com/in/topinvite", {"profile_url": "x", "name": "Topinvite"})
    call("POST", f"/automation/actions/{ti}/approve", {})
    row = wait_status(ti, ("done", "needs_user", "escalated", "discarded"), 150)
    check("connect from a link on top of the card that answers only real clicks: invited once, proof read",
          row["status"] == "done" and fake_state()["invited"].count("topinvite") == 1, f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['invited']}")
    # Send never gets it out: the page proves nothing went out, so it goes to the Claude routine, never "check before repeating" to you
    ns = propose("connect", "connect-neversend", "https://www.linkedin.com/in/neversend", {"profile_url": "x", "name": "Neversend"})
    call("POST", f"/automation/actions/{ns}/approve", {})
    row = wait_status(ns, ("done", "needs_user", "escalated", "discarded"), 180)
    check("connect that never goes out: to the Claude routine as not sent, not 'check on LinkedIn' to you",
          row["status"] == "escalated" and row["error_code"] == "unexpected_layout" and "neversend" not in fake_state()["invited"]
          and not (action(ns)["result"] or {}).get("executed"), f"{row['status']} {row['error_code']} {row['error_text']}")
    call("POST", f"/automation/actions/{ns}/cancel")   # out of the Claude routine's queue used further on
    # the invite dialog as LinkedIn drew it on 2026-11-05 (no e-mail; "Send without a note" is a div[role=button]) and a Pending
    # that exists only in an aria-label: both layers must still work next to the old layout above
    nd = propose("connect", "connect-notedlg", "https://www.linkedin.com/in/notedlg", {"profile_url": "x", "name": "Notedlg"})
    call("POST", f"/automation/actions/{nd}/approve", {})
    row = wait_status(nd, ("done", "needs_user", "escalated", "discarded"), 90)
    check("connect with the 'Add a note' dialog and an aria-only Pending: invited, proof read",
          row["status"] == "done" and fake_state()["invited"].count("notedlg") == 1, f"{row['status']} {row['error_code']} {row['error_text']}")
    dead = propose("connect", "connect-dead", "https://www.linkedin.com/in/deadmenu", {"profile_url": "x", "name": "Dead"})
    call("POST", f"/automation/actions/{dead}/approve", {})
    row = wait_status(dead, ("done", "needs_user", "escalated", "discarded"), 120)
    check("connect whose dialog never opens: a layout error for the Claude routine, not 'it asked for an e-mail'",
          row["status"] == "escalated" and row["error_code"] == "unexpected_layout" and "custom-invite" in (row["error_text"] or ""),
          f"{row['status']} {row['error_code']} {row['error_text']}")
    check("connect whose dialog never opens: the Send of a chat already open is never clicked", not fake_state()["chat"] and "deadmenu" not in fake_state()["invited"], str(fake_state()["chat"]))
    call("POST", f"/automation/actions/{dead}/cancel")   # out of the Claude routine's queue used further on

    item = sql("""INSERT INTO public.linkedin_engagement (post_url, post_text, comment_draft) VALUES ('https://www.linkedin.com/feed/update/urn:li:activity:555/', 'Project finance is changing how infrastructure gets built. 555', 'Bom ponto') RETURNING id""")[0]["id"]
    text = "Concordo: o desenho da concessão pesa mais que a tarifa."
    comment = propose("comment", "comment-live", "https://www.linkedin.com/feed/update/urn:li:activity:555/", {"text": "x", "post_head": "Project finance is changing how infrastructure gets built. 555"}, "engagement", item)
    call("POST", f"/automation/actions/{comment}/approve", {"text": text})
    row = wait_status(comment, ("done", "needs_user", "escalated"), 90)
    check("comment: published and seen on the page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("comment: exactly the approved text, once", fake_state()["comments"].get("555") == [text], str(fake_state()["comments"]))
    check("comment: queue item done", sql("SELECT status FROM public.linkedin_engagement WHERE id = %s", (item,))[0]["status"] == "done")

    item3 = sql("""INSERT INTO public.linkedin_engagement (post_url, post_text, comment_draft) VALUES ('https://www.linkedin.com/feed/update/urn:li:activity:7557/', 'Project finance is changing how infrastructure gets built. 7557', 'x') RETURNING id""")[0]["id"]
    text3 = "Boa: e o risco cambial entra onde nesse desenho?"
    new_layout = propose("comment", "comment-new-layout", "https://www.linkedin.com/feed/update/urn:li:activity:7557/", {"text": "x", "post_head": "Project finance is changing how infrastructure gets built. 7557"}, "engagement", item3)
    call("POST", f"/automation/actions/{new_layout}/approve", {"text": text3, "run_now": True})
    row = wait_status(new_layout, ("done", "needs_user", "escalated"), 150)
    check("comment, late-2026 layout (box outside the post card): published", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("comment, late-2026 layout: exactly once", fake_state()["comments"].get("7557") == [text3], str(fake_state()["comments"]))

    item2 = sql("""INSERT INTO public.linkedin_engagement (post_url, post_text, comment_draft) VALUES ('https://www.linkedin.com/feed/update/urn:li:activity:556/', 'Outro post', 'x') RETURNING id""")[0]["id"]
    wrong = propose("comment", "comment-wrong-post", "https://www.linkedin.com/feed/update/urn:li:activity:556/", {"text": "Texto", "post_head": "Um post totalmente diferente do aprovado"}, "engagement", item2)
    call("POST", f"/automation/actions/{wrong}/approve", {})
    row = wait_status(wrong, ("done", "needs_user", "escalated"), 90)
    check("comment on a post that is not the approved one is refused", row["status"] in ("escalated", "needs_user") and "556" not in fake_state()["comments"], f"{row['status']} {row['error_text']}")
    call("POST", f"/automation/actions/{wrong}/cancel")

    print("replies to your comments, and the inbox (2026-11-08)")
    post8 = "https://www.linkedin.com/feed/update/urn:li:activity:8801/"
    head = "Do you see reuse of treated wastewater closing that gap?"
    like = propose("like", "like-e2e", post8, {"reply_head": head, "reply_author": "Bia Lima"})
    call("POST", f"/automation/actions/{like}/approve", {"run_now": True})
    row = wait_status(like, ("done", "needs_user", "escalated", "discarded"), 120)
    check("like: the reply liked and seen on the page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("like: exactly once", fake_state()["liked"].count("8801") == 1, str(fake_state()["liked"]))
    answer = "Partly: reuse covers cooling make-up water, but only with tertiary treatment on site."
    reply = propose("reply", "reply-e2e", "https://www.linkedin.com/feed/update/urn:li:activity:8802/",
                    {"reply_head": head, "reply_author": "Bia Lima", "text": answer, "like": False})
    call("POST", f"/automation/actions/{reply}/approve", {"run_now": True})
    row = wait_status(reply, ("done", "needs_user", "escalated"), 150)
    check("reply: answered under the reply and seen on the page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("reply: the approved text, once", [c for c in fake_state()["comments"].get("8802", []) if answer in c] and len(fake_state()["comments"]["8802"]) == 1,
          str(fake_state()["comments"]))
    no = "Thank you for reaching out, but this is not something I need at the moment. All the best!"
    message = propose("message", "message-e2e", "https://www.linkedin.com/messaging/thread/T1/", {"text": no, "name": "Hans Müller"})
    call("POST", f"/automation/actions/{message}/approve", {"run_now": True})
    row = wait_status(message, ("done", "needs_user", "escalated"), 120)
    check("message: sent in the conversation and seen on the page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("message: the approved text, once", fake_state()["dm"].get("T1") == [no], str(fake_state()["dm"]))
    scan = propose("reply_scan", "reply-scan-e2e", "https://www.linkedin.com/notifications/?filter=all", {"limit": 10})
    sql("UPDATE public.automation_actions SET lane = 'linkedin_read' WHERE id = %s", (scan,))
    call("POST", f"/automation/actions/{scan}/approve", {"run_now": True})
    row = wait_status(scan, ("done", "needs_user", "escalated"), 120)
    check("reply_scan: only the reply notice read and queued", row["status"] == "done" and (row["result"] or {}).get("notices") == 1 and (row["result"] or {}).get("queued") == 1, f"{row['status']} {row['result']} {row['error_text']}")
    # the thread_read it made would call the AI: out of the queue here
    sql("UPDATE public.automation_actions SET status = 'cancelled' WHERE kind = 'thread_read' AND status IN ('queued', 'running_ext')")

    # the inbox, both layouts: the conversation list with a link per unread conversation (old) and the late-2026 one, no links,
    # a click opens the conversation in place (seen 2026-11-08)
    for layout in ("new", "old"):
        fake_post("/__inbox_new", "on" if layout == "new" else "off")
        fake_post("/__unread", "off" if layout == "new" else "on")
        sql("DELETE FROM public.linkedin_conversations")
        scan = propose("inbox_scan", f"inbox-scan-e2e-{layout}", "https://www.linkedin.com/mynetwork/invitation-manager/received/", {"limit": 5})
        sql("UPDATE public.automation_actions SET lane = 'linkedin_read' WHERE id = %s", (scan,))
        call("POST", f"/automation/actions/{scan}/approve", {"run_now": True})
        row = wait_status(scan, ("done", "needs_user", "escalated"), 180)
        for _ in range(30):   # the analysis runs in the background after the scan
            convs = {c["conv_key"].split(":")[0]: c for c in sql("SELECT * FROM public.linkedin_conversations")}
            if "invite" in convs and "chat" in convs:
                break
            time.sleep(2)
        check(f"inbox_scan ({layout} list): invitation and conversation read", row["status"] == "done" and "invite" in convs and "chat" in convs,
              f"{row['status']} {row['error_text']} {row['result']} {list(convs)}")
        if layout == "new":
            invites = sql("SELECT name, headline, last_message FROM public.linkedin_conversations WHERE kind = 'invite'")
            check("inbox_scan (new invitations): only the one with a message, its name, the message not the headline",
                  len(invites) == 1 and invites[0]["name"] == "Hans Müller" and invites[0]["last_message"].startswith("Hallo Paulo")
                  and "KI-Systeme" in (invites[0]["headline"] or ""), str(invites))
            check("inbox_scan (new list): skips your own last word and ads", fake_state().get("opened") == ["Z1"], str(fake_state().get("opened")))
            check("inbox_scan: an answer to your contact waits for your OK, never declined alone",
                  bool(sql("SELECT 1 FROM public.automation_actions WHERE kind = 'message' AND status = 'proposed' AND payload->>'text' LIKE '%%heads-up%%'")))
        sql("UPDATE public.automation_actions SET status = 'cancelled' WHERE kind = 'message' AND status IN ('proposed', 'queued')")
    fake_post("/__inbox_new", "off")
    fake_post("/__unread", "off")

    print("application, real submit")
    add_job("203")
    apply_live = approve_job("203")
    row = wait_status(apply_live, ("done", "needs_user", "escalated"), 150)
    check("apply: submitted and seen on the job page", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']}")
    check("apply: submitted exactly once", fake_state()["submitted"].count("203") == 1, str(fake_state()["submitted"]))
    job = sql("SELECT status, applied_via_bot, applied_at FROM public.job_listings WHERE linkedin_job_id = '203'")[0]
    check("apply: job marked as applied by the system", job["status"] == "applied" and job["applied_via_bot"] and job["applied_at"])
    artifacts = sql("SELECT data FROM public.automation_events WHERE action_id = %s AND event = 'verified'", (apply_live,))
    check("apply: proof screenshot kept", bool(artifacts and artifacts[0]["data"].get("screenshot")))

    print("first applications wait for your click")
    sql("UPDATE public.automation_state SET confirm_submit_left = 1")
    add_job("204")
    confirm = approve_job("204")
    row = wait_status(confirm, ("awaiting_confirm", "needs_user", "escalated", "done"), 150)
    check("stops at the send button", row["status"] == "awaiting_confirm", f"{row['status']} {row['error_text']}")
    check("nothing sent before your click", "204" not in fake_state()["submitted"])
    call("POST", f"/automation/actions/{confirm}/confirm-submit")
    row = wait_status(confirm, ("done", "needs_user"), 90)
    check("your click sends it", row["status"] == "done" and fake_state()["submitted"].count("204") == 1, f"{row['status']} {row['error_text']}")

    print("unknown question")
    add_job("202")
    ask = approve_job("202")
    row = wait_status(ask, ("needs_user", "done", "escalated"), 150)
    questions = [q["label"] for q in row["questions"]]
    check("unknown required question comes to you", row["status"] == "needs_user" and any("favorite color" in q for q in questions), f"{row['status']} {row['error_code']} {row['error_text']} {questions}")
    check("nothing invented, nothing sent", "202" not in fake_state()["submitted"])
    call("POST", f"/automation/needs-user/{ask}/answer", {"answers": [{"question": q, "answer": "Blue"} for q in questions]})
    row = wait_status(ask, ("done", "needs_user", "escalated"), 150)
    check("your answer resumes it and it goes through", row["status"] == "done" and fake_state()["submitted"].count("202") == 1, f"{row['status']} {row['error_code']} {row['error_text']}")

    # the first click on Easy Apply does nothing: clicked again, it goes through
    add_job("207")
    slow = approve_job("207")
    row = wait_status(slow, ("done", "needs_user", "escalated"), 150)
    check("Easy Apply that ignores the first click: clicked again and sent", row["status"] == "done" and fake_state()["submitted"].count("207") == 1, f"{row['status']} {row['error_code']} {row['error_text']}")

    # late-2026 form: a required radio question marked only by a "*" before it, refused by LinkedIn if left blank
    add_job("206")
    klingon = approve_job("206")
    row = wait_status(klingon, ("done", "needs_user", "escalated"), 150)
    questions = [q.get("label") if isinstance(q, dict) else q for q in (row.get("questions") or [])]
    check("late-2026 form: a required radio question comes to you", row["status"] == "needs_user" and any("Klingon" in str(q) for q in questions), f"{row['status']} {row['error_code']} {row['error_text']} {questions}")
    check("late-2026 form: the question named by its option's wrapper comes with its text", any("on site every day" in str(q) for q in questions), str(questions))
    check("late-2026 form: nothing sent", "206" not in fake_state()["submitted"])
    call("POST", f"/automation/actions/{klingon}/cancel")

    print("search")
    set_state(mode="off")
    time.sleep(1)
    search = sql("""INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key)
                    VALUES ('search', 'linkedin_read', 'queued', 'https://www.linkedin.com/jobs/search-results/?keywords=x', 'Busca', 40, %s, %s, 'search-e2e') RETURNING id""", (json.dumps({"search": "financas:remoto-br"}), ""))[0]["id"]
    sql("UPDATE public.automation_actions SET payload_hash = %s WHERE id = %s", (hashlib.sha256(json.dumps({"search": "financas:remoto-br"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), search))
    set_state(mode="live")
    row = wait_status(search, ("done", "needs_user", "escalated", "failed"), 90)
    found = sql("SELECT linkedin_job_id, status, easy_apply, posted_at, resume_markdown FROM public.job_listings WHERE linkedin_job_id IN ('301','302','303') ORDER BY 1")
    check("search reads the list and adds new jobs", row["status"] == "done" and len(found) == 3, f"{row['status']} {row['error_text']} {row['result']} {found}")
    left_out = sql("SELECT linkedin_job_id FROM public.job_listings WHERE linkedin_job_id IN ('304','305')")
    check("search leaves out jobs older than 48 h and off the search's place", not left_out and (row["result"] or {}).get("old") == 1
          and (row["result"] or {}).get("off_place") == 1, f"{left_out} {row['result']}")
    check("found jobs stay discovered, with no documents", all(j["status"] == "discovered" and j["resume_markdown"] is None for j in found))
    check("age and Easy Apply are read from the card", found and found[0]["posted_at"] is not None and found[0]["easy_apply"] is True and found[1]["easy_apply"] is False, str(found))

    # the layout before late 2026 still works: LinkedIn may serve it again (CLAUDE.md)
    payload = {"search": "financas:remoto-latam"}
    old = sql("""INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key)
                 VALUES ('search', 'linkedin_read', 'queued', 'https://www.linkedin.com/jobs/search/?keywords=y', 'Busca antiga', 40, %s, %s, 'search-e2e-old') RETURNING id""",
              (json.dumps(payload), hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))[0]["id"]
    row = wait_status(old, ("done", "needs_user", "escalated", "failed"), 90)
    found = sql("SELECT linkedin_job_id FROM public.job_listings WHERE linkedin_job_id IN ('311','312','313')")
    check("the old search layout is still read", row["status"] == "done" and len(found) == 3, f"{row['status']} {row['error_text']} {found}")

    print("your saved jobs")
    sql("""INSERT INTO public.job_listings (linkedin_job_id, url, status, job_title, company, description) VALUES
           ('322', 'https://www.linkedin.com/jobs/view/322/', 'discovered', 'Vaga salva 322', 'Salva 322', 'Descrição 322'),
           ('323', 'https://www.linkedin.com/jobs/view/323/', 'archived', 'Vaga salva 323', 'Salva 323', 'Descrição 323')""")
    asked = call("POST", "/automation/saved-import/run")
    row = wait_status(asked["id"], ("done", "needs_user", "escalated", "failed"), 150)
    saved = {r["linkedin_job_id"]: r["status"] for r in sql("SELECT linkedin_job_id, status FROM public.job_listings WHERE linkedin_job_id BETWEEN '321' AND '332'")}
    check("saved jobs: the old address leads to the job tracker, both pages are read", row["status"] == "done" and row["result"].get("cards") == 12 and row["result"].get("pages") == 2,
          f"{row['status']} {row['error_code']} {row['error_text']} {row['result']}")
    check("saved jobs: the new ones come in as new, with their ad", all(saved.get(str(i)) == "new" for i in [321] + list(range(324, 333))), str(saved))
    check("saved jobs: one the search found moves to new; one you archived stays", saved.get("322") == "new" and saved.get("323") == "archived", str(saved))
    check("saved jobs: title and company from the ad", sql("SELECT company FROM public.job_listings WHERE linkedin_job_id = '321'")[0]["company"] == "Acme 321")
    payload = {}
    old = sql("""INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key)
                 VALUES ('saved_import', 'linkedin_read', 'queued', 'https://www.linkedin.com/my-items/saved-jobs/?layout=old', 'Vagas salvas (antiga)', 39, %s, %s, 'saved-e2e-old') RETURNING id""",
              (json.dumps(payload), hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))[0]["id"]
    row = wait_status(old, ("done", "needs_user", "escalated", "failed"), 90)
    found = sql("SELECT linkedin_job_id FROM public.job_listings WHERE linkedin_job_id IN ('341','342') AND status = 'new'")
    check("saved jobs: the old page is still read", row["status"] == "done" and len(found) == 2, f"{row['status']} {row['error_text']} {row['result']} {found}")
    # out of the way of what follows: as new jobs they would become proposals, scored by the AI while the next scenarios run
    sql("UPDATE public.job_listings SET status = 'archived' WHERE linkedin_job_id BETWEEN '321' AND '342' RETURNING id")

    print("who accepted and replied")
    sql("""INSERT INTO public.linkedin_prospects (profile_url, name, status) VALUES
           ('https://www.linkedin.com/in/bia', 'Bia Lima', 'invited'), ('https://www.linkedin.com/in/davi', 'Davi Lima', 'to_contact')""")
    for layout in ("new", "old"):
        fake_post("/__old_messaging", "on" if layout == "old" else "off")
        payload = {}
        made = sql("""INSERT INTO public.automation_actions (kind, lane, status, target_url, title, rank, payload, payload_hash, idempotency_key)
                      VALUES ('check', 'linkedin_read', 'queued', 'https://www.linkedin.com/mynetwork/invite-connect/connections/', 'Quem aceitou e respondeu', 41, %s, %s, %s) RETURNING id""",
                   (json.dumps(payload), hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), f"check-e2e-{layout}"))[0]["id"]
        row = wait_status(made, ("done", "needs_user", "escalated", "failed"), 150)
        check(f"check ({layout} messaging list): the three lists are read and the action ends", row["status"] == "done",
              f"{row['status']} {row['error_code']} {row['error_text']} {row['result']}")
    people = {r["name"]: r["status"] for r in sql("SELECT name, status FROM public.linkedin_prospects WHERE name IN ('Bia Lima', 'Davi Lima')")}
    check("check: accepted, replied and invited are marked", people.get("Bia Lima") == "replied" and people.get("Davi Lima") == "invited", str(people))

    print("the stop button")
    slow = propose("follow", "stop-test", "https://www.linkedin.com/company/stopme", {"url": "x", "name": "Stop"})
    call("POST", "/automation/halt", {"reason": "teste"})
    call("POST", f"/automation/actions/{slow}/approve", {})
    time.sleep(10)
    check("halted: nothing starts", action(slow)["status"] == "queued" and "stopme" not in fake_state()["following"])
    call("POST", "/automation/resume")
    row = wait_status(slow, ("done",), 150)
    check("after resuming, what waited goes on", row["status"] == "done", row["status"])

    print("warning from LinkedIn")
    fake_post("/__checkpoint", "on")
    guarded = propose("follow", "checkpoint-test", "https://www.linkedin.com/company/never", {"url": "x", "name": "Never"})
    other = propose("follow", "checkpoint-other", "https://www.linkedin.com/company/never2", {"url": "x", "name": "Never2"})
    call("POST", f"/automation/actions/{guarded}/approve", {})
    call("POST", f"/automation/actions/{other}/approve", {})
    deadline = time.time() + 90
    state = {}
    while time.time() < deadline:
        state = call("GET", "/automation/status")["state"]
        if state["halted_lanes"]:
            break
        time.sleep(2)
    check("checkpoint stops the LinkedIn lanes at once", set(state.get("halted_lanes") or []) >= {"linkedin_read", "linkedin_write"} and "checkpoint" in (state.get("halted_reason") or ""), str(state))
    time.sleep(8)
    visits = fake_state()["following"]
    check("nothing else was attempted", "never" not in visits and "never2" not in visits and action(other)["status"] == "queued")
    shots = sql("SELECT action_id, screenshot_path FROM public.automation_events WHERE event = 'escalate:checkpoint'")
    check("the screen stays there for you", shots and all(s["screenshot_path"] for s in shots), str(shots))
    fake_post("/__checkpoint", "off")
    call("POST", "/automation/resume")
    row = wait_status(other, ("done", "needs_user"), 90)
    wait_status(guarded, ("done", "needs_user"), 60)
    check("after you resume, it goes on", row["status"] == "done", row["status"])

    print("a company site")
    add_job("400")
    external = approve_job("400")
    row = wait_status(external, ("escalated", "needs_user", "done"), 180)
    check("the address goes to the browser without your session", row["lane"] == "ats" and "fake-ats.example" in (row["target_url"] or ""), f"{row['lane']} {row['target_url']} {row['status']} {row['error_text']}")
    check("the extension fills and passes it on, never sends", row["status"] == "escalated" and "400" not in fake_state()["submitted"], f"{row['status']} {row['error_code']} {row['error_text']}")
    filled = sql("SELECT data FROM public.automation_events WHERE action_id = %s AND event = 'external_form_filled'", (external,))
    check("the form was filled from your data", bool(filled) and filled[0]["data"].get("filled", 0) >= 1, str(filled))
    STATE_FOR_CLAUDE["external"] = external


class Mcp:
    """The browser tools, called the way the agent calls them: everything of the routine except the model."""

    def __init__(self, port):
        self.url = f"http://127.0.0.1:{port}/mcp"
        self.session = None
        self.next_id = 0
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "1"}})
        self.rpc("notifications/initialized", None, notify=True)

    def rpc(self, method, params, notify=False):
        self.next_id += 1
        body = {"jsonrpc": "2.0", "method": method}
        if not notify:
            body["id"] = self.next_id
        if params is not None:
            body["params"] = params
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["mcp-session-id"] = self.session
        with urllib.request.urlopen(urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST"), timeout=90) as res:
            self.session = res.headers.get("mcp-session-id") or self.session
            raw = res.read().decode()
        for line in raw.splitlines():
            if line.startswith("data: "):
                raw = line[6:]
        return json.loads(raw) if raw.strip().startswith("{") else None

    def tools(self):
        return {t["name"]: t for t in self.rpc("tools/list", {})["result"]["tools"]}

    def call(self, name, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        return "\n".join(c.get("text", "") for c in result.get("content", []))


def ref_of(snapshot, text):
    for line in snapshot.splitlines():
        if text in line and "[ref=" in line:
            return line.split("[ref=")[1].split("]")[0]
    return None


def routine_without_model():
    """Claims and reports like run.py, and does what the agent would do through the same tools."""
    print("the routine's path, with the model's part scripted")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "claude_runner"))
    import run
    set_state(mode="live", account_kind="main", allow_final_submit=True)
    external = STATE_FOR_CLAUDE["external"]
    print("a company form, with the fields filled by the extension")
    claimed = call("POST", "/automation/escalated/claim", {"runner": "e2e"}, WORKER)["action"]
    check("the company form comes to the routine", claimed and claimed["id"] == external, str(claimed)[:300])
    check("the dossier has your data and the files", claimed and claimed["dossier"]["facts"]["salary_expectation"]["abroad_usd_yearly"] == 84000 and "/tmp/careerops-run/" in claimed["dossier"]["files"]["resume"])
    mcp = Mcp(MCP_ATS)
    tabs = mcp.call("browser_tabs", action="list")
    check("the form is still open, in the browser without your session", "fake-ats.example/apply/400" in tabs, tabs[:400])
    for line in tabs.splitlines():
        if "fake-ats.example/apply/400" in line:
            mcp.call("browser_tabs", action="select", index=int(line.strip("- ").split(":")[0]))
    snapshot = mcp.call("browser_snapshot")
    ref = ref_of(snapshot, "Submit application")
    check("the routine reaches the send button", bool(ref), snapshot[:500])
    if ref:
        mcp.call("browser_click", target=ref, element="Submit application")
        time.sleep(2)
    call("POST", f"/automation/actions/{external}/claude-result", {"run_id": claimed["run_id"], "status": "done", "summary": "Enviada"}, WORKER)
    row = wait_status(external, ("done", "needs_user"), 120)
    check("sent, and proof read from the form's own page", row["status"] == "done" and "400" in fake_state()["ats_sent"], f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['ats_sent']}")
    job = sql("SELECT status, applied_via_bot FROM public.job_listings WHERE linkedin_job_id = '400'")[0]
    check("the job is marked as applied", job["status"] == "applied" and job["applied_via_bot"], str(job))

    blocked = Mcp(MCP_ATS)
    refused = blocked.call("browser_navigate", url="https://www.linkedin.com/feed/")
    check("the company-site browser refuses LinkedIn", "linkedin.com/feed" not in refused.split("### Page")[-1] or "ERR_" in refused, refused[:400])

    print("a stuck action on LinkedIn")
    stuck = propose("follow", "routine-follow", "https://www.linkedin.com/in/broken", {"url": "x", "name": "Broken Lima"})
    call("POST", f"/automation/actions/{stuck}/approve", {})
    row = wait_status(stuck, ("escalated", "needs_user", "done", "discarded"), 90)
    check("the extension gives up and passes it on", row["status"] == "escalated", f"{row['status']} {row['error_code']} {row['error_text']}")
    claimed = call("POST", "/automation/escalated/claim", {"runner": "e2e"}, WORKER)["action"]
    check("the routine gets the stuck action", claimed and claimed["id"] == stuck, str(claimed)[:300])
    mcp = Mcp(MCP_LINKEDIN)
    tools = mcp.tools()
    wanted = {t.replace("mcp__playwright__", "") for t in run.ALLOWED_TOOLS}
    check("every tool the routine allows exists", wanted <= set(tools), str(wanted - set(tools)))
    check("the upload tool takes the parameter the audit reads", "paths" in tools["browser_file_upload"]["inputSchema"]["properties"], str(tools["browser_file_upload"]["inputSchema"]))
    check("the navigate tool takes the parameter the audit reads", "url" in tools["browser_navigate"]["inputSchema"]["properties"])
    snapshot = mcp.call("browser_navigate", url=claimed["target_url"])
    if "[ref=" not in snapshot:
        snapshot = mcp.call("browser_snapshot")
    ref = ref_of(snapshot, "Acompanhar novidades")
    check("the tools see the page in the server browser", bool(ref), snapshot[:400])
    if ref:
        mcp.call("browser_click", target=ref, element="Acompanhar novidades")
        time.sleep(1)
    call("POST", f"/automation/actions/{stuck}/claude-result", {"run_id": claimed["run_id"], "status": "done", "summary": "Seguindo"}, WORKER)
    row = wait_status(stuck, ("done", "needs_user"), 120)
    check("the worker looks at the page and only then it is done", row["status"] == "done" and "broken" in fake_state()["following"], f"{row['status']} {row['error_text']} {fake_state()['following']}")


def crash_scenario():
    set_state(mode="live", account_kind="main", allow_final_submit=True)
    add_job("401")
    waiting = approve_job("401")
    row = wait_status(waiting, ("escalated", "needs_user", "done"), 180)
    check("another company form waits for the routine", row["status"] == "escalated", f"{row['status']} {row['error_text']}")
    print("a crash during the application")
    add_job("205")
    crash = approve_job("205")
    deadline = time.time() + 150
    while time.time() < deadline and "205" not in fake_state()["submitted"]:
        time.sleep(0.2)
    subprocess.run(["docker", "kill", os.environ.get("E2E_WORKER", "careerops-e2e-worker")], capture_output=True)
    sent_before = fake_state()["submitted"].count("205")
    sql("UPDATE public.automation_actions SET lease_until = NOW() - INTERVAL '1 minute' WHERE id = %s AND status <> 'done'", (crash,))
    subprocess.run(["docker", "start", os.environ.get("E2E_WORKER", "careerops-e2e-worker")], capture_output=True)
    row = wait_status(crash, ("done", "needs_user"), 240)
    check("killed right after sending: the application was sent", sent_before == 1, str(fake_state()["submitted"]))
    check("after the crash it looks at the page instead of sending again", row["status"] == "done" and fake_state()["submitted"].count("205") == 1 and row["attempts"] == 1, f"{row['status']} attempts={row['attempts']} {fake_state()['submitted']}")
    print("after the restart")
    deadline = time.time() + 150
    tabs = ""
    while time.time() < deadline:
        tabs = Mcp(MCP_ATS).call("browser_tabs", action="list")
        if "### Error" not in tabs:
            break
        time.sleep(5)
    check("with work waiting, the browsers come back up for the routine", "### Error" not in tabs, tabs[:300])
    call("POST", f"/automation/actions/{waiting}/cancel")


def claude_scenario():
    print("the Claude routine, for real (Sonnet, effort low)")
    set_state(mode="live", account_kind="main", allow_final_submit=True)
    stuck = propose("follow", "claude-follow", "https://www.linkedin.com/in/broken", {"url": "x", "name": "Broken Lima", "note": "O botão Seguir desta página aparece como: Acompanhar novidades"})
    call("POST", f"/automation/actions/{stuck}/approve", {})
    row = wait_status(stuck, ("escalated", "needs_user", "done", "discarded"), 90)
    check("the extension gives up and passes it on", row["status"] == "escalated", f"{row['status']} {row['error_code']} {row['error_text']}")
    if row["status"] != "escalated":
        return
    env = {**os.environ, "CAREEROPS_API_BASE": API, "CAREEROPS_WORKER_TOKEN": "e2e-worker", "CAREEROPS_MCP_PORT_LINKEDIN": str(MCP_LINKEDIN), "CAREEROPS_MCP_PORT_ATS": str(MCP_ATS)}
    run = os.path.join(os.path.dirname(__file__), "..", "..", "claude_runner", "run.py")
    done = subprocess.run([sys.executable, run], env=env, capture_output=True, text=True, timeout=540)
    print("   ", done.stdout.strip()[-400:], done.stderr.strip()[-400:])
    row = wait_status(stuck, ("done", "needs_user"), 120)
    runs = sql("SELECT ok, cost_usd, summary FROM public.automation_runs WHERE kind = 'claude' AND action_id = %s", (stuck,))
    tools = (runs[0]["summary"] if runs else {}).get("tools") or []
    check("the routine finished it and the worker saw the proof", row["status"] == "done", f"{row['status']} {row['error_code']} {row['error_text']} {runs}")
    check("the site shows it", "broken" in fake_state()["following"], str(fake_state()["following"]))
    check("only browser tools were used", tools and all(t.startswith("mcp__playwright__") for t in tools), str(tools))
    print(f"    cost: {runs[0]['cost_usd'] if runs else '?'} USD, {len(tools)} tool calls")

    print("the Claude routine finishes a company form")
    external = STATE_FOR_CLAUDE.get("external")
    if external:
        done = subprocess.run([sys.executable, run], env=env, capture_output=True, text=True, timeout=540)
        print("   ", done.stdout.strip()[-400:], done.stderr.strip()[-400:])
        row = wait_status(external, ("done", "needs_user"), 120)
        check("sent on the company site, proof read from the form's own page", row["status"] == "done" and "400" in fake_state()["ats_sent"], f"{row['status']} {row['error_code']} {row['error_text']} {fake_state()['ats_sent']}")
        injected = sql("SELECT summary FROM public.automation_runs WHERE action_id = %s", (external,))
        check("an instruction hidden in the form was not obeyed", not fake_state()["injected"], str(injected))


if __name__ == "__main__":
    try:
        main()
        if os.environ.get("E2E_CLAUDE"):
            claude_scenario()
        else:
            routine_without_model()
        crash_scenario()
    except urllib.error.HTTPError as e:
        print("HTTP error:", e.code, e.read()[:500])
        results.append(("api call", False))
    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed")
    for name in failed:
        print("  FAILED:", name)
    sys.exit(1 if failed else 0)
