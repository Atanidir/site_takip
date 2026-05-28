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
    @app.template_filter('get_replied_messages')
    def get_replied_messages(resident):
        from app.models.models import ResidentMessage
        return ResidentMessage.query.filter(
            ResidentMessage.resident_id == resident.id,
            ResidentMessage.reply != None,
            ResidentMessage.reply != '',
            ResidentMessage.reply_read == False
        ).all()

    @app.template_filter('get_unread_replies')
    def get_unread_replies(user):
        from app.models.models import ResidentMessage, Resident
        if user.role == 'resident':
            res = Resident.query.filter_by(user_id=user.id, is_active=True).first()
            if res:
                return ResidentMessage.query.filter(
                    ResidentMessage.resident_id == res.id,
                    ResidentMessage.reply != None,
                    ResidentMessage.reply != '',
                    ResidentMessage.reply_read == False
                ).count()
        return 0

    @app.template_filter('get_unread_messages')
    def get_unread_messages(user):
        from app.models.models import ResidentMessage, Site
        if user.role == 'site_admin':
            site_ids = [s.id for s in user.managed_sites.all()]
            return ResidentMessage.query.filter(
                ResidentMessage.site_id.in_(site_ids),
                ResidentMessage.is_read == False,
                ResidentMessage.is_closed == False
            ).count() if site_ids else 0
        return 0

    @app.template_filter('get_unread_count')
    def get_unread_count(user):
        from app.models.models import Notification, ResidentMessage, Site
        notif_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        # Site adminse okunmamış sakin mesajlarını da say
        if user.role == 'site_admin':
            site_ids = [s.id for s in user.managed_sites.all()]
            msg_count = ResidentMessage.query.filter(
                ResidentMessage.site_id.in_(site_ids),
                ResidentMessage.is_read == False
            ).count() if site_ids else 0
            return notif_count + msg_count
        return notif_count

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
