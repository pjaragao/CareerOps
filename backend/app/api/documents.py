from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from typing import List, Optional, Dict, Any
from app.services.document_service import DocumentService
from pydantic import BaseModel

router = APIRouter(tags=["documents"])

class ValidationRequest(BaseModel):
    validated_data: Dict[str, Any]

class BulkValidationRequest(BaseModel):
    doc_ids: List[int]
    merged_data: Dict[str, Any]

@router.post("/bulk-validate")
async def validate_bulk(req: BulkValidationRequest):
    success = await DocumentService.validate_bulk(req.doc_ids, req.merged_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to validate documents in bulk")
    return {"ok": True}

@router.post("/consolidate")
async def consolidate(doc_ids: List[int] = Body(...)):
    return await DocumentService.consolidate_documents(doc_ids)

@router.post("/process-bulk")
async def process_bulk(doc_ids: List[int] = Body(...)):
    await DocumentService.process_bulk(doc_ids)
    return {"ok": True}

@router.get("")
async def list_documents():
    return DocumentService.get_documents()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    doc_id = await DocumentService.upload_document(file.filename, content, file.content_type)
    if not doc_id:
        raise HTTPException(status_code=500, detail="Failed to upload document")
    return {"id": doc_id, "status": "processing"}

@router.get("/{doc_id}")
async def get_document(doc_id: int):
    doc = DocumentService.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/{doc_id}/validate")
async def validate_document(doc_id: int, req: ValidationRequest):
    success = await DocumentService.validate_document(doc_id, req.validated_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to validate document")
    return {"ok": True}

@router.delete("/{doc_id}")
async def delete_document(doc_id: int):
    success = DocumentService.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document")
    return {"ok": True}

@router.post("/optimize-resume")
async def optimize_resume():
    return await DocumentService.optimize_resume_base()

@router.post("/aggregate")
async def aggregate_knowledge():
    await DocumentService.aggregate_knowledge()
    return {"ok": True}
