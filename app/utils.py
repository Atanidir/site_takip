import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models.models import SystemSettings


def get_settings(site_id=None):
    if site_id:
        s = SystemSettings.query.filter_by(scope='site', site_id=site_id).first()
        if s:
            return s
    g = SystemSettings.query.filter_by(scope='global').first()
    if g:
        return g
    return SystemSettings.query.filter_by(scope='site').first()


def send_mail(to_email, subject, body_html, site_id=None):
    cfg = get_settings(site_id)
    if not cfg or not cfg.mail_active or not cfg.smtp_host:
        return False, 'Mail ayarları yapılmamış.'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"{cfg.smtp_from_name} <{cfg.smtp_from_email}>"
        msg['To']      = to_email
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        if cfg.smtp_use_tls:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port)
        server.login(cfg.smtp_user, cfg.smtp_pass)
        server.sendmail(cfg.smtp_from_email, to_email, msg.as_string())
        server.quit()
        return True, 'Mail gönderildi.'
    except Exception as e:
        return False, str(e)


def send_sms(to_phone, message, site_id=None):
    cfg = get_settings(site_id)
    if not cfg or not cfg.sms_active:
        return False, 'SMS ayarları yapılmamış veya aktif değil.'

    phone = to_phone.replace(' ', '').replace('-', '').replace('+', '')
    if phone.startswith('0'):
        phone = phone[1:]
    elif phone.startswith('90'):
        phone = phone[2:]

    if cfg.sms_provider == 'vatansms' and cfg.vatansms_api_id:
        try:
            import requests as req
            payload = {
                "api_id"              : cfg.vatansms_api_id,
                "api_key"             : cfg.vatansms_api_key,
                "sender"              : cfg.netgsm_header or '8506939680',
                "message_type"        : "turkce",
                "message"             : message,
                "message_content_type": "bilgi",
                "phones"              : [phone]
            }
            r = req.post('https://api.vatansms.net/api/v1/1toN',
                         json=payload, timeout=10)
            data = r.json()
            if data.get('status') == 'success':
                return True, 'SMS gönderildi.'
            return False, f'VatanSMS hata: {data.get("description", data)}'
        except Exception as e:
            return False, str(e)

    elif cfg.netgsm_user:
        try:
            import requests as req
            params = {
                'usercode' : cfg.netgsm_user,
                'password' : cfg.netgsm_pass,
                'gsmno'    : '90' + phone,
                'message'  : message,
                'msgheader': cfg.netgsm_header,
            }
            r = req.get('https://api.netgsm.com.tr/sms/send/get/',
                        params=params, timeout=10)
            if r.text[:2] in ('00', '01', '02'):
                return True, 'SMS gönderildi.'
            return False, f'Netgsm hata: {r.text}'
        except Exception as e:
            return False, str(e)

    return False, 'SMS sağlayıcı ayarlanmamış.'
