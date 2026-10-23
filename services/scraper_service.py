"""
Scraper and Official Portal Sync Service for Government Job Deadline Guardian.
Simulates fetching fresh official recruitment feeds and verifying official government domains.
"""

from urllib.parse import urlparse
from datetime import datetime
from services.duplicate_service import process_job_notification

# Trusted official top-level and second-level government domains
TRUSTED_GOV_DOMAINS = [
    "gov.in", "nic.in", "upsc.gov.in", "ssc.gov.in", "ibps.in", "sbi.co.in",
    "rrbapply.gov.in", "rrbcdg.gov.in", "rac.gov.in", "isro.gov.in",
    "bpsc.bih.nic.in", "uppsc.up.nic.in", "joinindianarmy.nic.in",
    "iocl.com", "mha.gov.in", "dsssb.delhi.gov.in", "aiimsexams.ac.in",
    "bombayhighcourt.nic.in", "ctet.nic.in", "rajswasthya.nic.in"
]

# Simulated incoming feeds for sync testing
SIMULATED_FEED_BATCHES = [
    {
        "batch_name": "UPSC Official Gazette Feed",
        "jobs": [
            {
                "title": "Combined Defence Services Examination (CDS II 2026)",
                "organization": "Union Public Service Commission (UPSC)",
                "advt_no": "10/2026-CDS-II",
                "category": "Defence",
                "state": "All India",
                "vacancies": 459,
                "salary_pay": "Level 10 (₹56,100/-) + MSP",
                "min_age": 19,
                "max_age": 24,
                "min_qualification": "Graduate",
                "qualification_details": "Degree from recognized university",
                "stream_specialization": "Any",
                "age_relaxation_json": '{"General": 0, "OBC": 0, "SC": 0, "ST": 0}',
                "application_start": "2026-09-28",
                "deadline": "2026-10-27 18:00:00", # Corrigendum: extended from 2026-10-23!
                "application_fee": "₹200",
                "official_notification_url": "https://upsc.gov.in/examinations/combined-defence-services-examination-ii-2026",
                "official_apply_url": "https://upsconline.nic.in/ora/Detail.php?advt=10/2026-CDS-II",
                "source_portal": "upsc.gov.in"
            },
            {
                "title": "National Defence Academy & Naval Academy (NDA I 2027)",
                "organization": "Union Public Service Commission (UPSC)",
                "advt_no": "01/2027-NDA-I",
                "category": "Defence",
                "state": "All India",
                "vacancies": 400,
                "salary_pay": "Stipend ₹56,100/- p.m.",
                "min_age": 16,
                "max_age": 19,
                "min_qualification": "12th Pass",
                "qualification_details": "12th Class pass of 10+2 pattern of School Education or equivalent with Physics and Mathematics.",
                "stream_specialization": "Science",
                "age_relaxation_json": '{"General": 0, "OBC": 0, "SC": 0, "ST": 0}',
                "application_start": "2026-10-20",
                "deadline": "2026-11-25 18:00:00",
                "application_fee": "₹100 (SC/ST/Female Exempt)",
                "official_notification_url": "https://upsc.gov.in/examinations/national-defence-academy-i-2027",
                "official_apply_url": "https://upsconline.nic.in/",
                "source_portal": "upsc.gov.in"
            }
        ]
    },
    {
        "batch_name": "State PSCs & Railway Board Feeds",
        "jobs": [
            {
                "title": "Civil Services Examination (IAS / IFS) 2026", # Exact duplicate test!
                "organization": "Union Public Service Commission (UPSC)",
                "advt_no": "04/2026-CSP",
                "category": "Civil Services",
                "state": "All India",
                "vacancies": 1056,
                "salary_pay": "Level 10 (₹56,100 - ₹1,77,500)",
                "min_age": 21,
                "max_age": 32,
                "min_qualification": "Graduate",
                "qualification_details": "Graduation in any discipline",
                "stream_specialization": "Any",
                "deadline": "2026-10-21 18:00:00",
                "application_fee": "₹100",
                "official_notification_url": "https://upsc.gov.in/examinations/civil-services-preliminary-examination-2026",
                "official_apply_url": "https://upsconline.nic.in/",
                "source_portal": "upsc.gov.in"
            },
            {
                "title": "Junior Engineer (JE) Electrical & Mechanical Recruitment",
                "organization": "Railway Recruitment Boards (RRB)",
                "advt_no": "CEN 03/2026",
                "category": "Railways",
                "state": "All India",
                "vacancies": 7951,
                "salary_pay": "Level-6 (₹35,400/- plus DA)",
                "min_age": 18,
                "max_age": 33,
                "min_qualification": "Diploma",
                "qualification_details": "Three years Diploma in Civil/Mechanical/Electrical/Electronic Engineering from recognized university or B.Tech.",
                "stream_specialization": "Engineering",
                "age_relaxation_json": '{"OBC": 3, "SC": 5, "ST": 5, "PwD": 10}',
                "application_start": "2026-10-20",
                "deadline": "2026-11-28 23:59:00",
                "application_fee": "₹500 (₹400 refundable)",
                "official_notification_url": "https://rrbcdg.gov.in/cen-03-2026-je.pdf",
                "official_apply_url": "https://www.rrbapply.gov.in/",
                "source_portal": "rrbapply.gov.in"
            }
        ]
    }
]

def verify_official_link(url: str):
    """
    Check whether a URL belongs to a verified official government domain.
    Protects users against phishing or commercial job spam sites.
    """
    if not url or url.startswith("#"):
        return {"is_official": False, "reason": "No valid URL provided"}
    
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        
        # Check domain endings
        if hostname.endswith(".gov.in") or hostname.endswith(".nic.in"):
            return {
                "is_official": True,
                "domain": hostname,
                "badge": "Official .GOV.IN Portal",
                "message": "Authentic government portal verified by National Informatics Centre (NIC)."
            }
        
        # Check against approved list
        for trusted in TRUSTED_GOV_DOMAINS:
            if hostname == trusted or hostname.endswith("." + trusted):
                return {
                    "is_official": True,
                    "domain": hostname,
                    "badge": "Approved Recruitment Agency",
                    "message": "Verified recruitment board / state authority portal."
                }

        return {
            "is_official": False,
            "domain": hostname,
            "badge": "External Link",
            "message": "Non-standard recruitment URL. Proceed with caution."
        }
    except Exception as e:
        return {"is_official": False, "reason": str(e)}

def run_simulated_portal_sync():
    """
    Simulate running automated portal crawlers across UPSC, SSC, and Railway boards.
    Processes all items through duplicate detection engine.
    """
    results = []
    total_processed = 0
    new_count = 0
    corrigendum_count = 0
    duplicate_count = 0

    for batch in SIMULATED_FEED_BATCHES:
        batch_log = {"batch_name": batch["batch_name"], "sync_items": [], "items": []}
        for item in batch["jobs"]:
            total_processed += 1
            res = process_job_notification(item)
            if res["status"] == "NEW_INSERTED":
                new_count += 1
            elif res["status"] == "CORRIGENDUM_UPDATED":
                corrigendum_count += 1
            elif res["status"] == "DUPLICATE_IGNORED":
                duplicate_count += 1
            
            entry = {
                "title": item["title"],
                "org": item["organization"],
                "advt": item["advt_no"],
                "status": res["status"],
                "message": res["message"]
            }
            batch_log["sync_items"].append(entry)
            batch_log["items"].append(entry)
        results.append(batch_log)

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_processed": total_processed,
        "new_inserted": new_count,
        "corrigendums_applied": corrigendum_count,
        "duplicates_skipped": duplicate_count,
        "batches": results
    }
