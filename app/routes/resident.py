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
    return render_template('resident/dashboard.html',
                           resident=res, normal_dues=normal_dues,
                           yakit_dues=yakit_dues, expenses=expenses,
                           today=date.today())


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
