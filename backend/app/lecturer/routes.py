from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Section

lecturer_bp = Blueprint('lecturer', __name__)

def _ensure_lecturer():
    if not current_user.is_authenticated or current_user.role != 'lecturer':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

@lecturer_bp.route('/', endpoint='lecturer_dashboard')
@login_required
def lecturer_dashboard():
    guard = _ensure_lecturer()
    if guard:
        return guard
    return render_template('lecturer_dashboard.html')

@lecturer_bp.route('/sections', endpoint='lecturer_sections')
@login_required
def lecturer_sections():
    guard = _ensure_lecturer()
    if guard:
        return guard
    sections = Section.query.filter_by(instructor_id=current_user.id).all()
    return render_template('lecturer_sections.html', sections=sections)

# --- Alerts: Lecturer inbox and compose (manual multi-select of students they manage) ---
from app.models import Alert, AlertRecipient, Enrollment, User
from app.extensions import db

@lecturer_bp.route('/alerts', methods=['GET'], endpoint='lecturer_alerts_inbox')
@login_required
def lecturer_alerts_inbox():
    guard = _ensure_lecturer()
    if guard:
        return guard
    # Alerts addressed to this lecturer
    recs = (AlertRecipient.query
            .filter_by(recipient_id=current_user.id)
            .order_by(AlertRecipient.id.desc())
            .all())
    alert_ids = [r.alert_id for r in recs]
    alerts = []
    if alert_ids:
        alert_map = {a.id: a for a in Alert.query.filter(Alert.id.in_(alert_ids)).order_by(Alert.created_at.desc()).all()}
        for r in recs:
            a = alert_map.get(r.alert_id)
            if a:
                alerts.append({'rec': r, 'alert': a})
    # Mark as read
    unread = [r for r in recs if not r.is_read]
    if unread:
        for r in unread:
            r.is_read = True
        db.session.commit()
    return render_template('alerts_inbox.html', alerts=alerts, role='lecturer')


@lecturer_bp.route('/alerts/compose', methods=['GET', 'POST'], endpoint='lecturer_alerts_compose')
@login_required
def lecturer_alerts_compose():
    guard = _ensure_lecturer()
    if guard:
        return guard

    # Collect students enrolled in sections taught by this lecturer
    section_ids = [s.id for s in Section.query.filter_by(instructor_id=current_user.id).all()]
    student_ids = set()
    students = []
    if section_ids:
        enrollments = Enrollment.query.filter(Enrollment.section_id.in_(section_ids)).all()
        for enr in enrollments:
            if enr.student and enr.student.is_approved and enr.student.role == 'student':
                if enr.student.id not in student_ids:
                    student_ids.add(enr.student.id)
                    students.append(enr.student)

    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        body = (request.form.get('body') or '').strip()
        sel_ids = request.form.getlist('student_ids')
        if not title or not body:
            flash('Title and message body are required.', 'danger')
            return redirect(url_for('lecturer.lecturer_alerts_compose'))
        # Validate recipients are within managed students
        recipients = set()
        for sid in sel_ids:
            try:
                uid = int(sid)
                if uid in student_ids:
                    recipients.add(uid)
            except Exception:
                continue
        if not recipients:
            flash('Select at least one student.', 'danger')
            return redirect(url_for('lecturer.lecturer_alerts_compose'))

        alert = Alert(sender_id=current_user.id, sender_role='lecturer', title=title, body=body)
        db.session.add(alert)
        db.session.flush()
        for uid in recipients:
            db.session.add(AlertRecipient(alert_id=alert.id, recipient_id=uid, recipient_role='student'))
        db.session.commit()
        flash(f'Alert sent to {len(recipients)} student(s).', 'success')
        return redirect(url_for('lecturer.lecturer_alerts_inbox'))

    return render_template('alerts_compose.html', mode='lecturer', students=students)
