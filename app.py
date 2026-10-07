import os
import io
import psycopg2
from psycopg2.extras import DictCursor
import secrets
import string
from datetime import date, datetime
from functools import wraps
from urllib.parse import urljoin

import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
QR_DIR = os.path.join(BASE_DIR, "generated_qr")
os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret-key")
# PostgreSQL database URL.
# Set DATABASE_URL in Render Environment Variables.
app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL")

if not app.config["DATABASE_URL"]:
    raise RuntimeError(
        "DATABASE_URL environment variable is required."
    )
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

DEFAULT_ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
ALLOWED_TYPES = [
    "Educational", "Internship", "Experience", "Training/Course",
    "Professional", "Achievement", "Participation", "Other"
]

class DatabaseConnection:
    """PostgreSQL wrapper keeping the existing db().execute() style."""

    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = None

    def __enter__(self):
        self.conn = psycopg2.connect(self.database_url)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def execute(self, query, params=None):
        # Convert existing SQLite placeholders to PostgreSQL placeholders.
        query = query.replace("?", "%s")
        cursor = self.conn.cursor(cursor_factory=DictCursor)
        cursor.execute(query, params or ())
        return cursor


def db():
    return DatabaseConnection(app.config["DATABASE_URL"])


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                certificate_id TEXT UNIQUE NOT NULL,
                holder_name TEXT NOT NULL,
                certificate_type TEXT NOT NULL,
                title TEXT NOT NULL,
                issuer_name TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                expiry_date TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                notes TEXT,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_reason TEXT
            )
        """)

        existing = conn.execute(
            "SELECT id FROM admins WHERE username = ?",
            (DEFAULT_ADMIN_USER,)
        ).fetchone()

        if not existing:
            conn.execute(
                "INSERT INTO admins(username, password_hash, created_at) VALUES(?,?,?)",
                (
                    DEFAULT_ADMIN_USER,
                    generate_password_hash(DEFAULT_ADMIN_PASSWORD),
                    datetime.utcnow().isoformat(timespec="seconds")
                )
            )

def make_certificate_id():
    alphabet = string.ascii_uppercase + string.digits
    return "CERT-" + "".join(secrets.choice(alphabet) for _ in range(10))

def get_certificate(cert_id):
    with db() as conn:
        return conn.execute("SELECT * FROM certificates WHERE certificate_id = ?", (cert_id.strip().upper(),)).fetchone()

def status_details(cert):
    today = date.today()
    if cert["status"] == "Revoked":
        return "Revoked", "The issuer has revoked this certificate.", "danger"
    if cert["expiry_date"]:
        try:
            if date.fromisoformat(cert["expiry_date"]) < today:
                return "Expired", "The recorded expiry date has passed.", "warning"
        except ValueError:
            return "Review required", "The expiry date stored for this record is invalid.", "warning"
    if cert["status"] != "Active":
        return cert["status"], "The certificate is not currently marked active by the issuer.", "warning"
    return "Active", "The issuer's record is active and the certificate has not expired.", "success"

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please sign in to access the admin dashboard.", "info")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {"current_year": date.today().year}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["GET", "POST"])
def verify():
    cert_id = (request.values.get("certificate_id") or "").strip().upper()
    cert = None
    status = None
    message = None
    tone = None
    if cert_id:
        cert = get_certificate(cert_id)
        if cert:
            status, message, tone = status_details(cert)
        else:
            message = "No matching certificate record was found in this system. This does not by itself prove fraud; confirm with the named issuer."
            tone = "danger"
    return render_template("verify.html", certificate=cert, certificate_id=cert_id,
                           status=status, status_message=message, tone=tone)

@app.route("/certificate/<cert_id>/qr.png")
def certificate_qr(cert_id):
    cert = get_certificate(cert_id)
    if not cert:
        abort(404)
    verify_url = url_for("verify", certificate_id=cert["certificate_id"], _external=True)
    img = qrcode.make(verify_url)
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", download_name=f"{cert_id}_qr.png")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as conn:
            admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Welcome back. You are signed in.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@login_required
def dashboard():
    search = request.args.get("q", "").strip()
    with db() as conn:
        stats = {
            "total": conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
            "active": conn.execute("SELECT COUNT(*) FROM certificates WHERE status = 'Active'").fetchone()[0],
            "revoked": conn.execute("SELECT COUNT(*) FROM certificates WHERE status = 'Revoked'").fetchone()[0],
        }
        if search:
            like = f"%{search}%"
            certs = conn.execute("""
                SELECT * FROM certificates
                WHERE certificate_id LIKE ? OR holder_name LIKE ? OR title LIKE ? OR issuer_name LIKE ?
                ORDER BY id DESC LIMIT 200
            """, (like, like, like, like)).fetchall()
        else:
            certs = conn.execute("SELECT * FROM certificates ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("dashboard.html", stats=stats, certificates=certs, search=search)

@app.route("/admin/certificates/new", methods=["GET", "POST"])
@login_required
def create_certificate():
    if request.method == "POST":
        data = {
            "holder_name": request.form.get("holder_name", "").strip(),
            "certificate_type": request.form.get("certificate_type", "").strip(),
            "title": request.form.get("title", "").strip(),
            "issuer_name": request.form.get("issuer_name", "").strip(),
            "issue_date": request.form.get("issue_date", "").strip(),
            "expiry_date": request.form.get("expiry_date", "").strip() or None,
            "notes": request.form.get("notes", "").strip(),
        }
        if not all([data["holder_name"], data["certificate_type"], data["title"], data["issuer_name"], data["issue_date"]]):
            flash("Please fill in all required fields.", "danger")
            return render_template("certificate_form.html", types=ALLOWED_TYPES, form=data)
        if data["certificate_type"] not in ALLOWED_TYPES:
            flash("Choose a certificate type from the list.", "danger")
            return render_template("certificate_form.html", types=ALLOWED_TYPES, form=data)
        try:
            issue = date.fromisoformat(data["issue_date"])
            if data["expiry_date"] and date.fromisoformat(data["expiry_date"]) < issue:
                flash("Expiry date cannot be earlier than the issue date.", "danger")
                return render_template("certificate_form.html", types=ALLOWED_TYPES, form=data)
        except ValueError:
            flash("Please enter valid dates.", "danger")
            return render_template("certificate_form.html", types=ALLOWED_TYPES, form=data)
        cert_id = make_certificate_id()
        with db() as conn:
            conn.execute("""
                INSERT INTO certificates
                (certificate_id, holder_name, certificate_type, title, issuer_name, issue_date, expiry_date, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """, (cert_id, data["holder_name"], data["certificate_type"], data["title"],
                  data["issuer_name"], data["issue_date"], data["expiry_date"], data["notes"],
                  datetime.utcnow().isoformat(timespec="seconds")))
        flash(f"Certificate {cert_id} was registered.", "success")
        return redirect(url_for("certificate_detail", cert_id=cert_id))
    return render_template("certificate_form.html", types=ALLOWED_TYPES, form={})

@app.route("/admin/certificates/<cert_id>")
@login_required
def certificate_detail(cert_id):
    cert = get_certificate(cert_id)
    if not cert:
        abort(404)
    status, message, tone = status_details(cert)
    return render_template("certificate_detail.html", certificate=cert, status=status, status_message=message, tone=tone)

@app.route("/admin/certificates/<cert_id>/revoke", methods=["POST"])
@login_required
def revoke_certificate(cert_id):
    reason = request.form.get("reason", "").strip()
    cert = get_certificate(cert_id)
    if not cert:
        abort(404)
    if cert["status"] != "Revoked":
        with db() as conn:
            conn.execute("""
                UPDATE certificates SET status='Revoked', revoked_at=?, revoked_reason=?
                WHERE certificate_id=?
            """, (datetime.utcnow().isoformat(timespec="seconds"), reason or "No reason supplied", cert_id))
        flash(f"{cert_id} has been revoked.", "success")
    else:
        flash("This certificate is already revoked.", "info")
    return redirect(url_for("certificate_detail", cert_id=cert_id))

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404

@app.errorhandler(413)
def too_large(error):
    flash("The uploaded request is too large. This app accepts requests up to 8 MB.", "danger")
    return redirect(url_for("verify"))

init_db()

if __name__ == "__main__":
    # For local development only. Use a production WSGI server for deployment.
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=5000)
