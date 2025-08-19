import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
    # Allow override for tests/deployment via DATABASE_URL; default to project-local SQLite DB
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///attendance.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = os.environ.get('TESTING', '0') == '1'

    # Attendance code TTL (minutes) for open sessions
    ATTENDANCE_CODE_TTL_MINUTES = int(os.environ.get('ATTENDANCE_CODE_TTL_MINUTES', '15'))
    # Optional absolute base URL for QR deep links (e.g., https://example.edu); falls back to request.url_root
    BASE_URL = os.environ.get('BASE_URL')
