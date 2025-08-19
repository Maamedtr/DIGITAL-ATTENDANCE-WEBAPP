from .extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, lecturer, ta, student
    is_approved = db.Column(db.Boolean, default=False)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # Optionally, add more fields

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    department = db.relationship('Department', backref=db.backref('courses', lazy=True))

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)  # e.g., Monday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    level = db.Column(db.String(20), nullable=False)  # e.g., 100, 200, 300, 400
    course = db.relationship('Course', backref=db.backref('timetables', lazy=True))

class CourseAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # lecturer or ta
    course = db.relationship('Course', backref=db.backref('assignments', lazy=True))
    user = db.relationship('User', backref=db.backref('assignments', lazy=True))

# --- New MVP Models ---

class Section(db.Model):
    __tablename__ = 'section'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    section_code = db.Column(db.String(50), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ta_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    course = db.relationship('Course', backref=db.backref('sections', lazy=True))
    instructor = db.relationship('User', foreign_keys=[instructor_id],
                                 backref=db.backref('sections_taught', lazy=True))
    ta = db.relationship('User', foreign_keys=[ta_id],
                         backref=db.backref('sections_assisted', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('course_id', 'section_code', name='uq_section_course_code'),
    )

class Enrollment(db.Model):
    __tablename__ = 'enrollment'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    section = db.relationship('Section',
                              backref=db.backref('enrollments', lazy=True, cascade="all, delete-orphan"))
    student = db.relationship('User',
                              backref=db.backref('enrollments', lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint('section_id', 'student_id', name='uq_enrollment_section_student'),
    )

class ClassSession(db.Model):
    __tablename__ = 'class_session'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='scheduled')  # scheduled|open|closed
    open_code_hash = db.Column(db.String(255), nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    section = db.relationship('Section',
                              backref=db.backref('sessions', lazy=True, cascade="all, delete-orphan"))

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_record'
    id = db.Column(db.Integer, primary_key=True)
    class_session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='present')  # present|absent
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    class_session = db.relationship('ClassSession',
                                    backref=db.backref('attendance_records', lazy=True, cascade="all, delete-orphan"))
    student = db.relationship('User',
                              backref=db.backref('attendance_records', lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint('class_session_id', 'student_id', name='uq_attendance_session_student'),
    )
