from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class License(db.Model):
    __tablename__ = 'licenses'
    id              = db.Column(db.Integer, primary_key=True)
    license_key     = db.Column(db.String(64), unique=True, nullable=False)
    description     = db.Column(db.String(255))
    is_active       = db.Column(db.Boolean, default=True)
    valid_until     = db.Column(db.Date, nullable=True)
    is_demo         = db.Column(db.Boolean, default=False)
    demo_start_date = db.Column(db.DateTime, nullable=True)
    demo_end_date   = db.Column(db.DateTime, nullable=True)
    demo_onay       = db.Column(db.Boolean, default=False)
    demo_onay_date  = db.Column(db.DateTime, nullable=True)
    demo_onay_ip    = db.Column(db.String(45), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    users   = db.relationship('User', backref='license', lazy='dynamic')
    profile = db.relationship('LicenseProfile', backref='license', uselist=False,
                              cascade='all, delete-orphan')

    @property
    def demo_suresi_doldu(self):
        if self.is_demo and self.demo_end_date:
            return datetime.utcnow() > self.demo_end_date
        return False

    @property
    def demo_kalan_gun(self):
        if self.is_demo and self.demo_end_date:
            kalan = (self.demo_end_date - datetime.utcnow()).days
            return max(0, kalan)
        return 0

    def __repr__(self):
        return f'<License {self.license_key}>'


class LicenseProfile(db.Model):
    __tablename__ = 'license_profiles'
    id              = db.Column(db.Integer, primary_key=True)
    license_id      = db.Column(db.Integer, db.ForeignKey('licenses.id'), nullable=False)
    firma_adi       = db.Column(db.String(128))
    yetkili_adi     = db.Column(db.String(128))
    vergi_no        = db.Column(db.String(20))
    vergi_dairesi   = db.Column(db.String(64))
    tc_no           = db.Column(db.String(11))
    telefon         = db.Column(db.String(20))
    email           = db.Column(db.String(120))
    province        = db.Column(db.String(64))
    district        = db.Column(db.String(64))
    neighborhood    = db.Column(db.String(64))
    address         = db.Column(db.Text)
    notlar          = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LicenseProfile {self.firma_adi}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(128))
    phone         = db.Column(db.String(20))
    role          = db.Column(db.String(20), nullable=False)
    is_active     = db.Column(db.Boolean, default=True)
    license_id    = db.Column(db.Integer, db.ForeignKey('licenses.id'), nullable=True)
    must_change_pw= db.Column(db.Boolean, default=False)
    reset_token   = db.Column(db.String(64), nullable=True)
    reset_token_exp= db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    residencies   = db.relationship('Resident', backref='user', lazy='dynamic',
                                    foreign_keys='Resident.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_super_admin(self):
        return self.role == 'super_admin'

    def is_site_admin(self):
        return self.role == 'site_admin'

    def is_resident(self):
        return self.role == 'resident'

    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


site_admins_table = db.Table('site_admins',
    db.Column('site_id', db.Integer, db.ForeignKey('sites.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)


class Site(db.Model):
    __tablename__ = 'sites'
    id                   = db.Column(db.Integer, primary_key=True)
    name                 = db.Column(db.String(128), nullable=False)
    province             = db.Column(db.String(64))
    district             = db.Column(db.String(64))
    neighborhood         = db.Column(db.String(64))
    address              = db.Column(db.Text)
    uavt_code            = db.Column(db.String(20))
    is_active            = db.Column(db.Boolean, default=True)
    gecikme_turu         = db.Column(db.String(10), default='gunluk')
    gecikme_oran         = db.Column(db.Numeric(5, 2), default=0)
    iban                 = db.Column(db.String(32))
    banka_adi            = db.Column(db.String(64))
    hesap_sahibi         = db.Column(db.String(128))
    donem_baslangic_gun  = db.Column(db.Integer, default=1)
    donem_bitis_gun      = db.Column(db.Integer, default=1)
    hesaplama_tipi       = db.Column(db.String(20), default='tum_site')  # tum_site / blok_bazli
    aidat_kriteri        = db.Column(db.String(20), default='daire_sayisi')  # daire_sayisi / m2 / arsa_payi
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    blocks   = db.relationship('Block', backref='site', lazy='dynamic',
                               cascade='all, delete-orphan')
    managers = db.relationship('User', secondary=site_admins_table,
                               backref=db.backref('managed_sites', lazy='dynamic'))

    def __repr__(self):
        return f'<Site {self.name}>'


class Block(db.Model):
    __tablename__ = 'blocks'
    id            = db.Column(db.Integer, primary_key=True)
    site_id       = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    name          = db.Column(db.String(64), nullable=False)
    province      = db.Column(db.String(64))
    district      = db.Column(db.String(64))
    neighborhood  = db.Column(db.String(64))
    address       = db.Column(db.Text)
    dis_kapi_no   = db.Column(db.String(20))
    uavt_code     = db.Column(db.String(20))
    iban          = db.Column(db.String(32))
    banka_adi     = db.Column(db.String(64))
    hesap_sahibi  = db.Column(db.String(128))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    apartments = db.relationship('Apartment', backref='block', lazy='dynamic',
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Block {self.name}>'


class Apartment(db.Model):
    __tablename__ = 'apartments'
    id              = db.Column(db.Integer, primary_key=True)
    block_id        = db.Column(db.Integer, db.ForeignKey('blocks.id'), nullable=False)
    number          = db.Column(db.String(16), nullable=False)
    floor           = db.Column(db.String(32))
    province        = db.Column(db.String(64))
    district        = db.Column(db.String(64))
    neighborhood    = db.Column(db.String(64))
    address         = db.Column(db.Text)
    uavt_code       = db.Column(db.String(20))
    number_type     = db.Column(db.String(12), default='numeric')
    number_length   = db.Column(db.Integer, default=3)
    aidat_muaf      = db.Column(db.Boolean, default=False)
    demirbas_muaf   = db.Column(db.Boolean, default=False)
    yakit_muaf      = db.Column(db.Boolean, default=False)
    muaf_aciklama   = db.Column(db.String(128))
    gorevli_muaf    = db.Column(db.Boolean, default=False)
    m2              = db.Column(db.Numeric(8, 2), nullable=True)
    arsa_payi       = db.Column(db.Numeric(10, 4), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    residents = db.relationship('Resident', backref='apartment', lazy='dynamic',
                                cascade='all, delete-orphan')
    dues      = db.relationship('Due', backref='apartment', lazy='dynamic')

    def __repr__(self):
        return f'<Apartment {self.number}>'


class Resident(db.Model):
    __tablename__ = 'residents'
    id              = db.Column(db.Integer, primary_key=True)
    apartment_id    = db.Column(db.Integer, db.ForeignKey('apartments.id'), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    first_name      = db.Column(db.String(64), nullable=False)
    last_name       = db.Column(db.String(64), nullable=False)
    tc_no           = db.Column(db.String(11))
    birth_date      = db.Column(db.Date)
    phone           = db.Column(db.String(20))
    email           = db.Column(db.String(120))
    resident_type   = db.Column(db.String(20), nullable=False)
    move_in_date    = db.Column(db.Date)
    move_out_date   = db.Column(db.Date, nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Resident {self.first_name} {self.last_name}>'


class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'
    id       = db.Column(db.Integer, primary_key=True)
    site_id  = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=True)
    name     = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))

    types    = db.relationship('ExpenseType', backref='category', lazy='dynamic',
                               cascade='all, delete-orphan')
    expenses = db.relationship('Expense', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'


class ExpenseType(db.Model):
    __tablename__ = 'expense_types'
    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=False)
    name        = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))

    expenses    = db.relationship('Expense', backref='expense_type', lazy='dynamic')

    def __repr__(self):
        return f'<ExpenseType {self.name}>'


class Expense(db.Model):
    __tablename__ = 'expenses'
    id            = db.Column(db.Integer, primary_key=True)
    site_id       = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    block_id      = db.Column(db.Integer, db.ForeignKey('blocks.id'), nullable=True)
    category_id   = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=False)
    type_id       = db.Column(db.Integer, db.ForeignKey('expense_types.id'), nullable=False)
    amount        = db.Column(db.Numeric(12, 2), nullable=False)
    description   = db.Column(db.Text)
    expense_date  = db.Column(db.Date, nullable=False)
    period_year   = db.Column(db.Integer, nullable=False)
    period_month  = db.Column(db.Integer, nullable=False)
    receipt_no    = db.Column(db.String(64))
    is_recurring  = db.Column(db.Boolean, default=False)
    created_by    = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    site          = db.relationship('Site', foreign_keys=[site_id])
    creator       = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Expense {self.amount} [{self.expense_date}]>'


class Due(db.Model):
    __tablename__ = 'dues'
    id              = db.Column(db.Integer, primary_key=True)
    apartment_id    = db.Column(db.Integer, db.ForeignKey('apartments.id'), nullable=False)
    resident_id     = db.Column(db.Integer, db.ForeignKey('residents.id'), nullable=True)
    period_start    = db.Column(db.Date, nullable=True)
    period_end      = db.Column(db.Date, nullable=True)
    period_year     = db.Column(db.Integer, nullable=False)
    period_month    = db.Column(db.Integer, nullable=False)
    amount          = db.Column(db.Numeric(12, 2), nullable=False)
    demirbas_amount = db.Column(db.Numeric(12, 2), default=0)
    normal_amount   = db.Column(db.Numeric(12, 2), default=0)
    yakit_amount    = db.Column(db.Numeric(12, 2), default=0)
    due_date        = db.Column(db.Date, nullable=True)
    yakit_due_date  = db.Column(db.Date, nullable=True)
    is_paid         = db.Column(db.Boolean, default=False)
    paid_date       = db.Column(db.Date, nullable=True)
    payment_note    = db.Column(db.String(255))
    gecikme_gun     = db.Column(db.Integer, default=0)
    gecikme_bedel   = db.Column(db.Numeric(12,2), default=0)
    due_type        = db.Column(db.String(20), default='normal')
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    resident        = db.relationship('Resident', foreign_keys=[resident_id])
    creator         = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Due {self.period_year}/{self.period_month} apt:{self.apartment_id}>'


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id              = db.Column(db.Integer, primary_key=True)
    scope           = db.Column(db.String(20), default='global')
    site_id         = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=True)
    smtp_host       = db.Column(db.String(128))
    smtp_port       = db.Column(db.Integer, default=587)
    smtp_user       = db.Column(db.String(128))
    smtp_pass       = db.Column(db.String(256))
    smtp_from_name  = db.Column(db.String(64))
    smtp_from_email = db.Column(db.String(128))
    smtp_use_tls    = db.Column(db.Boolean, default=True)
    sms_provider    = db.Column(db.String(20), default='vatansms')
    netgsm_user     = db.Column(db.String(64))
    netgsm_pass     = db.Column(db.String(128))
    netgsm_header   = db.Column(db.String(20))
    vatansms_api_id = db.Column(db.String(20))
    vatansms_api_key= db.Column(db.String(64))
    mail_active          = db.Column(db.Boolean, default=False)
    sms_active           = db.Column(db.Boolean, default=False)
    odeme_saglayici      = db.Column(db.String(20), default=None)
    odeme_active         = db.Column(db.Boolean, default=False)
    iyzico_api_key       = db.Column(db.String(128))
    iyzico_secret_key    = db.Column(db.String(128))
    iyzico_base_url      = db.Column(db.String(128))
    paytr_merchant_id    = db.Column(db.String(64))
    paytr_merchant_key   = db.Column(db.String(128))
    paytr_merchant_salt  = db.Column(db.String(128))
    stripe_public_key    = db.Column(db.String(128))
    stripe_secret_key    = db.Column(db.String(128))
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemSettings {self.scope}>'


class Notification(db.Model):
    __tablename__ = 'notifications'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title       = db.Column(db.String(128), nullable=False)
    message     = db.Column(db.Text)
    link        = db.Column(db.String(256))
    is_read     = db.Column(db.Boolean, default=False)
    notif_type  = db.Column(db.String(30), default='info')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<Notification {self.title}>'


class SiteDocument(db.Model):
    __tablename__ = 'site_documents'
    id            = db.Column(db.Integer, primary_key=True)
    site_id       = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    category      = db.Column(db.String(64), nullable=False)
    title         = db.Column(db.String(256), nullable=False)
    filename      = db.Column(db.String(256), nullable=False)
    original_name = db.Column(db.String(256))
    file_size     = db.Column(db.Integer)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    site     = db.relationship('Site', foreign_keys=[site_id])
    uploader = db.relationship('User', foreign_keys=[uploaded_by])


class ResidentMessage(db.Model):
    __tablename__ = 'resident_messages'
    id          = db.Column(db.Integer, primary_key=True)
    site_id     = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey('residents.id'), nullable=False)
    sender_id   = db.Column(db.Integer, db.ForeignKey('users.id'))
    title       = db.Column(db.String(256), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    reply       = db.Column(db.Text)
    reply_at    = db.Column(db.DateTime)
    reply_read  = db.Column(db.Boolean, default=False)
    is_read     = db.Column(db.Boolean, default=False)
    is_closed   = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    site     = db.relationship('Site', foreign_keys=[site_id])
    resident = db.relationship('Resident', foreign_keys=[resident_id])
    sender   = db.relationship('User', foreign_keys=[sender_id])


class AdminDocument(db.Model):
    __tablename__ = 'admin_documents'
    id              = db.Column(db.Integer, primary_key=True)
    site_id         = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=True)
    target_user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    title           = db.Column(db.String(256), nullable=False)
    category        = db.Column(db.String(64), nullable=False)
    filename        = db.Column(db.String(256), nullable=False)
    original_name   = db.Column(db.String(256))
    file_size       = db.Column(db.Integer)
    uploaded_by     = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    site        = db.relationship('Site', foreign_keys=[site_id])
    target_user = db.relationship('User', foreign_keys=[target_user_id])
    uploader    = db.relationship('User', foreign_keys=[uploaded_by])


class AdminMessage(db.Model):
    __tablename__ = 'admin_messages'
    id               = db.Column(db.Integer, primary_key=True)
    site_id          = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    sender_id        = db.Column(db.Integer, db.ForeignKey('users.id'))
    title            = db.Column(db.String(256), nullable=False)
    message          = db.Column(db.Text, nullable=False)
    is_read          = db.Column(db.Boolean, default=False)
    super_admin_read = db.Column(db.Boolean, default=False)
    reply            = db.Column(db.Text, nullable=True)
    reply_at         = db.Column(db.DateTime, nullable=True)
    reply_read       = db.Column(db.Boolean, default=False)
    is_closed        = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    site   = db.relationship('Site', foreign_keys=[site_id])
    sender = db.relationship('User', foreign_keys=[sender_id])


# ─────────────────────────────────────────
# DUYURULAR
# ─────────────────────────────────────────

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id           = db.Column(db.Integer, primary_key=True)
    site_id      = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    title        = db.Column(db.String(256), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    publish_at   = db.Column(db.DateTime, nullable=False)
    is_published = db.Column(db.Boolean, default=False)
    send_sms     = db.Column(db.Boolean, default=False)
    send_mail    = db.Column(db.Boolean, default=False)
    sms_sent     = db.Column(db.Boolean, default=False)
    mail_sent    = db.Column(db.Boolean, default=False)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    site    = db.relationship('Site', foreign_keys=[site_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Announcement {self.title}>'


class DemoRequest(db.Model):
    __tablename__ = 'demo_requests'
    id               = db.Column(db.Integer, primary_key=True)
    full_name        = db.Column(db.String(128), nullable=False)
    phone            = db.Column(db.String(20), nullable=False)
    email            = db.Column(db.String(128), nullable=False)
    site_name        = db.Column(db.String(128))
    apartment_count  = db.Column(db.String(32))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    is_contacted     = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<DemoRequest {self.full_name}>'


class IsletmeProje(db.Model):
    __tablename__ = 'isletme_projeleri'
    id               = db.Column(db.Integer, primary_key=True)
    site_id          = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    block_id         = db.Column(db.Integer, db.ForeignKey('blocks.id'), nullable=True)
    yil              = db.Column(db.Integer, nullable=False)
    kmk_karar_tarihi = db.Column(db.Date, nullable=True)
    kmk_karar_no     = db.Column(db.String(64))
    daire_sayisi     = db.Column(db.Integer, nullable=False)
    notlar           = db.Column(db.Text)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    site     = db.relationship('Site', foreign_keys=[site_id])
    block    = db.relationship('Block', foreign_keys=[block_id])
    creator  = db.relationship('User', foreign_keys=[created_by])
    kalemler = db.relationship('IsletmeProjeKalem', backref='proje',
                               cascade='all, delete-orphan', lazy='dynamic')

    @property
    def aylik_toplam(self):
        return sum(float(k.aylik_tutar) for k in self.kalemler)

    @property
    def yillik_toplam(self):
        return self.aylik_toplam * 12

    @property
    def daire_basi_aidat(self):
        if self.daire_sayisi:
            return self.aylik_toplam / self.daire_sayisi
        return 0

    def __repr__(self):
        return f'<IsletmeProje {self.yil}>'


class IsletmeProjeKalem(db.Model):
    __tablename__ = 'isletme_proje_kalemleri'
    id          = db.Column(db.Integer, primary_key=True)
    proje_id    = db.Column(db.Integer, db.ForeignKey('isletme_projeleri.id'), nullable=False)
    kalem_adi   = db.Column(db.String(128), nullable=False)
    aylik_tutar = db.Column(db.Numeric(12, 2), nullable=False)
    aciklama    = db.Column(db.String(255))

    def __repr__(self):
        return f'<IsletmeProjeKalem {self.kalem_adi}>'

class Demirbas(db.Model):
    __tablename__ = 'demirbaslar'
    id              = db.Column(db.Integer, primary_key=True)
    site_id         = db.Column(db.Integer, db.ForeignKey('sites.id'))
    block_id        = db.Column(db.Integer, db.ForeignKey('blocks.id'))
    kategori        = db.Column(db.String(64))
    ad              = db.Column(db.String(128), nullable=False)
    adet            = db.Column(db.Integer, default=1)
    alis_tarihi     = db.Column(db.Date)
    alis_fiyati     = db.Column(db.Numeric(10,2))
    garanti_bitis   = db.Column(db.Date)
    durum           = db.Column(db.String(32), default='aktif')
    notlar          = db.Column(db.Text)
    fatura_dosya    = db.Column(db.String(256))
    fatura_orijinal_ad = db.Column(db.String(256))
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    site  = db.relationship('Site',  foreign_keys=[site_id])
    block = db.relationship('Block', foreign_keys=[block_id])

    @property
    def garanti_durumu(self):
        if not self.garanti_bitis:
            return 'bilinmiyor'
        from datetime import date
        kalan = (self.garanti_bitis - date.today()).days
        if kalan < 0:
            return 'bitti'
        elif kalan <= 30:
            return 'yaklasan'
        return 'aktif'

    @property
    def garanti_kalan_gun(self):
        if not self.garanti_bitis:
            return None
        from datetime import date
        return (self.garanti_bitis - date.today()).days
