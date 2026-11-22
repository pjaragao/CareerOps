"""/aprovar: the page that approves jobs from the phone with the link Lolo sends (ApprovalLinkService). The only path published on
the internet. The token comes in the link (?t=), the page moves it out of the address bar and sends it as X-Approval-Token."""
import secrets
import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services.approval_link_service import ApprovalLinkService

router = APIRouter()

# failed tokens: past this in 10 minutes, wrong tokens get 429 for a while (a valid one still works)
_BAD = deque(maxlen=200)
BAD_LIMIT = 40


def _link(token: Optional[str]) -> dict:
    t = time.monotonic()
    row = ApprovalLinkService.check(token)
    if row:
        return row
    _BAD.append(t)
    recent = sum(1 for x in _BAD if t - x < 600)
    if recent > BAD_LIMIT:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Espere alguns minutos.")
    raise HTTPException(status_code=401, detail="Link expirado ou revogado. Peça um novo ao Lolo (“link de aprovação”).")


def _headers(nonce: str = "") -> dict:
    return {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; "
                                       f"img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"}


@router.get("/aprovar", response_class=HTMLResponse, include_in_schema=False)
async def page():
    nonce = secrets.token_urlsafe(16)
    return HTMLResponse(PAGE.replace("__NONCE__", nonce), headers=_headers(nonce))


@router.get("/aprovar/api/jobs", include_in_schema=False)
async def jobs(x_approval_token: Optional[str] = Header(None)):
    link = _link(x_approval_token)
    return {"items": ApprovalLinkService.jobs(), "expires_at": link["expires_at"]}


@router.post("/aprovar/api/jobs/{action_id}/approve", include_in_schema=False)
async def approve(action_id: int, x_approval_token: Optional[str] = Header(None)):
    link = _link(x_approval_token)
    try:
        done = ApprovalLinkService.approve(action_id, link["id"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not done:
        raise HTTPException(status_code=409, detail="Essa vaga já saiu da lista")
    return {"ok": True, "status": done["status"]}


@router.post("/aprovar/api/jobs/{action_id}/reject", include_in_schema=False)
async def reject(action_id: int, x_approval_token: Optional[str] = Header(None)):
    link = _link(x_approval_token)
    if not ApprovalLinkService.reject(action_id, link["id"]):
        raise HTTPException(status_code=409, detail="Essa vaga já saiu da lista")
    return {"ok": True}


class AboveIn(BaseModel):
    min_score: int = Field(85, ge=70, le=100)


@router.post("/aprovar/api/approve-above", include_in_schema=False)
async def approve_above(req: AboveIn, x_approval_token: Optional[str] = Header(None)):
    link = _link(x_approval_token)
    return {"approved": ApprovalLinkService.approve_above(req.min_score, link["id"])}


async def public_guard(request: Request, call_next):
    """A request that came through the Tailscale Funnel (from the internet) reaches /aprovar and nothing else."""
    if request.headers.get("tailscale-funnel-request") and not (request.url.path == "/aprovar" or request.url.path.startswith("/aprovar/")):
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not found", status_code=404)
    return await call_next(request)


PAGE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<title>Vagas para aprovar</title>
<style>
:root { --bg:#f6f7f9; --card:#fff; --text:#16181d; --muted:#5d6470; --line:#e3e6ea; --accent:#1f6feb; --ok:#1a7f37; --warn:#9a6700; --bad:#cf222e; --chip:#eef1f5; }
@media (prefers-color-scheme: dark) { :root { --bg:#0e1116; --card:#161b22; --text:#e6edf3; --muted:#9198a1; --line:#2a313b; --accent:#4493f8; --ok:#3fb950; --warn:#d29922; --bad:#f85149; --chip:#21262d; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
header { position:sticky; top:0; z-index:2; background:var(--bg); padding:14px 16px 10px; border-bottom:1px solid var(--line); }
h1 { font-size:18px; margin:0 0 2px; }
.sub { color:var(--muted); font-size:13px; }
.bar { display:flex; gap:6px; overflow-x:auto; padding:10px 0 2px; scrollbar-width:none; }
.chip { flex:0 0 auto; border:1px solid var(--line); background:var(--chip); color:var(--text); border-radius:999px; padding:5px 11px; font-size:13px; }
.chip.on { background:var(--accent); border-color:var(--accent); color:#fff; }
main { padding:12px 16px 90px; max-width:720px; margin:0 auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; margin-bottom:12px; transition:opacity .25s; }
.card.gone { opacity:.35; }
.top { display:flex; gap:10px; align-items:flex-start; }
.score { flex:0 0 auto; min-width:42px; text-align:center; border-radius:8px; padding:4px 6px; font-weight:700; font-size:15px; color:#fff; background:var(--muted); }
.title { font-weight:600; font-size:16px; margin:0; }
.meta { color:var(--muted); font-size:13px; margin-top:2px; }
.src { display:inline-block; font-size:11px; padding:1px 7px; border-radius:999px; background:var(--chip); border:1px solid var(--line); color:var(--muted); margin-left:4px; vertical-align:1px; }
.reason { margin:10px 0 0; font-size:14px; }
.flag { margin-top:8px; font-size:13px; color:var(--warn); }
details { margin-top:8px; font-size:13px; color:var(--muted); }
details p { white-space:pre-line; margin:6px 0 0; }
.links { margin-top:8px; font-size:13px; }
.links a { color:var(--accent); }
.actions { display:flex; gap:8px; margin-top:12px; }
button { font:inherit; border-radius:10px; padding:11px 14px; border:1px solid var(--line); background:var(--card); color:var(--text); }
button.yes { flex:1; background:var(--ok); border-color:var(--ok); color:#fff; font-weight:600; }
button.no { flex:0 0 auto; }
button:disabled { opacity:.5; }
.bulk { position:fixed; left:0; right:0; bottom:0; padding:10px 16px calc(10px + env(safe-area-inset-bottom)); background:var(--bg); border-top:1px solid var(--line); }
.bulk button { width:100%; max-width:720px; display:block; margin:0 auto; }
.msg { text-align:center; color:var(--muted); padding:40px 10px; }
.toast { position:fixed; left:50%; bottom:80px; transform:translateX(-50%); background:var(--text); color:var(--bg); padding:8px 14px; border-radius:8px; font-size:14px; opacity:0; transition:opacity .2s; pointer-events:none; }
.toast.show { opacity:.92; }
</style>
</head>
<body>
<header>
  <h1>Vagas para aprovar</h1>
  <div class="sub" id="sub">Carregando…</div>
  <div class="bar" id="bar"></div>
</header>
<main id="list"><div class="msg">Carregando…</div></main>
<div class="bulk" id="bulk" hidden><button id="bulkBtn"></button></div>
<div class="toast" id="toast"></div>
<script nonce="__NONCE__">
(function () {
  var KEY = "careerops-approval-token";
  var params = new URLSearchParams(location.search);
  var token = params.get("t");
  try {
    if (token) { sessionStorage.setItem(KEY, token); localStorage.setItem(KEY, token); }
    else { token = sessionStorage.getItem(KEY) || localStorage.getItem(KEY); }
  } catch (e) {}
  if (params.has("t")) { history.replaceState(null, "", location.pathname); }
  var items = [], filter = "", busy = false;
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]; }); }
  function toast(t) { var el = $("toast"); el.textContent = t; el.classList.add("show"); setTimeout(function () { el.classList.remove("show"); }, 1800); }
  function ago(iso) {
    if (!iso) return "";
    var h = Math.round((Date.now() - new Date(iso).getTime()) / 3600000);
    return h < 1 ? "agora" : h < 48 ? "há " + h + " h" : "há " + Math.round(h / 24) + " dias";
  }
  function color(s) { return s >= 85 ? "var(--ok)" : s >= 70 ? "var(--accent)" : "var(--muted)"; }
  function safeUrl(u) { return /^https:\/\//i.test(u || "") ? u : ""; }
  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({"X-Approval-Token": token || "", "Content-Type": "application/json"}, opts.headers || {});
    return fetch("/aprovar/api" + path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (b) { if (!r.ok) throw new Error(b.detail || ("Erro " + r.status)); return b; });
    });
  }
  function visible() { return items.filter(function (i) { return !i._done && (!filter || i.source_label === filter); }); }
  function render() {
    var left = items.filter(function (i) { return !i._done; });
    $("sub").textContent = left.length ? left.length + (left.length === 1 ? " vaga esperando" : " vagas esperando") + " · nota e data" : "Nada esperando aprovação.";
    var counts = {};
    left.forEach(function (i) { counts[i.source_label] = (counts[i.source_label] || 0) + 1; });
    var chips = ['<button class="chip' + (filter ? "" : " on") + '" data-f="">Todas (' + left.length + ")</button>"];
    Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).forEach(function (k) {
      chips.push('<button class="chip' + (filter === k ? " on" : "") + '" data-f="' + esc(k) + '">' + esc(k) + " (" + counts[k] + ")</button>");
    });
    $("bar").innerHTML = left.length ? chips.join("") : "";
    var list = visible();
    $("list").innerHTML = list.length ? list.map(function (i) {
      var s = i.triage_score;
      var link = safeUrl(i.url), form = safeUrl(i.apply_url);
      return '<article class="card" id="c' + i.id + '">' +
        '<div class="top"><div class="score" style="background:' + color(s || 0) + '">' + (s == null ? "–" : s) + "</div><div>" +
        '<p class="title">' + esc(i.job_title) + "</p>" +
        '<div class="meta">' + esc(i.company) + '<span class="src">' + esc(i.source_label) + "</span></div>" +
        '<div class="meta">' + esc([i.location, ago(i.posted_at), i.easy_apply ? "Easy Apply" : ""].filter(Boolean).join(" · ")) + "</div>" +
        "</div></div>" +
        (i.triage_reason ? '<p class="reason">' + esc(i.triage_reason) + "</p>" : "") +
        (i.salary_flag ? '<div class="flag">⚠️ ' + esc(i.salary_flag) + "</div>" : "") +
        (i.eligibility_status === "warning" ? '<div class="flag">🟡 O anúncio pode exigir residência ou visto</div>' : "") +
        (i.excerpt ? "<details><summary>Trecho do anúncio</summary><p>" + esc(i.excerpt) + "…</p></details>" : "") +
        '<div class="links">' + (link ? '<a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">Abrir anúncio</a>' : "") +
        (form && form !== link ? ' · <a href="' + esc(form) + '" target="_blank" rel="noopener noreferrer">Formulário</a>' : "") + "</div>" +
        '<div class="actions"><button class="yes" data-a="approve" data-id="' + i.id + '">Aprovar</button>' +
        '<button class="no" data-a="reject" data-id="' + i.id + '">Descartar</button></div></article>';
    }).join("") : '<div class="msg">' + (left.length ? "Nenhuma vaga desta fonte." : "Tudo decidido por agora. 🎉") + "</div>";
    var top = left.filter(function (i) { return (i.triage_score || 0) >= 85; }).length;
    $("bulk").hidden = !top;
    $("bulkBtn").textContent = "Aprovar todas com nota ≥ 85 (" + top + ")";
  }
  function decide(id, action) {
    if (busy) return;
    var card = $("c" + id), item = items.find(function (i) { return i.id === id; });
    card.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
    api("/jobs/" + id + "/" + action, {method: "POST"}).then(function () {
      item._done = true; card.classList.add("gone");
      toast(action === "approve" ? "Aprovada ✓" : "Descartada");
      setTimeout(render, 300);
    }).catch(function (e) {
      toast(e.message); card.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
      if (/saiu da lista/.test(e.message)) { item._done = true; setTimeout(render, 600); }
    });
  }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.f !== undefined) { filter = b.dataset.f; render(); window.scrollTo(0, 0); return; }
    if (b.dataset.a) { decide(Number(b.dataset.id), b.dataset.a); return; }
    if (b.id === "bulkBtn") {
      var n = items.filter(function (i) { return !i._done && (i.triage_score || 0) >= 85; }).length;
      if (!confirm("Aprovar as " + n + " vagas com nota 85 ou mais?")) return;
      busy = true; b.disabled = true;
      api("/approve-above", {method: "POST", body: JSON.stringify({min_score: 85})}).then(function (r) {
        var ok = {}; (r.approved || []).forEach(function (id) { ok[id] = true; });
        items.forEach(function (i) { if (ok[i.id]) i._done = true; });
        toast((r.approved || []).length + " aprovadas ✓"); busy = false; b.disabled = false; render();
      }).catch(function (e) { toast(e.message); busy = false; b.disabled = false; });
    }
  });
  if (!token) { $("sub").textContent = ""; $("list").innerHTML = '<div class="msg">Abra pelo link que o Lolo mandou.</div>'; return; }
  api("/jobs").then(function (r) { items = r.items || []; render(); })
    .catch(function (e) { $("sub").textContent = ""; $("list").innerHTML = '<div class="msg">' + esc(e.message) + "</div>"; });
})();
</script>
</body>
</html>
"""
