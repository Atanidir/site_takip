from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date
from app import db
from app.models.models import (
    Site, Block, Apartment, Resident, User,
    ExpenseCategory, ExpenseType, Expense, Due, Notification
)
from sqlalchemy import text

site_admin_bp = Blueprint('site_admin', __name__)


def site_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'site_admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def get_current_sites():
    """Adminin yönettiği tüm siteleri döner."""
    return current_user.managed_sites.order_by(Site.name).all()


def get_active_site():
    """Session'daki aktif siteyi döner, yoksa ilk siteyi seçer."""
    sites = get_current_sites()
    if not sites:
        return None
    site_id = session.get('active_site_id')
    if site_id:
        site = Site.query.get(site_id)
        if site and site in sites:
            return site
    session['active_site_id'] = sites[0].id
    return sites[0]


# ── Site Seç ─────────────────────────────────────────────────────────────
@site_admin_bp.route('/select-site/<int:site_id>')
@login_required
@site_admin_required
def select_site(site_id):
    sites = get_current_sites()
    site = Site.query.get_or_404(site_id)
    if site not in sites:
        flash('Yetkisiz işlem.', 'danger')
        return redirect(url_for('site_admin.dashboard'))
    session['active_site_id'] = site_id
    flash(f'{site.name} seçildi.', 'info')
    return redirect(request.referrer or url_for('site_admin.dashboard'))


# ── Dashboard ──────────────────────────────────────────────────────────────
@site_admin_bp.route('/dashboard')
@login_required
@site_admin_required
def dashboard():
    sites = get_current_sites()
    site  = get_active_site()
    stats = {}
    if site:
        stats['blocks']      = site.blocks.count()
        stats['apartments']  = sum(b.apartments.count() for b in site.blocks)
        stats['residents']   = Resident.query.join(Apartment).join(Block)\
                                .filter(Block.site_id == site.id, Resident.is_active == True).count()
        stats['unpaid_dues'] = Due.query.join(Apartment).join(Block)\
                                .filter(Block.site_id == site.id, Due.is_paid == False).count()
    return render_template('site_admin/dashboard.html', site=site, sites=sites, stats=stats,
                           today=date.today())


# ── Site Kurulumu ─────────────────────────────────────────────────────────
@site_admin_bp.route('/site/setup', methods=['GET', 'POST'])
@login_required
@site_admin_required
def site_setup():
    site = get_active_site()
    if request.method == 'POST':
        if site:
            site.name         = request.form.get('name')
            site.province     = request.form.get('province')
            site.district     = request.form.get('district')
            site.neighborhood = request.form.get('neighborhood')
            site.address      = request.form.get('address')
            site.uavt_code    = request.form.get('uavt_code')
            site.gecikme_turu        = request.form.get('gecikme_turu', 'gunluk')
            site.gecikme_oran        = float(request.form.get('gecikme_oran', 0))
            site.iban                = request.form.get('iban', '').replace(' ', '')
            site.banka_adi           = request.form.get('banka_adi')
            site.hesap_sahibi        = request.form.get('hesap_sahibi')
            site.donem_baslangic_gun = int(request.form.get('donem_baslangic_gun', 1))
            site.donem_bitis_gun     = int(request.form.get('donem_bitis_gun', 1))
        else:
            site = Site(
                name=request.form.get('name'), province=request.form.get('province'),
                district=request.form.get('district'), neighborhood=request.form.get('neighborhood'),
                address=request.form.get('address'), uavt_code=request.form.get('uavt_code'),
                gecikme_turu=request.form.get('gecikme_turu', 'gunluk'),
                gecikme_oran=float(request.form.get('gecikme_oran', 0)),
                iban=request.form.get('iban', '').replace(' ', ''),
                banka_adi=request.form.get('banka_adi'),
                hesap_sahibi=request.form.get('hesap_sahibi'),
                donem_baslangic_gun=int(request.form.get('donem_baslangic_gun', 1)),
                donem_bitis_gun=int(request.form.get('donem_bitis_gun', 1)),
            )
            site.managers.append(current_user)
            db.session.add(site)
            db.session.flush()
            block_count = int(request.form.get('block_count', 0))
            for i in range(block_count):
                db.session.add(Block(site_id=site.id, name=f'{chr(65+i)} Blok'))
            session['active_site_id'] = site.id
        db.session.commit()
        flash('Site bilgileri kaydedildi.', 'success')
        return redirect(url_for('site_admin.dashboard'))
    return render_template('site_admin/site_setup.html', site=site)


# ── Yeni Site Ekle ────────────────────────────────────────────────────────
@site_admin_bp.route('/site/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_site():
    if request.method == 'POST':
        site = Site(
            name=request.form.get('name'), province=request.form.get('province'),
            district=request.form.get('district'), neighborhood=request.form.get('neighborhood'),
            address=request.form.get('address'), uavt_code=request.form.get('uavt_code'),
        )
        site.managers.append(current_user)
        db.session.add(site)
        db.session.flush()
        block_count = int(request.form.get('block_count', 0))
        for i in range(block_count):
            db.session.add(Block(site_id=site.id, name=f'{chr(65+i)} Blok'))
        session['active_site_id'] = site.id
        db.session.commit()
        flash(f'{site.name} oluşturuldu.', 'success')
        return redirect(url_for('site_admin.dashboard'))
    return render_template('site_admin/site_setup.html', site=None)


@site_admin_bp.route('/sites/<int:sid>/delete', methods=['POST'])
@login_required
@site_admin_required
def delete_site(sid):
    site = Site.query.get_or_404(sid)

    # Kullanıcının bu siteye yetkisi var mı
    if site not in current_user.managed_sites.all():
        flash('Bu siteyi silme yetkiniz yok.', 'danger')
        return redirect(url_for('site_admin.dashboard'))

    # Cascade silme — bağlı tüm veriler
    for blk in Block.query.filter_by(site_id=sid).all():
        for apt in Apartment.query.filter_by(block_id=blk.id).all():
            Due.query.filter_by(apartment_id=apt.id).delete()
            Resident.query.filter_by(apartment_id=apt.id).delete()
            db.session.delete(apt)
        # Bloğa ait giderleri sil
        Expense.query.filter_by(block_id=blk.id).delete()
        db.session.delete(blk)

    # Siteye ait giderleri sil
    Expense.query.filter_by(site_id=sid).delete()
    Notification.query.filter_by(user_id=current_user.id).delete()

    # Site-admin ilişkisini temizle
    from sqlalchemy import text
    db.session.execute(text('DELETE FROM site_admins WHERE site_id = :sid'), {'sid': sid})

    db.session.delete(site)
    db.session.commit()

    # Aktif site güncelle
    if session.get('active_site_id') == sid:
        session.pop('active_site_id', None)

    flash('Site ve tüm bağlı veriler silindi.', 'success')
    return redirect(url_for('site_admin.dashboard'))


# ── Blok Yönetimi ─────────────────────────────────────────────────────────
@site_admin_bp.route('/blocks')
@login_required
@site_admin_required
def blocks():
    site = get_active_site()
    if not site:
        flash('Önce site oluşturun.', 'warning')
        return redirect(url_for('site_admin.new_site'))
    return render_template('site_admin/blocks.html', site=site, blocks=site.blocks.all())


@site_admin_bp.route('/blocks/<int:bid>/delete', methods=['POST'])
@login_required
@site_admin_required
def delete_block(bid):
    blk = Block.query.get_or_404(bid)
    site = get_active_site()
    for apt in Apartment.query.filter_by(block_id=bid).all():
        Due.query.filter_by(apartment_id=apt.id).delete()
        Resident.query.filter_by(apartment_id=apt.id).delete()
        db.session.delete(apt)
    db.session.delete(blk)
    db.session.commit()
    flash('Blok ve tüm bağlı veriler silindi.', 'success')
    return redirect(url_for('site_admin.blocks'))


@site_admin_bp.route('/apartments/<int:aid>/delete', methods=['POST'])
@login_required
@site_admin_required
def delete_apartment(aid):
    apt = Apartment.query.get_or_404(aid)
    blk = apt.block
    Due.query.filter_by(apartment_id=aid).delete()
    Resident.query.filter_by(apartment_id=aid).delete()
    db.session.delete(apt)
    db.session.commit()
    flash('Daire ve tüm bağlı veriler silindi.', 'success')
    return redirect(url_for('site_admin.apartments', bid=blk.id))
    site = get_active_site()
    if not site:
        flash('Önce site oluşturun.', 'warning')
        return redirect(url_for('site_admin.new_site'))
    return render_template('site_admin/blocks.html', site=site, blocks=site.blocks.all())


@site_admin_bp.route('/blocks/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_block():
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.new_site'))
    if request.method == 'POST':
        db.session.add(Block(
            site_id=site.id, name=request.form.get('name'),
            province=request.form.get('province') or site.province,
            district=request.form.get('district') or site.district,
            neighborhood=request.form.get('neighborhood') or site.neighborhood,
            dis_kapi_no=request.form.get('dis_kapi_no'),
            uavt_code=request.form.get('uavt_code')
        ))
        db.session.commit()
        flash('Blok eklendi.', 'success')
        return redirect(url_for('site_admin.blocks'))
    return render_template('site_admin/block_form.html', site=site, block=None)


@site_admin_bp.route('/blocks/<int:bid>/edit', methods=['GET', 'POST'])
@login_required
@site_admin_required
def edit_block(bid):
    site = get_active_site()
    blk  = Block.query.get_or_404(bid)
    if request.method == 'POST':
        blk.name         = request.form.get('name')
        blk.province     = request.form.get('province') or site.province
        blk.district     = request.form.get('district') or site.district
        blk.neighborhood = request.form.get('neighborhood') or site.neighborhood
        blk.dis_kapi_no  = request.form.get('dis_kapi_no')
        blk.uavt_code    = request.form.get('uavt_code')
        db.session.commit()
        flash('Blok güncellendi.', 'success')
        return redirect(url_for('site_admin.blocks'))
    return render_template('site_admin/block_form.html', site=site, block=blk)


# ── Daire Yönetimi ────────────────────────────────────────────────────────
@site_admin_bp.route('/blocks/<int:bid>/apartments')
@login_required
@site_admin_required
def apartments(bid):
    site = get_active_site()
    blk  = Block.query.get_or_404(bid)
    return render_template('site_admin/apartments.html', site=site, block=blk,
                           apartments=blk.apartments.order_by(Apartment.number).all())


@site_admin_bp.route('/blocks/<int:bid>/apartments/bulk', methods=['GET', 'POST'])
@login_required
@site_admin_required
def bulk_apartments(bid):
    site = get_active_site()
    blk  = Block.query.get_or_404(bid)
    if request.method == 'POST':
        count=int(request.form.get('count',1)); num_type=request.form.get('number_type','numeric')
        num_length=int(request.form.get('number_length',3)); start_from=int(request.form.get('start_from',1))
        for i in range(count):
            n=start_from+i
            db.session.add(Apartment(
                block_id=blk.id, number=str(n).zfill(num_length) if num_type=='numeric' else str(n),
                number_type=num_type, number_length=num_length,
            ))
        db.session.commit()
        flash(f'{count} daire oluşturuldu.', 'success')
        return redirect(url_for('site_admin.apartments', bid=bid))
    return render_template('site_admin/bulk_apartments.html', site=site, block=blk)


@site_admin_bp.route('/blocks/<int:bid>/apartments/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_apartment(bid):
    site = get_active_site()
    blk  = Block.query.get_or_404(bid)
    if request.method == 'POST':
        db.session.add(Apartment(
            block_id=blk.id, number=request.form.get('number'),
            floor=request.form.get('floor') or None,
            number_type=request.form.get('number_type','numeric'),
            number_length=int(request.form.get('number_length',3)),
            uavt_code=request.form.get('uavt_code'),
            aidat_muaf=bool(request.form.get('aidat_muaf')),
            demirbas_muaf=bool(request.form.get('demirbas_muaf')),
            yakit_muaf=bool(request.form.get('yakit_muaf')),
            muaf_aciklama=request.form.get('muaf_aciklama')
        ))
        db.session.commit()
        flash('Daire eklendi.', 'success')
        return redirect(url_for('site_admin.apartments', bid=bid))
    return render_template('site_admin/apartment_form.html', site=site, block=blk, apartment=None)


@site_admin_bp.route('/apartments/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
@site_admin_required
def edit_apartment(aid):
    site = get_active_site()
    apt  = Apartment.query.get_or_404(aid)
    blk  = apt.block
    if request.method == 'POST':
        apt.number        = request.form.get('number')
        apt.floor         = request.form.get('floor') or None
        apt.number_type   = request.form.get('number_type')
        apt.number_length = int(request.form.get('number_length',3))
        apt.uavt_code     = request.form.get('uavt_code')
        apt.aidat_muaf    = bool(request.form.get('aidat_muaf'))
        apt.demirbas_muaf = bool(request.form.get('demirbas_muaf'))
        apt.yakit_muaf    = bool(request.form.get('yakit_muaf'))
        apt.muaf_aciklama = request.form.get('muaf_aciklama')
        db.session.commit()
        flash('Daire güncellendi.', 'success')
        return redirect(url_for('site_admin.apartments', bid=blk.id))
    return render_template('site_admin/apartment_form.html', site=site, block=blk, apartment=apt)


# ── Sakin Yönetimi ────────────────────────────────────────────────────────
@site_admin_bp.route('/apartments/<int:aid>/residents')
@login_required
@site_admin_required
def residents(aid):
    site = get_active_site()
    apt  = Apartment.query.get_or_404(aid)
    res  = Resident.query.filter_by(apartment_id=aid).order_by(Resident.move_in_date.desc()).all()
    return render_template('site_admin/residents.html', site=site, apartment=apt, residents=res)


@site_admin_bp.route('/apartments/<int:aid>/residents/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_resident(aid):
    site = get_active_site()
    apt  = Apartment.query.get_or_404(aid)
    # URL'den tip bilgisi al (kiracı ekle butonundan geliyorsa)
    default_type = request.args.get('type', 'owner')
    show_tenant_dialog = False

    if request.method == 'POST':
        tc_no = request.form.get('tc_no', '').strip()
        if tc_no and not _tc_dogrula(tc_no):
            flash('Geçersiz TC Kimlik No girdiniz.', 'danger')
            return render_template('site_admin/resident_form.html', site=site, apartment=apt,
                                   resident=None, default_type=default_type)
        email = request.form.get('email')
        u = User.query.filter_by(email=email).first() if email else None
        resident_type = request.form.get('resident_type')
        # Mükerrer kayıt kontrolü — aynı TC + aynı daire
        if tc_no:
            mevcut = Resident.query.filter_by(
                tc_no=tc_no, apartment_id=aid, is_active=True
            ).first()
            if mevcut:
                flash(f'Bu TC kimlik numarası ({tc_no}) zaten bu dairede aktif sakin olarak kayıtlı!', 'danger')
                return render_template('site_admin/resident_form.html',
                                       site=site, apartment=apt, resident=None,
                                       default_type=default_type)

        db.session.add(Resident(
            apartment_id=aid, first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'), tc_no=tc_no or None,
            birth_date=_parse_date(request.form.get('birth_date')), phone=request.form.get('phone'),
            email=email, resident_type=resident_type,
            move_in_date=_parse_date(request.form.get('move_in_date')),
            move_out_date=_parse_date(request.form.get('move_out_date')),
            is_active=True, notes=request.form.get('notes'), user_id=u.id if u else None
        ))
        db.session.commit()

        # TC varsa otomatik kullanıcı oluştur veya mevcut kullanıcıya bağla
        if tc_no:
            mevcut_user = User.query.filter_by(username=tc_no).first()
            if mevcut_user:
                # Kullanıcı zaten var, sadece sakin kaydına bağla
                son_sakin = Resident.query.filter_by(
                    apartment_id=aid, is_active=True
                ).order_by(Resident.id.desc()).first()
                if son_sakin:
                    son_sakin.user_id = mevcut_user.id
                db.session.commit()
            else:
                # Yeni kullanıcı oluştur
                email_to_use = email if email and not User.query.filter_by(email=email).first() else f'{tc_no}@siteaidat.local'
                yeni_user = User(
                    username  = tc_no,
                    email     = email_to_use,
                    full_name = f"{request.form.get('first_name')} {request.form.get('last_name')}",
                    phone     = request.form.get('phone'),
                    role      = 'resident',
                    is_active = True
                )
                yeni_user.set_password('')
                db.session.add(yeni_user)
                db.session.flush()
                son_sakin = Resident.query.filter_by(
                    apartment_id=aid, is_active=True
                ).order_by(Resident.id.desc()).first()
                if son_sakin:
                    son_sakin.user_id = yeni_user.id
                db.session.commit()
        flash('Sakin eklendi.', 'success')

        # Mülk sahibi kaydedildiyse kiracı durumunu kontrol et
        if resident_type == 'owner':
            aktif_kiraci = Resident.query.filter_by(
                apartment_id=aid, resident_type='tenant', is_active=True
            ).first()
            if aktif_kiraci:
                # Zaten kiracı var, çıktı mı diye sor
                return render_template('site_admin/residents.html', site=site, apartment=apt,
                                       residents=Resident.query.filter_by(apartment_id=aid).order_by(Resident.move_in_date.desc()).all(),
                                       show_existing_tenant_dialog=True,
                                       existing_tenant=aktif_kiraci)
            else:
                # Kiracı yok, eklensin mi diye sor
                return render_template('site_admin/residents.html', site=site, apartment=apt,
                                       residents=Resident.query.filter_by(apartment_id=aid).order_by(Resident.move_in_date.desc()).all(),
                                       show_tenant_dialog=True)
        return redirect(url_for('site_admin.residents', aid=aid))

    return render_template('site_admin/resident_form.html', site=site, apartment=apt,
                           resident=None, default_type=default_type)


@site_admin_bp.route('/residents/<int:rid>/edit', methods=['GET', 'POST'])
@login_required
@site_admin_required
def edit_resident(rid):
    site = get_active_site()
    res  = Resident.query.get_or_404(rid)
    apt  = res.apartment
    if request.method == 'POST':
        tc_no = request.form.get('tc_no', '').strip()
        if tc_no and not _tc_dogrula(tc_no):
            flash('Geçersiz TC Kimlik No girdiniz.', 'danger')
            return render_template('site_admin/resident_form.html', site=site, apartment=apt, resident=res, default_type=res.resident_type)

        eski_tip   = res.resident_type
        move_out   = _parse_date(request.form.get('move_out_date'))

        res.first_name    = request.form.get('first_name')
        res.last_name     = request.form.get('last_name')
        res.tc_no         = tc_no or None
        res.birth_date    = _parse_date(request.form.get('birth_date'))
        res.phone         = request.form.get('phone')
        res.email         = request.form.get('email')
        res.resident_type = request.form.get('resident_type')
        res.move_in_date  = _parse_date(request.form.get('move_in_date'))
        res.move_out_date = move_out
        res.notes         = request.form.get('notes')

        # Çıkış tarihi girilmişse otomatik pasif yap
        if move_out:
            res.is_active = False
            # Bağlı kullanıcıyı da pasif yap
            if res.tc_no:
                kullanici = User.query.filter_by(username=res.tc_no, role='resident').first()
                if kullanici:
                    kullanici.is_active = False
            # Ödenmemiş aidat var mı kontrol et
            odenmemis = Due.query.filter_by(
                resident_id=res.id, is_paid=False
            ).count()
            if odenmemis > 0:
                flash(f'Sakin pasife alındı ancak {odenmemis} adet ödenmemiş aidatı bulunmaktadır!', 'warning')
            else:
                flash('Sakin pasife alındı.', 'success')
        else:
            res.is_active = bool(request.form.get('is_active'))
            flash('Sakin bilgileri güncellendi.', 'success')

        db.session.commit()

        # Mülk sahibi çıkış yaptıysa yeni sahip dialog göster
        show_owner_dialog = (eski_tip == 'owner' and move_out is not None and not res.is_active)
        if show_owner_dialog:
            return render_template('site_admin/residents.html', site=site, apartment=apt,
                                   residents=Resident.query.filter_by(apartment_id=apt.id).order_by(Resident.move_in_date.desc()).all(),
                                   show_owner_dialog=True)
        return redirect(url_for('site_admin.residents', aid=apt.id))
    return render_template('site_admin/resident_form.html', site=site, apartment=apt, resident=res, default_type=res.resident_type)


# ── Gider Kategorileri & Türleri ──────────────────────────────────────────
@site_admin_bp.route('/expense-categories')
@login_required
@site_admin_required
def expense_categories():
    site = get_active_site()
    cats = ExpenseCategory.query.all() if site else []
    return render_template('site_admin/expense_categories.html', site=site, categories=cats)


@site_admin_bp.route('/expense-categories/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_expense_category():
    site = get_active_site()
    if request.method == 'POST':
        db.session.add(ExpenseCategory(name=request.form.get('name'),
                                       description=request.form.get('description')))
        db.session.commit()
        flash('Kategori eklendi.', 'success')
        return redirect(url_for('site_admin.expense_categories'))
    return render_template('site_admin/expense_category_form.html', site=site, category=None)


@site_admin_bp.route('/expense-types/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_expense_type():
    site = get_active_site()
    cats = ExpenseCategory.query.all()
    if request.method == 'POST':
        db.session.add(ExpenseType(category_id=int(request.form.get('category_id')),
                                   name=request.form.get('name'),
                                   description=request.form.get('description')))
        db.session.commit()
        flash('Gider türü eklendi.', 'success')
        return redirect(url_for('site_admin.expense_categories'))
    return render_template('site_admin/expense_type_form.html', site=site, categories=cats, expense_type=None)


# ── Gider Kayıtları ───────────────────────────────────────────────────────
@site_admin_bp.route('/expenses')
@login_required
@site_admin_required
def expenses():
    site  = get_active_site()
    year  = request.args.get('year',  datetime.now().year,  type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    exp_list = Expense.query.filter_by(site_id=site.id, period_year=year, period_month=month)\
                .order_by(Expense.expense_date.desc()).all() if site else []
    total = sum(float(e.amount) for e in exp_list)
    return render_template('site_admin/expenses.html', site=site,
                           expenses=exp_list, total=total, year=year, month=month)


@site_admin_bp.route('/expenses/new', methods=['GET', 'POST'])
@login_required
@site_admin_required
def new_expense():
    site  = get_active_site()
    sites = get_current_sites()
    cats  = ExpenseCategory.query.all() if site else []
    blocks = site.blocks.all() if site else []
    now   = datetime.now()
    if request.method == 'POST':
        sel_site_id = int(request.form.get('site_id', site.id))
        db.session.add(Expense(
            site_id=sel_site_id, category_id=int(request.form.get('category_id')),
            type_id=int(request.form.get('type_id')), amount=request.form.get('amount'),
            block_id=request.form.get('block_id') or None,
            description=request.form.get('description'),
            expense_date=_parse_date(request.form.get('expense_date')),
            period_year=int(request.form.get('period_year')),
            period_month=int(request.form.get('period_month')),
            receipt_no=request.form.get('receipt_no'),
            is_recurring=bool(request.form.get('is_recurring')),
            created_by=current_user.id
        ))
        db.session.commit()
        flash('Gider kaydedildi.', 'success')
        return redirect(url_for('site_admin.expenses'))
    return render_template('site_admin/expense_form.html', site=site, sites=sites,
                           categories=cats, blocks=blocks, expense=None,
                           today=date.today().isoformat(), now_year=now.year, now_month=now.month)


# ── Aidat Yönetimi ────────────────────────────────────────────────────────
@site_admin_bp.route('/dues')
@login_required
@site_admin_required
def dues():
    site     = get_active_site()
    year     = request.args.get('year',    datetime.now().year,  type=int)
    month    = request.args.get('month',   datetime.now().month, type=int)
    site_id  = request.args.get('site_id', type=int)
    blok_id  = request.args.get('blok_id', type=int)

    # Kullanıcının yönettiği tüm siteler
    from app.models.models import Site as SiteModel
    yonetilen_siteler = Site.query.join(
        db.Table('site_admins', db.metadata),
        (db.Table('site_admins', db.metadata).c.site_id == Site.id)
    ).filter(db.Table('site_admins', db.metadata).c.user_id == current_user.id).all() if not current_user.role == 'super_admin' else Site.query.all()

    aktif_site_id = site_id or (site.id if site else None)

    q = Due.query.join(Apartment).join(Block)
    if aktif_site_id:
        q = q.filter(Block.site_id == aktif_site_id)
    elif site:
        q = q.filter(Block.site_id == site.id)

    q = q.filter(Due.period_year == year, Due.period_month == month)

    if blok_id:
        q = q.filter(Block.id == blok_id)

    dues_list       = q.filter(Due.due_type == 'normal').order_by(Block.name, Apartment.number).all()
    yakit_dues_list = q.filter(Due.due_type == 'yakit').order_by(Block.name, Apartment.number).all()

    # Geçmiş dönemlerden ödenmemiş yakıt borçlarını da ekle
    gecmis_yakit_q = Due.query.join(Apartment).join(Block)
    if aktif_site_id:
        gecmis_yakit_q = gecmis_yakit_q.filter(Block.site_id == aktif_site_id)
    elif site:
        gecmis_yakit_q = gecmis_yakit_q.filter(Block.site_id == site.id)
    if blok_id:
        gecmis_yakit_q = gecmis_yakit_q.filter(Block.id == blok_id)

    gecmis_yakit = gecmis_yakit_q.filter(
        Due.due_type == 'yakit',
        Due.is_paid == False,
        db.or_(
            Due.period_year < year,
            db.and_(Due.period_year == year, Due.period_month < month)
        )
    ).order_by(Due.period_year, Due.period_month, Block.name, Apartment.number).all()

    # Geçmiş borçları listeye ekle (tekrar ekleme)
    mevcut_ids = {d.id for d in yakit_dues_list}
    for d in gecmis_yakit:
        if d.id not in mevcut_ids:
            yakit_dues_list.append(d)
    tum_dues        = dues_list + yakit_dues_list

    # Filtre için bloklar
    bloklar = Block.query.filter_by(site_id=aktif_site_id).order_by(Block.name).all() if aktif_site_id else []

    return render_template('site_admin/dues.html', site=site,
                           dues=dues_list, yakit_dues=yakit_dues_list,
                           year=year, month=month, today=date.today(),
                           yonetilen_siteler=yonetilen_siteler,
                           site_id=aktif_site_id, blok_id=blok_id, bloklar=bloklar)


@site_admin_bp.route('/dues/generate', methods=['GET', 'POST'])
@login_required
@site_admin_required
def generate_dues():
    site = get_active_site()
    now  = datetime.now()
    if request.method == 'POST':
        start_date    = _parse_date(request.form.get('start_date'))
        end_date      = _parse_date(request.form.get('end_date'))
        due_date      = _parse_date(request.form.get('due_date'))
        yakit_due_date= _parse_date(request.form.get('yakit_due_date'))
        year          = int(request.form.get('year'))
        month         = int(request.form.get('month'))
        demirbas_top  = float(request.form.get('demirbas_toplam', 0))
        normal_top    = float(request.form.get('normal_toplam', 0))
        yakit_top     = float(request.form.get('yakit_toplam', 0))

        # Toplam daire sayısı
        tum_daireler = []
        for blk in site.blocks.all():
            tum_daireler.extend(blk.apartments.all())

        daire_sayisi = len(tum_daireler)
        if daire_sayisi == 0:
            flash('Sistemde daire bulunamadı.', 'danger')
            return redirect(url_for('site_admin.generate_dues'))

        daire_demirbas = round(demirbas_top / daire_sayisi, 2)
        daire_normal   = round(normal_top   / daire_sayisi, 2)
        daire_yakit    = round(yakit_top    / daire_sayisi, 2) if yakit_top > 0 else 0

        count = 0
        for apt in tum_daireler:
            # Muafiyet kontrolleri
            normal_muaf   = apt.aidat_muaf
            demirbas_muaf = apt.demirbas_muaf
            yakit_muaf    = apt.yakit_muaf

            # Tüm muafiyetler varsa atla
            if normal_muaf and demirbas_muaf and yakit_muaf:
                continue

            # Mevcut aidat varsa atla
            if Due.query.filter_by(apartment_id=apt.id, period_year=year, period_month=month).first():
                continue

            # Aktif sakin bilgisi
            aktif_sakin = Resident.query.filter_by(apartment_id=apt.id, is_active=True).first()
            kiraci = Resident.query.filter_by(apartment_id=apt.id, is_active=True, resident_type='tenant').first()
            sahip  = Resident.query.filter_by(apartment_id=apt.id, resident_type='owner').order_by(Resident.move_in_date.desc()).first()

            # Muafiyete göre tutarları ayarla
            apt_demirbas = 0 if demirbas_muaf else daire_demirbas
            apt_normal   = 0 if normal_muaf else daire_normal
            apt_yakit    = 0 if yakit_muaf else daire_yakit

            if aktif_sakin is None:
                # Boş daire
                if apt_demirbas + apt_normal > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=sahip.id if sahip else None,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_demirbas + apt_normal,
                        demirbas_amount=apt_demirbas, normal_amount=apt_normal,
                        yakit_amount=0, due_type='normal',
                        due_date=due_date, is_paid=False, created_by=current_user.id
                    ))
                if apt_yakit > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=sahip.id if sahip else None,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_yakit, demirbas_amount=0, normal_amount=0,
                        yakit_amount=apt_yakit, due_type='yakit',
                        due_date=yakit_due_date, is_paid=False, created_by=current_user.id
                    ))
                count += 1

            elif kiraci:
                # Kiracıya → normal pay
                if apt_normal > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=kiraci.id,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_normal, demirbas_amount=0, normal_amount=apt_normal,
                        yakit_amount=0, due_type='normal',
                        due_date=due_date, is_paid=False, created_by=current_user.id
                    ))
                # Kiracıya yakıt
                if apt_yakit > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=kiraci.id,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_yakit, demirbas_amount=0, normal_amount=0,
                        yakit_amount=apt_yakit, due_type='yakit',
                        due_date=yakit_due_date, is_paid=False, created_by=current_user.id
                    ))
                # Mülk sahibine → demirbaş pay
                if apt_demirbas > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=sahip.id if sahip else None,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_demirbas, demirbas_amount=apt_demirbas, normal_amount=0,
                        yakit_amount=0, due_type='normal',
                        due_date=due_date, is_paid=False, created_by=current_user.id
                    ))
                count += 2

            else:
                # Mülk sahibi oturuyor
                if apt_demirbas + apt_normal > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=aktif_sakin.id,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_demirbas + apt_normal,
                        demirbas_amount=apt_demirbas, normal_amount=apt_normal,
                        yakit_amount=0, due_type='normal',
                        due_date=due_date, is_paid=False, created_by=current_user.id
                    ))
                if apt_yakit > 0:
                    db.session.add(Due(
                        apartment_id=apt.id, resident_id=aktif_sakin.id,
                        period_year=year, period_month=month,
                        period_start=start_date, period_end=end_date,
                        amount=apt_yakit, demirbas_amount=0, normal_amount=0,
                        yakit_amount=apt_yakit, due_type='yakit',
                        due_date=yakit_due_date, is_paid=False, created_by=current_user.id
                    ))
                count += 1

        db.session.commit()
        flash(f'{count} aidat kaydı oluşturuldu.', 'success')
        return redirect(url_for('site_admin.dues', year=year, month=month))
    return render_template('site_admin/generate_dues.html', site=site, year=now.year, month=now.month)


@site_admin_bp.route('/api/gider-hesapla')
@login_required
@site_admin_required
def api_gider_hesapla():
    site_id = request.args.get('site_id', type=int)
    start   = request.args.get('start')
    end     = request.args.get('end')

    site = Site.query.get_or_404(site_id)

    # Gider kategorilerini al
    cats = ExpenseCategory.query.all()
    demirbas_ids = [c.id for c in cats if 'demirbas' in c.name.lower().replace('ş','s').replace('â','a') or 'fixture' in c.name.lower()]
    yakit_ids    = [c.id for c in cats if 'yakit' in c.name.lower().replace('ı','i').replace('â','a') or 'yakıt' in c.name.lower()]
    normal_ids   = [c.id for c in cats if c.id not in demirbas_ids and c.id not in yakit_ids]

    # Tarih aralığındaki giderleri topla
    expenses = Expense.query.filter(
        Expense.site_id == site_id,
        Expense.expense_date >= start,
        Expense.expense_date <= end
    ).all()

    demirbas_top = sum(float(e.amount) for e in expenses if e.category_id in demirbas_ids)
    normal_top   = sum(float(e.amount) for e in expenses if e.category_id in normal_ids)
    yakit_top    = sum(float(e.amount) for e in expenses if e.category_id in yakit_ids)

    # Toplam daire sayısı
    daire_sayisi = sum(b.apartments.count() for b in site.blocks)
    daire_demirbas = round(demirbas_top / daire_sayisi, 2) if daire_sayisi > 0 else 0
    daire_yakit    = round(yakit_top    / daire_sayisi, 2) if daire_sayisi > 0 else 0

    return jsonify({
        'demirbas'      : demirbas_top,
        'normal'        : normal_top,
        'yakit'         : yakit_top,
        'daire_sayisi'  : daire_sayisi,
        'daire_demirbas': daire_demirbas,
        'daire_yakit'   : daire_yakit
    })


@site_admin_bp.route('/dues/<int:did>/pay', methods=['POST'])
@login_required
@site_admin_required
def pay_due(did):
    due  = Due.query.get_or_404(did)
    site = get_active_site()
    paid_date    = _parse_date(request.form.get('paid_date')) or date.today()
    payment_note = request.form.get('payment_note', '')

    due.is_paid      = True
    due.paid_date    = paid_date
    due.payment_note = payment_note

    # Gecikme hesabı
    if due.due_date and paid_date > due.due_date:
        gun = (paid_date - due.due_date).days
        due.gecikme_gun = gun
        oran = float(site.gecikme_oran or 0)
        if oran > 0:
            if site.gecikme_turu == 'gunluk':
                due.gecikme_bedel = round(float(due.amount) * (oran / 100) * gun, 2)
            else:  # aylık
                ay = gun / 30
                due.gecikme_bedel = round(float(due.amount) * (oran / 100) * ay, 2)
        else:
            due.gecikme_bedel = 0
    else:
        due.gecikme_gun   = 0
        due.gecikme_bedel = 0

    db.session.commit()
    flash('Ödeme kaydedildi.', 'success')
    return redirect(request.referrer or url_for('site_admin.dues'))


@site_admin_bp.route('/dues/<int:did>/toggle-paid')
@login_required
@site_admin_required
def toggle_due_paid(did):
    due = Due.query.get_or_404(did)
    due.is_paid       = not due.is_paid
    due.paid_date     = date.today() if due.is_paid else None
    due.gecikme_gun   = 0
    due.gecikme_bedel = 0
    due.payment_note  = None
    db.session.commit()
    flash('Aidat durumu güncellendi.', 'info')
    return redirect(request.referrer or url_for('site_admin.dues'))


# ── AJAX ──────────────────────────────────────────────────────────────────
@site_admin_bp.route('/api/expense-types/<int:cat_id>')
@login_required
@site_admin_required
def api_expense_types(cat_id):
    types = ExpenseType.query.filter_by(category_id=cat_id).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in types])


@site_admin_bp.route('/api/iller')
@login_required
@site_admin_required
def api_iller():
    rows = db.session.execute(text("SELECT ilid, iladi FROM il ORDER BY iladi")).fetchall()
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


@site_admin_bp.route('/api/ilceler/<int:il_id>')
@login_required
@site_admin_required
def api_ilceler(il_id):
    rows = db.session.execute(
        text("SELECT ilceid, ilceadi FROM ilce WHERE ilid = :ilid ORDER BY ilceadi"),
        {'ilid': il_id}
    ).fetchall()
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


@site_admin_bp.route('/api/mahalleler/<int:ilce_id>')
@login_required
@site_admin_required
def api_mahalleler(ilce_id):
    rows = db.session.execute(
        text("SELECT mahalleid, mahalleadi FROM mahalle WHERE ilceid = :ilceid ORDER BY mahalleadi"),
        {'ilceid': ilce_id}
    ).fetchall()
    return jsonify([{'id': r[0], 'ad': r[1]} for r in rows])


@site_admin_bp.route('/api/blocks/<int:site_id>')
@login_required
@site_admin_required
def api_blocks(site_id):
    blks = Block.query.filter_by(site_id=site_id).order_by(Block.name).all()
    return jsonify([{'id': b.id, 'name': b.name} for b in blks])


@site_admin_bp.route('/api/categories/<int:site_id>')
@login_required
@site_admin_required
def api_categories(site_id):
    cats = ExpenseCategory.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in cats])


# ── Yardımcı ─────────────────────────────────────────────────────────────
def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except Exception:
        return None


def _tc_dogrula(tc):
    if len(tc) != 11 or not tc.isdigit() or tc[0] == '0':
        return False
    d = [int(x) for x in tc]
    s1 = (d[0]+d[2]+d[4]+d[6]+d[8])*7 - (d[1]+d[3]+d[5]+d[7])
    if s1 % 10 != d[9]:
        return False
    if sum(d[:10]) % 10 != d[10]:
        return False
    return True


@site_admin_bp.route('/expenses/<int:eid>/edit', methods=['GET', 'POST'])
@login_required
@site_admin_required
def edit_expense(eid):
    site  = get_active_site()
    sites = get_current_sites()
    exp   = Expense.query.get_or_404(eid)
    cats  = ExpenseCategory.query.all()
    blocks = Block.query.filter_by(site_id=exp.site_id).all()
    now   = datetime.now()
    if request.method == 'POST':
        exp.site_id      = int(request.form.get('site_id', exp.site_id))
        exp.category_id  = int(request.form.get('category_id'))
        exp.type_id      = int(request.form.get('type_id'))
        exp.block_id     = request.form.get('block_id') or None
        exp.amount       = request.form.get('amount')
        exp.description  = request.form.get('description')
        exp.expense_date = _parse_date(request.form.get('expense_date'))
        exp.period_year  = int(request.form.get('period_year'))
        exp.period_month = int(request.form.get('period_month'))
        exp.receipt_no   = request.form.get('receipt_no')
        exp.is_recurring = bool(request.form.get('is_recurring'))
        db.session.commit()
        flash('Gider güncellendi.', 'success')
        return redirect(url_for('site_admin.expenses'))
    return render_template('site_admin/expense_form.html', site=site, sites=sites,
                           categories=cats, blocks=blocks, expense=exp,
                           today=exp.expense_date.isoformat() if exp.expense_date else date.today().isoformat(),
                           now_year=exp.period_year, now_month=exp.period_month)


@site_admin_bp.route('/dues/delete', methods=['GET', 'POST'])
@login_required
@site_admin_required
def delete_dues():
    site  = get_active_site()
    sites = get_current_sites()
    now   = datetime.now()

    if request.method == 'POST':
        site_id  = int(request.form.get('site_id'))
        block_id = request.form.get('block_id') or None
        year     = int(request.form.get('year'))
        month    = int(request.form.get('month'))

        q = Due.query.join(Apartment).join(Block).filter(
            Block.site_id == site_id,
            Due.period_year == year,
            Due.period_month == month
        )
        if block_id:
            q = q.filter(Block.id == int(block_id))

        count = q.count()
        due_ids = [d.id for d in q.all()]
        Due.query.filter(Due.id.in_(due_ids)).delete(synchronize_session='fetch')
        db.session.commit()
        flash(f'{count} aidat kaydı silindi.', 'success')
        return redirect(url_for('site_admin.dues', year=year, month=month))

    return render_template('site_admin/delete_dues.html', site=site, sites=sites,
                           year=now.year, month=now.month)


# ── Raporlama Ana Sayfa ───────────────────────────────────────────────────
@site_admin_bp.route('/reports')
@login_required
@site_admin_required
def reports():
    return redirect(url_for('site_admin.report_aidat'))


# ── Aidat Raporu ──────────────────────────────────────────────────────────
@site_admin_bp.route('/reports/aidat')
@login_required
@site_admin_required
def report_aidat():
    site  = get_active_site()
    now   = datetime.now()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    year   = request.args.get('year',   now.year,  type=int)
    month  = request.args.get('month',  now.month, type=int)
    blok_id = request.args.get('blok_id', '', type=str)
    durum  = request.args.get('durum',  'tumu')  # tumu | odenen | bekleyen | geciken

    q = Due.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Due.period_year == year,
        Due.period_month == month
    )
    if blok_id:
        q = q.filter(Block.id == int(blok_id))
    if durum == 'odenen':
        q = q.filter(Due.is_paid == True)
    elif durum == 'bekleyen':
        q = q.filter(Due.is_paid == False)
    elif durum == 'geciken':
        q = q.filter(Due.is_paid == False, Due.due_date < date.today())

    dues = q.order_by(Block.name, Apartment.number).all()

    toplam         = sum(float(d.amount) for d in dues)
    odenen         = sum(float(d.amount) for d in dues if d.is_paid)
    bekleyen       = sum(float(d.amount) for d in dues if not d.is_paid)
    gecikme_top    = sum(float(d.gecikme_bedel or 0) for d in dues)
    blocks         = site.blocks.order_by(Block.name).all()

    return render_template('site_admin/report_aidat.html',
        site=site, year=year, month=month, blok_id=blok_id, durum=durum,
        dues=dues, toplam=toplam, odenen=odenen, bekleyen=bekleyen,
        gecikme_top=gecikme_top, blocks=blocks, today=date.today()
    )


# ── Gider Raporu ──────────────────────────────────────────────────────────
@site_admin_bp.route('/reports/gider')
@login_required
@site_admin_required
def report_gider():
    site  = get_active_site()
    now   = datetime.now()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    year     = request.args.get('year',     now.year,  type=int)
    month    = request.args.get('month',    now.month, type=int)
    blok_id  = request.args.get('blok_id', '',        type=str)
    cat_id   = request.args.get('cat_id',  '',        type=str)
    type_id  = request.args.get('type_id', '',        type=str)

    q = Expense.query.filter_by(site_id=site.id, period_year=year, period_month=month)
    if blok_id:
        q = q.filter(Expense.block_id == int(blok_id))
    if cat_id:
        q = q.filter(Expense.category_id == int(cat_id))
    if type_id:
        q = q.filter(Expense.type_id == int(type_id))

    expenses = q.order_by(Expense.expense_date.desc()).all()
    toplam   = sum(float(e.amount) for e in expenses)

    from collections import defaultdict
    kategori_gider = defaultdict(float)
    blok_gider     = defaultdict(float)
    for e in expenses:
        kategori_gider[e.category.name] += float(e.amount)
        blok_adi = Block.query.get(e.block_id).name if e.block_id else 'Tüm Site'
        blok_gider[blok_adi] += float(e.amount)

    blocks     = site.blocks.order_by(Block.name).all()
    categories = ExpenseCategory.query.all()
    exp_types  = ExpenseType.query.filter(
        ExpenseType.category_id.in_([c.id for c in categories])
    ).all() if cat_id else []

    return render_template('site_admin/report_gider.html',
        site=site, year=year, month=month, blok_id=blok_id,
        cat_id=cat_id, type_id=type_id,
        expenses=expenses, toplam=toplam,
        kategori_gider=dict(kategori_gider), blok_gider=dict(blok_gider),
        blocks=blocks, categories=categories, exp_types=exp_types
    )


# ── Sakin Raporu ──────────────────────────────────────────────────────────
@site_admin_bp.route('/reports/sakin')
@login_required
@site_admin_required
def report_sakin():
    site  = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    blok_id = request.args.get('blok_id', '', type=str)
    durum   = request.args.get('durum',   'tumu')  # tumu | sahip | kiraci | bos

    sakin_listesi = []
    blok_q = site.blocks.order_by(Block.name)
    if blok_id:
        blok_q = blok_q.filter(Block.id == int(blok_id))

    for blk in blok_q.all():
        for apt in blk.apartments.order_by(Apartment.number).all():
            aktif  = Resident.query.filter_by(apartment_id=apt.id, is_active=True).all()
            sahip  = next((r for r in aktif if r.resident_type == 'owner'),  None)
            kiraci = next((r for r in aktif if r.resident_type == 'tenant'), None)

            if durum == 'sahip'  and not (sahip and not kiraci): continue
            if durum == 'kiraci' and not kiraci:                  continue
            if durum == 'bos'    and (sahip or kiraci):           continue

            sakin_listesi.append({
                'blok'  : blk.name,
                'daire' : apt.number,
                'apt_id': apt.id,
                'sahip' : sahip,
                'kiraci': kiraci,
            })

    blocks = site.blocks.order_by(Block.name).all()

    return render_template('site_admin/report_sakin.html',
        site=site, blok_id=blok_id, durum=durum,
        sakin_listesi=sakin_listesi, blocks=blocks
    )


# ── Site Ayarları ─────────────────────────────────────────────────────────
@site_admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@site_admin_required
def settings():
    from app.models.models import SystemSettings
    site = get_active_site()
    cfg  = SystemSettings.query.filter_by(scope='site', site_id=site.id).first() if site else None
    global_cfg = SystemSettings.query.filter_by(scope='global').first()

    if request.method == 'POST':
        if not cfg:
            cfg = SystemSettings(scope='site', site_id=site.id)
            db.session.add(cfg)

        cfg.smtp_host       = request.form.get('smtp_host')
        cfg.smtp_port       = int(request.form.get('smtp_port', 587))
        cfg.smtp_user       = request.form.get('smtp_user')
        cfg.smtp_from_name  = request.form.get('smtp_from_name')
        cfg.smtp_from_email = request.form.get('smtp_user')  # Kullanıcı adı = gönderen
        cfg.smtp_use_tls    = bool(request.form.get('smtp_use_tls'))
        cfg.mail_active     = bool(request.form.get('mail_active'))
        if request.form.get('smtp_pass'):
            cfg.smtp_pass   = request.form.get('smtp_pass')

        cfg.netgsm_user      = request.form.get('netgsm_user')
        cfg.netgsm_header    = request.form.get('netgsm_header')
        cfg.sms_active       = bool(request.form.get('sms_active'))
        cfg.sms_provider     = request.form.get('sms_provider', 'vatansms')
        cfg.vatansms_api_id  = request.form.get('vatansms_api_id')
        cfg.vatansms_api_key = request.form.get('vatansms_api_key')
        if request.form.get('netgsm_pass'):
            cfg.netgsm_pass = request.form.get('netgsm_pass')

        # Ödeme
        cfg.odeme_active        = bool(request.form.get('odeme_active'))
        cfg.odeme_saglayici     = request.form.get('odeme_saglayici')
        cfg.iyzico_api_key      = request.form.get('iyzico_api_key') or cfg.iyzico_api_key
        cfg.iyzico_base_url     = request.form.get('iyzico_base_url')
        cfg.paytr_merchant_id   = request.form.get('paytr_merchant_id') or cfg.paytr_merchant_id
        cfg.stripe_public_key   = request.form.get('stripe_public_key') or cfg.stripe_public_key
        if request.form.get('iyzico_secret_key'):
            cfg.iyzico_secret_key = request.form.get('iyzico_secret_key')
        if request.form.get('paytr_merchant_key'):
            cfg.paytr_merchant_key = request.form.get('paytr_merchant_key')
        if request.form.get('paytr_merchant_salt'):
            cfg.paytr_merchant_salt = request.form.get('paytr_merchant_salt')
        if request.form.get('stripe_secret_key'):
            cfg.stripe_secret_key = request.form.get('stripe_secret_key')

        db.session.commit()
        flash('Ayarlar kaydedildi.', 'success')

        if request.form.get('test_mail') and cfg.mail_active:
            from app.utils import send_mail
            test_to = request.form.get('test_email') or cfg.smtp_from_email
            ok, msg = send_mail(test_to, 'Test Maili',
                               f'<p>{site.name} sistemi mail testi başarılı!</p>')
            flash(f'Mail test: {msg}', 'success' if ok else 'danger')

        if request.form.get('test_sms') and cfg.sms_active:
            from app.utils import send_sms
            ok, msg = send_sms(request.form.get('test_phone', ''),
                              'Site Aidat sistemi SMS testi başarılı!', site.id)
            flash(f'SMS test: {msg}', 'success' if ok else 'danger')

        return redirect(url_for('site_admin.settings'))

    return render_template('site_admin/settings.html', cfg=cfg, global_cfg=global_cfg, site=site)


# ── Tüm Sakinler Listesi ──────────────────────────────────────────────────
@site_admin_bp.route('/all-residents')
@login_required
@site_admin_required
def all_residents():
    site    = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    blok_id  = request.args.get('blok_id', '')
    site_id  = request.args.get('site_id', '')
    tur      = request.args.get('tur', 'tumu')
    durum    = request.args.get('durum', 'aktif')
    arama    = request.args.get('arama', '').strip()

    # Kullanıcının yönettiği tüm siteler
    from app.models.models import Site
    yonetilen_siteler = current_user.managed_sites.all() if hasattr(current_user, 'managed_sites') else [site]

    q = Resident.query.join(Apartment).join(Block).filter(
        Block.site_id.in_([s.id for s in yonetilen_siteler])
    )

    if site_id:
        q = q.filter(Block.site_id == int(site_id))
    if blok_id:
        q = q.filter(Block.id == int(blok_id))
    if tur != 'tumu':
        q = q.filter(Resident.resident_type == tur)
    if durum == 'aktif':
        q = q.filter(Resident.is_active == True)
    elif durum == 'pasif':
        q = q.filter(Resident.is_active == False)
    if arama:
        q = q.filter(
            db.or_(
                Resident.first_name.ilike(f'%{arama}%'),
                Resident.last_name.ilike(f'%{arama}%'),
                Resident.tc_no.ilike(f'%{arama}%'),
                Resident.phone.ilike(f'%{arama}%'),
            )
        )

    residents = q.order_by(Block.name, Apartment.number, Resident.is_active.desc()).all()
    blocks    = Block.query.filter(Block.site_id.in_([s.id for s in yonetilen_siteler])).order_by(Block.name).all()

    return render_template('site_admin/all_residents.html',
        site=site, residents=residents, blocks=blocks,
        yonetilen_siteler=yonetilen_siteler,
        blok_id=blok_id, site_id=site_id, tur=tur, durum=durum, arama=arama
    )


# ── Bildirimler ───────────────────────────────────────────────────────────
@site_admin_bp.route('/notifications')
@login_required
@site_admin_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
                .order_by(Notification.created_at.desc()).limit(50).all()
    # Hepsini okundu yap
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('site_admin/notifications.html', notifications=notifs)


@site_admin_bp.route('/notifications/generate')
@login_required
@site_admin_required
def generate_notifications():
    """Mevcut duruma göre bildirimleri oluştur."""
    from app.models.models import Notification
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    today    = date.today()
    count    = 0

    # ── Gecikmiş aidatlar ──
    geciken = Due.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Due.is_paid   == False,
        Due.due_date  < today
    ).all()

    if geciken:
        # Aynı bildirim zaten var mı kontrol et (bugün oluşturulmuş)
        mevcut = Notification.query.filter_by(
            user_id    = current_user.id,
            notif_type = 'danger',
            title      = 'Gecikmiş Aidatlar'
        ).filter(
            Notification.created_at >= datetime.combine(today, datetime.min.time())
        ).first()
        if not mevcut:
            db.session.add(Notification(
                user_id    = current_user.id,
                title      = 'Gecikmiş Aidatlar',
                message    = f'{len(geciken)} adet aidat vadesi geçmiş.',
                link       = url_for('site_admin.dues'),
                notif_type = 'danger'
            ))
            count += 1

    # ── 3 gün içinde vadesi dolacak aidatlar ──
    from datetime import timedelta
    yaklasan = Due.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Due.is_paid   == False,
        Due.due_date  >= today,
        Due.due_date  <= today + timedelta(days=3)
    ).all()

    if yaklasan:
        mevcut = Notification.query.filter_by(
            user_id    = current_user.id,
            notif_type = 'warning',
            title      = 'Yaklaşan Aidat Vadesi'
        ).filter(
            Notification.created_at >= datetime.combine(today, datetime.min.time())
        ).first()
        if not mevcut:
            db.session.add(Notification(
                user_id    = current_user.id,
                title      = 'Yaklaşan Aidat Vadesi',
                message    = f'{len(yaklasan)} aidatın vadesi 3 gün içinde dolacak.',
                link       = url_for('site_admin.dues'),
                notif_type = 'warning'
            ))
            count += 1

    # ── Lisans süresi ──
    if current_user.license and current_user.license.valid_until:
        kalan = (current_user.license.valid_until - today).days
        if kalan <= 30:
            mevcut = Notification.query.filter_by(
                user_id    = current_user.id,
                notif_type = 'warning' if kalan > 0 else 'danger',
                title      = 'Lisans Uyarısı'
            ).filter(
                Notification.created_at >= datetime.combine(today, datetime.min.time())
            ).first()
            if not mevcut:
                db.session.add(Notification(
                    user_id    = current_user.id,
                    title      = 'Lisans Uyarısı',
                    message    = f'Lisansınız {"sona erdi" if kalan < 0 else f"{kalan} gün içinde dolacak"}.',
                    link       = '#',
                    notif_type = 'danger' if kalan < 0 else 'warning'
                ))
                count += 1

    db.session.commit()
    return redirect(url_for('site_admin.notifications'))


@site_admin_bp.route('/notifications/<int:nid>/read')
@login_required
@site_admin_required
def mark_notification_read(nid):
    n = Notification.query.get_or_404(nid)
    n.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for('site_admin.notifications'))


@site_admin_bp.route('/send-due-notifications')
@login_required
@site_admin_required
def send_due_notifications():
    """Sakinlere aidat vadesi yaklaşıyor/geçti bildirimi gönder."""
    from app.utils import send_mail, send_sms
    from datetime import timedelta

    site  = get_active_site()
    today = date.today()
    sent_mail = 0
    sent_sms  = 0
    errors    = []

    # 3 gün sonra vadesi dolacak ve bugün vadesi gelen aidatlar
    dues = Due.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Due.is_paid   == False,
        Due.due_date  >= today,
        Due.due_date  <= today + timedelta(days=3)
    ).all()

    # Gecikmiş aidatlar
    geciken = Due.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Due.is_paid   == False,
        Due.due_date  < today
    ).all()

    tum_dues = dues + geciken

    for due in tum_dues:
        res = due.resident
        if not res:
            continue

        gecikti = due.due_date and due.due_date < today
        kalan   = (due.due_date - today).days if due.due_date and not gecikti else 0

        if gecikti:
            konu = f'Gecikmiş Aidat Bildirimi — {site.name}'
            mesaj_kisa = f'{site.name} - {due.apartment.block.name} Daire {due.apartment.number}: {due.amount} ₺ tutarındaki aidatınız gecikmiştir.'
            mesaj_html = f"""
            <p>Sayın {res.full_name()},</p>
            <p><strong>{site.name}</strong> sitesindeki <strong>{due.apartment.block.name} / Daire {due.apartment.number}</strong> için
            <strong>{due.amount} ₺</strong> tutarındaki aidatınızın vadesi <strong>{due.due_date.strftime('%d.%m.%Y')}</strong> tarihinde geçmiştir.</p>
            {f'<p>Gecikme bedeli: <strong>{due.gecikme_bedel} ₺</strong></p>' if due.gecikme_bedel and due.gecikme_bedel > 0 else ''}
            {f'<p>Ödeme yapabileceğiniz IBAN: <strong>{site.iban}</strong> ({site.banka_adi})</p>' if site.iban else ''}
            <p>Lütfen en kısa sürede ödemenizi yapınız.</p>
            """
        else:
            konu = f'Aidat Vadesi Yaklaşıyor — {site.name}'
            mesaj_kisa = f'{site.name} - {due.apartment.block.name} Daire {due.apartment.number}: {due.amount} ₺ tutarındaki aidatınızın vadesi {kalan} gün içinde dolacak.'
            mesaj_html = f"""
            <p>Sayın {res.full_name()},</p>
            <p><strong>{site.name}</strong> sitesindeki <strong>{due.apartment.block.name} / Daire {due.apartment.number}</strong> için
            <strong>{due.amount} ₺</strong> tutarındaki aidatınızın vadesi <strong>{due.due_date.strftime('%d.%m.%Y')}</strong> tarihinde dolacaktır.</p>
            {f'<p>Ödeme yapabileceğiniz IBAN: <strong>{site.iban}</strong> ({site.banka_adi})</p>' if site.iban else ''}
            <p>Zamanında ödeme yaparak gecikme faizinden kaçınabilirsiniz.</p>
            """

        # Mail gönder
        if res.email:
            ok, msg = send_mail(res.email, konu, mesaj_html, site.id)
            if ok:
                sent_mail += 1
            else:
                errors.append(f'Mail ({res.full_name()}): {msg}')

        # SMS gönder
        if res.phone:
            ok, msg = send_sms(res.phone, mesaj_kisa, site.id)
            if ok:
                sent_sms += 1
            else:
                errors.append(f'SMS ({res.full_name()}): {msg}')

    if errors:
        flash(f'{sent_mail} mail, {sent_sms} SMS gönderildi. Hatalar: {"; ".join(errors[:3])}', 'warning')
    else:
        flash(f'{sent_mail} mail ve {sent_sms} SMS başarıyla gönderildi.', 'success')

    return redirect(url_for('site_admin.notifications'))


# ── Borçlu Pasif Sakinler ─────────────────────────────────────────────────
@site_admin_bp.route('/borclu-pasif-sakinler')
@login_required
@site_admin_required
def borclu_pasif_sakinler():
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    # Pasif sakinlerin ödenmemiş aidatlarını bul
    from sqlalchemy import func
    sonuclar = []
    pasif_sakinler = Resident.query.join(Apartment).join(Block).filter(
        Block.site_id == site.id,
        Resident.is_active == False
    ).all()

    for res in pasif_sakinler:
        odenmemis = Due.query.filter_by(resident_id=res.id, is_paid=False).all()
        if odenmemis:
            toplam_borc = sum(float(d.amount) for d in odenmemis)
            sonuclar.append({
                'resident'    : res,
                'apartment'   : res.apartment,
                'odenmemis'   : odenmemis,
                'toplam_borc' : toplam_borc
            })

    return render_template('site_admin/borclu_pasif_sakinler.html',
                           site=site, sonuclar=sonuclar)


# ── Sakin Kullanıcıları ───────────────────────────────────────────────────
@site_admin_bp.route('/sakin-kullanicilari')
@login_required
@site_admin_required
def sakin_kullanicilari():
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    # Sitedeki tüm sakinlerin TC'siyle eşleşen kullanıcılar
    site_tc_listesi = [
        r.tc_no for r in Resident.query.join(Apartment).join(Block)
        .filter(Block.site_id == site.id, Resident.tc_no != None).all()
    ]

    kullanicilar = User.query.filter(
        User.username.in_(site_tc_listesi),
        User.role == 'resident'
    ).all()

    # Her kullanıcıya sakin bilgisini ekle
    sonuclar = []
    for u in kullanicilar:
        res = Resident.query.filter_by(tc_no=u.username).order_by(
            Resident.is_active.desc(), Resident.move_in_date.desc()
        ).first()
        sonuclar.append({'kullanici': u, 'resident': res})

    return render_template('site_admin/sakin_kullanicilari.html',
                           site=site, sonuclar=sonuclar)


@site_admin_bp.route('/sakin-kullanicilari/<int:uid>/toggle', methods=['POST'])
@login_required
@site_admin_required
def toggle_sakin_kullanici(uid):
    u = User.query.get_or_404(uid)
    site = get_active_site()

    if u.is_active:
        # Pasif yap
        u.is_active = False
        db.session.commit()
        flash(f'{u.username} kullanıcısı pasif yapıldı.', 'success')
    else:
        # Aktif yap — daire seçimi
        apt_id = request.form.get('apartment_id', type=int)
        if not apt_id:
            flash('Lütfen bir daire seçin.', 'danger')
            return redirect(url_for('site_admin.sakin_kullanicilari'))

        apt = Apartment.query.get_or_404(apt_id)
        u.is_active = True

        # İlgili sakini de aktif yap
        res = Resident.query.filter_by(tc_no=u.username, apartment_id=apt_id).first()
        if res:
            res.is_active = True
            res.move_out_date = None
        else:
            flash('Sakin kaydı bulunamadı, sadece kullanıcı aktif yapıldı.', 'warning')

        db.session.commit()
        flash(f'{u.username} kullanıcısı {apt.block.name} / Daire {apt.number} için aktif yapıldı.', 'success')

    return redirect(url_for('site_admin.sakin_kullanicilari'))


# ── Evrak Klasörü ─────────────────────────────────────────────────────────
EVRAK_KATEGORILER = [
    'Kat Mülkiyeti Kararları',
    'Yönetim Planı',
    'Toplantı Tutanakları',
    'Sözleşmeler',
    'Faturalar',
    'Diğer'
]

@site_admin_bp.route('/evraklar')
@login_required
@site_admin_required
def evraklar():
    from app.models.models import SiteDocument
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))
    kategori = request.args.get('kategori', '')
    q = SiteDocument.query.filter_by(site_id=site.id)
    if kategori:
        q = q.filter_by(category=kategori)
    docs = q.order_by(SiteDocument.created_at.desc()).all()
    return render_template('site_admin/evraklar.html',
                           site=site, docs=docs,
                           kategoriler=EVRAK_KATEGORILER,
                           secili_kategori=kategori)


@site_admin_bp.route('/evraklar/yukle', methods=['GET', 'POST'])
@login_required
@site_admin_required
def evrak_yukle():
    from app.models.models import SiteDocument
    import os, uuid
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    if request.method == 'POST':
        dosya = request.files.get('dosya')
        if not dosya or dosya.filename == '':
            flash('Lütfen bir dosya seçin.', 'danger')
            return redirect(request.url)

        # Dosya kaydet
        upload_dir = os.path.join('/home/probissi/site_takip/uploads', str(site.id))
        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(dosya.filename)[1].lower()
        izin_verilen = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.txt']
        if ext not in izin_verilen:
            flash('Bu dosya türüne izin verilmiyor.', 'danger')
            return redirect(request.url)

        benzersiz_ad = f"{uuid.uuid4().hex}{ext}"
        dosya_yolu   = os.path.join(upload_dir, benzersiz_ad)
        dosya.save(dosya_yolu)
        dosya_boyut  = os.path.getsize(dosya_yolu)

        doc = SiteDocument(
            site_id       = site.id,
            category      = request.form.get('category'),
            title         = request.form.get('title'),
            filename      = benzersiz_ad,
            original_name = dosya.filename,
            file_size     = dosya_boyut,
            uploaded_by   = current_user.id
        )
        db.session.add(doc)
        db.session.commit()
        flash('Evrak başarıyla yüklendi.', 'success')
        return redirect(url_for('site_admin.evraklar'))

    return render_template('site_admin/evrak_yukle.html',
                           site=site, kategoriler=EVRAK_KATEGORILER)


@site_admin_bp.route('/evraklar/<int:doc_id>/indir')
@login_required
@site_admin_required
def evrak_indir(doc_id):
    from app.models.models import SiteDocument
    from flask import send_from_directory
    import os
    doc  = SiteDocument.query.get_or_404(doc_id)
    site = get_active_site()
    upload_dir = os.path.join('/home/probissi/site_takip/uploads', str(doc.site_id))
    return send_from_directory(upload_dir, doc.filename,
                               as_attachment=True,
                               download_name=doc.original_name)


@site_admin_bp.route('/evraklar/<int:doc_id>/sil', methods=['POST'])
@login_required
@site_admin_required
def evrak_sil(doc_id):
    from app.models.models import SiteDocument
    import os
    doc = SiteDocument.query.get_or_404(doc_id)
    dosya_yolu = os.path.join('/home/probissi/site_takip/uploads',
                              str(doc.site_id), doc.filename)
    if os.path.exists(dosya_yolu):
        os.remove(dosya_yolu)
    db.session.delete(doc)
    db.session.commit()
    flash('Evrak silindi.', 'success')
    return redirect(url_for('site_admin.evraklar'))


# ── Sakin Mesajları ───────────────────────────────────────────────────────
@site_admin_bp.route('/sakin-mesajlari')
@login_required
@site_admin_required
def sakin_mesajlari():
    from app.models.models import ResidentMessage
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    durum = request.args.get('durum', 'acik')  # acik | kapali | tumu
    q = ResidentMessage.query.filter_by(site_id=site.id)
    if durum == 'acik':
        q = q.filter_by(is_closed=False)
    elif durum == 'kapali':
        q = q.filter_by(is_closed=True)

    mesajlar = q.order_by(ResidentMessage.is_read, ResidentMessage.created_at.desc()).all()

    # Okunmamışları okundu yap
    for m in mesajlar:
        if not m.is_read:
            m.is_read = True
    db.session.commit()

    return render_template('site_admin/sakin_mesajlari.html',
                           site=site, mesajlar=mesajlar, durum=durum)


@site_admin_bp.route('/sakin-mesajlari/<int:mid>/cevapla', methods=['POST'])
@login_required
@site_admin_required
def sakin_mesaj_cevapla(mid):
    from app.models.models import ResidentMessage
    m = ResidentMessage.query.get_or_404(mid)
    cevap = request.form.get('reply', '').strip()
    if cevap:
        m.reply     = cevap
        m.reply_at  = datetime.now()
        m.is_closed = True
        db.session.commit()
        flash('Cevap gönderildi ve mesaj kapatıldı.', 'success')
    return redirect(url_for('site_admin.sakin_mesajlari'))


@site_admin_bp.route('/sakin-mesajlari/<int:mid>/kapat', methods=['POST'])
@login_required
@site_admin_required
def sakin_mesaj_kapat(mid):
    from app.models.models import ResidentMessage
    m = ResidentMessage.query.get_or_404(mid)
    m.is_closed = True
    db.session.commit()
    flash('Mesaj kapatıldı.', 'success')
    return redirect(url_for('site_admin.sakin_mesajlari'))


# ── Süper Admin'e Mesaj ───────────────────────────────────────────────────
@site_admin_bp.route('/superadmine-mesaj', methods=['GET', 'POST'])
@login_required
@site_admin_required
def superadmine_mesaj():
    from app.models.models import AdminMessage
    site = get_active_site()

    if request.method == 'POST':
        title   = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        if not title or not message:
            flash('Başlık ve mesaj boş olamaz.', 'danger')
        else:
            db.session.add(AdminMessage(
                site_id   = site.id if site else None,
                sender_id = current_user.id,
                title     = title,
                message   = message,
                is_read   = False
            ))
            db.session.commit()
            flash('Mesajınız sistem yöneticisine iletildi.', 'success')
            return redirect(url_for('site_admin.dashboard'))

    # Gönderilmiş mesajlar
    mesajlar = AdminMessage.query.filter_by(
        sender_id=current_user.id
    ).order_by(AdminMessage.created_at.desc()).all()

    return render_template('site_admin/superadmine_mesaj.html',
                           site=site, mesajlar=mesajlar)


# ── Yönetici Evrakları (site admin görüntüle) ─────────────────────────────
@site_admin_bp.route('/yonetici-evraklar')
@login_required
@site_admin_required
def yonetici_evraklar():
    from app.models.models import AdminDocument
    docs = AdminDocument.query.filter_by(target_user_id=current_user.id)\
               .order_by(AdminDocument.created_at.desc()).all()
    return render_template('site_admin/yonetici_evraklar.html', docs=docs)


@site_admin_bp.route('/yonetici-evraklar/<int:doc_id>/indir')
@login_required
@site_admin_required
def yonetici_evrak_indir(doc_id):
    from app.models.models import AdminDocument
    from flask import send_from_directory
    import os
    doc = AdminDocument.query.get_or_404(doc_id)
    if doc.target_user_id != current_user.id:
        flash('Bu evraka erişim yetkiniz yok.', 'danger')
        return redirect(url_for('site_admin.yonetici_evraklar'))
    upload_dir = os.path.join('/home/probissi/site_takip/uploads/admin', str(doc.target_user_id))
    return send_from_directory(upload_dir, doc.filename,
                               as_attachment=True, download_name=doc.original_name)


# ── Context Processor ─────────────────────────────────────────────────────
@site_admin_bp.context_processor
def inject_unread_admin_reply():
    from flask_login import current_user
    from app.models.models import AdminMessage
    count = 0
    try:
        if current_user.is_authenticated and current_user.role == 'site_admin':
            count = AdminMessage.query.filter_by(
                sender_id=current_user.id,
                reply_read=False
            ).filter(AdminMessage.reply != None).count()
    except Exception:
        pass
    return dict(site_admin_unread_reply=count)


# ── Sakin Mesajları Toplu Sil ─────────────────────────────────────────────
@site_admin_bp.route('/sakin-mesajlari/toplu-sil', methods=['POST'])
@login_required
@site_admin_required
def sakin_mesaj_toplu_sil():
    from app.models.models import ResidentMessage
    site = get_active_site()
    if site:
        ResidentMessage.query.filter_by(
            site_id=site.id, is_closed=True
        ).delete()
        db.session.commit()
        flash('Kapatılmış mesajlar silindi.', 'success')
    return redirect(url_for('site_admin.sakin_mesajlari', durum='kapali'))


# ── Tekrar Eden Giderleri Bu Aya Ekle ────────────────────────────────────
@site_admin_bp.route('/expenses/tekrar-eden-ekle', methods=['POST'])
@login_required
@site_admin_required
def tekrar_eden_ekle():
    site  = get_active_site()
    year  = int(request.form.get('year'))
    month = int(request.form.get('month'))

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    gecen_ay_tekrar = Expense.query.filter_by(
        site_id=site.id, period_year=prev_year,
        period_month=prev_month, is_recurring=True
    ).all()

    bu_ay_type_ids = {e.type_id for e in Expense.query.filter_by(
        site_id=site.id, period_year=year, period_month=month
    ).all()}

    count = 0
    for exp in gecen_ay_tekrar:
        if exp.type_id not in bu_ay_type_ids:
            db.session.add(Expense(
                site_id      = exp.site_id,
                block_id     = exp.block_id,
                category_id  = exp.category_id,
                type_id      = exp.type_id,
                amount       = exp.amount,
                description  = exp.description,
                expense_date = date.today(),
                period_year  = year,
                period_month = month,
                receipt_no   = exp.receipt_no,
                is_recurring = True,
                created_by   = current_user.id
            ))
            count += 1

    db.session.commit()
    flash(f'{count} tekrar eden gider bu aya eklendi.', 'success')
    return redirect(url_for('site_admin.expenses', year=year, month=month))





# ── Yardım Dosyaları ──────────────────────────────────────────────────────
@site_admin_bp.route('/yardim')
@login_required
@site_admin_required
def yardim():
    return render_template('site_admin/yardim.html')


# ── Duyuru Yönetimi ───────────────────────────────────────────────────────
@site_admin_bp.route('/duyurular')
@login_required
@site_admin_required
def duyurular():
    from app.models.models import Announcement
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))
    duyuru_list = Announcement.query.filter_by(site_id=site.id)\
        .order_by(Announcement.publish_at.desc()).all()
    return render_template('site_admin/duyurular.html',
                           site=site, duyurular=duyuru_list, now=datetime.now())


@site_admin_bp.route('/duyurular/yeni', methods=['GET', 'POST'])
@login_required
@site_admin_required
def yeni_duyuru():
    from app.models.models import Announcement
    site = get_active_site()
    if not site:
        return redirect(url_for('site_admin.dashboard'))

    if request.method == 'POST':
        publish_at = datetime.strptime(
            request.form.get('publish_at'), '%Y-%m-%dT%H:%M'
        )
        db.session.add(Announcement(
            site_id      = site.id,
            title        = request.form.get('title'),
            content      = request.form.get('content'),
            publish_at   = publish_at,
            send_sms     = bool(request.form.get('send_sms')),
            send_mail    = bool(request.form.get('send_mail')),
            is_published = False,
            created_by   = current_user.id
        ))
        db.session.commit()
        flash('Duyuru oluşturuldu. Belirlenen tarih ve saatte yayınlanacak.', 'success')
        return redirect(url_for('site_admin.duyurular'))

    return render_template('site_admin/duyuru_form.html', site=site, duyuru=None)


@site_admin_bp.route('/duyurular/<int:did>/sil', methods=['POST'])
@login_required
@site_admin_required
def duyuru_sil(did):
    from app.models.models import Announcement
    d = Announcement.query.get_or_404(did)
    db.session.delete(d)
    db.session.commit()
    flash('Duyuru silindi.', 'success')
    return redirect(url_for('site_admin.duyurular'))


@site_admin_bp.route('/duyurular/<int:did>/hemen-yayinla', methods=['POST'])
@login_required
@site_admin_required
def duyuru_hemen_yayinla(did):
    from app.models.models import Announcement
    from app.utils import send_mail, send_sms
    from app.models.models import Resident, Apartment, Block

    d = Announcement.query.get_or_404(did)
    site = get_active_site()

    d.is_published = True
    d.publish_at   = datetime.now()

    # SMS ve mail gönder
    if d.send_sms or d.send_mail:
        sakinler = Resident.query.join(Apartment).join(Block).filter(
            Block.site_id == site.id,
            Resident.is_active == True
        ).all()

        for res in sakinler:
            if d.send_mail and res.email:
                html = f'<h3>{d.title}</h3><p>{d.content}</p>'
                send_mail(res.email, d.title, html, site.id)
            if d.send_sms and res.phone:
                send_sms(res.phone, f'{d.title}: {d.content[:100]}', site.id)

        d.sms_sent  = d.send_sms
        d.mail_sent = d.send_mail

    db.session.commit()
    flash('Duyuru hemen yayınlandı ve bildirimler gönderildi.', 'success')
    return redirect(url_for('site_admin.duyurular'))
