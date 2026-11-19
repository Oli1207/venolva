"""Réglages gunicorn (production, derrière nginx)."""
import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() * 2 + 1)))
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
# nginx transmet le schéma d'origine ; Django s'en sert pour savoir que la requête est en HTTPS
forwarded_allow_ips = "127.0.0.1"
