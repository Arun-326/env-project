import os
import sqlite3
import psycopg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "class_project.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is not set.")

if not os.path.exists(SQLITE_DB):
    raise SystemExit(f"SQLite database not found: {SQLITE_DB}")


def main():
    sq = sqlite3.connect(SQLITE_DB)
    sq.row_factory = sqlite3.Row
    pg = psycopg.connect(DATABASE_URL)
    try:
        pg.execute("""CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, creator_name TEXT NOT NULL, enrollment_no TEXT NOT NULL UNIQUE,
            leader_password TEXT NOT NULL, email TEXT, mobile TEXT, gender TEXT, topic_name TEXT NOT NULL,
            description TEXT, looking_for_members INTEGER DEFAULT 1, creator_contact TEXT,
            ip_address TEXT, created_at TEXT)""")
        pg.execute("""CREATE TABLE IF NOT EXISTS join_requests (
            id INTEGER PRIMARY KEY, applicant_name TEXT NOT NULL, applicant_enrollment TEXT NOT NULL UNIQUE,
            applicant_email TEXT, applicant_mobile TEXT, applicant_gender TEXT, topic_id INTEGER NOT NULL
            REFERENCES topics(id) ON DELETE CASCADE, preferred_role TEXT, message TEXT, status TEXT DEFAULT 'pending',
            ip_address TEXT, created_at TEXT)""")
        pg.execute("""CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY, ip_address TEXT, page TEXT, timestamp TEXT)""")

        topics=sq.execute('SELECT * FROM topics ORDER BY id').fetchall()
        requests=sq.execute('SELECT * FROM join_requests ORDER BY id').fetchall()
        visits=sq.execute('SELECT * FROM visits ORDER BY id').fetchall()

        for r in topics:
            pg.execute("""INSERT INTO topics
                (id,creator_name,enrollment_no,leader_password,email,mobile,gender,topic_name,description,
                 looking_for_members,creator_contact,ip_address,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""", tuple(r))
        for r in requests:
            pg.execute("""INSERT INTO join_requests
                (id,applicant_name,applicant_enrollment,applicant_email,applicant_mobile,applicant_gender,topic_id,
                 preferred_role,message,status,ip_address,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""", tuple(r))
        for r in visits:
            pg.execute("""INSERT INTO visits (id,ip_address,page,timestamp)
                VALUES (%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""", tuple(r))

        # Keep new IDs above imported IDs.
        for table in ('topics','join_requests','visits'):
            pg.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), COALESCE((SELECT MAX(id) FROM {table}),1), true)")
        pg.commit()
        print(f'Migration complete: {len(topics)} topics, {len(requests)} join requests, {len(visits)} visits.')
    except Exception:
        pg.rollback()
        raise
    finally:
        sq.close(); pg.close()

if __name__ == '__main__':
    main()
