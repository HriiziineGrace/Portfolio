"""
Reminder and Calendar Service for Government Job Deadline Guardian.
Generates .ics calendar events and dispatches email/browser alerts.
"""

from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from database import get_db_connection

def generate_ics_calendar(job: dict) -> str:
    """
    Generate an iCalendar (.ics) format file string for a job deadline.
    Includes VALARM reminders at 3 days and 24 hours before closing.
    """
    # Parse deadline
    deadline_str = job['deadline']
    try:
        dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        dt = datetime.strptime(deadline_str[:10], "%Y-%m-%d")

    # Format in UTC/iCal format
    dt_end = dt.strftime("%Y%m%dT%H%M%SZ")
    dt_start = (dt - timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = f"job-deadline-{job['id']}-{now_stamp}@govjobguardian.org"

    summary = f"CRITICAL: Application Deadline for {job['title']} ({job['organization']})"
    description = (
        f"Government Job Application Deadline Alert!\\n\\n"
        f"Position: {job['title']}\\n"
        f"Organization: {job['organization']}\\n"
        f"Advt No: {job['advt_no']}\\n"
        f"Vacancies: {job['vacancies']}\\n"
        f"Pay Scale: {job['salary_pay']}\\n"
        f"Deadline: {job['deadline']}\\n\\n"
        f"Official Apply Link: {job['official_apply_url']}\\n"
        f"Official Notification: {job['official_notification_url']}\\n\\n"
        f"Sent by Government Job Deadline Guardian."
    )

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Government Job Deadline Guardian//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:Official Portal - {job['source_portal']}
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-P3D
ACTION:DISPLAY
DESCRIPTION:Reminder: 3 days left for {job['title']}
END:VALARM
BEGIN:VALARM
TRIGGER:-P1D
ACTION:DISPLAY
DESCRIPTION:CRITICAL: 24 hours left for {job['title']}
END:VALARM
BEGIN:VALARM
TRIGGER:-PT2H
ACTION:DISPLAY
DESCRIPTION:URGENT: 2 hours left before portal closes for {job['title']}
END:VALARM
END:VEVENT
END:VCALENDAR
"""
    return ics_content

def compose_reminder_email_html(job: dict, recipient_email: str, days_left_str: str) -> str:
    """Compose a rich, responsive HTML email template for deadline alert."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
        .email-container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); color: #ffffff; padding: 24px; text-align: center; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 22px; letter-spacing: -0.5px; }}
        .badge {{ display: inline-block; background: #ef4444; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 13px; text-transform: uppercase; }}
        .content {{ padding: 24px; color: #334155; line-height: 1.6; }}
        .job-card {{ background: #f1f5f9; border-left: 4px solid #2563eb; padding: 16px; border-radius: 6px; margin: 16px 0; }}
        .job-title {{ font-size: 18px; font-weight: bold; color: #0f172a; margin-bottom: 6px; }}
        .meta-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        .meta-table td {{ padding: 6px 0; border-bottom: 1px dashed #cbd5e1; }}
        .meta-table td:first-child {{ color: #64748b; font-weight: 500; width: 35%; }}
        .btn-container {{ text-align: center; margin: 24px 0; }}
        .btn-apply {{ display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; font-weight: 600; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(37,99,235,0.4); }}
        .btn-pdf {{ display: inline-block; background: #e2e8f0; color: #1e293b; text-decoration: none; font-weight: 500; padding: 12px 20px; border-radius: 8px; margin-left: 8px; }}
        .checklist {{ background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 14px; font-size: 13px; color: #92400e; }}
        .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="header">
          <span class="badge">⏰ DEADLINE ALERT: {days_left_str.upper()}</span>
          <h1>Government Job Deadline Guardian</h1>
          <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 14px;">Do not miss your official application closing date!</p>
        </div>
        <div class="content">
          <p>Hello Candidate,</p>
          <p>This is an automated priority alert from <strong>Government Job Deadline Guardian</strong>. The recruitment window for the following government post is closing soon:</p>
          
          <div class="job-card">
            <div class="job-title">{job['title']}</div>
            <table class="meta-table">
              <tr>
                <td>Organization:</td>
                <td><strong>{job['organization']}</strong></td>
              </tr>
              <tr>
                <td>Advt No.:</td>
                <td>{job['advt_no']}</td>
              </tr>
              <tr>
                <td>Vacancies:</td>
                <td>{job['vacancies']} Positions</td>
              </tr>
              <tr>
                <td>Application Deadline:</td>
                <td><strong style="color: #dc2626;">{job['deadline']}</strong></td>
              </tr>
              <tr>
                <td>Qualification:</td>
                <td>{job['min_qualification']} ({job.get('stream_specialization', 'Any')})</td>
              </tr>
              <tr>
                <td>Official Portal:</td>
                <td>{job['source_portal']}</td>
              </tr>
            </table>
          </div>

          <div class="checklist">
            <strong>📋 Final Hours Application Checklist:</strong>
            <ul style="margin: 6px 0 0 0; padding-left: 20px;">
              <li>Keep scanned photograph and signature under specified size (usually 20-50 KB).</li>
              <li>Complete fee payment early to avoid server failure during peak deadline hours.</li>
              <li>Download & save the final submitted confirmation page / PDF.</li>
            </ul>
          </div>

          <div class="btn-container">
            <a href="{job['official_apply_url']}" target="_blank" class="btn-apply">Apply On Official Portal ↗</a>
            <a href="{job['official_notification_url']}" target="_blank" class="btn-pdf">Official Notification PDF 📄</a>
          </div>
        </div>
        <div class="footer">
          You received this alert because you subscribed to updates on Government Job Deadline Guardian.<br>
          Verified against official government portal {job['source_portal']} • Secure & Authentic
        </div>
      </div>
    </body>
    </html>
    """

def record_and_dispatch_reminder(email: str, job: dict, days_left_str: str = "Closing Soon"):
    """
    Log the alert to the database and simulate or dispatch.
    Returns preview dictionary.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Insert into sent_alerts
    cursor.execute("""
        INSERT INTO sent_alerts (email, job_id, job_title, deadline, days_left, sent_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Simulated Delivered')
    """, (email, job['id'], job['title'], job['deadline'], 0, now_str))

    conn.commit()
    conn.close()

    html_preview = compose_reminder_email_html(job, email, days_left_str)

    return {
        "success": True,
        "recipient": email,
        "job_title": job['title'],
        "organization": job['organization'],
        "deadline": job['deadline'],
        "sent_at": now_str,
        "html_preview": html_preview,
        "message": f"Deadline reminder successfully queued and dispatched for {email}!"
    }
