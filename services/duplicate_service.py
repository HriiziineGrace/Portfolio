"""
Duplicate Detection Service for Government Job Deadline Guardian.
Detects exact duplicates, near duplicates, and official corrigendums (deadline extensions).
"""

import hashlib
import re
from datetime import datetime
from database import get_db_connection

def normalize_text(text: str) -> str:
    """Normalize text by stripping whitespace, punctuation, and lowercase."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def calculate_hash(title: str, organization: str, advt_no: str) -> str:
    """Generate SHA-256 fingerprint for a job notification."""
    normalized = f"{normalize_text(title)}|{normalize_text(organization)}|{normalize_text(advt_no)}"
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def string_similarity(s1: str, s2: str) -> float:
    """Simple token-based Jaccard similarity for near-duplicate detection."""
    set1 = set(re.findall(r'\w+', s1.lower()))
    set2 = set(re.findall(r'\w+', s2.lower()))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / union if union > 0 else 0.0

def process_job_notification(job_dict: dict):
    """
    Check an incoming job against database:
    1. If hash exists and deadline is identical -> DUPLICATE_IGNORED
    2. If org + advt_no matches but deadline changed -> CORRIGENDUM_UPDATED
    3. If fuzzy match on title and same organization -> NEAR_DUPLICATE_FLAGGED / MERGED
    4. Otherwise -> NEW_INSERTED
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    title = job_dict.get('title', '').strip()
    org = job_dict.get('organization', '').strip()
    advt_no = job_dict.get('advt_no', '').strip()
    deadline = job_dict.get('deadline', '').strip()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    fingerprint = calculate_hash(title, org, advt_no)

    # Check 1: Check by hash or exact Advt No + Org
    cursor.execute("""
        SELECT * FROM jobs 
        WHERE hash_fingerprint = ? OR (LOWER(TRIM(advt_no)) = LOWER(TRIM(?)) AND LOWER(TRIM(organization)) = LOWER(TRIM(?)))
    """, (fingerprint, advt_no, org))
    
    existing = cursor.fetchone()

    if existing:
        matched_id = existing['id']
        old_deadline = existing['deadline']

        # Corrigendum / Deadline extension check
        if old_deadline != deadline and deadline > old_deadline:
            corrigendum_note = f"Deadline officially extended from {old_deadline[:10]} to {deadline[:10]} via Corrigendum Notice."
            cursor.execute("""
                UPDATE jobs 
                SET deadline = ?, original_deadline = COALESCE(original_deadline, ?),
                    is_extended = 1, corrigendum_note = ?, updated_at = ?
                WHERE id = ?
            """, (deadline, old_deadline, corrigendum_note, now_str, matched_id))
            
            cursor.execute("""
                INSERT INTO duplicate_logs 
                (incoming_title, incoming_org, incoming_advt, matched_job_id, status, match_reason, detected_at)
                VALUES (?, ?, ?, ?, 'CORRIGENDUM_UPDATED', ?, ?)
            """, (title, org, advt_no, matched_id, f"Deadline extended from {old_deadline} to {deadline}", now_str))
            
            conn.commit()
            conn.close()
            return {
                "status": "CORRIGENDUM_UPDATED",
                "message": f"Corrigendum applied: Deadline extended for '{title}' to {deadline}.",
                "job_id": matched_id,
                "is_new": False
            }
        else:
            # Exact duplicate re-posted or already active
            cursor.execute("""
                INSERT INTO duplicate_logs 
                (incoming_title, incoming_org, incoming_advt, matched_job_id, status, match_reason, detected_at)
                VALUES (?, ?, ?, ?, 'DUPLICATE_IGNORED', 'Exact duplicate matching Advt No / Fingerprint already in system', ?)
            """, (title, org, advt_no, matched_id, now_str))
            conn.commit()
            conn.close()
            return {
                "status": "DUPLICATE_IGNORED",
                "message": f"Duplicate ignored: '{title}' ({advt_no}) is already registered.",
                "job_id": matched_id,
                "is_new": False
            }

    # Check 2: Near duplicate check across same organization
    cursor.execute("SELECT id, title, advt_no, deadline FROM jobs WHERE LOWER(TRIM(organization)) = LOWER(TRIM(?))", (org,))
    org_jobs = cursor.fetchall()
    for row in org_jobs:
        sim = string_similarity(title, row['title'])
        if sim > 0.82:
            # Very similar title in the same department
            cursor.execute("""
                INSERT INTO duplicate_logs 
                (incoming_title, incoming_org, incoming_advt, matched_job_id, status, match_reason, detected_at)
                VALUES (?, ?, ?, ?, 'NEAR_DUPLICATE_FLAGGED', ?, ?)
            """, (title, org, advt_no, row['id'], f"High similarity ({round(sim*100, 1)}%) with existing Job ID #{row['id']} '{row['title']}'", now_str))
            # We can still insert if user wishes, or return warning. For safety, let's treat as separate if advt_no differs, but log it.

    # Insert new job
    cursor.execute("""
        INSERT INTO jobs (
            hash_fingerprint, title, organization, advt_no, category, state, vacancies,
            salary_pay, min_age, max_age, min_qualification, qualification_details,
            stream_specialization, age_relaxation_json, application_start, deadline,
            original_deadline, is_extended, corrigendum_note, application_fee,
            official_notification_url, official_apply_url, source_portal, is_verified,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?
        )
    """, (
        fingerprint,
        title,
        org,
        advt_no,
        job_dict.get('category', 'General'),
        job_dict.get('state', 'All India'),
        int(job_dict.get('vacancies', 1)),
        job_dict.get('salary_pay', 'As per 7th CPC rules'),
        int(job_dict.get('min_age', 18)),
        int(job_dict.get('max_age', 35)),
        job_dict.get('min_qualification', 'Graduate'),
        job_dict.get('qualification_details', 'Degree from recognized university'),
        job_dict.get('stream_specialization', 'Any'),
        job_dict.get('age_relaxation_json', '{"OBC": 3, "SC": 5, "ST": 5, "PwD": 10, "Ex-Servicemen": 5}'),
        job_dict.get('application_start', now_str[:10]),
        deadline,
        None,
        0,
        None,
        job_dict.get('application_fee', '₹100 (Exempted for SC/ST/Women)'),
        job_dict.get('official_notification_url', '#'),
        job_dict.get('official_apply_url', '#'),
        job_dict.get('source_portal', 'gov.in'),
        1,
        now_str,
        now_str
    ))

    new_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO duplicate_logs 
        (incoming_title, incoming_org, incoming_advt, matched_job_id, status, match_reason, detected_at)
        VALUES (?, ?, ?, ?, 'NEW_INSERTED', 'Unique verified notification added successfully', ?)
    """, (title, org, advt_no, new_id, now_str))

    conn.commit()
    conn.close()

    return {
        "status": "NEW_INSERTED",
        "message": f"Successfully added new notification: '{title}'.",
        "job_id": new_id,
        "is_new": True
    }

def audit_check_text(title: str, org: str, advt: str):
    """Check duplicate status without saving, for user instant verification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fingerprint = calculate_hash(title, org, advt)

    cursor.execute("""
        SELECT id, title, organization, advt_no, deadline, is_extended 
        FROM jobs 
        WHERE hash_fingerprint = ? OR (LOWER(TRIM(advt_no)) = LOWER(TRIM(?)) AND LOWER(TRIM(organization)) = LOWER(TRIM(?)))
    """, (fingerprint, advt, org))
    exact = cursor.fetchone()

    if exact:
        conn.close()
        return {
            "duplicate": True,
            "match_type": "EXACT",
            "job": dict(exact),
            "message": f"Exact match found with active posting #{exact['id']}: '{exact['title']}'."
        }

    # Check for near matches in same organization
    cursor.execute("SELECT id, title, organization, advt_no, deadline FROM jobs WHERE LOWER(TRIM(organization)) = LOWER(TRIM(?))", (org,))
    candidates = cursor.fetchall()
    near_matches = []
    for c in candidates:
        sim = string_similarity(title, c['title'])
        if sim >= 0.70:
            near_matches.append({
                "job": dict(c),
                "similarity_score": round(sim * 100, 1)
            })

    conn.close()
    if near_matches:
        return {
            "duplicate": True,
            "match_type": "NEAR_DUPLICATE",
            "near_matches": near_matches,
            "message": f"Found {len(near_matches)} highly similar notification(s) under {org}."
        }

    return {
        "duplicate": False,
        "match_type": "UNIQUE",
        "message": "Notification is unique and verified! No duplicate found."
    }
