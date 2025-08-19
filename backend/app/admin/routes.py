from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User, Department, Course, Section, Enrollment
import io, csv
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__)

# -------- Helpers --------
def _ensure_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return None

# -------- Dashboard & Approvals --------
@admin_bp.route('/', endpoint='admin_dashboard')
@login_required
def admin_dashboard():
    guard = _ensure_admin()
    if guard:
        return guard
    pending_users = User.query.filter_by(is_approved=False).all()
    return render_template('admin_dashboard.html', pending_users=pending_users)

@admin_bp.route('/users/approvals', methods=['GET'], endpoint='users_approvals')
@login_required
def users_approvals():
    guard = _ensure_admin()
    if guard:
        return guard
    pending_users = User.query.filter_by(is_approved=False).all()
    return render_template('admin_users_approvals.html', pending_users=pending_users)

@admin_bp.route('/approve/<int:user_id>', methods=['POST'], endpoint='approve_user')
@login_required
def approve_user(user_id):
    guard = _ensure_admin()
    if guard:
        return guard
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'User {user.username} approved.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/reject/<int:user_id>', methods=['POST'], endpoint='reject_user')
@login_required
def reject_user(user_id):
    guard = _ensure_admin()
    if guard:
        return guard
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} rejected and deleted.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

# -------- Departments --------
@admin_bp.route('/departments', methods=['GET', 'POST'], endpoint='manage_departments')
@login_required
def manage_departments():
    guard = _ensure_admin()
    if guard:
        return guard
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name and not Department.query.filter_by(name=name).first():
            dept = Department(name=name)
            db.session.add(dept)
            db.session.commit()
            flash('Department added.', 'success')
        else:
            flash('Invalid or duplicate department name.', 'danger')
        return redirect(url_for('admin.manage_departments'))
    departments = Department.query.all()
    return render_template('departments.html', departments=departments)

@admin_bp.route('/departments/delete/<int:dept_id>', methods=['POST'], endpoint='delete_department')
@login_required
def delete_department(dept_id):
    guard = _ensure_admin()
    if guard:
        return guard
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    flash('Department deleted.', 'success')
    return redirect(url_for('admin.manage_departments'))

# -------- Courses --------
@admin_bp.route('/courses', methods=['GET', 'POST'], endpoint='manage_courses')
@login_required
def manage_courses():
    guard = _ensure_admin()
    if guard:
        return guard
    departments = Department.query.all()
    if request.method == 'POST':
        code = request.form['code'].strip().upper()
        title = request.form['title'].strip()
        department_id = request.form['department_id']
        if not code or not title or not department_id:
            flash('All fields are required.', 'danger')
        elif Course.query.filter_by(code=code).first():
            flash('Course code already exists.', 'danger')
        else:
            course = Course(code=code, title=title, department_id=department_id)
            db.session.add(course)
            db.session.commit()
            flash('Course added.', 'success')
        return redirect(url_for('admin.manage_courses'))
    courses = Course.query.all()
    return render_template('courses.html', courses=courses, departments=departments)

@admin_bp.route('/courses/delete/<int:course_id>', methods=['POST'], endpoint='delete_course')
@login_required
def delete_course(course_id):
    guard = _ensure_admin()
    if guard:
        return guard
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted.', 'success')
    return redirect(url_for('admin.manage_courses'))

# -------- Sections --------
@admin_bp.route('/sections', methods=['GET', 'POST'], endpoint='manage_sections')
@login_required
def manage_sections():
    guard = _ensure_admin()
    if guard:
        return guard
    courses = Course.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    tas = User.query.filter_by(role='ta').all()
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        section_code = request.form.get('section_code', '').strip()
        instructor_id = request.form.get('instructor_id')
        ta_id = request.form.get('ta_id') or None
        if not course_id or not section_code or not instructor_id:
            flash('Course, Section Code and Instructor are required.', 'danger')
        elif Section.query.filter_by(course_id=course_id, section_code=section_code).first():
            flash('Section code already exists for this course.', 'danger')
        else:
            section = Section(
                course_id=course_id,
                section_code=section_code,
                instructor_id=instructor_id,
                ta_id=ta_id
            )
            db.session.add(section)
            db.session.commit()
            flash('Section created.', 'success')
        return redirect(url_for('admin.manage_sections'))
    sections = Section.query.all()
    return render_template('admin_sections.html', sections=sections, courses=courses, lecturers=lecturers, tas=tas)

@admin_bp.route('/sections/delete/<int:section_id>', methods=['POST'], endpoint='delete_section')
@login_required
def delete_section(section_id):
    guard = _ensure_admin()
    if guard:
        return guard
    section = Section.query.get_or_404(section_id)
    db.session.delete(section)
    db.session.commit()
    flash('Section deleted.', 'success')
    return redirect(url_for('admin.manage_sections'))

# -------- Enrollments --------
@admin_bp.route('/enrollments', methods=['GET', 'POST'], endpoint='manage_enrollments')
@login_required
def manage_enrollments():
    guard = _ensure_admin()
    if guard:
        return guard
    sections = Section.query.all()
    students = User.query.filter_by(role='student').all()
    if request.method == 'POST':
        section_id = request.form.get('section_id')
        student_id = request.form.get('student_id')
        if not section_id or not student_id:
            flash('Section and Student are required.', 'danger')
        elif Enrollment.query.filter_by(section_id=section_id, student_id=student_id).first():
            flash('Student already enrolled in this section.', 'danger')
        else:
            enr = Enrollment(section_id=section_id, student_id=student_id)
            db.session.add(enr)
            db.session.commit()
            flash('Enrollment added.', 'success')
        return redirect(url_for('admin.manage_enrollments'))
    enrollments = Enrollment.query.all()
    return render_template('admin_enrollments.html', enrollments=enrollments, sections=sections, students=students)

@admin_bp.route('/enrollments/delete/<int:enrollment_id>', methods=['POST'], endpoint='delete_enrollment')
@login_required
def delete_enrollment(enrollment_id):
    guard = _ensure_admin()
    if guard:
        return guard
    enr = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enr)
    db.session.commit()
    flash('Enrollment deleted.', 'success')
    return redirect(url_for('admin.manage_enrollments'))


# -------- Bulk Enrollment via CSV --------
@admin_bp.route('/enrollments/upload', methods=['GET', 'POST'], endpoint='upload_enrollments')
@login_required
def upload_enrollments():
    guard = _ensure_admin()
    if guard:
        return guard

    sections = Section.query.all()
    if request.method == 'GET':
        return render_template('admin_enrollments_upload.html', sections=sections, result=None)

    # POST
    section_override_raw = (request.form.get('section_id') or '').strip()
    section_override_id = None
    if section_override_raw:
        try:
            section_override_id = int(section_override_raw)
        except Exception:
            flash('Invalid section selected.', 'danger')
            return redirect(url_for('admin.upload_enrollments'))

    create_missing = bool(request.form.get('create_missing'))

    file = request.files.get('csv_file') or request.files.get('file')
    if not file or file.filename == '':
        flash('Please select a CSV file.', 'danger')
        return redirect(url_for('admin.upload_enrollments'))

    try:
        text = file.read().decode('utf-8-sig')
    except Exception as e:
        flash(f'Could not read file: {e}', 'danger')
        return redirect(url_for('admin.upload_enrollments'))

    reader = csv.reader(io.StringIO(text))

    def is_header(row):
        low = [c.strip().lower() for c in row]
        return 'email' in low or 'username' in low

    results = {
        'enrolled': 0,
        'duplicates': 0,
        'created_pending': 0,
        'errors': []
    }

    line_no = 0
    for row in reader:
        line_no += 1
        if not row or (len(row) == 1 and row[0].strip() == ''):
            continue
        if line_no == 1 and is_header(row):
            continue

        cols = [c.strip() for c in row]
        email = cols[0] if len(cols) > 0 else ''
        username = cols[1] if len(cols) > 1 else ''
        section_id = section_override_id
        if section_id is None and len(cols) > 2 and cols[2]:
            try:
                section_id = int(cols[2])
            except Exception:
                results['errors'].append(f'Line {line_no}: invalid section_id value')
                continue

        if not section_id:
            results['errors'].append(f'Line {line_no}: missing section_id and no override selected')
            continue

        if not email or '@' not in email:
            results['errors'].append(f'Line {line_no}: invalid email')
            continue

        section = Section.query.get(section_id)
        if not section:
            results['errors'].append(f'Line {line_no}: section {section_id} not found')
            continue

        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            if not create_missing:
                results['errors'].append(f'Line {line_no}: user not found and create-missing disabled')
                continue
            # Create pending student user
            base_username = (username or email.split('@')[0]).strip()[:30] or 'student'
            candidate = base_username
            suffix = 1
            while User.query.filter_by(username=candidate).first():
                # ensure stays under 30 chars
                candidate = f"{base_username[:27]}{suffix:02d}"
                suffix += 1
            user = User(
                username=candidate,
                email=email.lower(),
                password=generate_password_hash('changeme'),
                role='student',
                is_approved=False
            )
            db.session.add(user)
            db.session.flush()
            results['created_pending'] += 1

        if user.role != 'student':
            results['errors'].append(f'Line {line_no}: user role must be student (found {user.role})')
            continue

        if Enrollment.query.filter_by(section_id=section_id, student_id=user.id).first():
            results['duplicates'] += 1
            continue

        enr = Enrollment(section_id=section_id, student_id=user.id)
        db.session.add(enr)
        results['enrolled'] += 1

    db.session.commit()
    return render_template('admin_enrollments_upload.html', sections=sections, result=results)
