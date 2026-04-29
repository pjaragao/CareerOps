import sys
import os

# Adiciona o diretório atual ao path para importar db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# override config for local run
import config
config.DB_HOST = "localhost"
config.DB_PORT = 54322  # Bypassing pooler to talk directly to Postgres
config.DB_USER = "postgres"
config.DB_PASSWORD = "n8n_supabase_pass" # from .env

from db import run_migration

if __name__ == "__main__":
    print("Running migration on port 54322...")
    run_migration()
    print("Migration finished.")
