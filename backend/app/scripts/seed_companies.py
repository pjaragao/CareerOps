
import sys
import os
import requests
from typing import List, Tuple

# Add backend to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.company_service import CompanyService
from app.db.session import get_db_connection

COMPANIES_LIST = [
    ("TestGorilla", "https://lnkd.in/gC9mdCtB", "JOB_PLATFORM"),
    ("airspace-link", "https://lnkd.in/gVfvwi5f", "DIRECT_EMPLOYER"),
    ("Pearson", "https://pearson.jobs/jobs/", "DIRECT_EMPLOYER"),
    ("Confluent", "https://lnkd.in/dNSTmUeH", "DIRECT_EMPLOYER"),
    ("Cengage Group", "https://lnkd.in/gGkT6jRZ", "DIRECT_EMPLOYER"),
    ("Quest Software", "https://lnkd.in/dkHSNGmM", "DIRECT_EMPLOYER"),
    ("Kforce", "https://lnkd.in/gYKxQXT3", "RECRUITMENT_AGENCY"),
    ("Upstart", "https://lnkd.in/dGR4DJ52", "DIRECT_EMPLOYER"),
    ("hims & hers", "https://lnkd.in/gr_SdVdE", "DIRECT_EMPLOYER"),
    ("UserGems", "https://lnkd.in/gXi3mNf6", "DIRECT_EMPLOYER"),
    ("blackbaud", "https://lnkd.in/gb-bCTtJ", "DIRECT_EMPLOYER"),
    ("Cash App", "https://lnkd.in/gdp8yUm8", "DIRECT_EMPLOYER"),
    ("LogicGate", "https://lnkd.in/gjgX27Bc", "DIRECT_EMPLOYER"),
    ("Faire", "https://lnkd.in/gYRNr9VM", "DIRECT_EMPLOYER"),
    ("Rec Room", "https://lnkd.in/gErDuTNa", "DIRECT_EMPLOYER"),
    ("VGS", "https://lnkd.in/g7Ajb77F", "DIRECT_EMPLOYER"),
    ("Patreon", "https://lnkd.in/gzQptMcQ", "DIRECT_EMPLOYER"),
    ("Beekeeper", "https://lnkd.in/gxd7rs7Q", "DIRECT_EMPLOYER"),
    ("Upwork", "https://lnkd.in/gt4HYmd6", "JOB_PLATFORM"),
    ("DocuSign", "https://lnkd.in/ggfUncZf", "DIRECT_EMPLOYER"),
    ("DealHub.io", "https://lnkd.in/gyNED4yp", "DIRECT_EMPLOYER"),
    ("Census", "https://lnkd.in/gAq7PGzc", "DIRECT_EMPLOYER"),
    ("Intrado", "https://lnkd.in/gH3wuNWZ", "DIRECT_EMPLOYER"),
    ("Cloudflare", "https://lnkd.in/g9JPXp2F", "DIRECT_EMPLOYER"),
    ("Funded.club", "https://lnkd.in/gpH4FazA", "RECRUITMENT_AGENCY"),
    ("Workiva", "https://lnkd.in/g-FUYYdR", "DIRECT_EMPLOYER"),
    ("MissionWired", "https://lnkd.in/gMA6AVdG", "DIRECT_EMPLOYER"),
    ("Workera", "https://lnkd.in/g2YzZu-H", "RECRUITMENT_AGENCY"),
    ("Jenius Bank", "https://lnkd.in/gxGqHGkH", "DIRECT_EMPLOYER"),
    ("Goinstacare", "https://lnkd.in/d6ZN5FVD", "DIRECT_EMPLOYER"),
    ("Uplers", "https://www.uplers.com", "RECRUITMENT_AGENCY"),
    ("Quantum", "https://lnkd.in/d8jFCeuU", "DIRECT_EMPLOYER"),
    ("Canonical", "https://lnkd.in/d9mf5Rr3", "DIRECT_EMPLOYER"),
    ("Kemecon", "http://kemecon.com", "DIRECT_EMPLOYER"),
    ("DigitalOcean", "https://lnkd.in/dYgDZ-WF", "DIRECT_EMPLOYER"),
    ("Atlassian", "https://Inkd.in/dp-SFzfT", "DIRECT_EMPLOYER"),
    ("AngelOne", "https://lnkd.in/dk3NwDn6", "DIRECT_EMPLOYER"),
    ("Help Scout", "https://lnkd.in/gW9akVhd", "DIRECT_EMPLOYER"),
    ("Appcues", "https://lnkd.in/dp2Jiupp", "DIRECT_EMPLOYER"),
    ("Arkency", "https://lnkd.in/dBB_wZaR", "DIRECT_EMPLOYER"),
    ("Automattic", "https://lnkd.in/ddSBdusv", "DIRECT_EMPLOYER"),
    ("Awesomemotive", "https://lnkd.in/diZZjb4J", "DIRECT_EMPLOYER"),
    ("Buffer", "https://lnkd.in/d7ihgxkA", "DIRECT_EMPLOYER"),
    ("apartment-list", "https://lnkd.in/ghw3h5dt", "DIRECT_EMPLOYER"),
    ("Constructor", "https://lnkd.in/daBzMdxM", "DIRECT_EMPLOYER"),
    ("Fleetio", "https://lnkd.in/gUQNDVNb", "DIRECT_EMPLOYER"),
    ("Agency Analytics", "https://lnkd.in/gD24k2ns", "DIRECT_EMPLOYER"),
    ("Contra", "https://contra.com/careers", "JOB_PLATFORM"),
    ("Xapobank", "http://www.xapobank.com", "DIRECT_EMPLOYER"),
    ("Symetra", "http://www.symetra.com", "DIRECT_EMPLOYER"),
    ("pagerduty", "https://lnkd.in/gerC6Frs", "DIRECT_EMPLOYER"),
    ("Docker, Inc", "https://lnkd.in/gfX5-pQG", "DIRECT_EMPLOYER"),
    ("Citizens Bank", "https://lnkd.in/g4s3qnaS", "DIRECT_EMPLOYER"),
    ("Doist", "https://doist.com/careers/", "DIRECT_EMPLOYER"),
    ("DuckDuckGo", "https://lnkd.in/d_Kv9dM6", "DIRECT_EMPLOYER"),
    ("aquia-inc", "https://lnkd.in/gTbs8YrZ", "DIRECT_EMPLOYER"),
    ("Bold", "https://lnkd.in/dZQ8dQnq", "DIRECT_EMPLOYER"),
    ("Akamai Technologies", "https://lnkd.in/dpTN5nPT", "DIRECT_EMPLOYER"),
    ("iVisa", "https://ivisa.breezy.hr/", "JOB_PLATFORM"),
    ("Affordmate", "http://www.affordmate.com", "RECRUITMENT_AGENCY"),
]

def seed():
    print(f"Starting seed of {len(COMPANIES_LIST)} companies...")
    for name, url, ctype in COMPANIES_LIST:
        print(f"Processing {name}...")
        final_url = CompanyService.unshorten_url(url)
        company_id = CompanyService.get_or_create_company(name, final_url, ctype)
        print(f"  -> Saved with ID {company_id} (Final URL: {final_url})")
    print("Seed completed!")

if __name__ == "__main__":
    seed()
