import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Department, Course, Section, Enrollment, ClassSession, AttendanceRecord
from werkzeug.security import generate_password_hash


@pytest.fixture
def app_instance(tmp_path):
    os.environ['TESTING'] = '1'
    db_file = tmp_path / "test_ta.db"
    os.environ['DATABASE_URL'] = f"sqlite:///{db_file}"
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def _create_base(app):
    with app.app_context():
        dept = Department(name='Physics')
        db.session.add(dept)
        db.session.commit()

        course = Course(code='PHYS101', title='Mechanics', department_id=dept.id)
        db.session.add(course)
        db.session.commit()

        lecturer = User(
            username='lect_ta',
            email='lect_ta@staff.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='lecturer',
            is_approved=True,
        )
        ta = User(
            username='ta_user',
            email='ta_user@staff.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='ta',
            is_approved=True,
        )
        student = User(
            username='stud_ta',
            email='stud_ta@st.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='student',
            is_approved=True,
        )
        db.session.add_all([lecturer, ta, student])
        db.session.commit()

        # Section assisted by TA
        section = Section(course_id=course.id, section_code='T1', instructor_id=lecturer.id, ta_id=ta.id)
        db.session.add(section)
        db.session.commit()

        enrollment = Enrollment(section_id=section.id, student_id=student.id)
        db.session.add(enrollment)
        db.session.commit()

        # Another section not assisted by this TA
        other_section = Section(course_id=course.id, section_code='X9', instructor_id=lecturer.id, ta_id=None)
        db.session.add(other_section)
        db.session.commit()

        # Session for assisted section
        sess = ClassSession(
            section_id=section.id,
            scheduled_start=datetime.utcnow(),
            scheduled_end=datetime.utcnow() + timedelta(hours=1),
            status='scheduled',
        )
        db.session.add(sess)
        db.session.commit()

        return {
            'dept': dept,
            'course': course,
            'lecturer': lecturer,
            'ta': ta,
            'student': student,
            'section': section,
            'other_section': other_section,
            'session': sess,
        }


def _login(client, username, password):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)


def _logout(client):
    return client.get('/auth/logout', follow_redirects=False)


def test_ta_can_manage_assisted_section_and_student_can_mark(app_instance, client):
    data = _create_base(app_instance)
    section = data['section']
    sess = data['session']
    ta = data['ta']
    student = data['student']

    # TA login
    r = _login(client, ta.username, 'pass123')
    assert r.status_code in (302, 303)

    # TA opens session (uses lecturer endpoints but authorized for TA)
    r2 = client.post(f'/lecturer/sessions/{sess.id}/open', follow_redirects=False)
    assert r2.status_code in (302, 303)
    loc = r2.headers.get('Location', '')
    parsed = urlparse(loc)
    q = parse_qs(parsed.query)
    code = q.get('code', [''])[0]
    assert code and len(code) == 6 and code.isdigit()

    # Student marks attendance with that code
    _logout(client)
    _login(client, student.username, 'pass123')
    r3 = client.post(f'/student/sessions/{sess.id}/mark', data={'code': code}, follow_redirects=False)
    assert r3.status_code in (302, 303)
    with app_instance.app_context():
        count = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=student.id).count()
        assert count == 1

    # TA can download session CSV
    _logout(client)
    _login(client, ta.username, 'pass123')
    r4 = client.get(f'/lecturer/sessions/{sess.id}/attendance.csv')
    assert r4.status_code == 200
    assert b'student_id,username,email,status,recorded_at' in r4.data or b'student_id' in r4.data


def test_ta_cannot_manage_unassigned_section(app_instance, client):
    data = _create_base(app_instance)
    other_section = data['other_section']
    ta = data['ta']

    _login(client, ta.username, 'pass123')
    # Attempt to load sessions page for section not assigned to TA
    r = client.get(f'/lecturer/sections/{other_section.id}/sessions', follow_redirects=False)
    # Should redirect away (access denied)
    assert r.status_code in (302, 303)