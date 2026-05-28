from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config

db       = SQLAlchemy()
migrate  = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmalısınız.'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Bildirim filter'ları
    from app.models.models import Notification
    @app.template_filter('get_unread_count')
    def get_unread_count(user):
        return Notification.query.filter_by(user_id=user.id, is_read=False).count()

    @app.template_filter('get_notifications')
    def get_notifications(user):
        return Notification.query.filter_by(user_id=user.id)\
                   .order_by(Notification.created_at.desc()).limit(10).all()

    # Blueprint kayıtları
    from app.routes.auth        import auth_bp
    from app.routes.super_admin import super_admin_bp
    from app.routes.site_admin  import site_admin_bp
    from app.routes.resident    import resident_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(super_admin_bp, url_prefix='/super-admin')
    app.register_blueprint(site_admin_bp,  url_prefix='/site-admin')
    app.register_blueprint(resident_bp,    url_prefix='/resident')

    return app
