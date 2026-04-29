import os
import json
import re
from ai_provider import get_provider, get_provider_info

LINKEDIN_LIMITS = """
## Limites Reais do LinkedIn (2024)
| Campo                  | Limite         |
|------------------------|----------------|
| Headline (Título)      | 220 caracteres |
| About (Sobre)          | 2.600 caracteres |
| Experience: title      | 100 caracteres |
| Experience: description| 2.000 caracteres por cargo |
| Skill name             | 80 caracteres  |
| Skills total           | até 100 skills |
"""

GUIDELINES = """
## Eixo 1: Otimização do Perfil
- **Títulos (Headline)**: Fórmula "Promessa + Resultado + Nicho Técnico". Máx 220 chars. Ex: "AI Solutions Architect & Digital Transformation Lead | Agentic AI, LLM Orchestration | Scaling Operations through Vibe Coding".
- **Sobre (About)**: Máx 2.600 chars. Funil de conversão, primeira pessoa. Gancho impactante nos primeiros 275 chars (visível sem clicar "ver mais" no mobile). Foco em ROI. Evitar jargões genéricos.
- **Experiência**: Máx 2.000 chars por cargo. Framework C-A-R. Métricas quantificáveis. Citar ferramentas modernas (n8n, LLM APIs, Vibe Coding, RAG).
- **Skills**: Máx 80 chars cada, até 100. Criar "fossos semânticos": para "Agentes de IA" incluir RAG, Orquestração, Bancos Vetoriais, Webhooks.

## Eixo 2: SSI (Social Selling Index)
- Comentários > 15 palavras com substância técnica.
- Artigos longos, newsletters, carrosséis PDF de alta densidade.
- Notas personalizadas < 200 chars citando insights do destinatário.

## Eixo 3: Entrevistas
- Vibe Coding: orquestração, leitura de código, depuração, testes E2E, janela de contexto.
- STAR: Situação, Tarefa, Ação técnica, Resultado quantificado.
- Agentic AI Design: ReAct, supervisão hierárquica, memória episódica/semântica, sandboxing.
"""

def _clean_ai_output(text: str) -> str:
    """Remove conversational filler, labels, and common AI chatter."""
    if not text: return ""
    text = re.sub(r'```[a-z]*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    text = text.replace("**", "").replace("*", "")
    intro_patterns = [
        r"as an expert.*?, i've redesigned.*?:",
        r"here is the updated.*?:",
        r"i have rewritten.*?:",
        r"rewritten about section:"
    ]
    for pattern in intro_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    lines = text.split('\n')
    filtered = []
    for line in lines:
        l = line.strip().lower()
        if not l:
            continue
        if any(token in l for token in ["tamanho:", "chars:", "opção:", "option:", "here is", "re-written", "about section", "redesigned your"]):
            continue
        if re.match(r'^[\-\=\*\_]{3,}$', l):
            continue
        if re.match(r'^\d+[\.\)]\s*$', line.strip()):
            continue
        cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
        if cleaned_line:
            filtered.append(cleaned_line)
    
    return "\n".join(filtered).strip()

def _call_ai(prompt: str, model_name: str = None, is_json: bool = False) -> str:
    """Call AI provider (any provider: Gemini, NVIDIA, Alibaba, Ollama)."""
    try:
        provider = get_provider()
        if is_json:
            result = provider.generate_json(prompt, model=model_name)
            return json.dumps(result)
        else:
            result = provider.generate_text(prompt, model=model_name)
            return _clean_ai_output(result)
    except Exception as e:
        print(f"Error calling AI provider: {e}")
        return f"Error calling AI provider: {str(e)}"

import profile_prompts

def analyze_profile(resume_md: str, model_name: str = None) -> str:
    system_prompt = profile_prompts.get_prompt("analyze")
    prompt = f"{system_prompt}\n\nPerfil Atual:\n{resume_md}"
    return _call_ai(prompt, model_name)

def get_profile_score(profile_data_md: str, model_name: str = None) -> dict:
    """Returns a numeric score and reason for the profile."""
    system_prompt = profile_prompts.get_prompt("score")
    prompt = f"{system_prompt}\n\nPerfil:\n{profile_data_md}"
    
    raw = _call_ai(prompt, model_name, is_json=True)
    
    try:
        clean_json = re.sub(r'```json\n?(.*?)\n?```', r'\1', raw, flags=re.DOTALL).strip()
        data = json.loads(clean_json)
        return {
            "score": int(data.get("score", 0)),
            "reason": str(data.get("reason", "Nenhuma justificativa fornecida."))
        }
    except Exception as e:
        print(f"JSON Parse Error for score: {e} | Raw: {raw[:200]}")
        return {"score": 0, "reason": f"Erro ao processar score"}

def optimize_headline(resume_md: str, model_name: str = None) -> str:
    system_prompt = profile_prompts.get_prompt("headline")
    prompt = f"{system_prompt}\n\nContexto do usuário:\n{resume_md}"
    return _call_ai(prompt, model_name)

def optimize_about(resume_md: str, model_name: str = None) -> str:
    system_prompt = profile_prompts.get_prompt("about")
    prompt = f"{system_prompt}\n\nCurrículo base:\n{resume_md}"
    return _call_ai(prompt, model_name)

def rewrite_experience_car(experience_text: str, model_name: str = None) -> str:
    system_prompt = profile_prompts.get_prompt("experience")
    prompt = f"{system_prompt}\n\nExperiências:\n{experience_text}"
    return _call_ai(prompt, model_name)

def generate_ssi_plan(profile_summary: str, model_name: str = None) -> str:
    prompt = f"""
Crie um plano de ação semanal de Social Selling Index (SSI) para este perfil.
O plano deve incluir 3 ideias de posts (artigos/carrosséis) de alto valor técnico sobre IA e automação, e estratégias de comentário/networking.

Perfil:
{profile_summary}
"""
    return _call_ai(prompt, model_name)
