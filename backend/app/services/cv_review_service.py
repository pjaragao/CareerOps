"""The reviewer that reads the CV and the cover letter before they go, in your place.

First what needs no AI: a forbidden term, a placeholder, an empty document, a PDF over two pages, and the ATS form of the
resume (contact line, real phone, links that are links, plain characters, standard headings, one date style, a readable text layer). Then a recruiter AI compares
both documents with the job and with your real history (the base resume and the knowledge base). Anything critical or major
sends the document back to be redone with the reviewer's instructions, up to cv_review_rounds times. If it still fails, the
application waits for you with the reviewer's reasons: nothing questionable goes out on its own."""
import logging
import re
from typing import List, Optional

from app.services import content_guard
from app.services.automation_service import _one, config
from app.services.skill_service import SkillService

log = logging.getLogger("cv_review")

# "[Company Name]", "[Candidate Name]", "[Seu nome]"... but not a markdown link "[text](url)"
PLACEHOLDER = re.compile(r"\[[^\]\n]{0,40}\b(company|empresa|nome|name|cargo|role|position|title|manager|data|date|address|endere[cç]o|phone|telefone)"
                         r"\b[^\]\n]{0,40}\](?!\()|\bTODO\b|lorem ipsum|\bX{2,}\b|<\s*insert|\{\{|\}\}|as an ai\b|como (uma )?ia\b", re.I)
BLOCKING = ("critical", "major")
MAX_PAGES = 2
REDO = ("A reviewer rejected the previous version of this document. Start from that version (below) and fix exactly what the "
        "reviewer asked; keep everything else as it is, so nothing that was right breaks now:\n")


def _job(job_id: int) -> dict:
    return _one("SELECT * FROM public.job_listings WHERE id = %s", (job_id,)) or {}


def render_pdf(markdown: str, name: str = "resume.pdf") -> Optional[bytes]:
    from app.services.pdf_service import PDFService
    try:
        return PDFService.generate_pdf(markdown, name)
    except Exception as e:
        log.info("pdf not rendered for review: %s", e)
        return None


def pdf_pages(markdown: str, name: str = "resume.pdf", pdf: Optional[bytes] = None) -> Optional[int]:
    """The resume as the recruiter gets it. None when the PDF could not be made (the AI review still runs)."""
    pdf = pdf or render_pdf(markdown, name)
    return (len(re.findall(rb"/Type\s*/Page(?!s)", pdf)) or None) if pdf else None


# ── ATS form (no AI needed) ──────────────────────────────────────────────────────────────────────────────────────
STANDARD_HEADING = re.compile(
    r"^(professional summary|summary|profile|objective|skills|technical skills|core competencies|key skills|professional experience|"
    r"work experience|experience|employment history|education|education & certifications|education and certifications|certifications|"
    r"languages|projects|publications|"
    r"resumo profissional|resumo|perfil|compet[eê]ncias( t[eé]cnicas)?|experi[eê]ncia profissional|experi[eê]ncia|forma[cç][aã]o( acad[eê]mica)?|"
    r"forma[cç][aã]o e certifica[cç][oõ]es|certifica[cç][oõ]es|idiomas|projetos|publica[cç][oõ]es)$", re.I)
UNSAFE_CHARS = re.compile("[\u2212\u2013\u2014\u2192\u21d2\u2265\u2264\u00d7\u2018\u2019\u201c\u201d\u2026\u00a0\u200b\u2022\u25cf]"
                          "|[\U0001F000-\U0001FAFF\u2600-\u27BF]")
DATE_STYLES = {
    "month-year": re.compile(r"\b(?:jan|feb|fev|mar|apr|abr|may|mai|jun|jul|aug|ago|sep|set|oct|out|nov|dec|dez)[a-z]*\.?\s+\d{4}\b", re.I),
    "numeric-month": re.compile(r"\b\d{1,2}/\d{4}\b"),
    "year-only": re.compile(r"(?<![\w/])(?:19|20)\d{2}\s*-\s*(?:(?:19|20)\d{2}|present|presente|atual|current|now)\b", re.I),
}


def pdf_text(pdf: bytes) -> Optional[tuple]:
    """(text as a parser reads it, link targets in the PDF). None if the PDF cannot be read."""
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        uris = []
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                action = annot.get_object().get("/A")
                if action and action.get("/URI"):
                    uris.append(str(action["/URI"]))
        return text, uris
    except Exception as e:
        log.info("pdf text not read for review: %s", e)
        return None


def ats_issues(resume: str, pdf: Optional[bytes], expect_portfolio: bool) -> List[dict]:
    """The resume as an ATS and a recruiter get it. Each item says what to change, as an instruction to the writer."""
    from app.services import cv_format
    issues = []

    def add(severity: str, problem: str, fix: str):
        issues.append({"doc": "resume", "severity": severity, "problem": f"ATS: {problem}", "fix": fix})

    lines = resume.split("\n")
    idx = cv_format.contact_line_index(lines)
    contact = lines[idx] if idx is not None else ""
    if idx is None:
        add("major", "sem linha de contato com e-mail no topo", "Add one contact line under the title: e-mail | phone | LinkedIn | GitHub, in plain text.")
    else:
        if cv_format.PLACEHOLDER_PHONE_RE.search(contact):
            add("critical", "o telefone é um modelo (00 00000-0000)", "Write the real phone number from the profile, never zeros.")
        elif not re.search(r"\+?\d[\d\s()-]{8,}\d", contact):
            add("major", "a linha de contato não tem telefone", "Add the candidate's phone number to the contact line.")
        for label, rx, key in (("LinkedIn", cv_format.LINKEDIN_RE, "linkedin.com"), ("GitHub", cv_format.GITHUB_RE, "github.com")):
            if not rx.search(contact):
                add("major", f"{label} ausente na linha de contato", f"Add the {label} address to the contact line as a markdown link.")
            elif not re.search(r"\[[^\]]*" + re.escape(key) + r"[^\]]*\]\(https?://", contact, re.I):
                add("major", f"{label} é só texto, não é link clicável", f"Write the {label} address as a markdown link: [text](https://...).")
        if expect_portfolio and not re.search(r"\[[^\]]*portf[^\]]*\]\(https?://", contact, re.I):
            add("major", "o link do portfólio não está na linha de contato", "Add the portfolio link to the contact line as a markdown link whose text says it is the portfolio.")
    unsafe = sorted({c for c in UNSAFE_CHARS.findall(resume)})
    if unsafe:
        add("major", "caracteres que o ATS lê mal: " + " ".join(unsafe[:8]), "Use plain characters only: '-' for dashes and minus, '->' for arrows, straight quotes, '-' for bullets, no emoji or symbols.")
    headings = [h.strip() for h in re.findall(r"^##\s+(.+)$", resume, re.M)]
    odd = [h for h in headings if not STANDARD_HEADING.match(h.strip().strip("*"))]
    if odd:
        add("major", "títulos de seção fora do padrão: " + "; ".join(odd[:4]),
            "Use standard section titles that an ATS recognizes (Professional Summary, Skills, Professional Experience, Education, Languages), one topic per title: never merge Education with Languages or add extra words.")
    if headings and not any(re.search(r"experi[eê]nc|experience|employment", h, re.I) for h in headings):
        add("major", "sem seção de experiência com título padrão", "Add a 'Professional Experience' section.")
    rest, used = resume, []
    for name, rx in DATE_STYLES.items():   # month-year first: its year must not count again as a year-only date
        if rx.search(rest):
            used.append(name)
            rest = rx.sub(" ", rest)
    if len(used) > 1:
        add("major", "estilos de data misturados: " + ", ".join(used), "Write every date as 'Mon YYYY - Mon YYYY' (or 'Mon YYYY - Present'): one style everywhere.")
    if re.search(r"<\s*(table|img|svg)|^\s*\|.*\|.*\|\s*$\n\s*\|[-: |]+\|", resume, re.M):
        add("major", "tabela ou imagem no currículo (o ATS perde o conteúdo)", "Remove tables and images: write the content as plain text and bullets.")
    if pdf:
        got = pdf_text(pdf)
        if got is None or len(got[0].strip()) < 200:
            add("critical", "o PDF não tem texto legível (camada de texto vazia)", "Regenerate the document as selectable text.")
        else:
            text, uris = got
            first = text[:200]
            if "@" not in text[:600]:
                add("major", "o e-mail não aparece no início do texto extraído do PDF", "Keep the contact line directly under the title.")
            if len(text) < 0.6 * len(re.sub(r"[#*`\[\]()]|https?://\S+", "", resume)):
                add("major", "o PDF perde texto na extração (colunas, caixas ou ícones)", "Use a single-column layout with plain text.")
            joined = " ".join(uris).lower()
            for label, key in (("LinkedIn", "linkedin.com"), ("GitHub", "github.com")):
                if key in contact.lower() and key not in joined:
                    add("major", f"o link de {label} não ficou clicável no PDF", f"Write the {label} address as a markdown link.")
            if expect_portfolio and "vercel.app" not in joined:
                add("major", "o link do portfólio não ficou clicável no PDF", "Write the portfolio address as a markdown link.")
    return issues


def quick_issues(resume: str, cover: str, pages: Optional[int]) -> List[dict]:
    issues = []
    for doc, text in (("resume", resume), ("cover", cover)):
        if not (text or "").strip():
            issues.append({"doc": doc, "severity": "critical", "problem": "documento vazio", "fix": "Write the document."})
            continue
        found = content_guard.forbidden_in(text)
        if found:
            issues.append({"doc": doc, "severity": "critical", "problem": f"termo proibido (NDA): {', '.join(found)}",
                           "fix": content_guard.retry_rule(found)})
        leftover = PLACEHOLDER.search(text)
        if leftover:
            issues.append({"doc": doc, "severity": "critical", "problem": f"sobra de modelo: {leftover.group(0)}",
                           "fix": f"Remove '{leftover.group(0)}' and write the real content."})
    if pages and pages > MAX_PAGES:
        # "shorter" alone does not work: the writer gets a size to hit, from how long this version came out
        target = int(len(resume) * MAX_PAGES / pages * 0.9)
        issues.append({"doc": "resume", "severity": "major", "problem": f"o PDF tem {pages} páginas",
                       "fix": f"The resume must fit in {MAX_PAGES} pages. This version has {pages} pages and {len(resume)} characters: write at most "
                              f"{target} characters of markdown. Keep the roles closest to this job in full; older or less related roles get one "
                              f"line each; at most 3 bullets per role; no skill listed twice."})
    return issues


class CvReviewService:
    @staticmethod
    async def review(job_id: int, previous_fixes: str = "") -> dict:
        """previous_fixes: what the last round asked for. A redone version is judged against it, not against a new list."""
        from app.api.actions import get_job_lang
        from app.services.profile_service import ProfileService
        job = _job(job_id)
        resume, cover = job.get("resume_markdown") or "", job.get("cover_letter") or ""
        pdf = render_pdf(resume) if resume.strip() else None
        pages = pdf_pages(resume, pdf=pdf) if resume.strip() else None
        issues = quick_issues(resume, cover, pages)
        if resume.strip():
            issues += ats_issues(resume, pdf, expect_portfolio=bool(job.get("portfolio_token")))
        reading = {}
        if resume.strip() and cover.strip():
            lang = get_job_lang(job)
            reading = await SkillService.run_skill("jobs/cv_review.md", {
                "job_title": job.get("job_title"), "company": job.get("company"), "lang_name": lang,
                "job_description": (job.get("description") or "")[:8000],
                "resume_base": ProfileService.get_resume_base("pt" if lang == "Portuguese" else "en"),
                "resume_markdown": resume, "cover_letter": cover, "pdf_pages": pages, "previous_fixes": previous_fixes})
            if not isinstance(reading, dict):
                raise RuntimeError("o revisor não devolveu uma avaliação")
            issues += [i for i in reading.get("issues") or [] if isinstance(i, dict) and i.get("doc") in ("resume", "cover")]
        # what the candidate lacks (German, years in a field) is no fault of the documents: noted, never redone
        for i in issues:
            if i.get("severity") == "gap":
                i["severity"] = "minor"
                i["gap"] = True
        blocking = [i for i in issues if i.get("severity") in BLOCKING]

        def instructions(doc: str) -> str:
            lines = [f"- {i.get('fix') or i.get('problem')}" for i in blocking if i["doc"] == doc]
            if not lines:   # only the document with a blocking problem is redone
                return ""
            extra = (reading.get(f"{doc}_instructions") or "").strip()
            return "\n".join(lines + ([extra] if extra else []))

        return {"approved": not blocking, "issues": issues, "pages": pages, "summary": reading.get("summary") or "",
                "resume_instructions": instructions("resume"), "cover_instructions": instructions("cover")}

    @staticmethod
    async def run(job_id: int, rounds: Optional[int] = None) -> dict:
        """Review; redo what failed; review again. Returns the last verdict and every round's."""
        from app.api.actions import ActionOptions, generate_cover_letter, generate_resume
        rounds = int((config().get("jobs") or {}).get("cv_review_rounds", 2) if rounds is None else rounds)
        history, asked = [], ""
        for n in range(rounds + 1):
            verdict = await CvReviewService.review(job_id, asked)
            history.append({k: verdict[k] for k in ("approved", "issues", "pages", "summary")})
            if not verdict["approved"] and n == rounds and only_too_long(verdict):
                # the writer could not get it to fit: the reviewer cuts it itself, then reads it once more
                fitted = fit_pages(_job(job_id).get("resume_markdown") or "")
                if fitted:
                    _one("UPDATE public.job_listings SET resume_markdown = %s WHERE id = %s RETURNING id", (fitted, job_id))
                    verdict = await CvReviewService.review(job_id, asked)
                    verdict["trimmed"] = True
                    history.append({k: verdict[k] for k in ("approved", "issues", "pages", "summary")})
            if verdict["approved"] or n == rounds:
                return {**verdict, "rounds": n, "history": history}
            job = _job(job_id)
            resume, cover = job.get("resume_markdown") or "", job.get("cover_letter") or ""
            if verdict["resume_instructions"] or not resume:
                await generate_resume(job_id, ActionOptions(orientation=redo(verdict["resume_instructions"], resume, verdict["pages"])))
            if verdict["cover_instructions"] or not cover:
                await generate_cover_letter(job_id, ActionOptions(orientation=redo(verdict["cover_instructions"], cover)))
            asked = "\n".join(f"{'Resume' if d == 'resume' else 'Cover letter'}:\n{verdict[d + '_instructions']}"
                              for d in ("resume", "cover") if verdict[d + "_instructions"])
        return {**verdict, "rounds": rounds, "history": history}   # not reached


PAGE_WORDS = re.compile(r"p[aá]gina|\bpages?\b|caracteres|characters|too long|longo demais|verbose|condens|length|comprimento", re.I)
HEADING = re.compile(r"^\s*(#{1,6}\s|\*\*[^*]+\*\*\s*(\|.*)?$)")
BULLET = re.compile(r"^\s*[-*+]\s+\S")


def only_too_long(verdict: dict) -> bool:
    """Everything still blocking is the resume being too long: nothing about its content."""
    blocking = [i for i in verdict.get("issues") or [] if i.get("severity") in BLOCKING]
    return bool(blocking) and all(i.get("doc") == "resume" and PAGE_WORDS.search(f"{i.get('problem')} {i.get('fix')}") for i in blocking)


def trim_once(markdown: str) -> Optional[str]:
    """One bullet less: the last bullet of the section with the most bullets (the lower one on a tie, older roles are
    lower). Headings, dates and each section's first bullet always stay. None when there is nothing left to cut."""
    lines = markdown.split("\n")
    sections, current = {}, -1
    for i, line in enumerate(lines):
        if HEADING.match(line):
            current = i
        elif BULLET.match(line):
            sections.setdefault(current, []).append(i)
    cuttable = [(len(b), start, b[-1]) for start, b in sections.items() if len(b) > 1]
    if not cuttable:
        return None
    _, _, last = max(cuttable)
    end = last + 1   # a bullet may wrap onto indented lines below it
    while end < len(lines) and lines[end].startswith((" ", "\t")) and lines[end].strip() and not BULLET.match(lines[end]):
        end += 1
    return "\n".join(lines[:last] + lines[end:])


def fit_pages(markdown: str, pages_of=None, tries: int = 60) -> Optional[str]:
    """Cut bullets one at a time until the PDF fits MAX_PAGES. None when it cannot be made to fit or the PDF is not rendered."""
    pages_of = pages_of or pdf_pages
    for _ in range(tries):
        pages = pages_of(markdown)
        if pages is None:
            return None
        if pages <= MAX_PAGES:
            return markdown
        markdown = trim_once(markdown)
        if markdown is None:
            return None
    return None


def redo(fixes: str, previous: str, pages: Optional[int] = None) -> str:
    """What the writer gets for another version: the fixes, the version they apply to, and (resume) a size that fits."""
    if not previous.strip():
        return fixes
    size = ""
    if pages is not None and pages <= MAX_PAGES:   # it fits now: adding what the reviewer asked must not push it to 3 pages
        size = f"\nIt fits {MAX_PAGES} pages now: the new version stays within {len(previous)} characters; cut something less relevant to add."
    return f"{REDO}{fixes}{size}\n\nPREVIOUS VERSION:\n<<<PREVIOUS\n{previous}\nPREVIOUS>>>"


def reasons(verdict: dict, limit: int = 8) -> str:
    """The reviewer's comment for you, one line per point: what is wrong and what it asked to fix; then its notes."""
    issues = verdict.get("issues") or []
    blocking = [i for i in issues if i.get("severity") in BLOCKING]
    notes = [i for i in issues if i.get("severity") not in BLOCKING]
    doc = lambda i: "CV" if i.get("doc") == "resume" else "Carta"
    lines = [f"• {doc(i)}: {i.get('problem')}" + (f" → {i['fix']}" if i.get("fix") and i.get("fix") != i.get("problem") else "")
             for i in blocking[:limit]]
    lines += [f"◦ {doc(i)} (observação): {i.get('problem')}" for i in notes[:3]]
    if verdict.get("summary"):
        lines.append(f"Resumo do revisor: {verdict['summary']}")
    return "\n".join(lines) or "sem detalhe"
