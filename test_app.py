"""
Comprehensive Verification Suite for Government Job Deadline Guardian.
Tests backend services, database integrity, duplicate detection,
eligibility evaluator, calendar generator, and Flask HTTP routes.
"""

import unittest
from datetime import datetime, date
from app import app
from database import init_db, get_db_connection
from services.duplicate_service import process_job_notification, audit_check_text, calculate_hash
from services.eligibility_service import evaluate_eligibility, calculate_age_details
from services.reminder_service import generate_ics_calendar, record_and_dispatch_reminder
from services.scraper_service import verify_official_link, run_simulated_portal_sync

from sample_data import seed_database

class TestJobGuardian(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        init_db()
        seed_database(silent=True)
        self._cleanup_test_data()

    def tearDown(self):
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM jobs WHERE advt_no LIKE 'TEST-%'")
        conn.execute("DELETE FROM duplicate_logs WHERE incoming_advt LIKE 'TEST-%'")
        conn.commit()
        conn.close()

    def test_database_has_jobs(self):
        """Verify database contains seeded jobs."""
        conn = get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 15, "Should have at least 15 seeded jobs.")

    def test_duplicate_detection_exact(self):
        """Verify exact duplicate gets flagged and ignored."""
        job = {
            "title": "National Testing Agency Recruitment 2026",
            "organization": "National Testing Agency",
            "advt_no": "TEST-NTA-2026",
            "category": "Civil Services",
            "state": "All India",
            "vacancies": 50,
            "min_age": 18,
            "max_age": 30,
            "min_qualification": "Graduate",
            "deadline": "2026-10-25 18:00:00"
        }
        # First insertion
        res1 = process_job_notification(job)
        self.assertIn(res1["status"], ["NEW_INSERTED", "DUPLICATE_IGNORED"])

        # Second insertion with same deadline -> DUPLICATE_IGNORED
        res2 = process_job_notification(job)
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")
        self.assertFalse(res2["is_new"])

    def test_corrigendum_extension(self):
        """Verify official deadline extension is recognized as a corrigendum."""
        job = {
            "title": "ISRO Assistant Recruitment 2026",
            "organization": "Indian Space Research Organisation (ISRO)",
            "advt_no": "TEST-ISRO-CORR-2026",
            "category": "Engineering/PSU",
            "state": "All India",
            "vacancies": 120,
            "min_age": 18,
            "max_age": 28,
            "min_qualification": "Graduate",
            "deadline": "2026-10-22 18:00:00"
        }
        process_job_notification(job)

        # Extended deadline
        job_extended = job.copy()
        job_extended["deadline"] = "2026-10-31 18:00:00"
        res = process_job_notification(job_extended)
        self.assertEqual(res["status"], "CORRIGENDUM_UPDATED")

    def test_eligibility_age_relaxation(self):
        """Test OBC candidate gets +3 years age relaxation."""
        sample_job = {
            "min_age": 21,
            "max_age": 30,
            "min_qualification": "Graduate",
            "stream_specialization": "Any",
            "age_relaxation_json": '{"OBC": 3, "SC": 5, "ST": 5}'
        }

        # Candidate born 1994-05-15 is ~32 years old as of Oct 2026
        # General UR should be OVER_AGE (max 30)
        profile_ur = {
            "dob": "1994-05-15",
            "category": "General",
            "qualification": "Graduate",
            "stream": "Any"
        }
        res_ur = evaluate_eligibility(profile_ur, sample_job, ref_date=date(2026, 10, 20))
        self.assertFalse(res_ur["eligible"])
        self.assertEqual(res_ur["status_type"], "OVER_AGE")

        # OBC candidate should be ELIGIBLE_RELAXED (max 30 + 3 = 33)
        profile_obc = {
            "dob": "1994-05-15",
            "category": "OBC",
            "qualification": "Graduate",
            "stream": "Any"
        }
        res_obc = evaluate_eligibility(profile_obc, sample_job, ref_date=date(2026, 10, 20))
        self.assertTrue(res_obc["eligible"])
        self.assertEqual(res_obc["status_type"], "ELIGIBLE_RELAXED")

    def test_official_link_verification(self):
        """Test trusted domain verification."""
        gov_url = "https://upsc.gov.in/examinations/notification"
        ver_gov = verify_official_link(gov_url)
        self.assertTrue(ver_gov["is_official"])

        fake_url = "https://freerarejobalerts.xyz/apply"
        ver_fake = verify_official_link(fake_url)
        self.assertFalse(ver_fake["is_official"])

    def test_calendar_ics_generation(self):
        """Test iCalendar generation."""
        job = {
            "id": 1,
            "title": "Civil Services Examination 2026",
            "organization": "UPSC",
            "advt_no": "04/2026-CSP",
            "vacancies": 1056,
            "salary_pay": "Level 10",
            "deadline": "2026-10-21 18:00:00",
            "official_apply_url": "https://upsconline.nic.in",
            "official_notification_url": "https://upsc.gov.in",
            "source_portal": "upsc.gov.in"
        }
        ics = generate_ics_calendar(job)
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("TRIGGER:-P3D", ics)
        self.assertIn("TRIGGER:-P1D", ics)
        self.assertIn("END:VCALENDAR", ics)

    def test_http_routes(self):
        """Verify all web pages and API routes return 200 OK."""
        # Index
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Deadline Guardian", resp.data)

        # Job detail
        resp = self.client.get('/job/1')
        self.assertEqual(resp.status_code, 200)

        # Eligibility page
        resp = self.client.get('/eligibility')
        self.assertEqual(resp.status_code, 200)

        # Deadline tracker page
        resp = self.client.get('/deadlines')
        self.assertEqual(resp.status_code, 200)

        # Duplicates audit page
        resp = self.client.get('/duplicates')
        self.assertEqual(resp.status_code, 200)

        # Admin page
        resp = self.client.get('/admin')
        self.assertEqual(resp.status_code, 200)

        # API: jobs
        resp = self.client.get('/api/jobs')
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data["success"])

        # API: check eligibility
        resp = self.client.post('/api/check-eligibility', json={
            "dob": "1998-05-15",
            "category": "OBC",
            "qualification": "Graduate",
            "stream": "Any"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreater(data["eligible_count"], 0)

        # API: calendar download
        resp = self.client.get('/api/calendar/1.ics')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'text/calendar')

    def test_admin_portal_sync(self):
        """Verify POST /admin with sync_portals executes and renders template properly."""
        resp = self.client.post('/admin', data={'sync_portals': '1'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Sync Complete", resp.data)
        self.assertIn(b"UPSC Official Gazette Feed", resp.data)

    def test_api_add_job_validation_and_duplicate(self):
        """Verify POST /api/add-job handles validation and duplicate flagging."""
        # Missing required fields
        bad_resp = self.client.post('/api/add-job', json={"title": "Missing Org"})
        self.assertEqual(bad_resp.status_code, 400)

        # Valid addition
        new_job = {
            "title": "TEST HAL Management Trainee 2026",
            "organization": "Hindustan Aeronautics Limited (HAL)",
            "advt_no": "TEST-HAL-MT-2026",
            "category": "Engineering/PSU",
            "state": "Karnataka",
            "vacancies": 80,
            "min_age": 21,
            "max_age": 28,
            "min_qualification": "B.Tech/BE",
            "deadline": "2026-11-25 18:00:00"
        }
        resp1 = self.client.post('/api/add-job', json=new_job)
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        self.assertIn(data1["status"], ["NEW_INSERTED", "DUPLICATE_IGNORED"])

        # Second addition should be duplicate
        resp2 = self.client.post('/api/add-job', json=new_job)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertEqual(data2["status"], "DUPLICATE_IGNORED")

    def test_api_reminder_subscription_and_dispatch(self):
        """Verify reminder subscription and instant alert preview dispatch."""
        # Invalid email
        bad_sub = self.client.post('/api/subscribe-reminder', json={"email": "notanemail", "job_id": 1})
        self.assertEqual(bad_sub.status_code, 400)

        # Valid subscription
        good_sub = self.client.post('/api/subscribe-reminder', json={"email": "applicant@test.gov.in", "job_id": 1, "notify_before_days": 3})
        self.assertEqual(good_sub.status_code, 200)
        self.assertTrue(good_sub.get_json()["success"])

        # Instant alert preview dispatch
        alert_resp = self.client.post('/api/send-instant-alert', json={"email": "applicant@test.gov.in", "job_id": 1})
        self.assertEqual(alert_resp.status_code, 200)
        alert_data = alert_resp.get_json()
        self.assertTrue(alert_data["success"])
        self.assertIn("html_preview", alert_data)
        self.assertIn("Application Deadline", alert_data["html_preview"])

    def test_job_not_found_handling(self):
        """Verify requesting non-existent job handles cleanly."""
        resp = self.client.get('/job/999999', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        cal_resp = self.client.get('/api/calendar/999999.ics')
        self.assertEqual(cal_resp.status_code, 404)

    def test_index_filters_and_sorting(self):
        """Verify search filters and sorting options execute without SQL errors."""
        filters = [
            '/?q=UPSC',
            '/?category=Civil+Services',
            '/?state=All+India',
            '/?qualification=Graduate',
            '/?urgency=24h',
            '/?urgency=48h',
            '/?urgency=7d',
            '/?urgency=active',
            '/?urgency=extended',
            '/?sort=urgency',
            '/?sort=newest',
            '/?sort=vacancies'
        ]
        for url in filters:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Filter URL {url} failed with {resp.status_code}")

if __name__ == '__main__':
    unittest.main()
