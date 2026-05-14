# 🧠 AI Context Engine (Deep Context)

O "Deep Context" é o coração da inteligência do CareerOps. Ele garante que cada interação da IA (seja otimizando um perfil, preparando para uma entrevista ou avaliando uma vaga) seja fundamentada em conquistas reais e métricas validadas, e não apenas em dados superficiais.

## 🏗️ Arquitetura de Dados

O fluxo de contexto segue um pipeline de consolidação:

1.  **Ingestão de Evidências**: O usuário faz o upload de documentos (Currículos, Portfólios, Descrições de Projetos).
2.  **Extração de Fatos**: A IA extrai conquistas no formato **STAR** (Situation, Task, Action, Result).
3.  **Validação**: O usuário revisa e aprova esses fatos no repositório de documentos.
4.  **Agregação de Conhecimento**: O `DocumentService.aggregate_knowledge()` consolida todos os dados validados em um único arquivo: `backend/app/skills/knowledge/user_data.md`.
5.  **Injeção de Contexto**: O arquivo `backend/app/skills/common/user_context.md` inclui o `user_data.md`. Qualquer Skill que precise de profundidade deve incluir o `user_context.md`.

---

## 🛠️ Regras de Ambiente e Runtime

Para que o Deep Context funcione corretamente, as seguintes regras de ambiente devem ser seguidas:

### 1. Persistência e Volumes (Docker)
O diretório `backend/app/skills/knowledge/` deve ter permissões de escrita para o usuário que executa o backend (root no container). No `docker-compose.yml`, o volume deve mapear corretamente `./backend/app:/app/app` para que o arquivo `user_data.md` persistido no container também seja visível no host.

### 2. Sincronização de Cache
O arquivo `user_data.md` funciona como um **Cache de Conhecimento Ativo**. 
- **Gatilho**: Sempre que um documento for validado ou um STAR case for editado manualmente, a função `aggregate_knowledge` deve ser chamada.
- **Fail-safe**: O template Jinja2 deve usar `{% include '...' ignore missing %}` para evitar erros de renderização caso a base de conhecimento ainda não tenha sido gerada.

### 3. Limites de Contexto (LLM)
Ao usar o Deep Context, o prompt enviado à IA aumenta significativamente.
- **Ambiente de Produção**: Recomenda-se o uso de modelos com janelas de contexto de pelo menos 128k (ex: Gemini 1.5 Flash/Pro) para evitar truncamento de experiências passadas.

---

## 🌊 Como Adicionar Contexto a um Novo Workflow

Ao criar uma nova Skill em `backend/app/skills/`, siga este padrão para garantir consistência:

```markdown
# [Instruções da Skill]

{% include 'common/critical_rules.md' %}
{% include 'common/language_rules.md' %}

# Dados do Candidato:
{{ profile_summary }}

# Base de Conhecimento (Deep Context):
{% include 'common/user_context.md' %}

# Instrução Específica:
...
```

---

## 📈 Benefícios da Unificação

| Recurso | Sem Deep Context | Com Deep Context |
| :--- | :--- | :--- |
| **Headline** | Baseada apenas no cargo atual. | Baseada em resultados (ex: "Redução de 25% em custos"). |
| **Outreach** | Mensagens genéricas. | Mensagens que citam projetos reais do portfólio. |
| **Job Evaluation** | Match de palavras-chave. | Match de experiência técnica real. |

---

> [!TIP]
> **Manutenção**: Periodicamente, limpe STAR cases obsoletos ou duplicados diretamente no banco de dados para manter o `user_data.md` denso e relevante.
