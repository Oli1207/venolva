# Déployer Venolva sur un serveur DigitalOcean

Un seul serveur (droplet Ubuntu) suffit au départ : nginx, l'API (gunicorn), PostgreSQL. Les fichiers prêts à l'emploi sont dans `deploy/` et `backend/gunicorn.conf.py`.

## Ce qu'il faut avoir
- Un nom de domaine qui pointe vers l'adresse du serveur (enregistrement A).
- Un service d'envoi d'e-mails (le code de connexion part par e-mail) avec un domaine d'envoi vérifié.
- Les clés Paystack et Jeko de production.
- Facultatif : un « Space » DigitalOcean pour les photos (sinon elles restent sur le disque du serveur).

## Installation (une fois)
```bash
sudo apt update && sudo apt install -y nginx postgresql python3-venv python3-pip git certbot python3-certbot-nginx nodejs npm
sudo adduser --system --group venolva
sudo mkdir -p /var/www/venolva && sudo chown $USER /var/www/venolva
git clone https://github.com/Oli1207/venolva.git /var/www/venolva

# Base de données
sudo -u postgres createuser venolva --pwprompt
sudo -u postgres createdb venolva -O venolva

# Backend
cd /var/www/venolva/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env     # puis le remplir (voir plus bas)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py createsuperuser   # e-mail du premier compte équipe

# Frontend
cd ../frontend && npm ci && npm run build

# Services
sudo cp /var/www/venolva/deploy/venolva.service /etc/systemd/system/
sudo cp /var/www/venolva/deploy/nginx.conf /etc/nginx/sites-available/venolva
sudo ln -s /etc/nginx/sites-available/venolva /etc/nginx/sites-enabled/
sudo chown -R venolva:venolva /var/www/venolva/backend/media
sudo certbot --nginx -d venolva.app
sudo systemctl enable --now venolva && sudo systemctl reload nginx
```

## Variables du fichier `backend/.env` en production
| Variable | Valeur |
|---|---|
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | valeur aléatoire de 40 caractères ou plus (`python -c "import secrets;print(secrets.token_urlsafe(60))"`). L'application refuse de démarrer sans elle. |
| `DJANGO_ALLOWED_HOSTS` | `venolva.app` |
| `CORS_ORIGINS` | `https://venolva.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://venolva.app` |
| `FRONTEND_URL` | `https://venolva.app` (retour après paiement) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | la base PostgreSQL |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | le service d'envoi |
| `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` | clés de production |
| `JEKO_API_KEY`, `JEKO_API_KEY_ID`, `JEKO_STORE_ID`, `JEKO_WEBHOOK_SECRET` | clés de production |
| `REDIS_URL` | facultatif ; sinon le cache des limites de requêtes utilise la base |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN` | facultatif ; photos dans un Space |

## Adresses à déclarer chez les prestataires de paiement
- Paystack : `https://venolva.app/api/payments/webhooks/paystack/`
- Jeko : `https://venolva.app/api/payments/webhooks/jeko/`

## Mises à jour
Après un `git pull` sur le serveur : `bash deploy/deploy.sh` (installe, migre, reconstruit le frontend, redémarre, vérifie `/api/health/`).

## À vérifier après la mise en ligne
- `https://venolva.app/api/health/` répond `{"ok": true}`.
- Se connecter avec le premier compte équipe, puis dans `/admin` > Réglages : fixer les commissions et la part de l'ambassadrice (elles valent 0 au départ).
- Faire un petit paiement de test avec chaque prestataire.
- Sauvegardes : activer les sauvegardes automatiques du droplet et faire un `pg_dump` régulier.
