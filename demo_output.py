"""
Demonstration script to display the live system output in terminal.
"""

import sqlite3
import sys

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from services.eligibility_service import evaluate_eligibility
from services.duplicate_service import audit_check_text
from services.scraper_service import verify_official_link

def show_output():
    conn = sqlite3.connect('job_guardian.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 70)
    print("🛡️  GOVERNMENT JOB DEADLINE GUARDIAN - SYSTEM OUTPUT PREVIEW")
    print("=" * 70)

    # 1. Active Jobs
    print("\n1. 📜 ACTIVE VACANCIES & CLOSING DEADLINES (Sample from Database):")
    print("-" * 70)
    jobs = cursor.execute("SELECT id, title, organization, advt_no, vacancies, deadline, is_extended FROM jobs LIMIT 4").fetchall()
    for j in jobs:
        ext = " [🔄 CORRIGENDUM: DEADLINE EXTENDED]" if j['is_extended'] else ""
        print(f"Post #{j['id']}: {j['title']}")
        print(f"   Authority: {j['organization']} | Advt: {j['advt_no']}")
        print(f"   Vacancies: {j['vacancies']:,} posts | Deadline: {j['deadline']}{ext}")
        print()

    # 2. Eligibility Engine
    print("\n2. 🎯 ELIGIBILITY EVALUATOR OUTPUT (DOB + Category + Qualification):")
    print("-" * 70)
    sample_job = cursor.execute("SELECT * FROM jobs WHERE id = 1").fetchone()
    candidate = {
        'dob': '1993-08-15',
        'category': 'OBC',
        'qualification': 'Graduate',
        'stream': 'Any'
    }
    res = evaluate_eligibility(candidate, dict(sample_job))
    print(f"Candidate: Born 1993-08-15 | Category: OBC | Qualification: Graduate")
    print(f"Evaluating for: {sample_job['title']}")
    print(f"Standard Age Limit: {sample_job['min_age']} - {sample_job['max_age']} Years")
    print(f"Candidate Current Age: {res['candidate_age_formatted']}")
    print(f"Relaxation Applied: +{res['relaxation_applied']} Years ({res['category']} Quota)")
    print(f"Effective Max Limit for Candidate: {res['effective_max_age']} Years")
    print(f"Final Verdict: {'✅ ' + res['summary'] if res['eligible'] else '❌ ' + res['summary']}")
    print("Detailed Reasons:")
    for r in res['reasons']:
        print(f"   • {r}")

    # 3. Duplicate Detection
    print("\n3. 🔄 DUPLICATE DETECTION ENGINE OUTPUT:")
    print("-" * 70)
    dup = audit_check_text(
        "Civil Services Examination (IAS / IFS) 2026",
        "Union Public Service Commission (UPSC)",
        "04/2026-CSP"
    )
    print("Incoming Notification: UPSC Civil Services Examination 2026 (04/2026-CSP)")
    print(f"Is Duplicate: {dup['duplicate']}")
    print(f"Match Type: {dup['match_type']}")
    print(f"Engine Decision: {dup['message']}")

    # 4. Anti-Scam Link Verification
    print("\n4. 🛡️ OFFICIAL DOMAIN VERIFICATION OUTPUT:")
    print("-" * 70)
    links = [
        "https://upsc.gov.in/examinations/civil-services",
        "https://rrbapply.gov.in/#/auth/login",
        "https://jobalert-free-apply.biz/register"
    ]
    for url in links:
        ver = verify_official_link(url)
        status_icon = "✅" if ver['is_official'] else "⚠️"
        print(f"{status_icon} URL: {url}")
        print(f"   Status: {ver['badge']} | Note: {ver['message']}")

    print("\n" + "=" * 70)
    print("🌐 Web Application is running live at: http://127.0.0.1:5000")
    print("=" * 70)

    conn.close()

if __name__ == '__main__':
    show_output()
