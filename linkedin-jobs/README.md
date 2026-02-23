# 🔗 LinkedIn Job Scraper

Aplicação que automatiza a coleta de vagas salvas no LinkedIn, extrai informações detalhadas (descrição, empresa, equipe de contratação) e gera currículos customizados via IA — tudo com uma interface web para gerenciamento.

## 📋 Visão Geral

```
LinkedIn (Saved Jobs)
        │
        ▼
   ┌─────────┐     ┌────────────┐     ┌──────────────┐     ┌────────────┐
   │ Scraper  │ ──▶ │ Processor  │ ──▶ │  Generator   │ ──▶ │  PDF (out)  │
   │(Playwright)│   │(Desc+Empresa)│   │(Gemini AI)   │     │(Gotenberg)  │
   └─────────┘     └────────────┘     └──────────────┘     └────────────┘
        │                │                    │
        └────────────────┴────────────────────┘
                         │
                    PostgreSQL
                    (Supabase)
```

### Pipeline

| Etapa | Descrição |
|-------|-----------|
| **Scrape** | Acessa o LinkedIn via Playwright, coleta vagas salvas (título, empresa, localização, Easy Apply) |
| **Process** | Abre cada vaga individualmente, extrai descrição completa, informações da empresa e equipe de contratação |
| **Generate** | Envia a descrição + currículo base para o Gemini AI, que gera um currículo customizado para a vaga |
| **PDF** | Converte o currículo gerado em PDF via Gotenberg |

## ⚙️ Pré-requisitos

- **Python 3.10+**
- **Docker** (para Supabase e Gotenberg)
- **Conta LinkedIn** (com vagas salvas)
- **API Key do Google Gemini**

## 🚀 Instalação

### 1. Clonar e instalar dependências

```bash
cd linkedin-jobs
pip install -r requirements.txt
playwright install chromium
```

### 2. Configurar variáveis de ambiente

Copie o arquivo de exemplo e preencha com suas credenciais:

```bash
cp .env.example .env
```

Edite o `.env`:

```env
# PostgreSQL (Supabase local)
SUPABASE_DB_HOST=localhost
SUPABASE_DB_PORT=54322
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=sua-senha-aqui

# Google Gemini API
GEMINI_API_KEY=sua-api-key-aqui

# Gotenberg (conversão HTML → PDF)
GOTENBERG_URL=http://localhost:3001

# LinkedIn
LINKEDIN_EMAIL=seu-email@example.com

# Configurações
OUTPUT_DIR=./output
SCRAPE_DELAY=4
MAX_JOBS=20
```

### 3. Subir os serviços Docker

```bash
# Gotenberg (gerador de PDF)
docker compose up -d

# Supabase (banco de dados) — na pasta ../supabase
cd ../supabase && docker compose up -d
```

### 4. Criar as tabelas

```bash
python main.py migrate
```

### 5. Login no LinkedIn

```bash
python main.py login
```

> Isso abre um navegador visível para você fazer login. A sessão é salva em `auth/` para uso futuro.

## 💻 Comandos CLI

```bash
# Login no LinkedIn (abre navegador)
python main.py login

# Coletar vagas salvas do LinkedIn
python main.py scrape [--max-jobs 20]

# Processar vagas novas (extrair descrições e dados da empresa)
python main.py process [--delay 4]

# Gerar currículos customizados (Gemini AI → PDF)
python main.py generate

# Pipeline completo (scrape → process → generate)
python main.py run [--max-jobs 20] [--delay 4]

# Executar migração SQL
python main.py migrate

# Ver status das vagas no banco
python main.py status
```

## 🌐 Interface Web

```bash
python web.py
```

Acesse **http://localhost:5050** — a interface permite:

- 📊 **Dashboard** com estatísticas das vagas (novas, processadas, prontas, erros)
- 🔍 **Filtros** por status (Todos, Novos, Processados, Prontos, Erros)
- 📄 **Detalhes expandidos** de cada vaga:
  - Descrição completa da vaga
  - Informações sobre a empresa (com link para o perfil)
  - Equipe de contratação (com links para os perfis dos recrutadores)
- ⬇️ **Download** dos PDFs gerados
- 🚀 **Botões de ação** para executar scrape, process e generate diretamente pela UI
- 🗑️ **Gerenciamento** de vagas (remover individual ou limpar tudo)

## 📁 Estrutura do Projeto

```
linkedin-jobs/
├── main.py                 # CLI principal
├── web.py                  # Interface Web (Flask)
├── scraper.py              # Scraper do LinkedIn (Playwright)
├── processor.py            # Processamento de vagas
├── db.py                   # Operações no banco (PostgreSQL)
├── resume_generator.py     # Gerador de currículo (Gemini AI)
├── resume_template.py      # Template HTML do currículo
├── resume_base.md          # Currículo base do candidato
├── prompt_template.md      # Prompt para o Gemini
├── config.py               # Carregamento de configurações
├── migration.sql           # Schema do banco de dados
├── update_db.py            # Script de migração incremental
├── requirements.txt        # Dependências Python
├── docker-compose.yml      # Docker (Gotenberg)
├── .env.example            # Exemplo de variáveis de ambiente
├── auth/                   # Sessão do LinkedIn (gitignored)
└── output/                 # PDFs gerados (gitignored)
```

## 🔧 Tecnologias

| Tecnologia | Uso |
|------------|-----|
| **Playwright** | Automação de browser para scraping do LinkedIn |
| **PostgreSQL** | Banco de dados via Supabase local |
| **Google Gemini** | IA generativa para customização de currículos |
| **Gotenberg** | Conversão HTML → PDF |
| **Flask** | Interface web para gerenciamento |
