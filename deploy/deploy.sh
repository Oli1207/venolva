#!/usr/bin/env bash
# Mise à jour du serveur : à lancer sur le serveur, dans /var/www/venolva, après un `git pull`.
# Première installation : voir docs/deploiement.md.
set -euo pipefail

cd /var/www/venolva
git pull --ff-only

# Backend
cd backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py createcachetable   # sans effet si la table existe ou si REDIS_URL est défini
.venv/bin/python manage.py check --deploy || true
cd ..

# Frontend
cd frontend
npm ci
npm run build
cd ..

sudo systemctl restart venolva
sleep 2
curl -fsS http://127.0.0.1:8000/api/health/ && echo " : l'API répond"
