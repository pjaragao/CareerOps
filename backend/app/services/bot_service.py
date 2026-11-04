"""Lolo, the WhatsApp bot: what the system has to tell you, and what you answer from there.

The bot holds no rules. It fetches the notifications below (texts ready to send), marks them delivered, and passes on what
you decide with the same routes the app uses. A notification is made once: an action records the last status you were told
about, so a change into a status worth telling becomes exactly one message."""
import html
import json
import logging
import re
import urllib.error
import urllib.request
from typing import Tuple, Dict, List, Optional
from urllib.parse import urlparse

from psycopg2.extras import Json

from app.core.config import settings
from app.services.automation_service import AutomationService, _local, _one, _rows, config, now, payload_hash

log = logging.getLogger("bot")

KIND_LABEL = {"apply": "Vagas", "comment": "Comentários", "connect": "Conexões", "follow": "Seguir"}
STATUS_LABEL = {"applied": "candidatura enviada", "interviewing": "em entrevista", "offer": "proposta", "rejected": "recusada",
                "done": "encerrada", "new": "nova", "discovered": "descoberta", "archived": "arquivada"}
POST_PATH = re.compile(r"^/(posts/[^/]+|feed/update/urn:li:(activity|share|ugcPost|groupPost):[\d-]+)/?$")
LINKEDIN_IN_PAGE = re.compile(r"https://www\.linkedin\.com/(?:posts|feed/update)/[^\s\"'<>]+")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _cfg() -> dict:
    return config().get("bot") or {}


def _ago(when) -> str:
    if not when:
        return ""
    hours = int((now() - when).total_seconds() // 3600)
    return f"há {hours} h" if hours < 48 else f"há {hours // 24} dias"


def _short(text: Optional[str], n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def expand_short_link(url: str) -> str:
    """lnkd.in/... (the app's "copy link"): where it points, read from the redirect without following it. Whatever comes
    back still has to be a LinkedIn post, so this never opens anything else."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=10) as r:   # no redirect: a page that holds the link
            found = LINKEDIN_IN_PAGE.search(r.read(500_000).decode("utf-8", "replace"))
            return html.unescape(found.group(0)) if found else ""
    except urllib.error.HTTPError as e:
        return e.headers.get("Location") or "" if 300 <= e.code < 400 else ""
    except Exception as e:
        log.info("short link not expanded (%s): %s", url, e)
        return ""


def normalize_post_url(url: str) -> str:
    """A LinkedIn post, as one address: no tracking, no fragment. Anything else is refused."""
    url = (url or "").strip()
    if url.startswith(("linkedin.com", "www.linkedin.com", "lnkd.in")):
        url = "https://" + url
    if urlparse(url).hostname == "lnkd.in":
        url = expand_short_link(url) or url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("linkedin.com", "www.linkedin.com"):
        raise ValueError("Não é um link do LinkedIn")
    if not POST_PATH.match(parsed.path):
        raise ValueError("O link não é de um post do LinkedIn (precisa ser /posts/..., /feed/update/... ou lnkd.in/...)")
    return f"https://www.linkedin.com{parsed.path.rstrip('/')}/"


def fetch_public_post(url: str) -> Dict[str, str]:
    """The post as anyone without a login sees it: LinkedIn shows public posts with their text in the page data. A post that
    needs a login comes back empty, and then the text has to come from you."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if urlparse(r.geturl()).hostname not in ("linkedin.com", "www.linkedin.com") or "/authwall" in r.geturl() or "/login" in r.geturl():
                return {}
            page = r.read(3_000_000).decode("utf-8", "replace")
    except Exception as e:
        log.info("public post not read (%s): %s", url, e)
        return {}
    return parse_post_page(page)


def parse_post_page(page: str) -> Dict[str, str]:
    for block in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in (data if isinstance(data, list) else data.get("@graph") or [data]):
            if not isinstance(item, dict):
                continue
            text = item.get("articleBody") or item.get("text")
            if text:
                author = item.get("author") or {}
                author = author[0] if isinstance(author, list) and author else author
                return {"text": html.unescape(str(text)).strip(), "author": str(author.get("name") or "") if isinstance(author, dict) else ""}
    meta = re.search(r'<meta[^>]+(?:property|name)="(?:og:description|description)"[^>]+content="([^"]+)"', page)
    title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page)
    if meta:
        author = html.unescape(title.group(1)).split(" on LinkedIn")[0].split(" no LinkedIn")[0].split("|")[0].strip() if title else ""
        return {"text": html.unescape(meta.group(1)).strip(), "author": author[:120]}
    return {}


class BotService:
    # ── Notifications ────────────────────────────────────────────────────
    @staticmethod
    def notify(kind: str, text: str, data: Optional[dict] = None, urgent: bool = False, key: Optional[str] = None) -> Optional[dict]:
        """One message for you. With a key, the same thing is never told twice."""
        return _one("""INSERT INTO public.bot_notifications (kind, urgent, text, data, dedupe_key) VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (dedupe_key) DO NOTHING RETURNING *""", (kind, urgent, text[:3800], Json(data or {}), key))

    @staticmethod
    def quiet() -> bool:
        start, end = (_cfg().get("quiet_hours") or [22, 7])[:2]
        hour = _local().hour
        return hour >= start or hour < end if start > end else start <= hour < end

    @staticmethod
    def pending(limit: int = 20) -> List[dict]:
        """What is still to be sent, oldest first. At night only what is urgent; the rest waits for the morning."""
        urgent_only = BotService.quiet()
        return _rows(f"""SELECT id, kind, urgent, text, data, created_at FROM public.bot_notifications
                          WHERE delivered_at IS NULL {"AND urgent" if urgent_only else ""} ORDER BY id LIMIT %s""", (limit,))

    @staticmethod
    def ack(ids: List[int]) -> int:
        return len(_rows("UPDATE public.bot_notifications SET delivered_at = NOW() WHERE id = ANY(%s) AND delivered_at IS NULL RETURNING id", (ids,)))

    # ── What changed (every minute, from the automation tick) ─────────────
    @staticmethod
    def collect() -> int:
        made = BotService._halt_notice()
        made += BotService._status_notices()
        made += BotService._proposals_digest()
        return made

    @staticmethod
    def _halt_notice() -> int:
        state = AutomationService.state()
        if not state.get("halted_at"):
            return 0
        lanes = ", ".join(state.get("halted_lanes") or []) or "todas"
        return bool(BotService.notify("halt", (
            f"⏹ *Automação parada* ({lanes})\nMotivo: {state.get('halted_reason') or '—'}\n\n"
            "Nada mais roda no LinkedIn até você religar. Se foi um aviso do LinkedIn, abra o navegador do servidor antes: "
            f"{settings.CAREEROPS_NOVNC_URL}\nPara religar, me diga “religar automação”."),
            {"halted_at": str(state["halted_at"])}, urgent=True, key=f"halt:{state['halted_at'].isoformat()}"))

    @staticmethod
    def _mark(action_id: int, status: str) -> bool:
        """Whether this status is news: it is recorded now, so it is told once."""
        return bool(_one("""UPDATE public.automation_actions SET notified_status = %s
                             WHERE id = %s AND notified_status IS DISTINCT FROM %s RETURNING id""", (status, action_id, status)))

    @staticmethod
    def _status_notices() -> int:
        made = 0
        # it left the status you were told about: coming back to it is news again
        _rows("""UPDATE public.automation_actions SET notified_status = NULL
                  WHERE notified_status IN ('needs_user', 'review_docs', 'awaiting_confirm') AND status <> notified_status""")
        done_kinds = list(_cfg().get("done_kinds") or ["apply", "comment"])
        for a in _rows("""
            SELECT a.*, j.company, j.job_title FROM public.automation_actions a
              LEFT JOIN public.job_listings j ON a.target_type = 'job' AND j.id = a.target_id
             WHERE a.notified_status IS DISTINCT FROM a.status
               AND (a.status IN ('needs_user', 'review_docs', 'awaiting_confirm')
                    OR (a.status = 'done' AND a.kind = ANY(%s) AND a.finished_at > NOW() - INTERVAL '1 day')
                    OR (a.status = 'done' AND a.kind = 'saved_import' AND a.run_now AND a.finished_at > NOW() - INTERVAL '1 day'))
             ORDER BY a.id LIMIT 30""", (done_kinds,)):
            if not BotService._mark(a["id"], a["status"]):
                continue
            BotService.notify(f"action_{a['status']}", *BotService._status_text(a))
            made += 1
        return made

    @staticmethod
    def _status_text(a: dict):
        title = a.get("title") or ""
        if a["status"] == "needs_user":
            questions = [q for q in (a.get("questions") or []) if isinstance(q, dict)]
            lines = [f"🙋 *Precisa de você* · {title}", a.get("error_text") or a.get("error_code") or ""]
            if questions:
                lines.append("Perguntas do formulário:")
                lines += [f"• {q.get('label') or q.get('question') or '(pergunta sem texto na página)'}" + (f" (opções: {', '.join(str(o) for o in q['options'][:6])})" if q.get("options") else "")
                          for q in questions[:8]]
                lines.append("Responda a esta mensagem (ex.: “aviso prévio = 30 dias”); a resposta fica salva para as próximas.")
            elif a.get("error_code") in ("captcha", "account_required", "email_verification", "session_expired", "checkpoint"):
                lines.append(f"Isso se resolve no navegador do servidor: {settings.CAREEROPS_NOVNC_URL}")
                lines.append("Depois responda a esta mensagem com “de novo”.")
            elif a.get("error_code") == "confirm_timeout":   # your OK still counts: it is filled again and sent without another wait
                lines.append("Responda a esta mensagem com “ok” (preenche de novo e envia, sem esperar outra vez) ou “não” (desiste).")
            else:
                lines.append("Responda a esta mensagem com “de novo” ou “não” (desiste).")
            return "\n".join(l for l in lines if l), {"action_id": a["id"], "questions": questions, "reply": "needs_user",
                                                         "error_code": a.get("error_code")}, False
        if a["status"] == "review_docs":
            job = a.get("target_id")
            files = [{"name": "CV", "path": f"/api/jobs/{job}/document.pdf?kind=resume"},
                     {"name": "Carta", "path": f"/api/jobs/{job}/document.pdf?kind=cover"}]
            if a.get("error_code") == "cv_review_failed":   # the reviewer agent sent it back and the redo still failed
                return (f"📄 *O revisor não aprovou o CV* · {a.get('job_title') or title} · {a.get('company') or ''}\n"
                        f"{a.get('error_text') or ''}\n"
                        "Mando o CV e a carta. Responda a esta mensagem com “ok” para enviar assim mesmo, ou “não” para desistir da vaga."), \
                    {"action_id": a["id"], "files": files, "reply": "review_docs"}, False
            return (f"📄 *CV para revisar* · {a.get('job_title') or title} · {a.get('company') or ''}\n"
                    "Mando o CV e a carta em seguida. Responda a esta mensagem com “ok” se estiver bom, ou “não” para desistir."), \
                {"action_id": a["id"], "files": files, "reply": "review_docs"}, False
        if a["status"] == "awaiting_confirm":
            return (f"🟢 *Pronto para enviar* · {title}\nO formulário está preenchido e parado no botão Enviar. "
                    "Responda a esta mensagem com “ok” para o clique final, ou “não” para desistir. "
                    "Ele espera 30 minutos; depois disso, o “ok” ainda vale: preenche de novo e envia."), {"action_id": a["id"], "reply": "awaiting_confirm"}, True
        if a["kind"] == "saved_import":   # only the one you asked for: the hourly ones are quiet
            r = a.get("result") or {}
            new = (r.get("added") or 0) + (r.get("promoted") or 0)
            seen = max((r.get("known") or 0) - (r.get("promoted") or 0), 0)
            return ("📥 *Vagas salvas*: " + (f"{new} nova(s) no CareerOps, a caminho da lista para aprovar" if new else "nenhuma nova")
                    + (f"; {seen} já estava(m) lá" if seen else "")
                    + (f"; {r['no_text']} sem texto do anúncio, tento na próxima" if r.get("no_text") else "") + "."), {"action_id": a["id"]}, False
        if a["kind"] == "comment":
            return f"💬 Comentário publicado no post de {(a.get('payload') or {}).get('author') or title}.", {"action_id": a["id"]}, False
        return f"✅ *Candidatura enviada* · {a.get('job_title') or title} · {a.get('company') or ''}", {"action_id": a["id"]}, False

    @staticmethod
    def _proposals_digest() -> int:
        fresh = _rows("SELECT id FROM public.automation_actions WHERE status = 'proposed' AND notified_status IS DISTINCT FROM 'proposed' LIMIT 1")
        if not fresh:
            return 0
        minutes = int(_cfg().get("digest_minutes", 30))
        if _one("SELECT 1 AS y FROM public.bot_notifications WHERE kind = 'proposals' AND created_at > NOW() - make_interval(mins => %s)", (minutes,)):
            return 0
        items = _rows("""UPDATE public.automation_actions SET notified_status = 'proposed'
                          WHERE status = 'proposed' AND notified_status IS DISTINCT FROM 'proposed' RETURNING id, kind""")
        ids = [i["id"] for i in items]
        kinds = [k for k in KIND_LABEL if any(i["kind"] == k for i in items)]
        # a long list reads better one subject at a time: one message per kind, each with the list filtered to it
        if len(ids) <= int(_cfg().get("split_over", 8)) or len(kinds) < 2:
            text, shown = BotService.inbox(ids, header=f"🗂️ *Para aprovar* ({len(ids)} nova(s))")
            return bool(BotService.notify("proposals", text, {"ids": shown, "reply": "list"}))
        made = 0
        for kind in kinds:
            group = [i["id"] for i in items if i["kind"] == kind]
            text, shown = BotService.inbox(group, header=f"🗂️ *Para aprovar · {KIND_LABEL[kind]}* ({len(group)} nova(s))", kind=kind)
            made += bool(BotService.notify("proposals", text, {"ids": shown, "kind": kind, "reply": "list"}))
        return made

    # ── Texts for the bot's answers ──────────────────────────────────────
    @staticmethod
    def approval_link(kind: Optional[str] = None) -> str:
        """The approval list in the app, filtered to one kind when given."""
        return f"{settings.CAREEROPS_APP_URL.rstrip('/')}/automacao?tab=aprovar" + (f"&tipo={kind}" if kind else "")

    @staticmethod
    def _eligibility_tag(r: dict) -> str:
        """The same warning as in Vagas: red when the ad requires it, yellow when it is soft or unclear."""
        if r.get("eligibility_status") not in ("blocked", "warning"):
            return ""
        names = {"residency": "residência", "work_authorization": "visto"}
        kinds = list(dict.fromkeys(names.get(i.get("type"), i.get("type")) for i in r.get("eligibility_issues") or [] if isinstance(i, dict)))
        return f"{'🔴' if r['eligibility_status'] == 'blocked' else '🟡'} {' + '.join(kinds) or 'elegibilidade'}"

    @staticmethod
    def inbox_text(ids: Optional[List[int]] = None, header: str = "🗂️ *Para aprovar*", limit: int = 25, kind: Optional[str] = None) -> str:
        return BotService.inbox(ids, header, limit, kind)[0]

    @staticmethod
    def inbox(ids: Optional[List[int]] = None, header: str = "🗂️ *Para aprovar*", limit: int = 25,
              kind: Optional[str] = None) -> Tuple[str, List[int]]:
        """The list to approve, numbered 1, 2, 3… and the ids in that order: a reply “ok 1 3” is about those lines."""
        where = "a.id = ANY(%s)" if ids is not None else "TRUE"
        rows = _rows(f"""
            SELECT a.*, j.triage_score, j.triage_reason, j.posted_at, j.easy_apply, j.company, j.job_title, j.location, j.salary_flag,
                   j.eligibility_status, j.eligibility_issues
              FROM public.automation_actions a LEFT JOIN public.job_listings j ON a.target_type = 'job' AND j.id = a.target_id
             WHERE a.status = 'proposed' AND {where} ORDER BY a.kind, a.rank, a.sort_at DESC""", (ids,) if ids is not None else ())
        if not rows:
            return "Nada esperando aprovação agora.", []
        lines, order = [header], []
        shown = 0
        several = len({r["kind"] for r in rows}) > 1
        for k, label in KIND_LABEL.items():
            group = [r for r in rows if r["kind"] == k]
            if not group:
                continue
            if several:
                lines.append(f"\n*{label}*")
            for r in group:
                if shown >= limit:
                    break
                shown += 1
                order.append(r["id"])
                n = f"*{shown}.*"
                p = r.get("payload") or {}
                fit = AutomationService.fit_of(r)
                fit = f"fit {fit}" if fit is not None else ""
                if k == "apply":
                    bits = [fit, BotService._eligibility_tag(r), "Easy Apply" if r.get("easy_apply") else "",
                            _ago(r.get("posted_at")), "⚠️ salário abaixo do piso" if r.get("salary_flag") else ""]
                    lines.append(f"{n} {r.get('job_title') or p.get('title')} · {r.get('company') or p.get('company') or ''} — "
                                 + ", ".join(b for b in bits if b))
                    if r.get("triage_reason"):
                        lines.append(f"   ↳ {_short(r['triage_reason'], 160)}")
                elif k == "comment":
                    lines.append(f"{n} no post de {p.get('author') or r.get('title')}{f' ({fit})' if fit else ''}: “{_short(p.get('text'), 600)}”")
                    lines.append(f"   ↳ {r.get('target_url')}")
                elif k == "connect":
                    lines.append(f"{n} {p.get('name') or r.get('title')} — {_short(p.get('headline'), 90)}{f' · {fit}' if fit else ''}")
                else:
                    lines.append(f"{n} {p.get('name') or r.get('title')}" + (f" — {_short(p.get('why'), 90)}" if p.get("why") else ""))
        if len(rows) > shown:
            lines.append(f"\n…e mais {len(rows) - shown} na lista abaixo.")
        lines.append(f"\n🔎 Lista com detalhes: {BotService.approval_link(kind)}")
        lines.append("Responda a esta mensagem: “ok” aprova todas (vai no horário, 8h–20h), “ok 1 3” só essas, “ok agora” executa já, "
                     "“não 2” rejeita a 2, “não” rejeita todas.")
        return "\n".join(lines), order

    @staticmethod
    def overview_text() -> str:
        st = AutomationService.status()
        state = st.get("state") or {}
        mode = {"off": "desligada", "dry_run": "em ensaio (para antes do último clique)", "live": "ligada"}.get(state.get("mode"), state.get("mode"))
        lines = [f"🤖 *Automação*: {mode} · conta {'principal' if state.get('account_kind') == 'main' else 'de teste'}"]
        if state.get("halted_at"):
            lines.append(f"⏹ Parada: {state.get('halted_reason')}")
        counts = st.get("counts") or {}
        labels = [("proposed", "para aprovar"), ("needs_user", "precisam de você"), ("review_docs", "CVs para revisar"),
                  ("awaiting_confirm", "esperando confirmação"), ("queued", "na fila"), ("running_ext", "em execução")]
        lines.append(" · ".join(f"{counts[k]} {l}" for k, l in labels if counts.get(k)) or "Nada pendente.")
        used = [f"{l['kind']} {l['used']}/{l['limit']}" for l in st.get("limits") or [] if l["kind"] in ("apply", "comment", "connect", "follow")]
        if used:
            lines.append("Hoje: " + ", ".join(used))
        return "\n".join(lines)

    # ── Notices from the e-mail reading ──────────────────────────────────
    @staticmethod
    def email_notice(event_id: int, classification: str, alert: Optional[str], halted: bool, reading: dict, job: Optional[dict],
                     m: dict, feedback: List[dict], archived: bool = False, status_change: Optional[tuple] = None,
                     confidence: float = 1.0) -> None:
        where = f"{job.get('job_title') or ''} · {job.get('company') or ''}" if job else (m.get("sender") or "")[:80]
        summary = reading.get("summary") or m.get("subject") or ""
        icon = {"interview": "📅 *Entrevista*", "offer": "🎉 *Proposta*", "assessment": "📝 *Teste ou case*",
                "recruiter_question": "❓ *Recrutador perguntou*", "rejection": "✖️ *Não seguiram*"}.get(classification)
        if classification == "linkedin_alert":
            if alert == "verification_code":
                text = "🔑 Chegou um código de verificação do LinkedIn. Se foi você entrando no navegador do servidor, está no seu e-mail."
            else:
                text = f"⚠️ *Aviso do LinkedIn por e-mail*: {summary}" + (
                    "\nParei a automação no LinkedIn e baixei um degrau. Só volta quando você disser “religar automação”." if halted else "")
            BotService.notify("linkedin_alert", text, {"event_id": event_id, "alert_kind": alert}, urgent=alert in ("restriction", "unusual_activity"),
                              key=f"email:{event_id}")
            return
        if not icon:
            return
        lines = [f"{icon}: {where}", summary, BotService._status_line(classification, job, status_change, confidence)]
        if classification == "recruiter_question":
            lines.append("Eu não respondo e-mails de recrutador por você: a resposta é sua.")
        if classification in ("interview", "offer", "assessment", "recruiter_question"):
            lines.append("O e-mail ficou na sua caixa de entrada, não lido.")
        elif archived:
            lines.append("Li e arquivei o e-mail.")
        for f in feedback:
            lines.append(f"💡 Feedback ({'CV' if f['target'] == 'cv' else 'você'} · {f['theme']}): {f['suggestion']}")
        if feedback:
            lines.append("Guardei em Sugestões, agrupado por tema, para avaliarmos juntos depois.")
        BotService.notify(f"email_{classification}", "\n".join(l for l in lines if l), {"event_id": event_id, "job_id": (job or {}).get("id")},
                          urgent=classification in ("interview", "offer"), key=f"email:{event_id}")

    @staticmethod
    def _status_line(classification: str, job: Optional[dict], change: Optional[tuple], confidence: float) -> str:
        """What happened to the job in the system, or why nothing did."""
        if classification not in ("rejection", "interview", "offer"):
            return ""
        if change:
            return f"📌 Vaga atualizada: {STATUS_LABEL.get(change[0], change[0])} → *{STATUS_LABEL.get(change[1], change[1])}*."
        if not job:
            return "📌 Não achei a vaga no sistema: nenhum status mudou (está em Automação → Respostas para você associar)."
        if not (config().get("email") or {}).get("auto_status"):
            return f"📌 A vaga continua como {STATUS_LABEL.get(job.get('status'), job.get('status'))}: a atualização automática está desligada."
        if classification == "rejection" and confidence < float((config().get("email") or {}).get("rejection_confidence", 0.9)):
            return f"📌 Não tenho certeza de que é uma recusa: a vaga continua como {STATUS_LABEL.get(job.get('status'), job.get('status'))} (confira em Respostas)."
        return f"📌 A vaga já estava como {STATUS_LABEL.get(job.get('status'), job.get('status'))}."

    # ── A post you sent to be commented ──────────────────────────────────
    @staticmethod
    async def comment_link(url: str, suggestion: str = "", post_text: str = "", author: str = "", angle: Optional[str] = None) -> dict:
        """You sent a post: a comment is drafted (following your suggestion, if any) and waits for your OK, like any other."""
        from app.services.linkedin_copilot_service import LinkedInCopilotService as Copilot
        url = normalize_post_url(url)
        suggestion, post_text, author = (suggestion or "").strip(), (post_text or "").strip(), (author or "").strip()
        read_from = "você" if post_text else ""
        if not post_text:
            page = fetch_public_post(url)
            post_text, author = page.get("text") or "", author or page.get("author") or ""
            read_from = "página pública" if post_text else ""
        if not post_text and not suggestion:
            return {"ok": False, "need": "post_text",
                    "detail": "Não consegui ler o post sem login. Mande o texto do post (ou um print) ou a sua ideia do comentário."}
        existing = _one("""SELECT a.* FROM public.automation_actions a JOIN public.linkedin_engagement e ON a.idempotency_key = 'comment:' || e.id
                            WHERE e.post_url = %s""", (url,))
        if existing and existing["status"] == "done":
            return {"ok": False, "detail": f"Você já comentou neste post (#{existing['id']})."}
        if existing and existing["status"] not in ("proposed", "rejected", "expired", "cancelled", "discarded"):
            return {"ok": False, "detail": f"Este post já tem um comentário em andamento (#{existing['id']}, {existing['status']})."}
        engagement = await Copilot.add_engagement(post_text or f"(texto do post não disponível; link: {url})", url, author or None,
                                                  instruction=suggestion or "O Paulo escolheu este post para comentar.", regenerate=True,
                                                  angle=angle)
        text = (engagement.get("comment_draft") or "").strip()
        if not text:
            return {"ok": False, "detail": "A IA não devolveu um comentário. Tente de novo ou mande a sua ideia."}
        # post_head stays empty: the server browser checks the page against it, and a pasted text may not match the page
        payload = {"post_url": url, "post_head": "", "post_full": (post_text or "")[:6000], "author": author or engagement.get("author_name"), "text": text,
                   "relevance": engagement.get("relevance"), "reason": engagement.get("reason"), "source": "lolo",
                   "variants": engagement.get("comment_variants") or {}}
        if existing:
            action = _one("""UPDATE public.automation_actions
                                SET status = 'proposed', payload = %s, payload_hash = %s, notified_status = 'proposed', error_code = NULL,
                                    error_text = NULL, finished_at = NULL, approved_at = NULL, expires_at = NULL, updated_at = NOW()
                              WHERE id = %s RETURNING *""", (Json(payload), payload_hash(payload), existing["id"]))
        else:
            action = AutomationService.create_action("comment", f"comment:{engagement['id']}", payload["author"] or "Post", url, payload,
                                                     target_type="engagement", target_id=engagement["id"], rank=5)
            _rows("UPDATE public.automation_actions SET notified_status = 'proposed' WHERE id = %s", (action["id"],))
        return {"ok": True, "action_id": action["id"], "text": text, "author": payload["author"], "post_excerpt": _short(post_text, 300),
                "read_from": read_from or "só a sua sugestão (o texto do post não abriu sem login)",
                "mode": AutomationService.state().get("mode")}

    # ── Suggestions from the e-mails ─────────────────────────────────────
    @staticmethod
    def suggestions(status: str = "new") -> List[dict]:
        """Grouped by who they are for (the CV or you) and theme, the most repeated first."""
        return _rows("""
            SELECT target, theme, COUNT(*) AS n,
                   json_agg(json_build_object('id', id, 'company', company, 'suggestion', suggestion, 'evidence', evidence_quote,
                                              'job_id', job_id, 'created_at', created_at) ORDER BY created_at DESC) AS items
              FROM public.improvement_suggestions WHERE status = %s
             GROUP BY target, theme ORDER BY n DESC, target, theme""", (status,))

    @staticmethod
    def set_suggestion(suggestion_id: int, status: str) -> Optional[dict]:
        return _one("""UPDATE public.improvement_suggestions SET status = %s, decided_at = CASE WHEN %s = 'new' THEN NULL ELSE NOW() END
                        WHERE id = %s RETURNING *""", (status, status, suggestion_id))

    @staticmethod
    def suggestions_text() -> str:
        groups = BotService.suggestions()
        if not groups:
            return "Nenhum feedback de recrutador guardado ainda."
        lines = ["💡 *Sugestões vindas dos e-mails* (agrupadas por tema)"]
        for g in groups:
            lines.append(f"\n*{'CV' if g['target'] == 'cv' else 'Você'} · {g['theme']}* ({g['n']})")
            lines += [f"• {i['company']}: {_short(i['suggestion'], 200)}" for i in g["items"][:5]]
        return "\n".join(lines)
