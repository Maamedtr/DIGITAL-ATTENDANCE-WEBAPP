import os
import io
import csv

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Department, Course, Section, Enrollment
from werkzeug.security import generate_password_hash


@pytest.fixture
def app_instance(tmp_path):
    os.environ['TESTING'] = '1'
    db_file = tmp_path / "test_admin_bulk.db"
    os.environ['DATABASE_URL'] = f"sqlite:///{db_file}"
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def _mk_admin(app):
    with app.app_context():
        admin = User(
            username='admin1',
            email='admin1@staff.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='admin',
            is_approved=True,
        )
        db.session.add(admin)
        db.session.commit()
        return admin


def _seed_base(app):
    with app.app_context():
        dept = Department(name='Engineering')
        db.session.add(dept)
        db.session.commit()
        course = Course(code='ENG101', title='Intro Eng', department_id=dept.id)
        db.session.add(course)
        db.session.commit()
        section = Section(course_id=course.id, section_code='S1', instructor_id=None, ta_id=None)
        # Create a dummy lecturer to satisfy not-null (if needed)
        if section.instructor_id is None:
            lect = User(
                username='lect_csv',
                email='lect_csv@staff.ug.edu.gh',
                password=generate_password_hash('pass123'),
                role='lecturer',
                is_approved=True,
            )
            db.session.add(lect)
            db.session.commit()
            section.instructor_id = lect.id
        db.session.add(section)
        db.session.commit()
        return dept, course, section


def _login_admin(client, username='admin1', password='pass123'):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)


def test_upload_enrolls_existing_student(app_instance, client):
    _mk_admin(app_instance)
    dept, course, section = _seed_base(app_instance)

    # Existing approved student
    with app_instance.app_context():
        stu = User(
            username='stu_csv',
            email='stu_csv@st.ug.edu.gh',
            password=generate_password_hash('pass123'),
            role='student',
            is_approved=True,
        )
        db.session.add(stu)
        db.session.commit()

    _login_admin(client)

    data = {
        'section_id': str(section.id),
        'create_missing': ''  # disabled
    }
    # Build a simple CSV with only email column
    csv_bytes = io.BytesIO(b"email\nstu_csv@st.ug.edu.gh\n")
    resp = client.post(
        '/admin/enrollments/upload',
        data={'csv_file': (csv_bytes, 'enroll.csv'), **data},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b'Upload Summary' in resp.data
    with app_instance.app_context():
        stu = User.query.filter_by(email='stu_csv@st.ug.edu.gh').first()
        assert stu is not None
        enr = Enrollment.query.filter_by(section_id=section.id, student_id=stu.id).first()
        assert enr is not None


def test_upload_creates_pending_and_enrolls_when_enabled(app_instance, client):
    _mk_admin(app_instance)
    dept, course, section = _seed_base(app_instance)

    _login_admin(client)

    data = {
        'section_id': str(section.id),
        'create_missing': 'on'  # enabled
    }
    csv_bytes = io.BytesIO(b"email\nnew_stu@st.ug.edu.gh\n")
    resp = client.post(
        '/admin/enrollments/upload',
        data={'csv_file': (csv_bytes, 'enroll2.csv'), **data},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b'Upload Summary' in resp.data
    with app_instance.app_context():
        stu = User.query.filter_by(email='new_stu@st.ug.edu.gh').first()
        assert stu is not None
        assert stu.role == 'student'
        assert stu.is_approved is False  # pending
        enr = Enrollment.query.filter_by(section_id=section.id, student_id=stu.id).first()
        assert enr is not None


def test_upload_reports_error_when_section_missing_and_no_override(app_instance, client):
    _mk_admin(app_instance)
    _seed_base(app_instance)

    _login_admin(client)

    data = {
        'create_missing': ''  # disabled
    }
    csv_bytes = io.BytesIO(b"email,username\nmissing@st.ug.edu.gh,missinguser\n")
    resp = client.post(
        '/admin/enrollments/upload',
        data={'csv_file': (csv_bytes, 'enroll3.csv'), **data},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b'Upload Summary' in resp.data
    # Expect an error listed
    assert b'missing section_id and no override selected' in resp.data