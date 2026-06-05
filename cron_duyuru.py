import os
import sys
sys.path.insert(0, '/var/www/probissi/data/www/probissite.com.tr/site_takip')

from app import create_app, db
from app.models.models import Announcement, Resident, Apartment, Block
from app.utils import send_mail, send_sms
from datetime import datetime

app = create_app('production')

with app.app_context():
    now = datetime.now()
    
    # Zamanı gelmiş ama yayınlanmamış duyurular
    bekleyen = Announcement.query.filter(
        Announcement.is_published == False,
        Announcement.publish_at <= now
    ).all()

    for d in bekleyen:
        d.is_published = True

        # SMS ve mail gönder
        if d.send_sms or d.send_mail:
            sakinler = Resident.query.join(Apartment).join(Block).filter(
                Block.site_id == d.site_id,
                Resident.is_active == True
            ).all()

            for res in sakinler:
                if d.send_mail and res.email and not d.mail_sent:
                    html = f'<h3>{d.title}</h3><p>{d.content}</p>'
                    send_mail(res.email, d.title, html, d.site_id)
                if d.send_sms and res.phone and not d.sms_sent:
                    send_sms(res.phone, f'{d.title}: {d.content[:100]}', d.site_id)

            d.sms_sent  = d.send_sms
            d.mail_sent = d.send_mail

        db.session.commit()
        print(f'Duyuru yayınlandı: {d.title}')

    if not bekleyen:
        print(f'{now} - Bekleyen duyuru yok.')
