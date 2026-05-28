import os
from app import create_app, db
from app.models.models import User, License

app = create_app(os.environ.get('FLASK_ENV', 'production'))


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, License=License)


@app.cli.command('init-db')
def init_db():
    """Veritabanı tablolarını oluşturur ve süper admin hesabı açar."""
    db.create_all()
    if not User.query.filter_by(role='super_admin').first():
        admin = User(
            username  = 'superadmin',
            email     = 'admin@siteaidat.local',
            full_name = 'Sistem Yöneticisi',
            role      = 'super_admin',
            is_active = True
        )
        admin.set_password('Admin1234!')
        db.session.add(admin)
        db.session.commit()
        print('✅ Süper admin oluşturuldu  →  kullanıcı: superadmin  |  şifre: Admin1234!')
    else:
        print('ℹ️  Süper admin zaten mevcut.')


if __name__ == '__main__':
    app.run()
