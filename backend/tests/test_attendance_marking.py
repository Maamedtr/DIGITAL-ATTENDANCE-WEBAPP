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
    db_file = tmp_path / "test_attendance.db"
    os.environ['DATABASE_URL'] = f"sqlite:///{db_file}"
    os.environ['TESTING'] = '1'
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def _create_basic_data(app):
    with app.app_context():
        # Department and course
        dept = Department(name='Computing')
        db.session.add(dept)
        db.session.commit()

        course = Course(code='CS101', title='Intro to CS', department_id=dept.id)
        db.session.add(course)
        db.session.commit()

        # Users
        lecturer = User(
            username='lect1',
            email='lect1@staff.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='lecturer',
            is_approved=True,
        )
        student = User(
            username='stud1',
            email='stud1@st.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='student',
            is_approved=True,
        )
        db.session.add_all([lecturer, student])
        db.session.commit()

        # Section and enrollment
        section = Section(course_id=course.id, section_code='A', instructor_id=lecturer.id)
        db.session.add(section)
        db.session.commit()

        enrollment = Enrollment(section_id=section.id, student_id=student.id)
        db.session.add(enrollment)
        db.session.commit()

        # Session
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
            'student': student,
            'section': section,
            'session': sess,
        }


def _login(client, username, password):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)


def _logout(client):
    return client.get('/auth/logout', follow_redirects=False)


def test_attendance_marking_flow(app_instance, client):
    data = _create_basic_data(app_instance)
    sess = data['session']
    section = data['section']
    lecturer = data['lecturer']
    student = data['student']

    # Lecturer login and open session
    resp = _login(client, lecturer.username, 'pass123')
    assert resp.status_code in (302, 303)

    resp = client.post(f'/lecturer/sessions/{sess.id}/open', follow_redirects=False)
    assert resp.status_code in (302, 303)
    loc = resp.headers.get('Location', '')
    assert '/lecturer/sections/' in loc and 'opened_session_id=' in loc and 'code=' in loc
    parsed = urlparse(loc)
    q = parse_qs(parsed.query)
    code = q.get('code', [''])[0]
    assert code and len(code) == 6 and code.isdigit()

    # Switch to student and mark attendance
    _logout(client)
    resp = _login(client, student.username, 'pass123')
    assert resp.status_code in (302, 303)

    # Ensure session listed for student (optional check)
    r = client.get('/student/sessions')
    assert r.status_code == 200

    r = client.post(f'/student/sessions/{sess.id}/mark', data={'code': code}, follow_redirects=False)
    assert r.status_code in (302, 303)

    with app_instance.app_context():
        count = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=student.id).count()
        assert count == 1

    # Idempotency: submit again
    r2 = client.post(f'/student/sessions/{sess.id}/mark', data={'code': code}, follow_redirects=False)
    assert r2.status_code in (302, 303)
    with app_instance.app_context():
        count2 = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=student.id).count()
        assert count2 == 1

    # Close session and ensure further submissions are rejected
    _logout(client)
    _login(client, lecturer.username, 'pass123')
    r3 = client.post(f'/lecturer/sessions/{sess.id}/close', follow_redirects=False)
    assert r3.status_code in (302, 303)

    _logout(client)
    _login(client, student.username, 'pass123')
    r4 = client.post(f'/student/sessions/{sess.id}/mark', data={'code': code}, follow_redirects=False)
    assert r4.status_code in (302, 303)
    with app_instance.app_context():
        count3 = AttendanceRecord.query.filter_by(class_session_id=sess.id, student_id=student.id).count()
        assert count3 == 1