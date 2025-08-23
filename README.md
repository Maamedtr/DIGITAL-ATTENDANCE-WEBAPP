# DIGITAL-ATTENDANCE-WEBAPP

Admin / School Management
Purpose: Full control over the system, database, and analytics
Dashboard Features
• Analytics & Reports
• Overall attendance percentage per day, week, month
Absentee trends & frequent absentees list

Student & Teacher Management
• Add/edit/remove student and teacher accounts.

Attendance Monitoring
• Live class attendance overview.
• Ability to edit or approve attendance corrections.
• Notifications
• Platform-wide announcements.
• Database Control
• Audit logs of attendance edits.

2. Teacher/ Assistant
   Purpose: Mark attendance, monitor student participation, and view analytics for their classes.
   Dashboard Features
   • Class Overview

Daily and monthly attendance percentage.
Attendance Marking
• Manual marking (present/absent/late).
• QR code based auto marking from student side.
Notifications
• Option to send absence reminders to students

3. Student
   Purpose: Add and Track personal attendance and get notified about absences.
   Dashboard Features
   • Attendance Overview
   • Get timetables
   • Calendar view with marked absences and presences based on timetable

Notifications
• Get Alerts for low attendance.
• get Class or school announcements

Profile & History
• Edit personal details.
• View detailed attendance logs.

---

## MVP Run & Configuration

Quick start

- Create and activate a virtualenv, then install dependencies:
  - pip install -r backend/requirements.txt
- Run the app:
  - python backend/run.py

Environment variables (configure before running)

- SECRET_KEY: Flask secret key for sessions and CSRF (required in production)
- DATABASE_URL: SQLAlchemy URL (default: sqlite:///attendance.db)
- ATTENDANCE_CODE_TTL_MINUTES: Minutes a session code remains valid (default: 15)
- BASE_URL: Absolute base URL used in QR deep links (e.g., https://example.edu). If not set, request.url_root is used.
- TESTING: Set to 1 to disable CSRF checks in tests and enable testing behaviors

Example (PowerShell):

- $env:SECRET_KEY = "change-me"
- $env:DATABASE_URL = "sqlite:///attendance.db"
- $env:ATTENDANCE_CODE_TTL_MINUTES = "15"
- $env:BASE_URL = "http://localhost:5000"

CSRF protection (MVP)

- CSRF is enforced for all POST/PUT/PATCH/DELETE requests via a custom middleware in [backend/app/**init**.py](backend/app/__init__.py)
- All forms have been updated to include {{ csrf_field }} (hidden input) to pass the token
- In testing mode (TESTING=1), CSRF checks are bypassed for simplicity

Testing

- Run the tests (pytest is required; install with pip install pytest):
  - pytest backend/tests -q

Included test coverage

- Student attendance marking + idempotency: [backend/tests/test_attendance_marking.py](backend/tests/test_attendance_marking.py)
- TTL enforcement: [backend/tests/test_attendance_ttl.py](backend/tests/test_attendance_ttl.py)
- TA workflow authorization and operations: [backend/tests/test_ta_workflow.py](backend/tests/test_ta_workflow.py)
- Admin bulk enrollment CSV edge cases: [backend/tests/test_admin_bulk_enrollment.py](backend/tests/test_admin_bulk_enrollment.py)

Operational notes

- Soft auto-close of expired sessions occurs on lecturer/TA sessions page load, based on min(scheduled_end, opened_at + ATTENDANCE_CODE_TTL_MINUTES)
- Student code submissions are rate-limited by IP and rejected after TTL expiry or session end
- Logging: session open/close, successful/duplicate attendance, wrong codes, and rate-limited attempts are logged via current_app.logger

Deployment checklist

- Set strong SECRET_KEY and configure DATABASE_URL to a production database
- Set BASE_URL so QR deep links resolve correctly on mobile
- Consider introducing Alembic migrations before schema changes (replace db.create_all)
- Reverse proxy should set X-Forwarded-For to preserve client IPs for rate limiting
