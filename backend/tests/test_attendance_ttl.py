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
    # Force immediate expiry of codes
    os.environ['ATTENDANCE_CODE_TTL_MINUTES'] = '0'
    os.environ['TESTING'] = '1'
    db_file = tmp_path / "test_ttl.db"
    os.environ['DATABASE_URL'] = f"sqlite:///{db_file}"
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def _create_data(app):
    with app.app_context():
        dept = Department(name='Math')
        db.session.add(dept)
        db.session.commit()

        course = Course(code='MATH101', title='Calculus I', department_id=dept.id)
        db.session.add(course)
        db.session.commit()

        lecturer = User(
            username='lect_ttl',
            email='lect_ttl@staff.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='lecturer',
            is_approved=True,
        )
        student = User(
            username='stud_ttl',
            email='stud_ttl@st.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='student',
            is_approved=True,
        )
        db.session.add_all([lecturer, student])
        db.session.commit()

        section = Section(course_id=course.id, section_code='B', instructor_id=lecturer.id)
        db.session.add(section)
        db.session.commit()

        enr = Enrollment(section_id=section.id, student_id=student.id)
        db.session.add(enr)
        db.session.commit()

        sess = ClassSession(
            section_id=section.id,
            scheduled_start=datetime.utcnow(),
            scheduled_end=datetime.utcnow() + timedelta(hours=1),
            status='scheduled',
        )
        db.session.add(sess)
        db.session.commit()

        return {'lecturer': lecturer, 'student': student, 'section': section, 'session': sess}


def _login(client, username, password):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)


def _logout(client):
    return client.get('/auth/logout', follow_redirects=False)


def test_code_expires_immediately_when_ttl_is_zero(app_instance, client):
    data = _create_data(app_instance)
    sess = data['session']
    lecturer = data['lecturer']
    student = data['student']

    # Lecturer opens the session
    _login(client, lecturer.username, 'pass123')
    resp = client.post(f'/lecturer/sessions/{sess.id}/open', follow_redirects=False)
    assert resp.status_code in (302, 303)
    loc = resp.headers.get('Location', '')
    parsed = urlparse(loc)
    q = parse_qs(parsed.query)
    code = q.get('code', [''])[0]
    assert code and len(code) == 6 and code.isdigit()
    _logout(client)

    # Student attempts to mark, but TTL=0 means expired immediately
    _login(client, student.username, 'pass123')
    r = client.post(f'/student/sessions/{sess.id}/mark', data={'code': code}, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app_instance.app_context():
        count = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=student.id).count()
        assert count == 0, "Attendance should not be recorded after TTL expiry"