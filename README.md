# Sports Management System

A Django web application that replaces manual sports record-keeping with one central platform for players, teams, tournaments, venues, performance and reports.

## Features
- **Accounts and roles:** registration and login for Administrator, Organizer, Coach and Player, with role-based permissions
- **Players:** profiles, achievements, medical records (visible only to admins, coaches and the player), search and filter
- **Teams:** create teams, assign coaches and players
- **Tournaments and matches:** automatic fixtures (round robin or knockout), result entry, live standings, next-round generation for knockouts
- **Venues:** grounds, facilities and bookings, with double-booking prevented at the database level
- **Performance:** record player points per match, automatic rankings and averages
- **Notifications:** in-app announcements plus email; results and new tournaments are announced automatically
- **Reports:** charts (Chart.js) and CSV export of player stats and standings

## Roles
| Role | Can do |
|---|---|
| Administrator | Everything |
| Organizer | Tournaments, venues and bookings, announcements, record stats, reports |
| Coach | Players, teams, record stats, reports, see medical records |
| Player | View everything except medical records of others; edit own profile |

## Tech stack
Python, Django, SQLite (local) / PostgreSQL (production), HTML/CSS, Chart.js, WhiteNoise, Gunicorn

## Run locally
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo     # optional demo data
python manage.py runserver
```
Open http://127.0.0.1:8000. Demo logins: `admin / admin12345`, and `organizer`, `coach`, `player` with password `demo12345`.
Django's built-in admin panel is at `/admin/` (superuser only). To create your own admin: `python manage.py createsuperuser`.

## Database schema
Profile, Team, Player, Venue, Booking, Tournament, Match, PlayerStat, Notification (see `core/models.py`).

## Deploy (Render)
1. Push to GitHub, then create a **PostgreSQL** database and a **Web Service** on render.com from the repo.
2. Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
3. Start command: `gunicorn config.wsgi`
4. Environment variables: `DATABASE_URL` (from Render's database), `SECRET_KEY` (any long random string), `DEBUG=0`, `ALLOWED_HOSTS=your-app.onrender.com`, `CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com`
5. Run `python manage.py createsuperuser` (and optionally `seed_demo`) in the Render shell.
