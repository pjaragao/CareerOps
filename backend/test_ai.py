import asyncio
from app.services.profile_service import ProfileService

async def main():
    text = """
    NAME: John Doe
    HEADLINE: Software Engineer
    ABOUT: Olá, eu sou engenheiro de software.
    EXPERIENCE: 
    Company A
    Software Engineer
    2020 - Present
    Eu construí muitas coisas.
    
    Company A
    Software Engineer
    2020 - Present
    I built many things.
    
    EDUCATION:
    University B
    BSc Computer Science
    2015 - 2019
    SKILLS: Python, React
    FULL_PAGE_DUMP: ...
    """
    res = await ProfileService.import_profile_ai(text)
    import json
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
