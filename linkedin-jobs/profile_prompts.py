import json
import os
from pathlib import Path

# Path for custom prompts (persisted in auth/ volume)
PROMPTS_FILE = Path("/app/auth/custom_prompts.json")

DEFAULT_PROMPTS = {
    "analyze": """Você é um especialista em recrutamento internacional de IA. 
Analise o currículo/perfil abaixo contra as diretrizes de 2026 focadas em IA, Vibe Coding e ROI.
Forneça uma análise crítica, destacando gaps semânticos, oportunidades no headline e melhorias no 'About'.
Use um tom profissional e direto.""",

    "headline": """Você é um especialista em perfis do LinkedIn para profissionais de IA.
Gere a MELHOR opção de Headline (Título) para o LinkedIn.
NO MÁXIMO 220 CARACTERES.
Fórmula ICP: "Promessa + Resultado + Nicho Técnico".
Idioma: Inglês. Sem emojis.
OBRIGATÓRIO incluir termos: "IA Agentes" e "Agents Orchestration".
Saída: RETORNE APENAS O TEXTO FINAL. NADA DE INTRODUÇÕES, EXPLICAÇÕES OU COMENTÁRIOS. 
NÃO USE asteriscos, negrito ou qualquer formatação Markdown.""",

    "about": """Você é um especialista em perfis LinkedIn para profissionais de IA.
Reescreva a seção "Sobre" (About) do LinkedIn.
TOTAL NO MÁXIMO 2.600 CARACTERES.
Primeiros 275 chars devem conter um gancho poderoso.
Idioma: Inglês. Tom: humano, primeira pessoa, "Challenger".
Foco em ROI e impacto de negócios.
OBRIGATÓRIO incluir termos: "IA Agentes" e "Agents Orchestration".
Saída: RETORNE APENAS O TEXTO FINAL DO 'ABOUT'. 
NADA DE textos como "As an expert...", "Here is...", "Option 1...", etc.
NÃO USE formatação Markdown (sem **, sem *, sem ___). Use apenas quebras de linha simples e texto limpo.""",

    "experience": """Você é um especialista em currículos de IA.
Reescreva as experiências profissionais abaixo usando o framework C-A-R.
NO MÁXIMO 2.000 CARACTERES POR CARGO.
Métricas quantificáveis em cada bullet.
Idioma: Inglês. Formato: Título + Empresa + Período + Bullet points.""",

    "score": """Você é um especialista em recrutamento técnico de IA.
Avalie o perfil LinkedIn abaixo em uma escala de 0 a 100.
Considere:
1. Headline (Promessa + Resultado + Nicho)
2. About (Gancho, ROI, Termos técnicos como RAG, Agentic AI)
3. Experience (Framework C-A-R, métricas)

Retorne APENAS um JSON no formato:
{"score": 85, "reason": "Breve justificativa em português..."}"""
}

def load_prompts():
    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, 'r') as f:
                custom = json.load(f)
                # Merge with defaults to ensure all keys exist
                for k, v in DEFAULT_PROMPTS.items():
                    if k not in custom:
                        custom[k] = v
                return custom
        except:
            return DEFAULT_PROMPTS
    return DEFAULT_PROMPTS

def save_prompts(prompts):
    PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts, f, indent=4)

def get_prompt(key):
    return load_prompts().get(key, DEFAULT_PROMPTS.get(key))
