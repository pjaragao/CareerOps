"""
Resume Generator — uses AI provider (Gemini, NVIDIA, Alibaba, Ollama) to create
customized resumes, then converts to PDF via Gotenberg.
"""
import json
import re
import requests
from datetime import datetime, timezone

from ai_provider import get_provider, get_provider_info, get_available_models
from config import GOTENBERG_URL, OUTPUT_DIR, RESUME_BASE_FILE, PROMPT_FILE, load_profile
import db
from resume_template import markdown_to_html, wrap_in_template


def _load_file(path) -> str:
    """Load a text file and return its contents."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _build_prompt(job: dict, profile: dict = None) -> str:
    """
    Build the AI prompt by loading prompt_template.md and resume_base.md
    and filling in the job details. Includes user profile context.
    """
    prompt_template = _load_file(PROMPT_FILE)
    resume_base = _load_file(RESUME_BASE_FILE)

    profile_context = ""
    if profile:
        personal = profile.get("personal", {})
        target_roles = profile.get("target_roles", [])
        skills = profile.get("skills", {})
        superpower = profile.get("superpower", "")
        proof_points = profile.get("proof_points", [])

        profile_context = f"""
# USER PROFILE CONTEXT

## Personal
Name: {personal.get('full_name', '')}
Location: {personal.get('location', '')}

## Target Roles
{', '.join(target_roles) if target_roles else 'Not specified'}

## Skills
Technical: {', '.join(skills.get('technical', []))}
Soft: {', '.join(skills.get('soft', []))}

## Superpower
{superpower}

## Proof Points
"""
        for pp in proof_points:
            profile_context += f"- {pp.get('title', '')}: {pp.get('description', '')} ({pp.get('metrics', '')})\n"

    return prompt_template.format(
        job_title=job.get("job_title", "Job Opportunity"),
        company=job.get("company", "Direct Hiring"),
        language=job.get("language", "en"),
        company_description=job.get("company_description", "Not available."),
        description=job.get("description", "")[:15000],
        resume_base=resume_base,
    ) + profile_context


def _call_ai(prompt: str, model_name: str = None) -> str:
    """
    Call AI provider and return the resume markdown.
    """
    provider = get_provider()
    response = provider.generate_json(prompt, model=model_name, temperature=0.7)

    if "resume_markdown" in response:
        return response["resume_markdown"]
    if "raw_text" in response:
        return response["raw_text"]
    if "error" in response:
        return f"Error: {response['error']}"

    return json.dumps(response)


def _convert_to_pdf(html: str) -> bytes:
    """
    Send HTML to Gotenberg and get PDF bytes back.
    """
    url = f"{GOTENBERG_URL}/forms/chromium/convert/html"

    files = {
        "index.html": ("index.html", html.encode("utf-8"), "text/html"),
    }

    response = requests.post(url, files=files, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gotenberg error {response.status_code}: {response.text[:500]}"
        )

    return response.content


def _safe_filename(text: str, max_len: int = 30) -> str:
    """Create a filesystem-safe string from text."""
    clean = re.sub(r'[^a-zA-Z0-9]', '_', text)
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean[:max_len]


def get_available_ai_models() -> dict:
    """Fetch available models from all AI providers."""
    return get_available_models()


def get_ai_provider_info() -> dict:
    """Get current AI provider configuration."""
    return get_provider_info()


def generate_resumes(job_ids: list[int] = None, model_name: str = None):
    """
    Generate customized resumes for jobs.
    Pipeline: AI → HTML → Gotenberg PDF → save file.
    """
    if job_ids:
        jobs = db.get_jobs_by_ids(job_ids)
    else:
        jobs = db.get_jobs_by_status("scraped")

    if not jobs:
        print("\n✅ No scraped jobs to generate resumes for.")
        return

    profile = load_profile()
    provider_info = get_provider_info()
    print(f"\n📝 Generating resumes for {len(jobs)} jobs...")
    print(f"   Provider: {provider_info['provider']} | Model: {provider_info['model']}")

    for i, job in enumerate(jobs, 1):
        title = job.get("job_title", "Unknown")
        company = job.get("company", "Unknown")
        print(f"\n   [{i}/{len(jobs)}] {title} @ {company}")

        try:
            print(f"   🤖 Calling AI ({provider_info['provider']}/{provider_info['model']})...")
            prompt = _build_prompt(job, profile)
            resume_md = _call_ai(prompt, model_name)

            if not resume_md or len(resume_md) < 100 or resume_md.startswith("Error:"):
                print(f"   ⚠️  AI response too short or error ({len(resume_md)} chars)")
                db.update_job_status(job["id"], "error")
                continue

            print("   🎨 Converting to HTML...")
            html_content = markdown_to_html(resume_md)
            full_html = wrap_in_template(html_content)

            print("   📄 Generating PDF via Gotenberg...")
            pdf_bytes = _convert_to_pdf(full_html)

            date_str = datetime.now().strftime("%Y%m%d")
            file_name = (
                f"{_safe_filename(company)}_{_safe_filename(title)}_{date_str}.pdf"
            )
            pdf_path = OUTPUT_DIR / file_name
            pdf_path.write_bytes(pdf_bytes)

            db.update_job_status(
                job["id"], "done",
                file_name=file_name,
                generated_at=datetime.now(timezone.utc),
            )

            print(f"   ✅ Saved: {pdf_path}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"   ❌ Error: {e}")
            db.update_job_status(job["id"], "error")

    print("\n✅ Resume generation complete.")


def generate_cover_letters(job_ids: list[int] = None, model_name: str = None):
    """
    Generate customized cover letters for jobs and save to DB.
    """
    if job_ids:
        jobs = db.get_jobs_by_ids(job_ids)
    else:
        jobs = db.get_jobs_by_status("scraped")

    if not jobs:
        print("\n✅ No jobs to generate cover letters for.")
        return

    profile = load_profile()
    provider = get_provider()
    provider_info = get_provider_info()
    resume_base = _load_file(RESUME_BASE_FILE)

    print(f"\n📝 Generating cover letters for {len(jobs)} jobs...")
    print(f"   Provider: {provider_info['provider']} | Model: {provider_info['model']}")

    for i, job in enumerate(jobs, 1):
        title = job.get("job_title", "Unknown")
        company = job.get("company", "Unknown")
        print(f"\n   [{i}/{len(jobs)}] {title} @ {company}")

        try:
            profile_context = ""
            if profile:
                personal = profile.get("personal", {})
                profile_context = f"\n## Candidate Info\nName: {personal.get('full_name', '')}\nLocation: {personal.get('location', '')}\n"

            prompt = f"""
Baseado no currículo fornecido abaixo, escreva uma carta de apresentação (Cover Letter) profissional em {job.get('language', 'en')} para a vaga intitulada '{title}' na empresa '{company}'.
A carta deve ser persuasiva, destacar as qualificações mais relevantes do currículo para a vaga baseando-se na descrição da vaga abaixo, e ser formatada de maneira limpa.
NÃO use formatação markdown como asteriscos ou blocos de código. Apenas texto limpo, pronto para copiar.
{profile_context}

DESCRIÇÃO DA VAGA:
{job.get('description', '')[:5000]}

MEU CURRÍCULO BASE:
{resume_base}
"""
            print(f"   🤖 Calling AI ({provider_info['provider']}) for Cover Letter...")
            cover_letter_text = provider.generate_text(prompt, model=model_name, temperature=0.7)

            if not cover_letter_text or cover_letter_text.startswith("Error:"):
                print(f"   ⚠️  AI response empty or error")
                continue

            db.update_job_status(
                job["id"], job["status"],
                cover_letter=cover_letter_text
            )

            print(f"   ✅ Cover Letter saved to DB.")

        except Exception as e:
            print(f"   ❌ Error generating cover letter: {e}")

    print("\n✅ Cover Letter generation complete.")


def chat_with_job(job: dict, question: str, orientation: str, tone: str = "semi-formal", model_name: str = None) -> str:
    """
    Generate an answer to an employer's question using the job context and candidate's resume/cover letter.
    """
    provider = get_provider()
    resume_base = _load_file(RESUME_BASE_FILE)
    profile = load_profile()

    profile_context = ""
    if profile:
        personal = profile.get("personal", {})
        superpower = profile.get("superpower", "")
        profile_context = f"""
## Candidate Profile
Name: {personal.get('full_name', '')}
Superpower: {superpower}
"""

    if tone == "informal":
        tone_instruction = "Tom: Informal, leve, direto, amigável (um pouco menos formal)."
    elif tone == "formal":
        tone_instruction = "Tom: Muito formal, estritamente profissional e polido."
    else:
        tone_instruction = "Tom: Semi-formal, equilibrado, profissional mas acessível."

    prompt = f"""Você é um assistente especialista em ajudar o candidato a responder perguntas de formulários de emprego.
Por favor, responda a pergunta do empregador abaixo com base no currículo, na carta de apresentação e nas orientações do candidato.
Siga rigidamente as instruções de Tom abaixo ao construir sua resposta.
{tone_instruction}
Idioma obrigatório: {job.get('language', 'en')}.
Apenas forneça a resposta final, sem introduções adicionais.
{profile_context}

VAGA: {job.get('job_title')} na empresa {job.get('company')}

DESCRIÇÃO DA VAGA:
{job.get('description', '')[:3000]}

CURRÍCULO BASE DO CANDIDATO:
{resume_base[:3000]}

CARTA DE APRESENTAÇÃO DO CANDIDATO:
{job.get('cover_letter', 'Nenhuma carta de apresentação fornecida.')}

ORIENTAÇÃO DO CANDIDATO:
{orientation}

PERGUNTA DO EMPREGADOR:
{question}
"""
    try:
        return provider.generate_text(prompt, model=model_name, temperature=0.7)
    except Exception as e:
        return f"Error connecting to AI provider: {str(e)}"
