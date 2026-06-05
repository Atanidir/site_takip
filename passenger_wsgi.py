import os
import sys
import site
sys.dont_write_bytecode = True

# Relative path kullanımı
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, 'site_takip')

# Virtualenv site-packages - relative path ile bul
VENV_DIR = os.path.join(BASE_DIR, '.venv')
if os.path.exists(VENV_DIR):
    # .venv klasörü varsa onu kullan
    import glob
    site_packages = glob.glob(os.path.join(VENV_DIR, 'lib', 'python*', 'site-packages'))
    if site_packages:
        site.addsitedir(site_packages[0])
else:
    # Kitsune virtualenv yolunu dene
    import glob
    venv_patterns = [
        os.path.join(BASE_DIR, '..', '..', '..', '..', 'data', 'virtualenv', 'site_takip', '*', 'lib', 'python*', 'site-packages'),
    ]
    for pattern in venv_patterns:
        matches = glob.glob(pattern)
        if matches:
            site.addsitedir(matches[0])
            break

sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

os.environ["DATABASE_URL"] = "postgresql://probissi_aidat:V~&d=5+HpW2?!+2@127.0.0.1:5432/probissi_aidat_db"
os.environ["SECRET_KEY"]   = "probissi-aidat-2026-xK9mP3qL7nR2vT8w"
os.environ["FLASK_ENV"]    = "production"

from app import create_app
application = create_app('production')

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('127.0.0.1', 20001, application)
    httpd.serve_forever()
