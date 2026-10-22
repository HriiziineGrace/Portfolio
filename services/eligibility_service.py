"""
Eligibility Service for Government Job Deadline Guardian.
Evaluates candidate age, category relaxations, and educational qualifications against job requirements.
"""

from datetime import datetime, date
import json

# Qualification hierarchy rank for general progression
QUALIFICATION_RANK = {
    "10th Pass": 10,
    "ITI": 11,
    "12th Pass": 12,
    "Diploma": 13,
    "Graduate": 14,
    "B.Tech/BE": 14,
    "LLB": 14,
    "MBBS": 14,
    "Post Graduate": 16,
    "PhD": 18
}

DEFAULT_RELAXATIONS = {
    "General": 0,
    "EWS": 0,
    "OBC": 3,
    "SC": 5,
    "ST": 5,
    "PwD": 10,
    "Ex-Servicemen": 5
}

def calculate_age_details(dob_str: str, ref_date: date = None):
    """
    Calculate age in years, months, and total years as a float.
    dob_str expected in 'YYYY-MM-DD'.
    """
    if not ref_date:
        ref_date = date(2026, 10, 20)  # Anchor to system current date
    
    try:
        birth_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
    except Exception:
        return None

    # Calculate years
    years = ref_date.year - birth_date.year
    months = ref_date.month - birth_date.month
    days = ref_date.day - birth_date.day

    if days < 0:
        months -= 1
        days += 30
    if months < 0:
        years -= 1
        months += 12

    total_years_float = round(years + (months / 12.0) + (days / 365.0), 2)
    return {
        "years": years,
        "months": months,
        "days": days,
        "total_float": total_years_float,
        "formatted": f"{years} yrs, {months} mos"
    }

def check_qualification_match(candidate_qual: str, candidate_stream: str, job_min_qual: str, job_stream: str):
    """
    Check if candidate's qualification satisfies the job requirement.
    """
    cand_rank = QUALIFICATION_RANK.get(candidate_qual, 0)
    job_rank = QUALIFICATION_RANK.get(job_min_qual, 0)

    # General check: candidate level must be >= job minimum level
    level_ok = cand_rank >= job_rank

    # Specific professional degree overrides
    if job_min_qual == "B.Tech/BE" and candidate_qual not in ["B.Tech/BE", "Post Graduate"]:
        level_ok = False
    elif job_min_qual == "MBBS" and candidate_qual != "MBBS":
        level_ok = False
    elif job_min_qual == "LLB" and candidate_qual not in ["LLB", "Post Graduate"]:
        level_ok = False

    # Stream check
    stream_ok = True
    if job_stream and job_stream != "Any":
        if candidate_stream and candidate_stream != "Any" and candidate_stream != job_stream:
            stream_ok = False

    return level_ok and stream_ok

def evaluate_eligibility(candidate_profile: dict, job_row: dict, ref_date: date = None):
    """
    Evaluate candidate profile against a job posting.
    candidate_profile: {
        'dob': 'YYYY-MM-DD',
        'category': 'General' | 'OBC' | 'SC' | 'ST' | 'EWS' | 'PwD' | 'Ex-Servicemen',
        'qualification': 'Graduate',
        'stream': 'Any' | 'Engineering' | 'Science' ...
    }
    """
    dob_str = candidate_profile.get('dob')
    category = candidate_profile.get('category', 'General')
    cand_qual = candidate_profile.get('qualification', 'Graduate')
    cand_stream = candidate_profile.get('stream', 'Any')

    age_info = calculate_age_details(dob_str, ref_date)
    if not age_info:
        return {
            "eligible": False,
            "status_type": "INVALID_DOB",
            "reason": "Please provide a valid Date of Birth.",
            "age_text": "Unknown"
        }

    cand_years = age_info['years']
    min_age = job_row['min_age']
    base_max_age = job_row['max_age']

    # Parse relaxation
    relaxations = DEFAULT_RELAXATIONS.copy()
    if job_row.get('age_relaxation_json'):
        try:
            custom_rel = json.loads(job_row['age_relaxation_json'])
            relaxations.update(custom_rel)
        except Exception:
            pass

    relaxation_years = relaxations.get(category, 0)
    effective_max_age = base_max_age + relaxation_years

    # Age checks
    under_age = cand_years < min_age
    over_age = cand_years > effective_max_age
    age_ok = (not under_age) and (not over_age)

    # Qualification check
    qual_ok = check_qualification_match(
        cand_qual,
        cand_stream,
        job_row['min_qualification'],
        job_row.get('stream_specialization', 'Any')
    )

    is_overall_eligible = age_ok and qual_ok

    reasons = []
    status_type = "ELIGIBLE"

    if under_age:
        status_type = "UNDER_AGE"
        reasons.append(f"Minimum age required is {min_age} years. You are {age_info['formatted']}.")
    elif over_age:
        status_type = "OVER_AGE"
        diff = cand_years - effective_max_age
        reasons.append(f"Exceeds maximum age limit of {effective_max_age} years (including {category} +{relaxation_years}yr relaxation) by {diff} year(s).")
    else:
        if relaxation_years > 0 and cand_years > base_max_age:
            status_type = "ELIGIBLE_RELAXED"
            reasons.append(f"Eligible under {category} category relaxation (standard max {base_max_age} + {relaxation_years} yrs = {effective_max_age} yrs).")
        else:
            reasons.append(f"Age {age_info['formatted']} is within normal limit ({min_age} - {base_max_age} yrs).")

    if not qual_ok:
        status_type = "QUALIFICATION_MISMATCH" if age_ok else "INELIGIBLE_MULTIPLE"
        req_text = job_row['min_qualification']
        if job_row.get('stream_specialization') and job_row['stream_specialization'] != 'Any':
            req_text += f" ({job_row['stream_specialization']})"
        reasons.append(f"Requires minimum {req_text}. Candidate has {cand_qual} ({cand_stream}).")
    else:
        reasons.append(f"Qualification '{cand_qual}' satisfies job requirement '{job_row['min_qualification']}'.")

    return {
        "eligible": is_overall_eligible,
        "status_type": status_type,
        "age_ok": age_ok,
        "qual_ok": qual_ok,
        "candidate_age_formatted": age_info['formatted'],
        "candidate_age_years": cand_years,
        "min_age": min_age,
        "base_max_age": base_max_age,
        "effective_max_age": effective_max_age,
        "relaxation_applied": relaxation_years,
        "category": category,
        "reasons": reasons,
        "summary": "Eligible to apply!" if is_overall_eligible else ("Over Age" if over_age else ("Under Age" if under_age else "Qualification requirement not satisfied"))
    }
