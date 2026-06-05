import os
import sys
import site
sys.dont_write_bytecode = True

site.addsitedir('/var/www/probissi/data/www/probissite.com.tr/.venv/lib/python3.10/site-packages')

PROJECT_DIR = '/var/www/probissi/data/www/probissite.com.tr/site_takip'
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

os.environ["DATABASE_URL"] = "postgresql://probissi_aidat:V~&d=5+HpW2?!+2@127.0.0.1:5432/probissi_aidat_db"
os.environ["SECRET_KEY"]   = "probissi-aidat-2026-xK9mP3qL7nR2vT8w"
os.environ["FLASK_ENV"]    = "development"
os.environ["FLASK_DEBUG"]  = "1"

from app import create_app
application = create_app('production')

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('127.0.0.1', 20001, application)
    httpd.serve_forever()
