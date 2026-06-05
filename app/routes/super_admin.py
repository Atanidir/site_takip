from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from datetime import date, datetime
from app import db
from app.models.models import User, License, LicenseProfile, Site

super_admin_bp = Blueprint('super_admin', __name__)


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ──────────────────────────────────────────────────────────────
@super_admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    today = date.today()
    stats = {
        'licenses'       : License.query.count(),
        'active_licenses': License.query.filter_by(is_active=True).count(),
        'suresi_dolan'   : License.query.filter(
                               License.valid_until != None,
                               License.valid_until < today
                           ).count(),
        'site_admins'    : User.query.filter_by(role='site_admin').count(),
        'sites'          : Site.query.count(),
        'residents'      : User.query.filter_by(role='resident').count(),
    }
    # Süresi yaklaşan lisanslar (30 gün içinde)
    from datetime import timedelta
    yaklasan = License.query.filter(
        License.valid_until != None,
        License.valid_until >= today,
        License.valid_until <= today + timedelta(days=30)
    ).all()
    return render_template('super_admin/dashboard.html', stats=stats, yaklasan=yaklasan, today=today)


# ── Lisans Yönetimi ────────────────────────────────────────────────────────
@super_admin_bp.route('/licenses')
@login_required
@super_admin_required
def licenses():
    all_licenses = License.query.order_by(License.created_at.desc()).all()
    return render_template('super_admin/licenses.html', licenses=all_licenses, today=date.today())


@super_admin_bp.route('/licenses/new', methods=['GET', 'POST'])
@login_required
@super_admin_required
def new_license():
    if request.method == 'POST':
        import secrets
        key = request.form.get('license_key') or secrets.token_urlsafe(24)
        from datetime import datetime, timedelta
        is_demo = bool(request.form.get('is_demo'))
        demo_start = None
        demo_end   = None
        if is_demo:
            demo_start = datetime.utcnow()
            demo_end   = demo_start + timedelta(days=14)

        lic = License(
            license_key     = key,
            description     = request.form.get('description'),
            valid_until     = request.form.get('valid_until') or None,
            is_active       = True,
            is_demo         = is_demo,
            demo_start_date = demo_start,
            demo_end_date   = demo_end,
        )
        db.session.add(lic)
        db.session.commit()
        flash('Lisans oluşturuldu.', 'success')
        return redirect(url_for('super_admin.licenses'))
    return render_template('super_admin/license_form.html', license=None)


@super_admin_bp.route('/licenses/<int:lid>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_license(lid):
    lic = License.query.get_or_404(lid)
    if request.method == 'POST':
        from datetime import datetime, timedelta
        lic.description = request.form.get('description')
        lic.valid_until = request.form.get('valid_until') or None
        lic.is_active   = bool(request.form.get('is_active'))
        # Demo uzatma
        if request.form.get('demo_uzat'):
            lic.demo_end_date = datetime.utcnow() + timedelta(days=int(request.form.get('demo_uzat_gun', 14)))
        # Demo'dan lisansa geçiş
        if request.form.get('demo_bitir'):
            lic.is_demo = False
            lic.demo_end_date = None
        db.session.commit()
        flash('Lisans güncellendi.', 'success')
        return redirect(url_for('super_admin.licenses'))
    return render_template('super_admin/license_form.html', license=lic)


@super_admin_bp.route('/licenses/<int:lid>/toggle')
@login_required
@super_admin_required
def toggle_license(lid):
    lic = License.query.get_or_404(lid)
    lic.is_active = not lic.is_active
    db.session.commit()
    flash('Lisans durumu güncellendi.', 'info')
    return redirect(url_for('super_admin.licenses'))


# ── Site Admin Yönetimi ────────────────────────────────────────────────────
@super_admin_bp.route('/site-admins')
@login_required
@super_admin_required
def site_admins():
    admins = User.query.filter_by(role='site_admin').order_by(User.created_at.desc()).all()
    return render_template('super_admin/site_admins.html', admins=admins, today=date.today())


@super_admin_bp.route('/site-admins/new', methods=['GET', 'POST'])
@login_required
@super_admin_required
def new_site_admin():
    licenses = License.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        lic_id   = request.form.get('license_id') or None

        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Bu e-posta zaten kullanılıyor.', 'danger')
        else:
            user = User(
                username   = username,
                email      = email,
                full_name  = request.form.get('full_name'),
                phone      = request.form.get('phone'),
                role       = 'site_admin',
                license_id = int(lic_id) if lic_id else None,
                is_active  = True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Site admin oluşturuldu.', 'success')
            return redirect(url_for('super_admin.site_admins'))

    return render_template('super_admin/site_admin_form.html', licenses=licenses, admin=None)


@super_admin_bp.route('/site-admins/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_site_admin(uid):
    user     = User.query.get_or_404(uid)
    licenses = License.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        user.full_name  = request.form.get('full_name')
        user.phone      = request.form.get('phone')
        user.email      = request.form.get('email')
        user.license_id = int(request.form.get('license_id')) if request.form.get('license_id') else None
        user.is_active  = bool(request.form.get('is_active'))
        if request.form.get('password'):
            user.set_password(request.form.get('password'))
        db.session.commit()
        flash('Kullanıcı güncellendi.', 'success')
        return redirect(url_for('super_admin.site_admins'))
    return render_template('super_admin/site_admin_form.html', licenses=licenses, admin=user)


@super_admin_bp.route('/site-admins/<int:uid>/toggle')
@login_required
@super_admin_required
def toggle_site_admin(uid):
    user = User.query.get_or_404(uid)
    user.is_active = not user.is_active
    db.session.commit()
    flash('Kullanıcı durumu güncellendi.', 'info')
    return redirect(url_for('super_admin.site_admins'))


# ── Lisans Profili ─────────────────────────────────────────────────────────
@super_admin_bp.route('/licenses/<int:lid>/profile', methods=['GET', 'POST'])
@login_required
@super_admin_required
def license_profile(lid):
    lic     = License.query.get_or_404(lid)
    profile = lic.profile

    if request.method == 'POST':
        if profile:
            profile.firma_adi     = request.form.get('firma_adi')
            profile.yetkili_adi   = request.form.get('yetkili_adi')
            profile.vergi_no      = request.form.get('vergi_no')
            profile.vergi_dairesi = request.form.get('vergi_dairesi')
            profile.tc_no         = request.form.get('tc_no')
            profile.telefon       = request.form.get('telefon')
            profile.email         = request.form.get('email')
            profile.province      = request.form.get('province')
            profile.district      = request.form.get('district')
            profile.neighborhood  = request.form.get('neighborhood')
            profile.address       = request.form.get('address')
            profile.notlar        = request.form.get('notlar')
        else:
            profile = LicenseProfile(
                license_id    = lid,
                firma_adi     = request.form.get('firma_adi'),
                yetkili_adi   = request.form.get('yetkili_adi'),
                vergi_no      = request.form.get('vergi_no'),
                vergi_dairesi = request.form.get('vergi_dairesi'),
                tc_no         = request.form.get('tc_no'),
                telefon       = request.form.get('telefon'),
                email         = request.form.get('email'),
                province      = request.form.get('province'),
                district      = request.form.get('district'),
                neighborhood  = request.form.get('neighborhood'),
                address       = request.form.get('address'),
                notlar        = request.form.get('notlar')
            )
            db.session.add(profile)
        db.session.commit()
        flash('Profil kaydedildi.', 'success')
        return redirect(url_for('super_admin.license_profile', lid=lid))

    return render_template('super_admin/license_profile.html', license=lic, profile=profile)


# ── Adres AJAX ────────────────────────────────────────────────────────────
@super_admin_bp.route('/api/iller')
@login_required
@super_admin_required
def api_iller():
    from sqlalchemy import text
    rows = db.session.execute(text("SELECT ilid, iladi FROM il ORDER BY iladi")).fetchall()
    from flask import jsonify
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


@super_admin_bp.route('/api/ilceler/<int:il_id>')
@login_required
@super_admin_required
def api_ilceler(il_id):
    from sqlalchemy import text
    from flask import jsonify
    rows = db.session.execute(
        text("SELECT ilceid, ilceadi FROM ilce WHERE ilid = :ilid ORDER BY ilceadi"),
        {'ilid': il_id}
    ).fetchall()
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


@super_admin_bp.route('/api/mahalleler/<int:ilce_id>')
@login_required
@super_admin_required
def api_mahalleler(ilce_id):
    from sqlalchemy import text
    from flask import jsonify
    rows = db.session.execute(
        text("SELECT mahalleid, mahalleadi FROM mahalle WHERE ilceid = :ilceid ORDER BY mahalleadi"),
        {'ilceid': ilce_id}
    ).fetchall()
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


# ── Sistem Ayarları ────────────────────────────────────────────────────────
@super_admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@super_admin_required
def settings():
    from app.models.models import SystemSettings
    cfg = SystemSettings.query.filter_by(scope='global').first()

    if request.method == 'POST':
        if not cfg:
            cfg = SystemSettings(scope='global')
            db.session.add(cfg)

        # Mail
        cfg.smtp_host       = request.form.get('smtp_host')
        cfg.smtp_port       = int(request.form.get('smtp_port', 587))
        cfg.smtp_user       = request.form.get('smtp_user')
        cfg.smtp_from_name  = request.form.get('smtp_from_name')
        cfg.smtp_from_email = request.form.get('smtp_user')
        cfg.smtp_use_tls    = bool(request.form.get('smtp_use_tls'))
        cfg.mail_active     = bool(request.form.get('mail_active'))
        if request.form.get('smtp_pass'):
            cfg.smtp_pass   = request.form.get('smtp_pass')

        # SMS
        cfg.netgsm_user      = request.form.get('netgsm_user')
        cfg.netgsm_header    = request.form.get('netgsm_header')
        cfg.sms_active       = bool(request.form.get('sms_active'))
        cfg.sms_provider     = request.form.get('sms_provider', 'vatansms')
        cfg.vatansms_api_id  = request.form.get('vatansms_api_id')
        cfg.vatansms_api_key = request.form.get('vatansms_api_key')
        if request.form.get('netgsm_pass'):
            cfg.netgsm_pass = request.form.get('netgsm_pass')

        db.session.commit()
        flash('Ayarlar kaydedildi.', 'success')

        if request.form.get('test_mail') and cfg.mail_active:
            from app.utils import send_mail
            test_to = request.form.get('test_email') or cfg.smtp_from_email
            ok, msg = send_mail(test_to, 'Test Maili', '<p>Site Aidat sistemi mail testi başarılı!</p>')
            flash(f'Mail test: {msg}', 'success' if ok else 'danger')

        if request.form.get('test_sms') and cfg.sms_active:
            from app.utils import send_sms
            ok, msg = send_sms(request.form.get('test_phone', ''), 'Site Aidat sistemi SMS testi başarılı!')
            flash(f'SMS test: {msg}', 'success' if ok else 'danger')

        return redirect(url_for('super_admin.settings'))

    return render_template('super_admin/settings.html', cfg=cfg)


# ── Giriş Logları ─────────────────────────────────────────────────────────
@super_admin_bp.route('/login-logs')
@login_required
@super_admin_required
def login_logs():
    from sqlalchemy import text
    logs = db.session.execute(text("""
        SELECT g.id, g.kimlik, g.ip_adresi, g.basarili, g.tarih, g.aciklama,
               u.full_name, u.role
        FROM giris_loglari g
        LEFT JOIN users u ON u.id = g.kullanici_id
        ORDER BY g.tarih DESC
        LIMIT 200
    """)).fetchall()
    return render_template('super_admin/login_logs.html', logs=logs)


# ── Siteye Özel Evrak ─────────────────────────────────────────────────────
ADMIN_DOC_KATEGORILER = [
    'Yönetim Planı',
    'Kat Mülkiyeti Kararları',
    'Sözleşmeler',
    'Duyurular',
    'Diğer'
]

@super_admin_bp.route('/evraklar')
@login_required
@super_admin_required
def admin_evraklar():
    from app.models.models import AdminDocument
    user_id = request.args.get('user_id', type=int)
    q = AdminDocument.query
    if user_id:
        q = q.filter_by(target_user_id=user_id)
    docs  = q.order_by(AdminDocument.created_at.desc()).all()
    site_adminler = User.query.filter_by(role='site_admin').all()
    return render_template('super_admin/admin_evraklar.html',
                           docs=docs, site_adminler=site_adminler,
                           kategoriler=ADMIN_DOC_KATEGORILER,
                           secili_user=user_id)


@super_admin_bp.route('/evraklar/yukle', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admin_evrak_yukle():
    from app.models.models import AdminDocument
    import os, uuid
    site_adminler = User.query.filter_by(role='site_admin').all()

    if request.method == 'POST':
        target_user_id = request.form.get('target_user_id', type=int)
        dosya          = request.files.get('dosya')
        if not dosya or dosya.filename == '':
            flash('Lütfen bir dosya seçin.', 'danger')
            return redirect(request.url)

        ext = os.path.splitext(dosya.filename)[1].lower()
        izin_verilen = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.txt']
        if ext not in izin_verilen:
            flash('Bu dosya türüne izin verilmiyor.', 'danger')
            return redirect(request.url)

        upload_dir = os.path.join('/var/www/probissi/data/www/probissite.com.tr/site_takip/uploads/admin', str(target_user_id))
        os.makedirs(upload_dir, exist_ok=True)
        benzersiz_ad = f"{uuid.uuid4().hex}{ext}"
        dosya_yolu   = os.path.join(upload_dir, benzersiz_ad)
        dosya.save(dosya_yolu)

        db.session.add(AdminDocument(
            target_user_id = target_user_id,
            title          = request.form.get('title'),
            category       = request.form.get('category'),
            filename       = benzersiz_ad,
            original_name  = dosya.filename,
            file_size      = os.path.getsize(dosya_yolu),
            uploaded_by    = current_user.id
        ))
        db.session.commit()
        flash('Evrak başarıyla gönderildi.', 'success')
        return redirect(url_for('super_admin.admin_evraklar'))

    return render_template('super_admin/admin_evrak_yukle.html',
                           site_adminler=site_adminler,
                           kategoriler=ADMIN_DOC_KATEGORILER)


@super_admin_bp.route('/evraklar/<int:doc_id>/indir')
@login_required
@super_admin_required
def admin_evrak_indir(doc_id):
    from app.models.models import AdminDocument
    from flask import send_from_directory
    import os
    doc = AdminDocument.query.get_or_404(doc_id)
    upload_dir = os.path.join('/var/www/probissi/data/www/probissite.com.tr/site_takip/uploads/admin', str(doc.target_user_id))
    return send_from_directory(upload_dir, doc.filename,
                               as_attachment=True, download_name=doc.original_name)


@super_admin_bp.route('/evraklar/<int:doc_id>/sil', methods=['POST'])
@login_required
@super_admin_required
def admin_evrak_sil(doc_id):
    from app.models.models import AdminDocument
    import os
    doc = AdminDocument.query.get_or_404(doc_id)
    dosya_yolu = os.path.join('/var/www/probissi/data/www/probissite.com.tr/site_takip/uploads/admin',
                              str(doc.target_user_id), doc.filename)
    if os.path.exists(dosya_yolu):
        os.remove(dosya_yolu)
    db.session.delete(doc)
    db.session.commit()
    flash('Evrak silindi.', 'success')
    return redirect(url_for('super_admin.admin_evraklar'))


# ── Site Admin Mesajları ───────────────────────────────────────────────────
@super_admin_bp.route('/site-mesajlari')
@login_required
@super_admin_required
def site_mesajlari():
    from app.models.models import AdminMessage
    durum = request.args.get('durum', 'acik')
    if durum == 'kapali':
        mesajlar = AdminMessage.query.filter_by(is_closed=True)            .order_by(AdminMessage.created_at.desc()).all()
    else:
        mesajlar = AdminMessage.query.filter_by(is_closed=False)            .order_by(AdminMessage.is_read, AdminMessage.created_at.desc()).all()
        for m in mesajlar:
            m.is_read = True
            m.super_admin_read = True
        db.session.commit()
    return render_template('super_admin/site_mesajlari.html', mesajlar=mesajlar)


@super_admin_bp.route('/site-mesajlari/<int:mid>/cevapla', methods=['POST'])
@login_required
@super_admin_required
def site_mesaj_cevapla(mid):
    from app.models.models import AdminMessage
    m = AdminMessage.query.get_or_404(mid)
    cevap = request.form.get('reply', '').strip()
    if cevap:
        m.reply      = cevap
        m.reply_at   = datetime.utcnow()
        m.reply_read = False
        db.session.commit()
        flash('Cevap gönderildi.', 'success')
    return redirect(url_for('super_admin.site_mesajlari'))
    
    
    # ── Context Processor ─────────────────────────────────────────────────────
@super_admin_bp.app_context_processor
def inject_unread_messages():
    from flask_login import current_user
    from app.models.models import AdminMessage
    count = 0
    try:
        if current_user.is_authenticated and current_user.role == 'super_admin':
            count = AdminMessage.query.filter_by(is_read=False).count()
    except Exception:
        pass
    return dict(super_admin_unread=count)

# ── Mesaj Kapat ───────────────────────────────────────────────────────────
@super_admin_bp.route('/site-mesajlari/<int:mid>/kapat', methods=['POST'])
@login_required
@super_admin_required
def site_mesaj_kapat(mid):
    from app.models.models import AdminMessage
    m = AdminMessage.query.get_or_404(mid)
    m.is_closed = True
    db.session.commit()
    flash('Mesaj kapatıldı.', 'success')
    return redirect(url_for('super_admin.site_mesajlari'))


# ── Kapatılmış Mesajları Toplu Sil ───────────────────────────────────────
@super_admin_bp.route('/site-mesajlari/toplu-sil', methods=['POST'])
@login_required
@super_admin_required
def site_mesaj_toplu_sil():
    from app.models.models import AdminMessage
    AdminMessage.query.filter_by(is_closed=True).delete()
    db.session.commit()
    flash('Kapatılmış mesajlar silindi.', 'success')
    return redirect(url_for('super_admin.site_mesajlari'))


# ── Demo Talepleri ────────────────────────────────────────────────────────
@super_admin_bp.route('/demo-talepleri')
@login_required
@super_admin_required
def demo_talepleri():
    from app.models.models import DemoRequest
    talepler = DemoRequest.query.order_by(DemoRequest.created_at.desc()).all()
    return render_template('super_admin/demo_talepleri.html', talepler=talepler)


@super_admin_bp.route('/demo-talepleri/<int:tid>/iletisim-kuruldu', methods=['POST'])
@login_required
@super_admin_required
def demo_iletisim_kuruldu(tid):
    from app.models.models import DemoRequest
    t = DemoRequest.query.get_or_404(tid)
    t.is_contacted = True
    db.session.commit()
    flash('İletişim kuruldu olarak işaretlendi.', 'success')
    return redirect(url_for('super_admin.demo_talepleri'))
