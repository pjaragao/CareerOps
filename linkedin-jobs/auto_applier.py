"""
Auto Applier — Autonomous job search based on user strategies.
"""
import time
import logging
from playwright.sync_api import sync_playwright
import db
from config import SESSION_FILE

logger = logging.getLogger(__name__)

def search_jobs(keywords: list[str], locations: list[str], remote_only: bool = True, max_results: int = 50):
    """
    Search for jobs on LinkedIn based on keywords and locations.
    Saves new job URLs to pipeline_urls table.
    """
    print(f"\n🔍 Buscando vagas para: {keywords} em {locations}...")
    
    with sync_playwright() as p:
        if not SESSION_FILE.exists():
            print("❌ Sessão do LinkedIn não encontrada. Execute 'python main.py login' primeiro.")
            return []

        # Launch browser (headless for background search)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page = context.new_page()

        found_urls = []
        
        for kw in keywords:
            for loc in locations:
                # Build LinkedIn search URL
                # f_WT=2 is the filter for Remote
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={kw.replace(' ', '%20')}&location={loc.replace(' ', '%20')}"
                if remote_only:
                    search_url += "&f_WT=2"
                
                print(f"   🔎 Pesquisando: '{kw}' em '{loc}'...")
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(5)
                    
                    # Scroll a few times to load results
                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                    
                    # Extract job links
                    # We look for links containing /jobs/view/
                    links = page.query_selector_all('a[href*="/jobs/view/"]')
                    page_urls = []
                    for link in links:
                        href = link.get_attribute("href")
                        if href:
                            # Normalize URL (remove query params)
                            clean_url = href.split("?")[0]
                            if clean_url not in found_urls:
                                found_urls.append(clean_url)
                                page_urls.append(clean_url)
                    
                    print(f"   ✅ Encontradas {len(page_urls)} vagas nesta busca.")
                                
                except Exception as e:
                    print(f"   ⚠️ Erro durante a busca: {e}")
                    continue
        
        # Save new ones to pipeline_urls
        new_count = 0
        for url in found_urls:
            if not db.job_exists(url):
                if db.add_pipeline_url(url, source="auto_applier"):
                    new_count += 1
        
        print(f"\n✨ Busca concluída! {len(found_urls)} totais, {new_count} novas adicionadas à fila de processamento.")
        browser.close()
        return found_urls


def auto_apply_job(job_id: int):
    """
    Tenta realizar a candidatura simplificada (Easy Apply) para uma vaga.
    Utiliza os dados do user_profile para preencher os passos.
    """
    job = db.get_job_by_id(job_id)
    if not job or not job.get("easy_apply"):
        print(f"   ❌ Vaga {job_id} não é elegível para candidatura simplificada.")
        return False
    
    profile = db.get_user_profile()
    if not profile:
        print("   ❌ Perfil de usuário não encontrado. Preencha o Onboarding primeiro.")
        return False

    print(f"\n🤖 Iniciando Auto-Apply para: {job['job_title']} @ {job['company']}")

    with sync_playwright() as p:
        # Usamos headless=False para que o usuário possa supervisionar o primeiro teste se necessário,
        # ou headless=True para automação total.
        browser, context = scraper._create_context(p, headless=True)
        page = context.new_page()
        try:
            page.goto(job["url"], wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            
            # Clicar no botão de Candidatura Simplificada
            apply_btn = page.query_selector('button.jobs-apply-button')
            if apply_btn:
                apply_btn.click()
                time.sleep(3)
                
                # Loop para lidar com os passos do modal
                for step in range(1, 11): # Máximo 10 passos
                    print(f"   Passo {step}...")
                    
                    # Verificar se há perguntas ou campos para preencher
                    # (Lógica avançada de preenchimento seria integrada aqui)
                    
                    # Tentar avançar
                    next_btn = page.query_selector('button:has-text("Next"), button:has-text("Avançar"), button:has-text("Review")')
                    if not next_btn:
                        # Tentar submeter
                        submit_btn = page.query_selector('button:has-text("Submit application"), button:has-text("Enviar candidatura")')
                        if submit_btn:
                            submit_btn.click()
                            time.sleep(3)
                            print("   ✅ Candidatura enviada com sucesso!")
                            db.update_job_status(job_id, "applied", applied_via_bot=True)
                            return True
                        break
                    
                    next_btn.click()
                    time.sleep(2)
            
            print("   ⚠️ Não foi possível completar a candidatura automaticamente.")
            return False
        except Exception as e:
            print(f"   ❌ Erro no Auto-Apply: {e}")
            return False
        finally:
            browser.close()


def run_all_strategies():
    """Execute search for all active strategies in database."""
    strategies = db.get_search_strategies(active_only=True)
    if not strategies:
        print("ℹ️ Nenhuma estratégia de busca ativa encontrada no banco.")
        return
    
    print(f"🚀 Iniciando {len(strategies)} estratégias de busca...")
    for strat in strategies:
        print(f"\n📌 Estratégia: {strat['title']}")
        search_jobs(
            keywords=strat['keywords'],
            locations=strat['locations'],
            remote_only=strat.get('remote_only', True)
        )
