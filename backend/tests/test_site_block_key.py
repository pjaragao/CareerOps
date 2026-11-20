"""Site blocks per company on shared ATS hosts (2026-11-20: two CAPTCHA failures skipped all of jobs.lever.co)."""
from app.services.site_service import block_key


def test_shared_ats_hosts_count_per_company():
    assert block_key("https://jobs.lever.co/megaport/7658c6d8/apply") == "jobs.lever.co/megaport"
    assert block_key("https://jobs.smartrecruiters.com/ColliersInternationalEMEA/7440-associate") == "jobs.smartrecruiters.com/colliersinternationalemea"
    assert block_key("https://jobs.ashbyhq.com/omnea/abc") == "jobs.ashbyhq.com/omnea"
    assert block_key("https://boards.greenhouse.io/acme/jobs/1?gh_src=x") == "boards.greenhouse.io/acme"


def test_a_company_host_stays_the_host():
    assert block_key("https://careers-cravath.icims.com/jobs/3608/job?mode=job") == "careers-cravath.icims.com"
    assert block_key("https://adesso1.recruitee.com/o/senior-ai-engineer") == "adesso1.recruitee.com"
    assert block_key("careers.bowman.com") == "careers.bowman.com"
    assert block_key("https://jobs.lever.co/") == "jobs.lever.co"
    assert block_key("") == ""
