# System Overview

This document explains the architecture, data model, core flows, and current functionality of the Attendance MVP. It also highlights areas for improvement, reports on MVP completeness, and proposes next steps.

## Architecture

- Framework: Flask (Blueprint-based modular app)
- Persistence: SQLAlchemy ORM with SQLite (default), overrideable via DATABASE_URL
- Auth: Flask-Login (role-based guards)
- UI: Jinja templates, Tailwind via CDN
- Structure:
  - App factory: [backend/app/**init**.py](backend/app/__init__.py)
  - Configuration: [backend/app/config.py](backend/app/config.py)
  - Database and login manager: [backend/app/extensions.py](backend/app/extensions.py)
  - Models: [backend/app/models.py](backend/app/models.py)
  - Blueprints:
    - Admin: [backend/app/admin/routes.py](backend/app/admin/routes.py)
    - Lecturer: [backend/app/lecturer/routes.py](backend/app/lecturer/routes.py)
    - Student: [backend/app/student/routes.py](backend/app/student/routes.py)
    - TA: [backend/app/ta/routes.py](backend/app/ta/routes.py)
    - Auth: [backend/app/auth/routes.py](backend/app/auth/routes.py)
    - Attendance (sessions/marking/reporting): [backend/app/attendance/routes.py](backend/app/attendance/routes.py)
  - Templates: [backend/app/templates/](backend/app/templates/)
  - Entrypoint: [backend/run.py](backend/run.py)

Key runtime config in [backend/app/config.py](backend/app/config.py):

- DATABASE_URL, SECRET_KEY
- ATTENDANCE_CODE_TTL_MINUTES (default 15)
- BASE_URL (for absolute QR deep links; falls back to request.url_root)
- TESTING flag

## Data Model

Defined in [backend/app/models.py](backend/app/models.py):

- [models.User](backend/app/models.py:5)
  - Fields: username, email (unique), password (hash), role in {admin, lecturer, ta, student}, is_approved
- [models.Department](backend/app/models.py:13)
  - name (unique)
- [models.Course](backend/app/models.py:18)
  - code (unique), title, department_id
- [models.Timetable](backend/app/models.py:25)
  - Optional for MVP scheduling context
- [models.CourseAssignment](backend/app/models.py:34)
  - Optional legacy mapping for lecturer/ta to course
- [models.Section](backend/app/models.py:44)
  - course_id, section_code (unique per course), instructor_id, ta_id
  - Unique: (course_id, section_code)
- [models.Enrollment](backend/app/models.py:62)
  - section_id, student_id
  - Unique: (section_id, student_id)
- [models.ClassSession](backend/app/models.py:77)
  - section_id, scheduled_start, scheduled_end, status in {scheduled|open|closed}, open_code_hash, opened_at, closed_at
- [models.AttendanceRecord](backend/app/models.py:91)
  - class_session_id, student_id, status (present), recorded_at
  - Unique: (class_session_id, student_id)

## Core Flows

### Authentication and Roles

- Login/register in [backend/app/auth/routes.py](backend/app/auth/routes.py)
- Admin approval gate: non-admin users must be is_approved before access
- Role guards implemented across blueprints

### Admin Flow

- Approvals and CRUD for Departments/Courses/Sections/Enrollments in [backend/app/admin/routes.py](backend/app/admin/routes.py)
- Bulk enrollment upload (CSV) endpoint and UI:
  - Page and processing: [backend/app/admin/routes.py](backend/app/admin/routes.py)
  - UI: [backend/app/templates/admin_enrollments_upload.html](backend/app/templates/admin_enrollments_upload.html)
  - Link from: [backend/app/templates/admin_enrollments.html](backend/app/templates/admin_enrollments.html)
  - Behavior:
    - CSV: email, username(optional), section_id(optional if selected in UI)
    - Idempotent enrollment, optional creation of pending student accounts
    - Summarized results (enrolled, duplicates, created_pending, errors)

### Lecturer Flow

- Manage own sections in [backend/app/lecturer/routes.py](backend/app/lecturer/routes.py)
- Sessions lifecycle for a section in [attendance.lecturer_sessions()](backend/app/attendance/routes.py:28)
  - Create, list, view open code/QR, see attendance count, soft auto-close after TTL/end
- Open a session with code generation in [attendance.open_session()](backend/app/attendance/routes.py:118)
  - Generates 6-digit code, hashes it, sets status=open and opened_at
- Close a session in [attendance.close_session()](backend/app/attendance/routes.py:154)
- Review session attendance in [attendance.lecturer_session_attendance()](backend/app/attendance/routes.py:233)
  - Per-enrollment present/absent visualization
- Export session CSV in [attendance.lecturer_session_attendance_csv()](backend/app/attendance/routes.py:275)

### TA Flow

- TAs manage assisted sections (where Section.ta_id == TA.id) using the same lecturer endpoints
- Authorization sharing:
  - Role/membership checks in attendance helpers
- TA pages:
  - Dashboard: [backend/app/ta/routes.py](backend/app/ta/routes.py)
  - Assisted sections list (reusing lecturer sections template)
- TA capabilities mirror lecturer’s for their assigned sections:
  - Open/close sessions, view attendance, export CSV

### Student Flow

- See open sessions for enrolled sections in [backend/app/student/routes.py](backend/app/student/routes.py)
  - Page: student_sessions.html
- Mark attendance with code (while open and within TTL) in [attendance.student_mark()](backend/app/attendance/routes.py:177)
  - Validates role, enrollment, session open, code, TTL, idempotency
- Attendance history and per-section summaries:
  - Endpoint/UI: [backend/app/student/routes.py](backend/app/student/routes.py), [backend/app/templates/student_attendance.html](backend/app/templates/student_attendance.html)
  - CSV export for own attendance

### QR and TTL Behavior

- Absolute QR links for mobile: constructed in [attendance.lecturer_sessions()](backend/app/attendance/routes.py:28) using BASE_URL or request.url_root
- TTL enforcement (min(scheduled_end, opened_at+TTL)):
  - Student code submission blocked after expiry in [attendance.student_mark()](backend/app/attendance/routes.py:177)
  - Soft auto-close on lecturer session listing in [attendance.lecturer_sessions()](backend/app/attendance/routes.py:28)

### Reporting

- Lecturer: session-level attendance counts, detailed list, and CSV
- Admin: section-level sessions summary and section-level CSV
  - Admin pages: [backend/app/attendance/routes.py](backend/app/attendance/routes.py), [backend/app/templates/admin_attendance.html](backend/app/templates/admin_attendance.html)

## Templates

- Base layout and role-aware nav: [backend/app/templates/base.html](backend/app/templates/base.html)
- Admin pages:
  - Dashboard, approvals, departments, courses, sections, enrollments, bulk upload
- Lecturer pages:
  - Sections list: [backend/app/templates/lecturer_sections.html](backend/app/templates/lecturer_sections.html)
  - Sessions: [backend/app/templates/lecturer_sessions.html](backend/app/templates/lecturer_sessions.html)
  - Session attendance: [backend/app/templates/lecturer_session_attendance.html](backend/app/templates/lecturer_session_attendance.html)
- Student pages:
  - Dashboard, open sessions: [backend/app/templates/student_sessions.html](backend/app/templates/student_sessions.html)
  - Mark attendance: [backend/app/templates/student_mark_attendance.html](backend/app/templates/student_mark_attendance.html)
  - Attendance history: [backend/app/templates/student_attendance.html](backend/app/templates/student_attendance.html)
- Admin attendance overview: [backend/app/templates/admin_attendance.html](backend/app/templates/admin_attendance.html)

## Tests

- Student attendance flow: [backend/tests/test_attendance_marking.py](backend/tests/test_attendance_marking.py)
- TTL enforcement: [backend/tests/test_attendance_ttl.py](backend/tests/test_attendance_ttl.py)
- TA workflow: [backend/tests/test_ta_workflow.py](backend/tests/test_ta_workflow.py)

## Security and Authorization

- Role guards throughout (admin/lecturer/ta/student)
- Lecturer/TA access to sessions is constrained to their managed sections using helper checks in [backend/app/attendance/routes.py](backend/app/attendance/routes.py)
- Student attendance restricted to enrolled sections
- Session marking only within TTL and while session is open
- Unique constraints prevent duplicate enrollments and attendance rows

## Areas Needing Improvement

- CSRF protection
  - Forms currently post without explicit CSRF tokens; integrate Flask-WTF or server-side CSRF tokens for POST routes
- Error handling and DB integrity
  - Wrap attendance creation in try/except to handle race conditions on the unique constraint with a friendly message
- Input validation
  - Strengthen server-side validation for all forms (lengths, formats) and give field-level feedback in templates
- Rate limiting/throttling
  - Add per-IP throttles to student mark endpoint to reduce brute force on codes
- Auditing and observability
  - Log key events (session open/close, attendance attempts, CSV exports) with structured logs
- Background tasks
  - Replace “soft auto-close on GET” with scheduled jobs if/when a task runner is introduced; consider Alembic for schema migrations
- Authentication lifecycle
  - Password reset, email verification, SSO (optional for MVP but valuable in production)
- Access tests and coverage
  - Expand tests for admin CSV edge cases and lecturer/TA boundary conditions
- Performance and UX
  - Pagination for large lists (enrollments, sessions)
  - Real-time refresh for attendee counts during an open session (long-poll or websocket)
- Configuration hygiene
  - Require BASE_URL in production for QR correctness
  - Environment-specific config files
- Security of CSV upload
  - Enforce size limits and strict content type; sanitize and validate rows robustly

## MVP Completeness Report

Covered:

- Account roles and approvals (admin)
- Departments/courses/sections CRUD (admin)
- Enrollments CRUD + CSV bulk upload (admin)
- Lecturer session lifecycle (create/open/close), randomized codes, QR, TTL (lecturer)
- Student open sessions, code-based marking with TTL and idempotency (student)
- Student attendance history and CSV (student)
- Session reporting + CSV, counts, per-student status (lecturer)
- Section reporting + CSV (admin)
- TA workflow for assisted sections (open/close, reporting, exports) (ta)
- Tests for core flows (marking, TTL, TA)

Remaining for production-hardening (not strictly required for MVP):

- CSRF, stricter validation, rate limiting, error pages
- Background auto-close, full audit logs
- Migrations (Alembic) vs db.create_all()
- More test coverage and CI pipeline
- Mobile and accessibility polish

## Suggested Next Implementations

1. Harden security and reliability

- Add CSRF across POST forms and rate limit sensitive endpoints
- Implement audit logging for key actions
- Improve error pages and form-level validations
  Files to touch:
- [backend/app/attendance/routes.py](backend/app/attendance/routes.py)
- [backend/app/student/routes.py](backend/app/student/routes.py)
- [backend/app/admin/routes.py](backend/app/admin/routes.py)
- [backend/app/templates/\*](backend/app/templates/)

2. Migrations and environment setup

- Introduce Alembic migrations, split dev/test/prod config, and add seed scripts
- Dockerize app for reproducible runs; add CI job for tests
  Files to touch:
- [backend/app/config.py](backend/app/config.py)
- Alembic scaffolding (new)
- CI configuration (new)

3. Real-time attendance updates and UX polish

- Auto-refresh or real-time attendee counts on lecturer sessions
- Visual indicators for TTL countdown in student mark page (optional)
- Pagination and search for admin pages
  Files to touch:
- [backend/app/templates/lecturer_sessions.html](backend/app/templates/lecturer_sessions.html)
- [backend/app/attendance/routes.py](backend/app/attendance/routes.py)

4. Optional integrations

- SSO (university auth), email notifications for approvals or bulk enrollment feedback
- Export enhancements (XLSX), per-student semester summary downloads

## Key Endpoints Index (selected)

- Lecturers/TAs:
  - [attendance.lecturer_sessions()](backend/app/attendance/routes.py:28)
  - [attendance.open_session()](backend/app/attendance/routes.py:118)
  - [attendance.close_session()](backend/app/attendance/routes.py:154)
  - [attendance.lecturer_session_attendance()](backend/app/attendance/routes.py:233)
  - [attendance.lecturer_session_attendance_csv()](backend/app/attendance/routes.py:275)
- Students:
  - [attendance.student_mark()](backend/app/attendance/routes.py:177)
  - Student pages in [backend/app/student/routes.py](backend/app/student/routes.py)
- Admin:
  - Admin attendance pages in [backend/app/attendance/routes.py](backend/app/attendance/routes.py)
  - Bulk enrollment: [backend/app/admin/routes.py](backend/app/admin/routes.py)

## Runbook

- Install deps: `pip install -r` [backend/requirements.txt](backend/requirements.txt)
- Run: `python` [backend/run.py](backend/run.py)
- Default DB: [backend/attendance.db](backend/attendance.db) (overridable via DATABASE_URL)
- First-time:
  - Register users, approve in admin
  - Create departments/courses/sections
  - Enroll students (CSV optional)
  - Start sessions (lecturer/TA), students mark with code or QR link
