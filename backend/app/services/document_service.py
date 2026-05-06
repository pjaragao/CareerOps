import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from markitdown import MarkItDown
from app.db.session import get_db_connection, get_db_cursor
from app.services.skill_service import SkillService
from app.services.profile_service import ProfileService
from app.core.config import settings

class DocumentService:
    @staticmethod
    def get_documents() -> List[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT id, filename, content_type, processing_status, extracted_data, created_at, last_processed_at FROM public.user_documents ORDER BY created_at DESC")
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_document(doc_id: int) -> Optional[dict]:
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT * FROM public.user_documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    async def upload_document(filename: str, content: bytes, content_type: str) -> int:
        # 1. Save to database with 'pending' status
        conn = get_db_connection()
        doc_id = None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.user_documents (filename, content_type, processing_status)
                    VALUES (%s, %s, 'pending')
                    RETURNING id
                """, (filename, content_type))
                doc_id = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        if not doc_id:
            return None

        # 2. Save file to disk for later processing
        upload_dir = os.path.join(settings.PROJECT_DIR, "backend/app/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc_id}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        return doc_id

    @staticmethod
    async def process_document(doc_id: int, content: bytes = None):
        """Converts file to Markdown and triggers AI extraction."""
        conn = get_db_connection()
        try:
            # 1. Get content from disk if not provided
            if content is None:
                upload_dir = os.path.join(settings.PROJECT_DIR, "backend/app/uploads")
                file_path = os.path.join(upload_dir, f"{doc_id}")
                if not os.path.exists(file_path):
                    print(f"File not found for doc {doc_id}")
                    return
                with open(file_path, "rb") as f:
                    content = f.read()

            with conn.cursor() as cur:
                cur.execute("UPDATE public.user_documents SET processing_status = 'processing' WHERE id = %s", (doc_id,))
            conn.commit()

            # 2. Parse with MarkItDown
            # Save temporary file for markitdown to read
            temp_path = f"/tmp/doc_{doc_id}_{datetime.now().timestamp()}"
            with open(temp_path, "wb") as f:
                f.write(content)
            
            try:
                md = MarkItDown()
                result = md.convert(temp_path)
                raw_text = result.text_content
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            # 3. Trigger AI extraction
            current_profile = ProfileService.get_profile()
            extraction = await SkillService.run_skill(
                "onboarding/process_document.md",
                {
                    "raw_text": raw_text,
                    "current_profile": current_profile
                }
            )

            # 4. Update DB with extracted data and 'awaiting_validation' status
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.user_documents 
                    SET raw_text = %s, extracted_data = %s, processing_status = 'awaiting_validation', last_processed_at = NOW() 
                    WHERE id = %s
                """, (raw_text, json.dumps(extraction), doc_id))
            conn.commit()

        except Exception as e:
            print(f"Error processing document {doc_id}: {e}")
            with conn.cursor() as cur:
                cur.execute("UPDATE public.user_documents SET processing_status = 'failed' WHERE id = %s", (doc_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    async def validate_document(doc_id: int, validated_data: dict) -> bool:
        """Saves user-approved data and updates the global knowledge base."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.user_documents 
                    SET validated_data = %s, processing_status = 'validated' 
                    WHERE id = %s
                """, (json.dumps(validated_data), doc_id))
            conn.commit()
            
            # Extract raw cases to interview_stories
            if "star_cases" in validated_data:
                from app.services.interview_service import InterviewService
                for case in validated_data["star_cases"]:
                    # Save as raw case
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO public.interview_stories (title, situation, task, action, result, is_raw, source_doc_id, updated_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s, NOW())
                        """, (
                            case.get("title", "Raw Experience"),
                            case.get("situation", ""),
                            case.get("task", ""),
                            case.get("action", ""),
                            case.get("result", ""),
                            doc_id
                        ))
                conn.commit()

            # Trigger aggregation
            await DocumentService.aggregate_knowledge()
            return True
        finally:
            conn.close()

    @staticmethod
    async def consolidate_documents(doc_ids: List[int]) -> dict:
        """Consolidates multiple documents into a single knowledge base using AI."""
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT extracted_data FROM public.user_documents WHERE id = ANY(%s)", (doc_ids,))
                rows = cur.fetchall()
                all_data = [row['extracted_data'] for row in rows if row['extracted_data']]

            if not all_data:
                return {}

            # Get current profile for context
            from app.services.profile_service import ProfileService
            profile = ProfileService.get_profile()
            
            # Use consolidate_review skill to merge intelligently
            from app.services.skill_service import SkillService
            result = await SkillService.run_skill(
                "knowledge/consolidate_review.md",
                {
                    "current_profile": profile,
                    "new_data": all_data
                }
            )
            return result
        finally:
            conn.close()

    @staticmethod
    async def validate_bulk(doc_ids: List[int], merged_data: dict) -> bool:
        """Validates multiple documents at once and updates the knowledge base."""
        conn = get_db_connection()
        try:
            # Mark all documents as validated
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.user_documents 
                    SET processing_status = 'validated', validated_data = %s
                    WHERE id = ANY(%s)
                """, (json.dumps(merged_data), doc_ids))
            conn.commit()

            # Save STAR cases
            if "star_cases" in merged_data:
                for case in merged_data["star_cases"]:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO public.interview_stories (title, situation, task, action, result, is_raw, source_doc_id, updated_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, %s, NOW())
                        """, (
                            case.get("title", "Bulk Experience"),
                            case.get("situation", ""),
                            case.get("task", ""),
                            case.get("action", ""),
                            case.get("result", ""),
                            doc_ids[0]
                        ))
                conn.commit()

            await DocumentService.aggregate_knowledge()
            return True
        except Exception as e:
            print(f"Error in bulk validation: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    async def aggregate_knowledge():
        """Aggregates all validated data into a single Markdown file for prompt injection."""
        conn = get_db_connection()
        try:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT validated_data FROM public.user_documents WHERE processing_status = 'validated'")
                all_data = [row['validated_data'] for row in cur.fetchall()]
            
            if not all_data:
                # Create empty file
                knowledge_path = os.path.join(settings.PROJECT_DIR, "backend/app/skills/knowledge/user_data.md")
                os.makedirs(os.path.dirname(knowledge_path), exist_ok=True)
                with open(knowledge_path, "w") as f:
                    f.write("<!-- No validated knowledge available -->")
                return

            # Use AI to compile a clean knowledge base
            result = await SkillService.run_skill(
                "knowledge/compile_knowledge.md",
                {"all_validated_data": all_data},
                response_format="text"
            )

            # Save to skills directory for Jinja2 inclusion
            knowledge_path = os.path.join(settings.PROJECT_DIR, "backend/app/skills/knowledge/user_data.md")
            os.makedirs(os.path.dirname(knowledge_path), exist_ok=True)
            with open(knowledge_path, "w", encoding="utf-8") as f:
                f.write(result)

        finally:
            conn.close()

    @staticmethod
    def delete_document(doc_id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.user_documents WHERE id = %s", (doc_id,))
            conn.commit()
            # Note: Cascade delete handles interview_stories.
            # We should probably trigger aggregation again to remove this doc's data.
            asyncio.create_task(DocumentService.aggregate_knowledge())
            return True
        except Exception:
            return False
        finally:
            conn.close()

    @staticmethod
    async def optimize_resume_base() -> Dict[str, Any]:
        """Suggests improvements to resume_base.md using the Knowledge Base."""
        resume_content = ProfileService.get_resume_base()
        
        # Load Knowledge Base content
        knowledge_path = os.path.join(settings.PROJECT_DIR, "backend/app/skills/knowledge/user_data.md")
        knowledge = ""
        if os.path.exists(knowledge_path):
            with open(knowledge_path, "r", encoding="utf-8") as f:
                knowledge = f.read()

        if not knowledge:
            return {"error": "No validated knowledge base found. Please process and validate documents first."}

        result = await SkillService.run_skill(
            "onboarding/update_resume.md",
            {
                "current_resume": resume_content,
                "knowledge_base": knowledge
            }
        )
        return result

    @staticmethod
    async def process_bulk(doc_ids: List[int]):
        """Triggers processing for multiple documents."""
        for doc_id in doc_ids:
            # Trigger each as a separate task
            asyncio.create_task(DocumentService.process_document(doc_id))
        return True
