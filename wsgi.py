"""Production WSGI entry point.

Local (Windows):
    waitress-serve --port=8050 --threads=4 wsgi:server

EC2 / Linux (gunicorn):
    gunicorn -w 1 --threads 4 -b 0.0.0.0:8050 --timeout 120 wsgi:server
"""
import index          # registers all callbacks and sets app.layout
from app import app   # noqa: F401 — needed for the import side-effect check

server = app.server   # Flask WSGI object consumed by gunicorn / waitress
