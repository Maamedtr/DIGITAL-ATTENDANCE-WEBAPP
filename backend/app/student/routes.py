from flask import Blueprint, render_template, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from sqlalchemy import and_
from app.models import Enrollment, ClassSession, Section, AttendanceRecord
import io, csv

student_bp = Blueprint('student', __name__)

def _ensure_student():
    if not current_user.is_authenticated or current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

@student_bp.route('/', endpoint='student_dashboard')
@login_required
def student_dashboard():
    guard = _ensure_student()
    if guard:
        return guard
    return render_template('student_dashboard.html')

@student_bp.route('/sessions', methods=['GET'], endpoint='student_sessions')
@login_required
def student_sessions():
    guard = _ensure_student()
    if guard:
        return guard
    open_sessions = (
        ClassSession.query
        .join(Section, ClassSession.section_id == Section.id)
        .join(Enrollment, and_(Enrollment.section_id == Section.id, Enrollment.student_id == current_user.id))
        .filter(ClassSession.status == 'open')
        .order_by(ClassSession.scheduled_start.desc())
        .all()
    )
    attended_session_ids = {
        rec.class_session_id for rec in AttendanceRecord.query.filter_by(student_id=current_user.id).all()
    }
    return render_template('student_sessions.html', open_sessions=open_sessions, attended_session_ids=attended_session_ids)


@student_bp.route('/attendance', methods=['GET'], endpoint='student_attendance')
@login_required
def student_attendance():
    guard = _ensure_student()
    if guard:
        return guard

    # Sections the student is enrolled in
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    sections = [enr.section for enr in enrollments]

    # Gather all session ids across enrolled sections
    all_sessions_by_section = {}
    all_session_ids = []
    for sec in sections:
        secsessions = (ClassSession.query
                       .filter_by(section_id=sec.id)
                       .order_by(ClassSession.scheduled_start.desc())
                       .all())
        all_sessions_by_section[sec.id] = secsessions
        all_session_ids.extend([s.id for s in secsessions])

    # Attendance records for this student across all those sessions
    attended_records = []
    if all_session_ids:
        attended_records = AttendanceRecord.query.filter(
            AttendanceRecord.student_id == current_user.id,
            AttendanceRecord.class_session_id.in_(all_session_ids)
        ).all()
    attended_by_session = {rec.class_session_id: rec for rec in attended_records}

    # Build per-section summaries
    per_section = []
    for sec in sections:
        sessions = all_sessions_by_section.get(sec.id, [])
        total = len(sessions)
        present = sum(1 for s in sessions if s.id in attended_by_session)
        pct = (present / total * 100.0) if total else 0.0
        per_section.append({
            'section': sec,
            'total': total,
            'present': present,
            'pct': pct
        })

    # Build recent sessions table across all sections (limit to 50)
    all_sessions_sorted = sorted(
        [s for sl in all_sessions_by_section.values() for s in sl],
        key=lambda s: s.scheduled_start,
        reverse=True
    )
    recent_sessions = []
    for s in all_sessions_sorted[:50]:
        rec = attended_by_session.get(s.id)
        recent_sessions.append({
            'session': s,
            'section': s.section,
            'course': s.section.course,
            'status': 'present' if rec else 'absent',
            'recorded_at': rec.recorded_at if rec else None
        })

    return render_template(
        'student_attendance.html',
        per_section=per_section,
        recent_sessions=recent_sessions
    )


@student_bp.route('/attendance.csv', methods=['GET'], endpoint='student_attendance_csv')
@login_required
def student_attendance_csv():
    guard = _ensure_student()
    if guard:
        return guard

    # Sections and sessions
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    sections = [enr.section for enr in enrollments]
    all_sessions = []
    for sec in sections:
        all_sessions.extend(
            ClassSession.query.filter_by(section_id=sec.id).order_by(ClassSession.scheduled_start.asc()).all()
        )
    session_by_id = {s.id: s for s in all_sessions}
    session_ids = list(session_by_id.keys())

    # Attendance records (only this student's)
    recs = []
    if session_ids:
        recs = AttendanceRecord.query.filter(
            AttendanceRecord.student_id == current_user.id,
            AttendanceRecord.class_session_id.in_(session_ids)
        ).all()
    attended_ids = {r.class_session_id for r in recs}
    rec_map = {r.class_session_id: r for r in recs}

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'section_code', 'course_code', 'course_title',
        'session_id', 'scheduled_start', 'scheduled_end',
        'status', 'recorded_at'
    ])

    # Write a row for every session across enrolled sections
    for s in sorted(all_sessions, key=lambda x: x.scheduled_start):
        sec = s.section
        course = sec.course
        rec = rec_map.get(s.id)
        status = 'present' if s.id in attended_ids else 'absent'
        recorded_at = rec.recorded_at.isoformat(timespec='seconds') if rec else ''
        writer.writerow([
            sec.section_code,
            course.code,
            course.title,
            s.id,
            s.scheduled_start.isoformat(timespec='minutes'),
            s.scheduled_end.isoformat(timespec='minutes'),
            status,
            recorded_at
        ])

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="my_attendance.csv"'
    return resp
