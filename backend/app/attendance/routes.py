from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import secrets
import segno
import io, csv
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import Section, ClassSession, Enrollment, AttendanceRecord

attendance_bp = Blueprint('attendance', __name__)

# --------- Helpers ---------
def _require_role(role: str):
    if not current_user.is_authenticated or current_user.role != role:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

def _parse_dt_local(value: str) -> datetime:
    # Expecting input from <input type="datetime-local"> => "YYYY-MM-DDTHH:MM"
    return datetime.strptime(value, '%Y-%m-%dT%H:%M')

def _require_roles(*roles):
    if not current_user.is_authenticated or current_user.role not in roles:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

def _is_section_manager(section: Section) -> bool:
    try:
        if current_user.role == 'lecturer':
            return section.instructor_id == current_user.id
        if current_user.role == 'ta':
            return section.ta_id == current_user.id
    except Exception:
        return False
    return False

# --------- Lecturer: Sessions for a Section ---------
@attendance_bp.route('/lecturer/sections/<int:section_id>/sessions', methods=['GET', 'POST'], endpoint='lecturer_sessions')
@login_required
def lecturer_sessions(section_id: int):
    guard = _require_roles('lecturer', 'ta')
    if guard:
        return guard

    section = Section.query.get_or_404(section_id)
    if not _is_section_manager(section):
        flash('You may only manage your assigned sections.', 'danger')
        return redirect(url_for('ta.ta_dashboard') if getattr(current_user, 'role', None) == 'ta' else url_for('lecturer.lecturer_dashboard'))

    if request.method == 'POST':
        try:
            start_raw = request.form.get('scheduled_start', '').strip()
            end_raw = request.form.get('scheduled_end', '').strip()
            if not start_raw or not end_raw:
                raise ValueError('Start and end are required.')
            scheduled_start = _parse_dt_local(start_raw)
            scheduled_end = _parse_dt_local(end_raw)
            if scheduled_end <= scheduled_start:
                raise ValueError('End must be after start.')
            sess = ClassSession(
                section_id=section.id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                status='scheduled'
            )
            db.session.add(sess)
            db.session.commit()
            flash('Class session created.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create session: {e}', 'danger')
        return redirect(url_for('attendance.lecturer_sessions', section_id=section.id))

    sessions = ClassSession.query.filter_by(section_id=section.id).order_by(ClassSession.scheduled_start.desc()).all()
    
    # Soft auto-close expired open sessions (based on scheduled_end and TTL)
    now_utc = datetime.utcnow()
    ttl_minutes = current_app.config.get('ATTENDANCE_CODE_TTL_MINUTES', 15)
    changed = False
    for s in sessions:
        if s.status == 'open':
            # Compute expiry: min(scheduled_end, opened_at + TTL) when opened_at exists
            if s.opened_at:
                expires_at = min(s.scheduled_end, s.opened_at + timedelta(minutes=ttl_minutes))
            else:
                expires_at = s.scheduled_end
            if now_utc > expires_at:
                s.status = 'closed'
                s.closed_at = now_utc
                changed = True
    if changed:
        db.session.commit()
    
    opened_code = request.args.get('code')
    opened_session_id = request.args.get('opened_session_id', type=int)
    qr_svg = None
    opened_attendee_count = None
    opened_expires_at = None
    if opened_code and opened_session_id:
        # Build QR payload deep link (absolute URL): /student/sessions/{id}/mark?code=NNNNNN
        base_url = (current_app.config.get('BASE_URL') or request.url_root).rstrip('/')
        path = url_for('attendance.student_mark', session_id=opened_session_id)
        payload_url = f"{base_url}{path}?code={opened_code}"
        qr = segno.make(payload_url)
        # data URI SVG for easy embedding
        qr_svg = qr.svg_data_uri(scale=5)
        # Count attendees for this opened session
        opened_attendee_count = AttendanceRecord.query.filter_by(class_session_id=opened_session_id).count()
        # Compute expiry time for banner display
        opened_sess = next((s for s in sessions if s.id == opened_session_id), None)
        if opened_sess:
            if opened_sess.opened_at:
                opened_expires_at = min(opened_sess.scheduled_end, opened_sess.opened_at + timedelta(minutes=ttl_minutes))
            else:
                opened_expires_at = opened_sess.scheduled_end
    
    return render_template('lecturer_sessions.html',
                           section=section,
                           sessions=sessions,
                           opened_code=opened_code,
                           opened_session_id=opened_session_id,
                           qr_svg=qr_svg,
                           opened_attendee_count=opened_attendee_count,
                           opened_expires_at=opened_expires_at,
                           now_utc=now_utc)

# --------- Lecturer: Open/Close Session ---------
@attendance_bp.route('/lecturer/sessions/<int:session_id>/open', methods=['POST'], endpoint='open_session')
@login_required
def open_session(session_id: int):
    guard = _require_roles('lecturer', 'ta')
    if guard:
        return guard

    sess = ClassSession.query.get_or_404(session_id)
    if not _is_section_manager(sess.section):
        flash('You may only open sessions for your assigned sections.', 'danger')
        return redirect(url_for('ta.ta_dashboard') if getattr(current_user, 'role', None) == 'ta' else url_for('lecturer.lecturer_dashboard'))

    if sess.status == 'closed':
        flash('Cannot reopen a closed session.', 'danger')
        return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id))
    
    # Prevent opening a session that is already open
    if sess.status == 'open':
        flash('Session already open.', 'warning')
        return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id))
    
    # Prevent multiple open sessions for the same section
    existing_open = ClassSession.query.filter_by(section_id=sess.section_id, status='open').first()
    if existing_open and existing_open.id != sess.id:
        flash('Another session for this section is already open.', 'danger')
        return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id))
    
    code = f"{secrets.randbelow(1_000_000):06d}"
    sess.open_code_hash = generate_password_hash(code)
    sess.status = 'open'
    sess.opened_at = datetime.utcnow()
    db.session.commit()
    flash('Session opened. Code generated.', 'success')
    return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id,
                            opened_session_id=sess.id, code=code))

@attendance_bp.route('/lecturer/sessions/<int:session_id>/close', methods=['POST'], endpoint='close_session')
@login_required
def close_session(session_id: int):
    guard = _require_roles('lecturer', 'ta')
    if guard:
        return guard

    sess = ClassSession.query.get_or_404(session_id)
    if not _is_section_manager(sess.section):
        flash('You may only close sessions for your assigned sections.', 'danger')
        return redirect(url_for('ta.ta_dashboard') if getattr(current_user, 'role', None) == 'ta' else url_for('lecturer.lecturer_dashboard'))

    if sess.status != 'open':
        flash('Session is not open.', 'warning')
        return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id))

    sess.status = 'closed'
    sess.closed_at = datetime.utcnow()
    db.session.commit()
    flash('Session closed.', 'success')
    return redirect(url_for('attendance.lecturer_sessions', section_id=sess.section_id))

# --------- Student: Mark Attendance ---------
@attendance_bp.route('/student/sessions/<int:session_id>/mark', methods=['GET', 'POST'], endpoint='student_mark')
@login_required
def student_mark(session_id: int):
    guard = _require_role('student')
    if guard:
        return guard

    sess = ClassSession.query.get_or_404(session_id)
    
    # Must be open
    if sess.status != 'open' or not sess.open_code_hash:
        flash('Session is not open for marking.', 'danger')
        return redirect(url_for('student.student_sessions'))
    
    # Must be enrolled
    enrolled = Enrollment.query.filter_by(section_id=sess.section_id, student_id=current_user.id).first()
    if not enrolled:
        flash('You are not enrolled in this section.', 'danger')
        return redirect(url_for('student.student_sessions'))
    
    # Enforce TTL and scheduled_end expiry
    now_utc = datetime.utcnow()
    ttl_minutes = current_app.config.get('ATTENDANCE_CODE_TTL_MINUTES', 15)
    if sess.opened_at:
        expires_at = min(sess.scheduled_end, sess.opened_at + timedelta(minutes=ttl_minutes))
    else:
        expires_at = sess.scheduled_end
    if now_utc > expires_at:
        flash('Session has expired for marking.', 'danger')
        return redirect(url_for('student.student_sessions'))
    
    prefill_code = request.args.get('code', '')
    # Check if attendance already recorded to adjust UI and idempotency
    already_marked = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=current_user.id).first() is not None
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code or len(code) != 6 or not code.isdigit():
            flash('Invalid code format.', 'danger')
            return redirect(url_for('attendance.student_mark', session_id=session_id))
        if not check_password_hash(sess.open_code_hash, code):
            flash('Incorrect code.', 'danger')
            return redirect(url_for('attendance.student_mark', session_id=session_id))
    
        if already_marked:
            flash('Attendance already recorded for this session.', 'info')
            return redirect(url_for('student.student_sessions'))
    
        rec = AttendanceRecord(class_session_id=sess.id, student_id=current_user.id, status='present')
        db.session.add(rec)
        db.session.commit()
        flash('Attendance recorded as present.', 'success')
        return redirect(url_for('student.student_sessions'))
    
    return render_template('student_mark_attendance.html', session=sess, prefill_code=prefill_code, already_marked=already_marked)
# --------- Lecturer: Session Attendance Review and CSV ---------
@attendance_bp.route('/lecturer/sessions/<int:session_id>/attendance', methods=['GET'], endpoint='lecturer_session_attendance')
@login_required
def lecturer_session_attendance(session_id: int):
    guard = _require_roles('lecturer', 'ta')
    if guard:
        return guard

    sess = ClassSession.query.get_or_404(session_id)
    section = sess.section
    if not _is_section_manager(section):
        flash('You may only review attendance for your assigned sections.', 'danger')
        return redirect(url_for('ta.ta_sections') if getattr(current_user, 'role', None) == 'ta' else url_for('lecturer.lecturer_sections'))

    enrollments = Enrollment.query.filter_by(section_id=section.id).all()
    present_records = AttendanceRecord.query.filter_by(class_session_id=sess.id).all()
    present_ids = {rec.student_id for rec in present_records}

    students = []
    for enr in enrollments:
        stu = enr.student
        students.append({
            'id': stu.id,
            'username': stu.username,
            'email': stu.email,
            'status': 'present' if stu.id in present_ids else 'absent'
        })

    total = len(enrollments)
    present = len(present_ids)
    pct = (present / total * 100.0) if total else 0.0

    return render_template(
        'lecturer_session_attendance.html',
        section=section,
        session=sess,
        students=students,
        total=total,
        present=present,
        pct=pct
    )


@attendance_bp.route('/lecturer/sessions/<int:session_id>/attendance.csv', methods=['GET'], endpoint='lecturer_session_attendance_csv')
@login_required
def lecturer_session_attendance_csv(session_id: int):
    guard = _require_roles('lecturer', 'ta')
    if guard:
        return guard

    sess = ClassSession.query.get_or_404(session_id)
    section = sess.section
    if not _is_section_manager(section):
        flash('You may only export attendance for your assigned sections.', 'danger')
        return redirect(url_for('ta.ta_sections') if getattr(current_user, 'role', None) == 'ta' else url_for('lecturer.lecturer_sections'))

    enrollments = Enrollment.query.filter_by(section_id=section.id).all()
    recs = AttendanceRecord.query.filter_by(class_session_id=sess.id).all()
    rec_map = {r.student_id: r for r in recs}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'session_id', 'section_code', 'scheduled_start', 'scheduled_end',
        'student_id', 'username', 'email', 'status', 'recorded_at'
    ])

    for enr in enrollments:
        stu = enr.student
        rec = rec_map.get(stu.id)
        status = 'present' if rec else 'absent'
        recorded_at = rec.recorded_at.isoformat(timespec='seconds') if rec else ''
        writer.writerow([
            sess.id,
            section.section_code,
            sess.scheduled_start.isoformat(timespec='minutes'),
            sess.scheduled_end.isoformat(timespec='minutes'),
            stu.id,
            stu.username,
            stu.email,
            status,
            recorded_at
        ])

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="session_{sess.id}_attendance.csv"'
    return resp


# --------- Admin: Section Attendance Overview and CSV ---------
@attendance_bp.route('/admin/sections/<int:section_id>/attendance', methods=['GET'], endpoint='admin_section_attendance')
@login_required
def admin_section_attendance(section_id: int):
    guard = _require_role('admin')
    if guard:
        return guard

    section = Section.query.get_or_404(section_id)
    sessions = ClassSession.query.filter_by(section_id=section.id).order_by(ClassSession.scheduled_start.desc()).all()

    session_rows = []
    total_enrolled = Enrollment.query.filter_by(section_id=section.id).count()
    for sess in sessions:
        present = AttendanceRecord.query.filter_by(class_session_id=sess.id).count()
        pct = (present / total_enrolled * 100.0) if total_enrolled else 0.0
        session_rows.append({
            'session': sess,
            'present': present,
            'total': total_enrolled,
            'pct': pct
        })

    return render_template(
        'admin_attendance.html',
        section=section,
        session_rows=session_rows
    )


@attendance_bp.route('/admin/sections/<int:section_id>/attendance.csv', methods=['GET'], endpoint='admin_section_attendance_csv')
@login_required
def admin_section_attendance_csv(section_id: int):
    guard = _require_role('admin')
    if guard:
        return guard

    section = Section.query.get_or_404(section_id)
    sessions = ClassSession.query.filter_by(section_id=section.id).order_by(ClassSession.scheduled_start.asc()).all()
    enrollments = Enrollment.query.filter_by(section_id=section.id).all()

    # Preload attendance into maps for quick lookup
    attendance_by_session = {}
    for sess in sessions:
        recs = AttendanceRecord.query.filter_by(class_session_id=sess.id).all()
        attendance_by_session[sess.id] = {r.student_id: r for r in recs}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'session_id', 'session_start', 'session_end',
        'student_id', 'username', 'email', 'status', 'recorded_at'
    ])

    for sess in sessions:
        rec_map = attendance_by_session.get(sess.id, {})
        for enr in enrollments:
            stu = enr.student
            rec = rec_map.get(stu.id)
            status = 'present' if rec else 'absent'
            recorded_at = rec.recorded_at.isoformat(timespec='seconds') if rec else ''
            writer.writerow([
                sess.id,
                sess.scheduled_start.isoformat(timespec='minutes'),
                sess.scheduled_end.isoformat(timespec='minutes'),
                stu.id,
                stu.username,
                stu.email,
                status,
                recorded_at
            ])

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="section_{section.id}_attendance.csv"'
    return resp