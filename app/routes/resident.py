from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from datetime import date
from app.models.models import Resident, Due, Expense, Block

resident_bp = Blueprint('resident', __name__)


def resident_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'resident':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@resident_bp.route('/dashboard')
@login_required
@resident_required
def dashboard():
    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    normal_dues = []
    yakit_dues  = []
    expenses    = []
    if res:
        # Sadece bu sakine ait aidatlar
        normal_dues = Due.query.filter_by(resident_id=res.id, due_type='normal')\
                      .order_by(Due.period_year.desc(), Due.period_month.desc()).limit(24).all()
        yakit_dues  = Due.query.filter_by(resident_id=res.id, due_type='yakit')\
                      .order_by(Due.period_year.desc(), Due.period_month.desc()).limit(24).all()
        site_id = res.apartment.block.site_id
        expenses = Expense.query.filter_by(site_id=site_id)\
                    .order_by(Expense.expense_date.desc()).limit(20).all()
    # Ödeme ayarları
    odeme_cfg = None
    if res:
        from app.models.models import SystemSettings
        site_id = res.apartment.block.site_id
        odeme_cfg = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
        if not odeme_cfg or not odeme_cfg.odeme_active:
            odeme_cfg = SystemSettings.query.filter_by(scope='global').first()
        if odeme_cfg and not odeme_cfg.odeme_active:
            odeme_cfg = None

    # Aktif duyurular
    duyurular = []
    if res:
        from app.models.models import Announcement
        from datetime import datetime
        duyurular = Announcement.query.filter_by(
            site_id=site_id, is_published=True
        ).order_by(Announcement.publish_at.desc()).limit(5).all()

    return render_template('resident/dashboard.html',
                           resident=res, normal_dues=normal_dues,
                           yakit_dues=yakit_dues, expenses=expenses,
                           today=date.today(), odeme_cfg=odeme_cfg,
                           duyurular=duyurular)


from flask import request
from app import db
from app.models.models import ResidentMessage


@resident_bp.route('/mesaj-gonder', methods=['GET', 'POST'])
@login_required
@resident_required
def mesaj_gonder():
    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not res:
        flash('Aktif sakin kaydınız bulunamadı.', 'danger')
        return redirect(url_for('resident.dashboard'))

    if request.method == 'POST':
        title   = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        if not title or not message:
            flash('Başlık ve mesaj boş olamaz.', 'danger')
        else:
            db.session.add(ResidentMessage(
                site_id     = res.apartment.block.site_id,
                resident_id = res.id,
                sender_id   = current_user.id,
                title       = title,
                message     = message,
                is_read     = False
            ))
            db.session.commit()
            flash('Mesajınız yöneticiye iletildi.', 'success')
            return redirect(url_for('resident.dashboard'))

    return render_template('resident/mesaj_gonder.html', resident=res)


@resident_bp.route('/mesajlarim')
@login_required
@resident_required
def mesajlarim():
    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not res:
        return redirect(url_for('resident.dashboard'))
    mesajlar = ResidentMessage.query.filter_by(
        resident_id=res.id
    ).order_by(ResidentMessage.created_at.desc()).all()

    # Cevapları okundu yap
    for m in mesajlar:
        if m.reply and not m.reply_read:
            m.reply_read = True
    db.session.commit()

    return render_template('resident/mesajlarim.html', resident=res, mesajlar=mesajlar)


@resident_bp.route('/odeme-baslat', methods=['GET', 'POST'])
@login_required
@resident_required
def odeme_baslat():
    from app.models.models import SystemSettings
    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not res:
        flash('Aktif sakin kaydınız bulunamadı.', 'danger')
        return redirect(url_for('resident.dashboard'))

    site_id = res.apartment.block.site_id
    odeme_cfg = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
    if not odeme_cfg or not odeme_cfg.odeme_active:
        odeme_cfg = SystemSettings.query.filter_by(scope='global').first()
    if not odeme_cfg or not odeme_cfg.odeme_active:
        flash('Online ödeme aktif değil.', 'danger')
        return redirect(url_for('resident.dashboard'))

    # Ödenmemiş aidatlar
    unpaid_dues = Due.query.filter_by(
        resident_id=res.id, is_paid=False
    ).order_by(Due.period_year.desc(), Due.period_month.desc()).all()

    if request.method == 'POST':
        due_ids = request.form.getlist('due_ids')
        if not due_ids:
            flash('Lütfen en az bir aidat seçin.', 'danger')
            return redirect(url_for('resident.odeme_baslat'))

        # Seçilen aidatların toplamı
        secilen_dues = Due.query.filter(Due.id.in_(due_ids)).all()
        toplam = sum(float(d.amount) for d in secilen_dues)

        # Sağlayıcıya yönlendir
        if odeme_cfg.odeme_saglayici == 'iyzico':
            return redirect(url_for('resident.iyzico_odeme',
                due_ids=','.join(due_ids), toplam=toplam))
        elif odeme_cfg.odeme_saglayici == 'paytr':
            return redirect(url_for('resident.paytr_odeme',
                due_ids=','.join(due_ids), toplam=toplam))
        elif odeme_cfg.odeme_saglayici == 'stripe':
            return redirect(url_for('resident.stripe_odeme',
                due_ids=','.join(due_ids), toplam=toplam))

    return render_template('resident/odeme_baslat.html',
                           resident=res, unpaid_dues=unpaid_dues,
                           odeme_cfg=odeme_cfg)


@resident_bp.route('/iyzico-odeme')
@login_required
@resident_required
def iyzico_odeme():
    from app.models.models import SystemSettings
    import iyzipay, json

    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    due_ids = request.args.get('due_ids', '').split(',')
    toplam  = float(request.args.get('toplam', 0))

    site_id = res.apartment.block.site_id
    odeme_cfg = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
    if not odeme_cfg or not odeme_cfg.odeme_active:
        odeme_cfg = SystemSettings.query.filter_by(scope='global').first()

    options = {
        'api_key'    : odeme_cfg.iyzico_api_key,
        'secret_key' : odeme_cfg.iyzico_secret_key,
        'base_url'   : odeme_cfg.iyzico_base_url or 'https://sandbox-api.iyzipay.com'
    }

    basket_items = []
    dues = Due.query.filter(Due.id.in_(due_ids)).all()
    for due in dues:
        basket_items.append({
            'id'       : str(due.id),
            'name'     : f'Aidat {due.period_month}/{due.period_year}',
            'category1': 'Aidat',
            'itemType' : 'VIRTUAL',
            'price'    : str(round(float(due.amount), 2))
        })

    request_data = {
        'locale'              : 'tr',
        'conversationId'      : f'due-{"-".join(due_ids)}',
        'price'               : str(round(toplam, 2)),
        'paidPrice'           : str(round(toplam, 2)),
        'currency'            : 'TRY',
        'basketId'            : f'basket-{res.id}',
        'paymentGroup'        : 'PRODUCT',
        'callbackUrl'         : url_for('resident.iyzico_callback', _external=True),
        'enabledInstallments' : ['1', '2', '3', '6', '9', '12'],
        'buyer': {
            'id'                 : str(current_user.id),
            'name'               : res.first_name,
            'surname'            : res.last_name,
            'gsmNumber'          : res.phone or '+905000000000',
            'email'              : current_user.email,
            'identityNumber'     : res.tc_no or '11111111110',
            'registrationAddress': res.apartment.block.site.address or 'Turkiye',
            'ip'                 : request.remote_addr,
            'city'               : 'Istanbul',
            'country'            : 'Turkey',
        },
        'shippingAddress': {
            'contactName': res.first_name + ' ' + res.last_name,
            'city'       : 'Istanbul',
            'country'    : 'Turkey',
            'address'    : res.apartment.block.site.address or 'Turkiye',
        },
        'billingAddress': {
            'contactName': res.first_name + ' ' + res.last_name,
            'city'       : 'Istanbul',
            'country'    : 'Turkey',
            'address'    : res.apartment.block.site.address or 'Turkiye',
        },
        'basketItems': basket_items
    }

    checkout = iyzipay.CheckoutFormInitialize().create(request_data, options)
    result   = json.loads(checkout.read().decode('utf-8'))

    if result.get('status') == 'success':
        return render_template('resident/iyzico_odeme.html',
                               checkout_form_content=result.get('checkoutFormContent'),
                               due_ids=due_ids)
    else:
        flash(f'Odeme baslatılamadı: {result.get("errorMessage")}', 'danger')
        return redirect(url_for('resident.odeme_baslat'))


@resident_bp.route('/iyzico-callback', methods=['POST'])
def iyzico_callback():
    from app.models.models import SystemSettings
    import iyzipay, json
    from datetime import datetime as dt

    token = request.form.get('token')
    odeme_cfg = SystemSettings.query.filter_by(scope='global').first()
    options = {
        'api_key'    : odeme_cfg.iyzico_api_key,
        'secret_key' : odeme_cfg.iyzico_secret_key,
        'base_url'   : odeme_cfg.iyzico_base_url or 'https://sandbox-api.iyzipay.com'
    }

    checkout = iyzipay.CheckoutForm().retrieve({'locale': 'tr', 'token': token}, options)
    result   = json.loads(checkout.read().decode('utf-8'))

    if result.get('paymentStatus') == 'SUCCESS':
        conversation_id = result.get('conversationId', '')
        due_ids = conversation_id.replace('due-', '').split('-')
        dues = Due.query.filter(Due.id.in_(due_ids)).all()
        for due in dues:
            due.is_paid     = True
            due.paid_date   = dt.today().date()
            due.payment_note = 'Iyzico online odeme'
        db.session.commit()
        flash('Odemeniz basariyla alindi!', 'success')
    else:
        flash('Odeme basarisiz veya iptal edildi.', 'danger')

    return redirect(url_for('resident.dashboard'))


@resident_bp.route('/paytr-odeme')
@login_required
@resident_required
def paytr_odeme():
    from app.models.models import SystemSettings
    import hashlib, base64, hmac, json, requests as req

    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    due_ids = request.args.get('due_ids', '').split(',')
    toplam  = float(request.args.get('toplam', 0))

    site_id = res.apartment.block.site_id
    odeme_cfg = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
    if not odeme_cfg or not odeme_cfg.odeme_active:
        odeme_cfg = SystemSettings.query.filter_by(scope='global').first()

    merchant_id   = odeme_cfg.paytr_merchant_id
    merchant_key  = odeme_cfg.paytr_merchant_key
    merchant_salt = odeme_cfg.paytr_merchant_salt

    user_basket = json.dumps([
        [f'Aidat {d.period_month}/{d.period_year}', str(round(float(d.amount), 2)), 1]
        for d in Due.query.filter(Due.id.in_(due_ids)).all()
    ])

    merchant_ok_url   = url_for('resident.paytr_callback_ok',  _external=True)
    merchant_fail_url = url_for('resident.paytr_callback_fail', _external=True)

    user_ip        = request.remote_addr
    merchant_oid   = f'due-{"-".join(due_ids)}'
    email          = current_user.email
    payment_amount = int(round(toplam * 100))
    user_name      = f'{res.first_name} {res.last_name}'
    user_address   = res.apartment.block.site.address or 'Türkiye'
    user_phone     = res.phone or '05000000000'

    hash_str = merchant_id + user_ip + merchant_oid + email + str(payment_amount) + user_basket + '0' + 'TL' + merchant_salt
    token    = base64.b64encode(hmac.new(merchant_key.encode(), hash_str.encode(), hashlib.sha256).digest()).decode()

    params = {
        'merchant_id'      : merchant_id,
        'user_ip'          : user_ip,
        'merchant_oid'     : merchant_oid,
        'email'            : email,
        'payment_amount'   : payment_amount,
        'paytr_token'      : token,
        'user_basket'      : base64.b64encode(user_basket.encode()).decode(),
        'debug_on'         : 1,
        'no_installment'   : 0,
        'max_installment'  : 0,
        'user_name'        : user_name,
        'user_address'     : user_address,
        'user_phone'       : user_phone,
        'merchant_ok_url'  : merchant_ok_url,
        'merchant_fail_url': merchant_fail_url,
        'timeout_limit'    : 30,
        'currency'         : 'TL',
        'test_mode'        : 1,
        'lang'             : 'tr',
    }

    r = req.post('https://www.paytr.com/odeme/api/get-token', data=params, timeout=10)
    result = r.json()

    if result.get('status') == 'success':
        iframe_token = result.get('token')
        return render_template('resident/paytr_odeme.html',
                               iframe_token=iframe_token, due_ids=due_ids)
    else:
        flash(f'Ödeme başlatılamadı: {result.get("reason")}', 'danger')
        return redirect(url_for('resident.odeme_baslat'))


@resident_bp.route('/paytr-callback-ok', methods=['POST'])
def paytr_callback_ok():
    from datetime import datetime
    merchant_oid = request.form.get('merchant_oid', '')
    due_ids = merchant_oid.replace('due-', '').split('-')
    dues = Due.query.filter(Due.id.in_(due_ids)).all()
    for due in dues:
        due.is_paid     = True
        due.paid_date   = datetime.today().date()
        due.payment_note = 'PayTR online ödeme'
    db.session.commit()
    flash('Ödemeniz başarıyla alındı!', 'success')
    return redirect(url_for('resident.dashboard'))


@resident_bp.route('/paytr-callback-fail', methods=['POST'])
def paytr_callback_fail():
    flash('Ödeme başarısız veya iptal edildi.', 'danger')
    return redirect(url_for('resident.dashboard'))


@resident_bp.route('/stripe-odeme')
@login_required
@resident_required
def stripe_odeme():
    from app.models.models import SystemSettings
    import stripe

    res = Resident.query.filter_by(user_id=current_user.id, is_active=True).first()
    due_ids = request.args.get('due_ids', '').split(',')
    toplam  = float(request.args.get('toplam', 0))

    site_id = res.apartment.block.site_id
    odeme_cfg = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
    if not odeme_cfg or not odeme_cfg.odeme_active:
        odeme_cfg = SystemSettings.query.filter_by(scope='global').first()

    stripe.api_key = odeme_cfg.stripe_secret_key

    line_items = []
    dues = Due.query.filter(Due.id.in_(due_ids)).all()
    for due in dues:
        line_items.append({
            'price_data': {
                'currency'    : 'try',
                'unit_amount' : int(round(float(due.amount) * 100)),
                'product_data': {
                    'name': f'Aidat {due.period_month}/{due.period_year}'
                },
            },
            'quantity': 1,
        })

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url=url_for('resident.stripe_callback_ok',
                            due_ids=','.join(due_ids), _external=True),
        cancel_url=url_for('resident.odeme_baslat', _external=True),
        customer_email=current_user.email,
    )

    return redirect(session.url, code=303)


@resident_bp.route('/stripe-callback-ok')
@login_required
@resident_required
def stripe_callback_ok():
    from datetime import datetime
    due_ids = request.args.get('due_ids', '').split(',')
    dues = Due.query.filter(Due.id.in_(due_ids)).all()
    for due in dues:
        due.is_paid     = True
        due.paid_date   = datetime.today().date()
        due.payment_note = 'Stripe online ödeme'
    db.session.commit()
    flash('Ödemeniz başarıyla alındı!', 'success')
    return redirect(url_for('resident.dashboard'))


@resident_bp.route('/yardim')
@login_required
@resident_required
def yardim():
    return render_template('resident/yardim.html')
