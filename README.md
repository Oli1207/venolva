# Venolva

Réseau social du sport pour la Côte d'Ivoire. L'idée de départ : ne plus aller seul à la salle, en trouvant un binôme qui a le même objectif, dans la même salle, aux mêmes heures.

## Structure

- `backend/` : Django 5 + Django REST Framework, authentification par numéro (+225) et code à usage unique, JWT.
- `frontend/` : React 18 + Vite + React Router, d'après les maquettes (22 écrans). La v1 couvre la connexion, l'inscription en 3 étapes, le fil, la publication, les binômes, le profil d'un binôme, les séances, les messages et le profil.

## Lancer le backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_gyms      # salles d'exemple
.venv/Scripts/python.exe manage.py seed_pros      # coach et nutritionniste de démonstration
.venv/Scripts/python.exe manage.py createsuperuser # numéro au format 0700000000
.venv/Scripts/python.exe manage.py runserver
.venv/Scripts/python.exe manage.py test
```

En développement, le code de connexion est renvoyé dans la réponse (`dev_code`) et envoyé par e-mail dans la console du serveur. En production, renseigner `EMAIL_BACKEND` (SMTP) et les variables `EMAIL_*` du fichier `.env.example`.

Base de données : SQLite en développement (sans variables `POSTGRES_*`), **PostgreSQL en production** (renseigner `POSTGRES_DB` et les variables associées dans `.env`, puis `manage.py migrate` sur une base vide).

Les identifiants sont des UUID et les migrations ont été réinitialisées : une ancienne base SQLite de développement doit être supprimée (`db.sqlite3`) avant de relancer `migrate`.

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173, /api est relayé vers le backend sur le port 8000
npm run build
```

Lancer le backend d'abord. Les deux serveurs tournent en parallèle. En mode test, l'écran de code affiche le code de connexion.

## API (v1, cœur binôme)

| Route | Rôle |
| --- | --- |
| `POST /api/auth/otp/request/` | Envoie un code (limité à 5 par numéro et par heure) |
| `POST /api/auth/otp/verify/` | Vérifie le code, crée le compte si besoin, renvoie les jetons |
| `GET/PATCH /api/auth/me/` | Mon compte et mon profil (objectifs, salle, créneaux) |
| `GET /api/gyms/`, `GET /api/gyms/<id>/` | Salles (note, membres) et profil complet : horaires, ouvert maintenant, formules, cours, mon avis |
| `GET/POST /api/gyms/<id>/reviews/` | Avis (un par membre, modifiable, pas sur sa propre salle) |
| `POST /api/gym-plans/<id>/request/` | Demander une formule : la salle est prévenue par message |
| `POST /api/gym-classes/<id>/book\|cancel/` | Réserver ou libérer une place à un cours |
| `GET/POST/PATCH /api/my/gym/`, `PUT .../hours/` | Espace gérant : ma salle, mes horaires |
| `/api/my/gym/plans/`, `/classes/`, `/requests/` | Formules, cours (avec participants) et demandes à accepter ou refuser |
| `GET /api/matches/` | Binômes compatibles, du plus au moins compatible |
| `GET /api/members/<id>/` | Profil d'un binôme avec la compatibilité |
| `GET/POST /api/meetups/` | Mes séances, proposer une séance |
| `POST /api/meetups/<id>/respond\|cancel\|arrive/` | Répondre, annuler, signaler son arrivée |
| `GET/POST /api/posts/` | Fil : un seul format pour tous les auteurs |
| `POST /api/posts/<id>/join/` | « Je viens » sur une demande de binôme |
| `GET /api/conversations/`, `POST .../start/` | Discussions et non lus |
| `GET/POST /api/conversations/<id>/messages/` | Messages (sondage avec `?after=<id>`) |
| `GET /api/pro/me/`, `POST /api/pro/apply/` | État de mon dossier pro, envoyer le dossier |
| `GET /api/pros/`, `GET /api/pros/<id>/` | Annuaire des pros validés, profil public avec services |
| `GET /api/pros/<id>/slots/?service=&date=` | Heures de début libres |
| `GET/POST /api/my/services/`, `PATCH/DELETE .../<id>/` | Mes services (pros validés) |
| `GET/PUT /api/my/availability/` | Mes plages horaires de la semaine |
| `GET /api/payments/methods/`, `POST /api/payments/` | Moyens de paiement disponibles, démarrer un paiement (renvoie l'adresse de la page sécurisée) |
| `POST /api/payments/<ref>/verify/`, `GET .../<ref>/` | Vérification au retour du client, état d'un paiement |
| `POST /api/payments/webhooks/paystack/`, `.../jeko/` | Confirmations signées des prestataires (sans JWT) |
| `GET/POST /api/bookings/` | Mes réservations (`?role=pro` pour celles reçues), réserver |
| `POST /api/bookings/<id>/confirm\|decline\|cancel\|complete\|mark_paid/` | Cycle de vie d'une réservation |
| `GET/POST /api/listings/`, `GET/PATCH/DELETE .../<id>/` | Marché : annonces (filtres `category`, `q`, `commune`, `mine=1`) |
| `POST /api/listings/<id>/photos/` | Ajoute une photo (4 au maximum) |
| `POST /api/listings/<id>/contact/`, `.../report/` | Écrire au vendeur, signaler l'annonce |

## Compatibilité

Score sur 100 : salle 35 (ou 10 pour la même commune), objectif 25, jours 15, créneaux 15, niveau 10. Les profils masqués ou incomplets ne sont jamais proposés.

## Ponctualité

Note sur 5 : part des séances terminées où la personne est arrivée à moins de 10 minutes de l'heure. Elle n'apparaît qu'après 3 séances terminées, et chacun peut la masquer.

## Comptes pro et réservations

Un seul compte pour tous. Le professionnel envoie un dossier (métier, justificatif) depuis son profil. L'équipe le valide dans le back-office Django (Dossiers pro, action « Valider »), ce qui donne la coche verte et ouvre les services. Un dossier non validé ne donne accès à rien de public.

Une réservation demande un créneau dans les horaires du pro, libre et à plus d'une heure. Le pro la confirme ou la refuse. Une séance à deux se partage à parts égales (l'arrondi va au client).

**Paiement** : en ligne (voir plus bas) ou sur place, le pro marquant alors la réservation comme payée.

## Marché entre membres

Tout membre peut vendre avec un compte normal : 10 annonces en vente au maximum, de 500 à 5 000 000 FCFA, 4 photos. Les catégories sont limitées (poids, machines, tenues, accessoires), sans compléments ni produits de santé. L'acheteur écrit au vendeur depuis l'annonce, ils se retrouvent de préférence à la salle, et le vendeur marque l'article vendu. Aucun paiement ne passe par l'app pour l'instant.

Les photos sont vérifiées avec Pillow, redressées, réduites à 1600 px et ré-encodées en JPEG, ce qui retire leurs métadonnées (dont la position GPS). Elles sont stockées dans `backend/media/` en développement. En production, il faudra un stockage objet (Cloudinary ou S3). Les signalements se traitent dans le back-office.

## Salles

La page d'une salle montre ses horaires (avec « ouvert maintenant »), ses formules, ses cours collectifs avec le nombre de places restantes, et les avis des membres. Une salle appartient à un gérant : soit un compte « Salle de sport » validé qui crée sa fiche depuis l'app, soit un membre rattaché à une salle existante par l'équipe (champ « Gérant » dans le back-office). Le gérant gère ses horaires, ses formules, ses cours et les demandes d'abonnement. Une demande de formule envoie un message au gérant et se règle sur place : aucun paiement ne passe par l'app.

Données de démonstration : `manage.py seed_gyms` crée un gérant (+225 07 00 00 02 03) avec horaires, formules et un cours pour Salle Riviera 3.

## Paiement en ligne

Deux prestataires, comme dans le projet mon_ticket :
- **Jeko** : Wave, Orange Money, MTN MoMo, Moov. Actif seulement si `JEKO_API_KEY`, `JEKO_API_KEY_ID` et `JEKO_STORE_ID` sont renseignés.
- **Paystack** : carte bancaire, et mobile money en repli quand Jeko n'est pas disponible ou tombe en panne.

Le client est redirigé vers la page sécurisée du prestataire, jamais de saisie de carte ou de code chez nous. Le paiement n'est considéré reçu qu'après une **confirmation signée** (webhook) dont la signature et le montant exact sont vérifiés. Si le webhook tarde, la page de retour interroge le prestataire. Un webhook rejoué ne change rien, un montant inattendu passe en « à vérifier » et un double paiement est marqué « à rembourser » (back-office, Paiements).

Ce qu'on peut payer : une réservation de pro (après sa confirmation, chacun sa part pour une séance à deux) et un cours collectif payant.

**À configurer côté prestataires** (adresse publique obligatoire, pas `localhost`) :
- Paystack, Settings > API Keys & Webhooks : `https://<ton-domaine>/api/payments/webhooks/paystack/`
- Jeko, Paramètres > API & Webhooks : `https://<ton-domaine>/api/payments/webhooks/jeko/`

Les clés de `mon_ticket` copiées dans `backend/.env` sont des clés Paystack de test. La commission, le mode de paiement et le reversement se règlent dans l'administration (voir plus bas).

## Administration

L'administration est dans l'app, sur `/admin` (pas le Django admin). Elle est réservée aux comptes « équipe » (`is_staff`) et s'ouvre depuis le profil. Pour créer le premier administrateur : `manage.py createsuperuser` (numéro au format 0700000000), puis connexion par code comme tout le monde. Ensuite, un superutilisateur peut donner l'accès équipe à d'autres comptes depuis la page Utilisateurs.

Pages : tableau de bord, **réglages**, paiements, **reversements**, dossiers pro, salles, modération, utilisateurs, journal.

**Réglages** (page Réglages, modifiables sans toucher au code, avec confirmation avant enregistrement) : commission sur les réservations et sur les cours, mode de paiement (Jeko puis Paystack, ou un seul), délai avant reversement, reversement minimum, annulation gratuite, prix minimum et maximum, délai minimum de réservation, annonces et photos par membre, règles du code de connexion. Un taux de commission particulier peut être fixé par vendeur.

**Argent** :
- À chaque paiement, la commission (taux du vendeur, sinon taux par défaut) est calculée et figée : `fee` pour Venolva, `net` pour le pro ou la salle. Le client paie le même prix.
- Après la séance et le délai d'attente, le `net` devient disponible. L'administrateur crée un **reversement** (il regroupe tout le disponible d'un bénéficiaire), fait le virement hors de l'app (Wave, Orange, MTN…) ou via l'export CSV, puis note la référence. Les virements ne sont pas automatiques : aucun argent ne sort sans une action humaine.
- Les pros et les salles voient leur solde et leur compte de réception dans **Mes revenus**.
- **Annulations** : si le pro annule, le client est remboursé. Si le client annule au moins « annulation gratuite » heures avant, il est remboursé ; sinon le pro garde la somme. Un cours annulé par la salle rembourse tous les inscrits. Le paiement passe « à rembourser » : l'administrateur rembourse chez Jeko ou Paystack, puis le note dans la page Paiements.
- Un montant inattendu passe « à vérifier », un double paiement « à rembourser ».

Chaque action d'administration est inscrite au **journal** (auteur, date, valeur avant et après pour les réglages).

## Ambassadeurs

Un ambassadeur représente Venolva et touche un pourcentage de **ce que la plateforme gagne** (sa commission), jamais de l'argent des pros et des salles. Page Ambassadeurs de l'administration, espace « Ambassadrice » dans le profil de la personne.

- **Contrat** : durée fixe (6 mois par défaut), brouillon tant qu'il n'est pas signé, renouvelable en créant le contrat suivant (même taux et durée, modifiables), résiliable avant le terme. Deux contrats d'une même personne ne peuvent pas se chevaucher. Un brouillon ne rapporte rien.
- **Gains** : la commission d'un paiement compte quand la séance a eu lieu et que le délai d'attente avant reversement est écoulé, donc quand plus aucun remboursement n'est possible. Seuls les paiements encaissés comptent, pas les remboursés, doublons ou paiements à vérifier.
- **Relevés** : l'administrateur clôture un mois terminé. Le relevé fige les commissions, le taux et le montant, puis il se règle à la main (référence du virement). Un paiement n'est jamais compté deux fois (contrainte en base) ; annuler un relevé non versé libère ses paiements. Le montant se calcule au FCFA le plus proche.
- **Réglages** : taux et durée par défaut dans Réglages > Ambassadeurs. Chaque contrat garde son propre taux.
- **Contrat à signer** : `docs/contrat-ambassadrice.docx`, un modèle à faire relire par un juriste avant signature. Les passages entre crochets sont à remplir.
- Les codes promo et l'attribution par ambassadeur viendront plus tard : pour l'instant, la part porte sur toutes les commissions de la plateforme.
