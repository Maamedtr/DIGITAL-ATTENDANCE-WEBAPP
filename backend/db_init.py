from app import create_app
from app.extensions import db
from app.models import User, Department, Course, Section, Enrollment
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    db.create_all()

    def ensure_user(username, email, password, role, approved=True):
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                role=role,
                is_approved=approved
            )
            db.session.add(user)
            db.session.commit()
            print(f"User created: {username} / {password} ({role})")
        return user

    # Seed users
    admin = ensure_user('admin', 'admin@example.com', 'admin@123', 'admin', True)
    lect1 = ensure_user('lect1', 'lect1@example.com', 'pass123', 'lecturer', True)
    ta1 = ensure_user('ta1', 'ta1@example.com', 'pass123', 'ta', True)
    stud1 = ensure_user('stud1', 'stud1@example.com', 'pass123', 'student', True)

    # Seed Department
    dept = Department.query.filter_by(name='Computer Science').first()
    if not dept:
        dept = Department(name='Computer Science')
        db.session.add(dept)
        db.session.commit()
        print('Department created: Computer Science')

    # Seed Course
    course = Course.query.filter_by(code='CS101').first()
    if not course:
        course = Course(code='CS101', title='Introduction to Computer Science', department_id=dept.id)
        db.session.add(course)
        db.session.commit()
        print('Course created: CS101')

    # Seed Section
    section = Section.query.filter_by(course_id=course.id, section_code='A1').first()
    if not section:
        section = Section(course_id=course.id, section_code='A1', instructor_id=lect1.id, ta_id=ta1.id)
        db.session.add(section)
        db.session.commit()
        print('Section created: A1')

    # Seed Enrollment
    enr = Enrollment.query.filter_by(section_id=section.id, student_id=stud1.id).first()
    if not enr:
        enr = Enrollment(section_id=section.id, student_id=stud1.id)
        db.session.add(enr)
        db.session.commit()
        print('Enrollment created: stud1 in CS101 A1')

    print('Database initialized and seeded.')
