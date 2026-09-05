# Environmental Science Project Topic Manager

Flask web app for creating project topics, joining teams, leader approvals, admin management, PostgreSQL persistence, CSV exports, and student request-status lookup.

## Render
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set `DATABASE_URL`, `SECRET_KEY`, and `ADMIN_PASSWORD` in Render Environment Variables.

## Admin features
- View topic/request/visit statistics
- Search topics and requests
- Filter requests by status
- Edit topics
- Open/close member enrollment
- Delete topics or requests
- Accept/reject/reset requests
- Export topics/requests/visits to CSV
- Clear visit logs

## Student feature
- Check join-request status using enrollment number

The application uses PostgreSQL in production when `DATABASE_URL` is present and SQLite locally otherwise.
