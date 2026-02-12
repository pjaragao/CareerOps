"""
LinkedIn Job Scraper — CLI principal.

Uso:
    python main.py login         # Login no LinkedIn (abre browser)
    python main.py scrape        # Scrape saved jobs → banco de dados
    python main.py process       # Extrair descrições das vagas novas
    python main.py generate      # Gerar currículos customizados
    python main.py run           # Pipeline completo (scrape → process → generate)
    python main.py migrate       # Executar migration SQL
    python main.py status        # Ver status das vagas no banco
"""
import argparse
import sys

import db


def cmd_login(args):
    """Login no LinkedIn — abre browser visível."""
    from scraper import login
    login()


def cmd_scrape(args):
    """Scrape saved jobs do LinkedIn."""
    from scraper import scrape_saved_jobs
    scrape_saved_jobs(max_jobs=args.max_jobs)


def cmd_process(args):
    """Processar vagas novas (extrair descrições)."""
    from processor import process_new_jobs
    process_new_jobs(delay=args.delay)


def cmd_generate(args):
    """Gerar currículos customizados via Gemini + Gotenberg."""
    from resume_generator import generate_resumes
    generate_resumes()


def cmd_run(args):
    """Pipeline completo: scrape → process → generate."""
    print("🚀 Running full pipeline...\n")

    # Step 1: Scrape
    from scraper import scrape_saved_jobs
    scrape_saved_jobs(max_jobs=args.max_jobs)

    # Step 2: Process
    from processor import process_new_jobs
    process_new_jobs(delay=args.delay)

    # Step 3: Generate
    from resume_generator import generate_resumes
    generate_resumes()

    print("\n🎉 Pipeline complete!")


def cmd_migrate(args):
    """Executar migration SQL."""
    db.run_migration()


def cmd_status(args):
    """Mostrar status das vagas no banco."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Count by status
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM public.job_listings
                GROUP BY status
                ORDER BY status
            """)
            rows = cur.fetchall()

            if not rows:
                print("\n📊 No jobs in database yet.")
                return

            print("\n📊 Job Listings Status:")
            print("   " + "-" * 30)
            total = 0
            for status, count in rows:
                print(f"   {status:<15} {count:>5}")
                total += count
            print("   " + "-" * 30)
            print(f"   {'TOTAL':<15} {total:>5}")

            # Show recent jobs
            cur.execute("""
                SELECT job_title, company, status, created_at
                FROM public.job_listings
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent = cur.fetchall()

            if recent:
                print(f"\n   Latest jobs:")
                for title, company, status, created in recent:
                    title_short = (title or "???")[:40]
                    company_short = (company or "???")[:20]
                    print(f"   [{status:<10}] {title_short} @ {company_short}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Scraper — scrape saved jobs, generate customized resumes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  login      Login to LinkedIn (opens browser for manual login)
  scrape     Scrape saved jobs from LinkedIn
  process    Extract full job descriptions for new jobs
  generate   Generate customized resumes (Gemini AI + PDF)
  run        Full pipeline: scrape → process → generate
  migrate    Run database migration
  status     Show job listings status summary
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # login
    sub_login = subparsers.add_parser("login", help="Login to LinkedIn")
    sub_login.set_defaults(func=cmd_login)

    # scrape
    sub_scrape = subparsers.add_parser("scrape", help="Scrape saved jobs")
    sub_scrape.add_argument("--max-jobs", type=int, default=20,
                            help="Maximum number of jobs to scrape (default: 20)")
    sub_scrape.set_defaults(func=cmd_scrape)

    # process
    sub_process = subparsers.add_parser("process", help="Process new jobs")
    sub_process.add_argument("--delay", type=int, default=4,
                             help="Delay between requests in seconds (default: 4)")
    sub_process.set_defaults(func=cmd_process)

    # generate
    sub_generate = subparsers.add_parser("generate", help="Generate resumes")
    sub_generate.set_defaults(func=cmd_generate)

    # run (full pipeline)
    sub_run = subparsers.add_parser("run", help="Full pipeline")
    sub_run.add_argument("--max-jobs", type=int, default=20,
                         help="Maximum number of jobs to scrape (default: 20)")
    sub_run.add_argument("--delay", type=int, default=4,
                         help="Delay between requests in seconds (default: 4)")
    sub_run.set_defaults(func=cmd_run)

    # migrate
    sub_migrate = subparsers.add_parser("migrate", help="Run database migration")
    sub_migrate.set_defaults(func=cmd_migrate)

    # status
    sub_status = subparsers.add_parser("status", help="Show status summary")
    sub_status.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
