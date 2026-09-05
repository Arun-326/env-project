# Environmental Science Project Manager

Production-ready Flask app with Render Postgres support.

## Local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

If `DATABASE_URL` is not set, the app uses the local `class_project.db`.

## Render

Set these Environment Variables on the Render web service:

- `DATABASE_URL` = the Render Postgres **Internal Database URL**
- `SECRET_KEY` = a long random secret
- `ADMIN_PASSWORD` = your chosen admin password

Start Command:

```bash
gunicorn app:app
```

## Migrate existing SQLite data

Use the separate `migrate_db.py` script once, with the Render Postgres **External Database URL** in your local shell:

```bash
export DATABASE_URL='YOUR_EXTERNAL_POSTGRES_URL'
python migrate_db.py
```

Never commit `DATABASE_URL`, `.env`, passwords, or secret keys.
