import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

os.environ["DATABASE_URL"] = "postgresql://probissi_aidat:V~&d=5+HpW2?!+2@127.0.0.1:5432/probissi_aidat_db"
os.environ["SECRET_KEY"]   = "probissi-aidat-2026-xK9mP3qL7nR2vT8w"
os.environ["FLASK_ENV"]    = "production"

from app import create_app
application = create_app('production')