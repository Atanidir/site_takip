from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app import db
from app.models.models import User, Resident

auth_bp = Blueprint('auth', __name__)


def _role_url(user):
    if user.role == 'super_admin':
        return url_for('super_admin.dashboard')
    elif user.role == 'site_admin':
        return url_for('site_admin.dashboard')
    elif user.role == 'resident':
        return url_for('resident.dashboard')
    return url_for('auth.login')


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(_role_url(current_user))
    return render_template('landing.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(_role_url(current_user))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()

        # Sakin kullanıcısı TC ile giriş — şifre henüz oluşturulmamış
        if user and user.role == 'resident' and not user.password_hash:
            flash('Henüz şifrenizi oluşturmadınız. Lütfen "İlk Giriş / Şifremi Unuttum" bağlantısını kullanın.', 'warning')
            return render_template('auth/login.html')

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            flash(f'Hoş geldiniz, {user.full_name or user.username}!', 'success')

            # Başarılı giriş logu
            try:
                from sqlalchemy import text
                from app import db
                db.session.execute(text("""
                    INSERT INTO giris_loglari (kullanici_id, kimlik, ip_adresi, basarili, tarih, aciklama)
                    VALUES (:uid, :kimlik, :ip, true, NOW(), 'Başarılı giriş')
                """), {
                    'uid'   : user.id,
                    'kimlik': user.username,
                    'ip'    : request.remote_addr
                })
                db.session.commit()
            except Exception:
                pass

            # Site admin girişinde otomatik bildirim oluştur
            if user.role == 'site_admin':
                try:
                    from app.models.models import Notification, Due, Apartment, Block, Site
                    from datetime import date, timedelta
                    today = date.today()

                    site = Site.query.filter(Site.managers.any(id=user.id)).first()
                    if site:
                        # Gecikmiş aidatlar
                        geciken = Due.query.join(Apartment).join(Block).filter(
                            Block.site_id == site.id,
                            Due.is_paid == False,
                            Due.due_date < today
                        ).count()
                        if geciken:
                            mevcut = Notification.query.filter_by(
                                user_id=user.id, notif_type='danger', title='Gecikmiş Aidatlar'
                            ).filter(Notification.created_at >= datetime.combine(today, datetime.min.time())).first()
                            if not mevcut:
                                db.session.add(Notification(
                                    user_id=user.id, title='Gecikmiş Aidatlar',
                                    message=f'{geciken} adet aidat vadesi geçmiş.',
                                    link='/site-admin/dues', notif_type='danger'
                                ))

                        # 3 gün içinde vadesi dolacak
                        yaklasan = Due.query.join(Apartment).join(Block).filter(
                            Block.site_id == site.id,
                            Due.is_paid == False,
                            Due.due_date >= today,
                            Due.due_date <= today + timedelta(days=3)
                        ).count()
                        if yaklasan:
                            mevcut = Notification.query.filter_by(
                                user_id=user.id, notif_type='warning', title='Yaklaşan Aidat Vadesi'
                            ).filter(Notification.created_at >= datetime.combine(today, datetime.min.time())).first()
                            if not mevcut:
                                db.session.add(Notification(
                                    user_id=user.id, title='Yaklaşan Aidat Vadesi',
                                    message=f'{yaklasan} aidatın vadesi 3 gün içinde dolacak.',
                                    link='/site-admin/dues', notif_type='warning'
                                ))

                        # Lisans uyarısı
                        if user.license and user.license.valid_until:
                            kalan = (user.license.valid_until - today).days
                            if kalan <= 30:
                                mevcut = Notification.query.filter_by(
                                    user_id=user.id, title='Lisans Uyarısı'
                                ).filter(Notification.created_at >= datetime.combine(today, datetime.min.time())).first()
                                if not mevcut:
                                    db.session.add(Notification(
                                        user_id=user.id, title='Lisans Uyarısı',
                                        message=f'Lisansınız {"sona erdi" if kalan < 0 else f"{kalan} gün içinde dolacak"}.',
                                        link='#', notif_type='danger' if kalan < 0 else 'warning'
                                    ))

                        db.session.commit()
                except Exception:
                    pass

            next_page = request.args.get('next')
            return redirect(next_page or _role_url(user))
        else:
            flash('Kullanıcı adı veya şifre hatalı.', 'danger')
            # Başarısız giriş logu
            try:
                from sqlalchemy import text
                from app import db
                uid = user.id if user else None
                db.session.execute(text("""
                    INSERT INTO giris_loglari (kullanici_id, kimlik, ip_adresi, basarili, tarih, aciklama)
                    VALUES (:uid, :kimlik, :ip, false, NOW(), 'Hatalı şifre veya kullanıcı bulunamadı')
                """), {
                    'uid'   : uid,
                    'kimlik': username,
                    'ip'    : request.remote_addr
                })
                db.session.commit()
            except Exception:
                pass

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yapıldı.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/sifremi-unuttum', methods=['GET', 'POST'])
def forgot_password():
    """TC ile kimlik doğrula, yeni şifre belirle."""
    step = request.args.get('step', '1')

    if request.method == 'POST':
        step = request.form.get('step', '1')

        if step == '1':
            tc_no = request.form.get('tc_no', '').strip()
            user  = User.query.filter_by(username=tc_no, role='resident').first()
            if not user:
                flash('Bu TC kimlik numarasına ait kullanıcı bulunamadı.', 'danger')
                return render_template('auth/forgot_password.html', step='1')

            # Session'a TC kaydet
            session['reset_tc'] = tc_no
            return render_template('auth/forgot_password.html', step='2', tc_no=tc_no)

        elif step == '2':
            tc_no    = session.get('reset_tc')
            password = request.form.get('password', '')
            confirm  = request.form.get('confirm', '')

            if not tc_no:
                return redirect(url_for('auth.forgot_password'))
            if len(password) < 6:
                flash('Şifre en az 6 karakter olmalıdır.', 'danger')
                return render_template('auth/forgot_password.html', step='2', tc_no=tc_no)
            if password != confirm:
                flash('Şifreler eşleşmiyor.', 'danger')
                return render_template('auth/forgot_password.html', step='2', tc_no=tc_no)

            user = User.query.filter_by(username=tc_no).first()
            user.set_password(password)
            user.must_change_pw = False
            db.session.commit()
            session.pop('reset_tc', None)

            login_user(user)
            flash('Şifreniz oluşturuldu. Hoş geldiniz!', 'success')
            return redirect(_role_url(user))

    return render_template('auth/forgot_password.html', step='1')


@auth_bp.route('/sifre-sifirla', methods=['GET', 'POST'])
def reset_password_request():
    """Site admin için e-posta ile şifre sıfırlama isteği."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user  = User.query.filter_by(email=email, role='site_admin').first()

        if user:
            import secrets
            from datetime import timedelta
            token = secrets.token_urlsafe(32)
            user.reset_token     = token
            user.reset_token_exp = datetime.utcnow() + timedelta(hours=2)
            db.session.commit()

            reset_url = url_for('auth.reset_password', token=token, _external=True)

            # Mail gönder
            from app.utils import send_mail
            html = f"""
            <p>Merhaba {user.full_name or user.username},</p>
            <p>Şifre sıfırlama talebiniz alındı. Aşağıdaki bağlantıya tıklayarak yeni şifrenizi belirleyebilirsiniz:</p>
            <p><a href="{reset_url}" style="background:#2563eb;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;">
                Şifremi Sıfırla
            </a></p>
            <p>Bu bağlantı 2 saat geçerlidir.</p>
            <p>Eğer bu talebi siz yapmadıysanız bu e-postayı görmezden gelebilirsiniz.</p>
            """
            ok, msg = send_mail(email, 'Şifre Sıfırlama — Site Aidat', html)
            if ok:
                flash('Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.', 'success')
            else:
                flash(f'Mail gönderilemedi: {msg} — Sistem yöneticinizle iletişime geçin.', 'danger')
        else:
            # Güvenlik için aynı mesajı göster
            flash('Eğer bu e-posta kayıtlıysa sıfırlama bağlantısı gönderildi.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html')


@auth_bp.route('/sifre-sifirla/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Token ile şifre sıfırlama."""
    from datetime import datetime as dt
    user = User.query.filter_by(reset_token=token).first()

    if not user or not user.reset_token_exp or user.reset_token_exp < dt.utcnow():
        flash('Geçersiz veya süresi dolmuş bağlantı.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        if len(password) < 6:
            flash('Şifre en az 6 karakter olmalıdır.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Şifreler eşleşmiyor.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.reset_token     = None
        user.reset_token_exp = None
        db.session.commit()

        flash('Şifreniz güncellendi. Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/demo-talep', methods=['POST'])
def demo_talep():
    from app.models.models import DemoRequest
    from app.utils import send_mail
    import json

    full_name       = request.form.get('full_name', '').strip()
    phone           = request.form.get('phone', '').strip()
    email           = request.form.get('email', '').strip()
    site_name       = request.form.get('site_name', '').strip()
    apartment_count = request.form.get('apartment_count', '').strip()

    if not full_name or not phone or not email:
        return json.dumps({'success': False, 'message': 'Ad, telefon ve e-posta zorunludur.'}), 400

    # Veritabanına kaydet
    db.session.add(DemoRequest(
        full_name       = full_name,
        phone           = phone,
        email           = email,
        site_name       = site_name,
        apartment_count = apartment_count
    ))
    db.session.commit()

    # E-posta gönder
    html = f'''
    <h2>Yeni Demo Talebi</h2>
    <p><strong>Ad Soyad:</strong> {full_name}</p>
    <p><strong>Telefon:</strong> {phone}</p>
    <p><strong>E-posta:</strong> {email}</p>
    <p><strong>Site Adı:</strong> {site_name or '-'}</p>
    <p><strong>Daire Sayısı:</strong> {apartment_count or '-'}</p>
    '''
    send_mail('info@probissite.com.tr', f'Yeni Demo Talebi - {full_name}', html)

    return json.dumps({'success': True, 'message': 'Talebiniz alındı!'}), 200
