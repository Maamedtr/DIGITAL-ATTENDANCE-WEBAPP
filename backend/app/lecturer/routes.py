from flask import Blueprint, render_template, redirect, url_for, flash
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
