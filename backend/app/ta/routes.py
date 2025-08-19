from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Section

ta_bp = Blueprint('ta', __name__)

def _ensure_ta():
    if not current_user.is_authenticated or current_user.role != 'ta':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

@ta_bp.route('/', endpoint='ta_dashboard')
@login_required
def ta_dashboard():
    guard = _ensure_ta()
    if guard:
        return guard
    return render_template('lecturer_dashboard.html')

@ta_bp.route('/sections', endpoint='ta_sections')
@login_required
def ta_sections():
    guard = _ensure_ta()
    if guard:
        return guard
    sections = Section.query.filter_by(ta_id=current_user.id).all()
    # Reuse lecturer sections template structure but with TA-specific heading
    return render_template('lecturer_sections.html', sections=sections, ta_view=True)
