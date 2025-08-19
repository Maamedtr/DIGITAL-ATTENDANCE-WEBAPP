from flask import Flask
from .extensions import db
from .admin.routes import admin_bp
from .lecturer.routes import lecturer_bp
from .ta.routes import ta_bp
from .student.routes import student_bp
from .auth.routes import auth_bp
from .attendance.routes import attendance_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    db.init_app(app)
    from .extensions import login_manager
    login_manager.init_app(app)
    # Ensure tables exist for MVP (no migrations)
    with app.app_context():
        db.create_all()

    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(lecturer_bp, url_prefix='/lecturer')
    app.register_blueprint(ta_bp, url_prefix='/ta')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(attendance_bp)

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    return app
