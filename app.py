import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "class_project.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def using_postgres():
    return bool(DATABASE_URL)


def get_db():
    """Use Render Postgres in production; SQLite locally."""
    if using_postgres():
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed.")
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    execute(conn, "PRAGMA foreign_keys = ON")
    return conn


def execute(conn, sql, params=()):
    if using_postgres():
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def init_db():
    conn = get_db()
    try:
        if using_postgres():
            execute(conn, """
                CREATE TABLE IF NOT EXISTS topics (
                    id SERIAL PRIMARY KEY,
                    creator_name TEXT NOT NULL,
                    enrollment_no TEXT NOT NULL UNIQUE,
                    leader_password TEXT NOT NULL,
                    email TEXT,
                    mobile TEXT,
                    gender TEXT,
                    topic_name TEXT NOT NULL,
                    description TEXT,
                    looking_for_members INTEGER DEFAULT 1,
                    creator_contact TEXT,
                    ip_address TEXT,
                    created_at TEXT
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS join_requests (
                    id SERIAL PRIMARY KEY,
                    applicant_name TEXT NOT NULL,
                    applicant_enrollment TEXT NOT NULL UNIQUE,
                    applicant_email TEXT,
                    applicant_mobile TEXT,
                    applicant_gender TEXT,
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    preferred_role TEXT,
                    message TEXT,
                    status TEXT DEFAULT 'pending',
                    ip_address TEXT,
                    created_at TEXT
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY,
                    ip_address TEXT,
                    page TEXT,
                    timestamp TEXT
                )
            """)
        else:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_name TEXT NOT NULL,
                    enrollment_no TEXT NOT NULL UNIQUE,
                    leader_password TEXT NOT NULL,
                    email TEXT,
                    mobile TEXT,
                    gender TEXT,
                    topic_name TEXT NOT NULL,
                    description TEXT,
                    looking_for_members INTEGER DEFAULT 1,
                    creator_contact TEXT,
                    ip_address TEXT,
                    created_at TEXT
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS join_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_name TEXT NOT NULL,
                    applicant_enrollment TEXT NOT NULL UNIQUE,
                    applicant_email TEXT,
                    applicant_mobile TEXT,
                    applicant_gender TEXT,
                    topic_id INTEGER NOT NULL,
                    preferred_role TEXT,
                    message TEXT,
                    status TEXT DEFAULT 'pending',
                    ip_address TEXT,
                    created_at TEXT,
                    FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    page TEXT,
                    timestamp TEXT
                )
            """)
        conn.commit()
    finally:
        conn.close()


# ---------------- Helpers ----------------
def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def leader_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "leader_enrollment" not in session:
            flash("Please log in as a team leader first.", "error")
            return redirect(url_for("leader_login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin"))
        return view(*args, **kwargs)
    return wrapped


# ---------------- Visit logging ----------------
@app.before_request
def log_visit():
    if request.path.startswith("/static"):
        return

    # Do not let a database/logging problem prevent the website from opening.
    try:
        conn = get_db()
        execute(conn, 
            "INSERT INTO visits (ip_address, page, timestamp) VALUES (?, ?, ?)",
            (
                get_client_ip(),
                request.path,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------- Public routes ----------------
@app.route("/")
def index():
    conn = get_db()
    try:
        if using_postgres():
            topics = execute(conn, """
                SELECT t.*,
                       (SELECT STRING_AGG(
                            jr.applicant_name || ' (' || jr.applicant_enrollment || ')', ', '
                        )
                        FROM join_requests jr
                        WHERE jr.topic_id = t.id AND jr.status = 'accepted'
                       ) AS team_members
                FROM topics t
                ORDER BY t.id DESC
            """).fetchall()
        else:
            topics = execute(conn, """
                SELECT t.*,
                       (SELECT GROUP_CONCAT(
                            jr.applicant_name || ' (' || jr.applicant_enrollment || ')', ', '
                        )
                        FROM join_requests jr
                        WHERE jr.topic_id = t.id AND jr.status = 'accepted'
                       ) AS team_members
                FROM topics t
                ORDER BY t.id DESC
            """).fetchall()
    finally:
        conn.close()
    return render_template("index.html", topics=topics)


@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        ip = get_client_ip()

        creator_name = request.form.get("creator_name", "").strip()
        enrollment_no = request.form.get("enrollment_no", "").strip()
        leader_password = request.form.get("leader_password", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        gender = request.form.get("gender", "").strip()
        topic_name = request.form.get("topic_name", "").strip()
        description = request.form.get("description", "").strip()
        looking_for_members = 1 if request.form.get("looking_for_members") else 0
        creator_contact = request.form.get("creator_contact", "").strip()

        if not (creator_name and enrollment_no and topic_name and leader_password):
            flash(
                "Name, enrollment number, topic name, and leader password are required.",
                "error",
            )
            return render_template("create.html")

        conn = get_db()
        try:

            execute(conn, """
                INSERT INTO topics (
                    creator_name, enrollment_no, leader_password, email, mobile,
                    gender, topic_name, description, looking_for_members,
                    creator_contact, ip_address, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                creator_name,
                enrollment_no,
                leader_password,
                email,
                mobile,
                gender,
                topic_name,
                description,
                looking_for_members,
                creator_contact,
                ip,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()
            flash("Topic created successfully.", "success")
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                flash("This enrollment number has already been used to create a topic.", "error")
            else:
                conn.rollback()
                app.logger.exception("Topic creation failed")
                flash("Could not create the topic. Please try again.", "error")
        finally:
            conn.close()

        return redirect(url_for("index"))

    return render_template("create.html")


@app.route("/join/<int:topic_id>", methods=["GET", "POST"])
def join(topic_id):
    conn = get_db()
    topic = execute(conn, 
        "SELECT * FROM topics WHERE id = ?", (topic_id,)
    ).fetchone()

    if not topic:
        conn.close()
        flash("Topic not found.", "error")
        return redirect(url_for("index"))

    if not topic["looking_for_members"]:
        conn.close()
        flash("This topic is no longer accepting members.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        ip = get_client_ip()

        applicant_name = request.form.get("applicant_name", "").strip()
        applicant_enrollment = request.form.get("applicant_enrollment", "").strip()
        applicant_email = request.form.get("applicant_email", "").strip()
        applicant_mobile = request.form.get("applicant_mobile", "").strip()
        applicant_gender = request.form.get("applicant_gender", "").strip()
        preferred_role = request.form.get("preferred_role", "").strip()
        message = request.form.get("message", "").strip()

        if not (applicant_name and applicant_enrollment):
            conn.close()
            flash("Name and enrollment number are required.", "error")
            return render_template("join.html", topic=topic)

        try:
            execute(conn, """
                INSERT INTO join_requests (
                    applicant_name, applicant_enrollment, applicant_email,
                    applicant_mobile, applicant_gender, topic_id,
                    preferred_role, message, status, ip_address, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (
                applicant_name,
                applicant_enrollment,
                applicant_email,
                applicant_mobile,
                applicant_gender,
                topic_id,
                preferred_role,
                message,
                ip,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            conn.commit()
            flash("Join request sent successfully.", "success")
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                flash("This enrollment number has already sent a join request.", "error")
            else:
                conn.rollback()
                app.logger.exception("Join request failed")
                flash("Could not send the join request. Please try again.", "error")
        finally:
            conn.close()

        return redirect(url_for("index"))

    conn.close()
    return render_template("join.html", topic=topic)


# ---------------- Leader routes ----------------
@app.route("/leader_login", methods=["GET", "POST"])
def leader_login():
    if request.method == "POST":
        enrollment_no = request.form.get("enrollment_no", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        leader = execute(conn, 
            "SELECT * FROM topics WHERE enrollment_no = ?", (enrollment_no,)
        ).fetchone()
        conn.close()

        if leader and leader["leader_password"] == password:
            session["leader_enrollment"] = enrollment_no
            flash("Login successful.", "success")
            return redirect(url_for("leader_dashboard"))

        flash("Invalid enrollment number or password.", "error")

    return render_template("leader_login.html")


@app.route("/leader_dashboard")
@leader_required
def leader_dashboard():
    enrollment_no = session["leader_enrollment"]

    conn = get_db()
    topic = execute(conn, 
        "SELECT * FROM topics WHERE enrollment_no = ?", (enrollment_no,)
    ).fetchone()

    if not topic:
        conn.close()
        session.pop("leader_enrollment", None)
        flash("No topic found for this leader.", "error")
        return redirect(url_for("leader_login"))

    join_requests = execute(conn, """
        SELECT
            jr.id AS request_id,
            jr.applicant_name,
            jr.applicant_enrollment,
            jr.applicant_email,
            jr.applicant_mobile,
            jr.applicant_gender,
            jr.preferred_role,
            jr.message,
            jr.status,
            jr.created_at
        FROM join_requests jr
        WHERE jr.topic_id = ?
        ORDER BY jr.id DESC
    """, (topic["id"],)).fetchall()

    accepted_count = execute(conn, """
        SELECT COUNT(*) AS count
        FROM join_requests
        WHERE topic_id = ? AND status = 'accepted'
    """, (topic["id"],)).fetchone()["count"]

    conn.close()

    return render_template(
        "leader_dashboard.html",
        topic=topic,
        join_requests=join_requests,
        accepted_count=accepted_count,
    )


def update_join_request(request_id, new_status):
    if "leader_enrollment" not in session:
        flash("Please log in as a team leader first.", "error")
        return redirect(url_for("leader_login"))

    conn = get_db()
    leader = execute(conn, 
        "SELECT id FROM topics WHERE enrollment_no = ?",
        (session["leader_enrollment"],),
    ).fetchone()

    if not leader:
        conn.close()
        session.pop("leader_enrollment", None)
        flash("Leader account not found.", "error")
        return redirect(url_for("leader_login"))

    join_request = execute(conn, 
        "SELECT * FROM join_requests WHERE id = ?", (request_id,)
    ).fetchone()

    if not join_request:
        conn.close()
        flash("Join request not found.", "error")
        return redirect(url_for("leader_dashboard"))

    # Security: a leader can only modify requests for their own topic.
    if join_request["topic_id"] != leader["id"]:
        conn.close()
        flash("You are not allowed to modify this request.", "error")
        return redirect(url_for("leader_dashboard"))

    execute(conn, 
        "UPDATE join_requests SET status = ? WHERE id = ?",
        (new_status, request_id),
    )
    conn.commit()
    conn.close()

    flash(f"Request {new_status}.", "success")
    return redirect(url_for("leader_dashboard"))


@app.route("/leader/accept/<int:request_id>")
@leader_required
def leader_accept(request_id):
    return update_join_request(request_id, "accepted")


@app.route("/leader/reject/<int:request_id>")
@leader_required
def leader_reject(request_id):
    return update_join_request(request_id, "rejected")


@app.route("/leader/logout")
def leader_logout():
    session.pop("leader_enrollment", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))


# ---------------- Admin routes ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin"))
        flash("Incorrect admin password.", "error")

    if not session.get("admin_logged_in"):
        return render_template("admin_login.html")

    conn = get_db()
    join_requests = execute(conn, """
        SELECT
            jr.*,
            t.topic_name,
            t.creator_name
        FROM join_requests jr
        LEFT JOIN topics t ON t.id = jr.topic_id
        ORDER BY jr.id DESC
    """).fetchall()
    topics = execute(conn, "SELECT * FROM topics ORDER BY id DESC").fetchall()
    visits = execute(conn, "SELECT * FROM visits ORDER BY id DESC").fetchall()

    stats = {
        "topics": execute(conn, "SELECT COUNT(*) AS count FROM topics").fetchone()["count"],
        "requests": execute(conn, "SELECT COUNT(*) AS count FROM join_requests").fetchone()["count"],
        "accepted": execute(conn, 
            "SELECT COUNT(*) AS count FROM join_requests WHERE status = 'accepted'"
        ).fetchone()["count"],
        "visits": execute(conn, "SELECT COUNT(*) AS count FROM visits").fetchone()["count"],
    }

    conn.close()

    return render_template(
        "admin.html",
        join_requests=join_requests,
        topics=topics,
        visits=visits,
        stats=stats,
    )


@app.route("/admin/request/<int:request_id>/<action>")
@admin_required
def admin_request_action(request_id, action):
    if action not in {"accepted", "rejected", "pending"}:
        flash("Invalid request action.", "error")
        return redirect(url_for("admin"))

    conn = get_db()
    execute(conn, 
        "UPDATE join_requests SET status = ? WHERE id = ?",
        (action, request_id),
    )
    conn.commit()
    conn.close()

    flash(f"Request status changed to {action}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/topic/<int:topic_id>/toggle")
@admin_required
def admin_toggle_topic(topic_id):
    conn = get_db()
    topic = execute(conn, 
        "SELECT looking_for_members FROM topics WHERE id = ?", (topic_id,)
    ).fetchone()

    if topic:
        new_value = 0 if topic["looking_for_members"] else 1
        execute(conn, 
            "UPDATE topics SET looking_for_members = ? WHERE id = ?",
            (new_value, topic_id),
        )
        conn.commit()
        flash("Topic member status updated.", "success")
    else:
        flash("Topic not found.", "error")

    conn.close()
    return redirect(url_for("admin"))


@app.route("/admin/topic/<int:topic_id>/delete")
@admin_required
def admin_delete_topic(topic_id):
    conn = get_db()
    execute(conn, "DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
    flash("Topic deleted.", "success")
    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("index"))


# Initialize tables when Gunicorn imports this module.
init_db()

# ---------------- Start ----------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
