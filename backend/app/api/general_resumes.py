import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.general_resume_service import GeneralResumeService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/general-resumes", tags=["general-resumes"])


class ResumeIn(BaseModel):
    title: Optional[str] = None
    lang: Optional[str] = None
    target_title: Optional[str] = None
    used_on: Optional[str] = None
    content_md: Optional[str] = None


def _found(resume):
    if not resume:
        raise HTTPException(status_code=404, detail="CV não encontrado")
    return resume


async def _ai(call):
    try:
        return await call
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("")
async def list_resumes():
    return {"resumes": GeneralResumeService.list()}


@router.post("")
async def create_resume(data: ResumeIn):
    return GeneralResumeService.create(data.model_dump())


@router.get("/{resume_id}")
async def get_resume(resume_id: int):
    return _found(GeneralResumeService.get(resume_id))


@router.put("/{resume_id}")
async def update_resume(resume_id: int, data: ResumeIn):
    return _found(GeneralResumeService.update(resume_id, data.model_dump(exclude_none=True)))


@router.delete("/{resume_id}")
async def delete_resume(resume_id: int):
    if not GeneralResumeService.delete(resume_id):
        raise HTTPException(status_code=404, detail="CV não encontrado")
    return {"ok": True}


@router.post("/{resume_id}/review")
async def review_resume(resume_id: int):
    return await _ai(GeneralResumeService.review(resume_id))


@router.post("/{resume_id}/improve")
async def improve_resume(resume_id: int):
    return await _ai(GeneralResumeService.improve(resume_id))


@router.post("/{resume_id}/form-suggestions")
async def form_suggestions(resume_id: int):
    return await _ai(GeneralResumeService.form_suggestions(resume_id))


@router.get("/{resume_id}/pdf")
async def resume_pdf(resume_id: int):
    resume = _found(GeneralResumeService.get(resume_id))
    if not (resume.get("content_md") or "").strip():
        raise HTTPException(status_code=400, detail="o CV está vazio")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", resume.get("target_title") or resume["title"]).strip("_") or "resume"
    pdf = PDFService.generate_pdf(resume["content_md"], f"{name}.pdf")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Resume_{name}.pdf"'})
