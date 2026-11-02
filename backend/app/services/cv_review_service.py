"""The reviewer that reads the CV and the cover letter before they go, in your place.

First what needs no AI: a forbidden term, a placeholder, an empty document, a PDF over two pages. Then a recruiter AI compares
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
REDO = ("A reviewer rejected the previous version of this document. Write it again from the base resume, fixing exactly "
        "this and keeping everything else that was right:\n")


def _job(job_id: int) -> dict:
    return _one("SELECT * FROM public.job_listings WHERE id = %s", (job_id,)) or {}


def pdf_pages(markdown: str, name: str = "resume.pdf") -> Optional[int]:
    """The resume as the recruiter gets it. None when the PDF could not be made (the AI review still runs)."""
    from app.services.pdf_service import PDFService
    try:
        pdf = PDFService.generate_pdf(markdown, name)
    except Exception as e:
        log.info("pdf not rendered for review: %s", e)
        return None
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf)) or None


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
    async def review(job_id: int) -> dict:
        from app.api.actions import get_job_lang
        from app.services.profile_service import ProfileService
        job = _job(job_id)
        resume, cover = job.get("resume_markdown") or "", job.get("cover_letter") or ""
        pages = pdf_pages(resume) if resume.strip() else None
        issues = quick_issues(resume, cover, pages)
        reading = {}
        if resume.strip() and cover.strip():
            lang = get_job_lang(job)
            reading = await SkillService.run_skill("jobs/cv_review.md", {
                "job_title": job.get("job_title"), "company": job.get("company"), "lang_name": lang,
                "job_description": (job.get("description") or "")[:8000],
                "resume_base": ProfileService.get_resume_base("pt" if lang == "Portuguese" else "en"),
                "resume_markdown": resume, "cover_letter": cover, "pdf_pages": pages})
            if not isinstance(reading, dict):
                raise RuntimeError("o revisor não devolveu uma avaliação")
            issues += [i for i in reading.get("issues") or [] if isinstance(i, dict) and i.get("doc") in ("resume", "cover")]
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
        history = []
        for n in range(rounds + 1):
            verdict = await CvReviewService.review(job_id)
            history.append({k: verdict[k] for k in ("approved", "issues", "pages", "summary")})
            if verdict["approved"] or n == rounds:
                return {**verdict, "rounds": n, "history": history}
            if verdict["resume_instructions"] or not _job(job_id).get("resume_markdown"):
                await generate_resume(job_id, ActionOptions(orientation=REDO + verdict["resume_instructions"]))
            if verdict["cover_instructions"] or not _job(job_id).get("cover_letter"):
                await generate_cover_letter(job_id, ActionOptions(orientation=REDO + verdict["cover_instructions"]))
        return {**verdict, "rounds": rounds, "history": history}   # not reached


def reasons(verdict: dict, limit: int = 4) -> str:
    """What still fails, in a line or two for you."""
    blocking = [i for i in verdict.get("issues") or [] if i.get("severity") in BLOCKING]
    parts = [f"{'CV' if i['doc'] == 'resume' else 'carta'}: {i.get('problem')}" for i in blocking[:limit]]
    return "; ".join(parts) or verdict.get("summary") or "sem detalhe"
