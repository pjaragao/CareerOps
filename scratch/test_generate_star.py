import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.interview_service import InterviewService
from app.services.settings_service import SettingsService

async def test_generate():
    print("Testing generate_star_case...")
    description = "implementação sharpoint on prems 2010, com diversas listas para controle, gerenciamento de arquivos com versionamento. controle de ativos, controle de contratos, controle oficios e mais listas para gestão interna da empresa"
    
    try:
        result = await InterviewService.generate_star_case(description)
        print("Result:", result)
    except Exception as e:
        print("Error caught in test script:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_generate())
