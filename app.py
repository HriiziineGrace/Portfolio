"""
Main Flask Application for Government Job Deadline Guardian.
Features:
- Official Government Job Notifications & Feed
- Real-time Deadline Tracker with Visual Urgency Countdowns
- Multi-criteria Search & Filters
- Interactive Age & Reservation Eligibility Checker
- Multi-tier Duplicate & Corrigendum Detection
- Direct Official Links with .gov.in Verification Badges
- Reminder Dispatcher & iCalendar (.ics) Exporter
"""

import os
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, flash
from database import init_db, get_db_connection
from services.eligibility_service import evaluate_eligibility, calculate_age_details
from services.duplicate_service import process_job_notification, audit_check_text
from services.reminder_service import generate_ics_calendar, record_and_dispatch_reminder
from services.scraper_service import verify_official_link, run_simulated_portal_sync

app = Flask(__name__)
app.secret_key = "gov-job-guardian-secret-key-2026"

# Ensure DB is created
init_db()

def get_current_system_time():
    """Anchor reference time (2026-10-20 current context or local time)."""
    # Using anchor 2026-10-20
    return datetime(2026, 10, 20, 11, 0, 0)

def parse_deadline(deadline_str):
    """Safely parse deadline string to datetime object."""
    try:
        return datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(deadline_str[:10], "%Y-%m-%d")
        except Exception:
            return datetime.now() + timedelta(days=7)

def enrich_job_with_deadline_meta(job_row):
    """Calculate remaining time, urgency category, and deadline formatting."""
    job = dict(job_row)
    now = get_current_system_time()
    dl_dt = parse_deadline(job['deadline'])
    diff = dl_dt - now

    total_seconds = int(diff.total_seconds())
    is_expired = total_seconds <= 0

    if is_expired:
        urgency = "EXPIRED"
        urgency_class = "urgency-expired"
        urgency_label = "Application Closed"
        countdown_text = "Closed"
        days_remaining = -1
    else:
        days = diff.days
        hours = int((diff.seconds) / 3600)
        minutes = int(((diff.seconds) % 3600) / 60)
        seconds = int((diff.seconds) % 60)
        days_remaining = days

        if total_seconds <= 86400 * 2:  # <= 48 hours
            urgency = "CRITICAL"
            urgency_class = "urgency-critical"
            urgency_label = f"Closing in {hours}h {minutes}m!"
            countdown_text = f"{hours}h {minutes}m {seconds}s"
        elif days <= 5:
            urgency = "URGENT"
            urgency_class = "urgency-urgent"
            urgency_label = f"{days} Days Left"
            countdown_text = f"{days}d {hours}h {minutes}m"
        elif days <= 14:
            urgency = "APPROACHING"
            urgency_class = "urgency-approaching"
            urgency_label = f"{days} Days Left"
            countdown_text = f"{days}d {hours}h"
        else:
            urgency = "OPEN"
            urgency_class = "urgency-open"
            urgency_label = f"{days} Days Left"
            countdown_text = f"{days}d {hours}h"

    job['time_remaining_seconds'] = max(0, total_seconds)
    job['days_remaining'] = days_remaining
    job['urgency'] = urgency
    job['urgency_class'] = urgency_class
    job['urgency_label'] = urgency_label
    job['countdown_text'] = countdown_text
    job['deadline_formatted'] = dl_dt.strftime("%d %b %Y, %I:%M %p")
    job['is_closed'] = is_expired
    
    # Official portal verification check
    job['verification_info'] = verify_official_link(job.get('official_apply_url') or job.get('official_notification_url'))
    return job

@app.context_processor
def inject_global_data():
    """Inject common stats and current time into all templates."""
    now = get_current_system_time()
    return {
        "current_time_str": now.strftime("%d %B %Y, %I:%M %p"),
        "current_year": 2026
    }

# ----------------- PAGE ROUTES -----------------

@app.route('/')
def index():
    """Main dashboard: search, multi-filters, urgency ticker, and job listings."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Search & Filter params
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    state = request.args.get('state', '').strip()
    qualification = request.args.get('qualification', '').strip()
    urgency_filter = request.args.get('urgency', '').strip()
    sort_by = request.args.get('sort', 'urgency').strip()

    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if query:
        sql += " AND (title LIKE ? OR organization LIKE ? OR advt_no LIKE ? OR qualification_details LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    if category:
        sql += " AND category = ?"
        params.append(category)

    if state:
        sql += " AND (state = ? OR state = 'All India')"
        params.append(state)

    if qualification:
        sql += " AND min_qualification = ?"
        params.append(qualification)

    cursor.execute(sql, params)
    raw_jobs = cursor.fetchall()

    # Enrich jobs with deadline countdown & urgency
    jobs = [enrich_job_with_deadline_meta(j) for j in raw_jobs]

    # Filter by urgency if requested
    if urgency_filter == '24h':
        jobs = [j for j in jobs if not j['is_closed'] and j['time_remaining_seconds'] <= 86400]
    elif urgency_filter == '48h':
        jobs = [j for j in jobs if not j['is_closed'] and j['time_remaining_seconds'] <= 86400 * 2]
    elif urgency_filter == '7d':
        jobs = [j for j in jobs if not j['is_closed'] and j['time_remaining_seconds'] <= 86400 * 7]
    elif urgency_filter == 'active':
        jobs = [j for j in jobs if not j['is_closed']]
    elif urgency_filter == 'extended':
        jobs = [j for j in jobs if j.get('is_extended') == 1]

    # Sorting
    if sort_by == 'urgency':
        jobs.sort(key=lambda x: (x['is_closed'], x['time_remaining_seconds']))
    elif sort_by == 'newest':
        jobs.sort(key=lambda x: x['created_at'], reverse=True)
    elif sort_by == 'vacancies':
        jobs.sort(key=lambda x: x['vacancies'], reverse=True)

    # Calculate overall dashboard stats
    cursor.execute("SELECT COUNT(*) as total_jobs, SUM(vacancies) as total_vacancies FROM jobs")
    stats_row = cursor.fetchone()
    total_jobs = stats_row['total_jobs'] or 0
    total_vacancies = stats_row['total_vacancies'] or 0

    # Closing soon (< 48 hrs)
    critical_count = sum(1 for j in jobs if j['urgency'] == 'CRITICAL')
    extended_count = sum(1 for j in jobs if j.get('is_extended') == 1)

    # Distinct categories, qualifications, and states for filter dropdowns
    cursor.execute("SELECT DISTINCT category FROM jobs ORDER BY category ASC")
    categories = [r['category'] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT min_qualification FROM jobs ORDER BY min_qualification ASC")
    qualifications = [r['min_qualification'] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT state FROM jobs ORDER BY state ASC")
    states = [r['state'] for r in cursor.fetchall()]

    conn.close()

    return render_template(
        'index.html',
        jobs=jobs,
        total_jobs=total_jobs,
        total_vacancies=total_vacancies,
        critical_count=critical_count,
        extended_count=extended_count,
        categories=categories,
        qualifications=qualifications,
        states=states,
        current_query=query,
        current_category=category,
        current_state=state,
        current_qualification=qualification,
        current_urgency=urgency_filter,
        current_sort=sort_by
    )

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    """Detailed job view with countdown, official verification, eligibility and calendar link."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()
    conn.close()

    if not job_row:
        flash("Job notification not found.", "error")
        return redirect(url_for('index'))

    job = enrich_job_with_deadline_meta(job_row)
    return render_template('job_detail.html', job=job)

@app.route('/eligibility')
def eligibility_page():
    """Dedicated Eligibility Checker page with age calculator & qualification filter."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT min_qualification FROM jobs ORDER BY min_qualification ASC")
    qualifications = [r['min_qualification'] for r in cursor.fetchall()]
    conn.close()

    return render_template('eligibility.html', qualifications=qualifications)

@app.route('/deadlines')
def deadline_tracker_page():
    """Visual Timeline & Calendar view of upcoming deadlines."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY deadline ASC")
    raw_jobs = cursor.fetchall()
    conn.close()

    enriched = [enrich_job_with_deadline_meta(j) for j in raw_jobs]
    
    # Categorize into timeline buckets
    buckets = {
        "closing_48h": [],
        "this_week": [],
        "next_week": [],
        "later": [],
        "expired": []
    }

    for j in enriched:
        if j['is_closed']:
            buckets["expired"].append(j)
        elif j['time_remaining_seconds'] <= 86400 * 2:
            buckets["closing_48h"].append(j)
        elif j['days_remaining'] <= 7:
            buckets["this_week"].append(j)
        elif j['days_remaining'] <= 14:
            buckets["next_week"].append(j)
        else:
            buckets["later"].append(j)

    return render_template('deadline_tracker.html', buckets=buckets, all_jobs=enriched)

@app.route('/duplicates')
def duplicates_page():
    """Duplicate Detection & Corrigendum Audit Log center."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM duplicate_logs ORDER BY id DESC LIMIT 50")
    logs = cursor.fetchall()

    cursor.execute("SELECT * FROM jobs WHERE is_extended = 1 ORDER BY updated_at DESC")
    extended_jobs = cursor.fetchall()
    conn.close()

    enriched_extended = [enrich_job_with_deadline_meta(j) for j in extended_jobs]

    return render_template('duplicates.html', logs=logs, extended_jobs=enriched_extended)

@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    """Admin console to add notifications and trigger portal sync."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sync_result = None
    if request.method == 'POST' and 'sync_portals' in request.form:
        sync_result = run_simulated_portal_sync()
        flash("Official portals synchronized successfully!", "success")

    cursor.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 20")
    recent_jobs = cursor.fetchall()
    conn.close()

    return render_template('admin.html', recent_jobs=recent_jobs, sync_result=sync_result)

# ----------------- API ENDPOINTS -----------------

@app.route('/api/jobs')
def api_get_jobs():
    """JSON API to retrieve jobs with filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY deadline ASC")
    rows = cursor.fetchall()
    conn.close()

    jobs = [enrich_job_with_deadline_meta(r) for r in rows]
    return jsonify({"success": True, "count": len(jobs), "jobs": jobs})

@app.route('/api/check-eligibility', methods=['POST'])
def api_check_eligibility():
    """
    Evaluates candidate profile (DOB, category, qualification, stream)
    against all jobs or a specified job_id.
    """
    data = request.get_json() or {}
    dob = data.get('dob')
    category = data.get('category', 'General')
    qualification = data.get('qualification', 'Graduate')
    stream = data.get('stream', 'Any')
    job_id = data.get('job_id')

    if not dob:
        return jsonify({"success": False, "error": "Date of Birth is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if job_id:
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        rows = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM jobs ORDER BY deadline ASC")
        rows = cursor.fetchall()
    conn.close()

    candidate_profile = {
        "dob": dob,
        "category": category,
        "qualification": qualification,
        "stream": stream
    }

    results = []
    eligible_count = 0

    for r in rows:
        job_dict = enrich_job_with_deadline_meta(r)
        eval_res = evaluate_eligibility(candidate_profile, job_dict)
        job_dict['eligibility'] = eval_res
        if eval_res['eligible']:
            eligible_count += 1
        results.append(job_dict)

    # Sort so eligible jobs appear first
    results.sort(key=lambda x: (not x['eligibility']['eligible'], x['time_remaining_seconds']))

    age_meta = calculate_age_details(dob)

    return jsonify({
        "success": True,
        "candidate_age": age_meta['formatted'] if age_meta else "Unknown",
        "total_evaluated": len(results),
        "eligible_count": eligible_count,
        "results": results
    })

@app.route('/api/check-duplicate', methods=['POST'])
def api_check_duplicate():
    """Check duplicate status of job notification without adding."""
    data = request.get_json() or {}
    title = data.get('title', '')
    org = data.get('organization', '')
    advt = data.get('advt_no', '')

    res = audit_check_text(title, org, advt)
    return jsonify(res)

@app.route('/api/add-job', methods=['POST'])
def api_add_job():
    """Add a new job notification through duplicate detection engine."""
    data = request.get_json() or request.form.to_dict()
    if not data.get('title') or not data.get('organization') or not data.get('deadline'):
        return jsonify({"success": False, "error": "Title, Organization, and Deadline are required."}), 400

    res = process_job_notification(data)
    return jsonify(res)

@app.route('/api/subscribe-reminder', methods=['POST'])
def api_subscribe_reminder():
    """Subscribe user email for deadline reminders."""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    job_id = data.get('job_id')
    notify_days = int(data.get('notify_before_days', 3))

    if not email or '@' not in email:
        return jsonify({"success": False, "error": "A valid email address is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO reminders (email, job_id, notify_before_days, created_at)
        VALUES (?, ?, ?, ?)
    """, (email, job_id, notify_days, now_str))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Successfully subscribed {email} for deadline alerts {notify_days} days before closing!"
    })

@app.route('/api/send-instant-alert', methods=['POST'])
def api_send_instant_alert():
    """Trigger instant deadline reminder email simulation and return preview."""
    data = request.get_json() or {}
    email = data.get('email', 'applicant@example.com').strip()
    job_id = data.get('job_id')

    if not job_id:
        return jsonify({"success": False, "error": "Job ID is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()
    conn.close()

    if not job_row:
        return jsonify({"success": False, "error": "Job not found."}), 404

    job = enrich_job_with_deadline_meta(job_row)
    dispatch_result = record_and_dispatch_reminder(email, job, job['urgency_label'])

    return jsonify(dispatch_result)

@app.route('/api/calendar/<int:job_id>.ics')
def download_calendar(job_id):
    """Download standard iCalendar (.ics) event for Google / Apple / Outlook calendar."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()
    conn.close()

    if not job_row:
        return "Job not found", 404

    job = enrich_job_with_deadline_meta(job_row)
    ics_text = generate_ics_calendar(job)

    filename = f"gov-job-deadline-{job['advt_no'].replace('/', '_')}.ics"
    return Response(
        ics_text,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/sync-portals', methods=['POST'])
def api_sync_portals():
    """Trigger live portal crawler sync with duplicate detection."""
    sync_report = run_simulated_portal_sync()
    return jsonify({"success": True, "report": sync_report})

if __name__ == '__main__':
    print("Government Job Deadline Guardian running on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
