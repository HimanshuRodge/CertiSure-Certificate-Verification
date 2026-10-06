# CertiSure — Certificate Verification System

A software-only Flask web application for registering certificates and verifying them through a database lookup and a QR code. Suitable as a final-year project starter.

## Features

- Admin login for certificate record management
- Register educational, internship, experience, training/course, professional, achievement, participation, and other certificates
- Automatically generated unique certificate IDs
- QR code per certificate, linking to the public verification page
- Public certificate ID lookup without login
- Separate display of database record match (authenticity evidence) and current status (active / expired / revoked)
- Revoke a certificate with a recorded reason
- Search dashboard and basic statistics
- SQLite database created automatically on first run
- Responsive dashboard and public pages

## Important distinction: authenticity vs. validity

**Authenticity / record match:** The system checks whether the submitted ID matches a record in this app's database. That is only meaningful when an authorized issuer controls the records. This starter does not independently prove a document image has not been edited, and it does not connect to a university or government registry.

**Validity / status:** For a matching record, the app checks whether the issuer has marked it `Active` or `Revoked`, and whether an optional expiry date has passed. An authentic certificate may be expired or revoked. `Active` means the issuer record is active and the recorded expiry date has not passed; it is not a guarantee of acceptance by every third party.

## Requirements

- Python 3.10 or newer recommended
- pip
- Internet connection only for the Google Fonts stylesheet; the app itself runs locally without an external verification API

## Setup on Windows

Open Command Prompt or PowerShell in the project folder:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Setup on Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## First-run admin credentials

- Username: `admin`
- Password: `ChangeMe123!`

**Change these before any shared or production deployment.** The first admin is created on initial database setup. To set credentials before the first run, define environment variables:

Windows PowerShell:
```powershell
$env:ADMIN_USERNAME="your-admin"
$env:ADMIN_PASSWORD="a-long-unique-password"
$env:SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

Linux/macOS:
```bash
export ADMIN_USERNAME="your-admin"
export ADMIN_PASSWORD="a-long-unique-password"
export SECRET_KEY="replace-with-a-long-random-secret"
python app.py
```

If the database has already been created, changing these variables does not reset the existing admin password. For a fresh test database, stop the app and remove `instance/certificates.db`, then start it again. This deletes all locally stored certificate records.

## Basic workflow

1. Sign in through **Admin sign in**.
2. Choose **Register certificate** and enter the issuer-approved details.
3. Save the record. The app generates a certificate ID.
4. Open the certificate details page and download its QR image.
5. Share the certificate ID or embed the QR code on the certificate.
6. A recipient enters the ID or scans the QR to see the matching record and status.
7. Revoke records through the detail page if the issuer cancels a certificate.

## QR code and deployment notes

QR codes encode the public URL for this app. Locally they point to `127.0.0.1`, which works only on the same machine. For real recipients, deploy behind HTTPS on a public domain and generate/download the QR code after deployment. Do not expose the development server directly to the internet.

## Security and production checklist

This is a project starter, not a hardened production identity system. Before production use:
- Change the default admin password and `SECRET_KEY`.
- Use HTTPS and a production WSGI server such as Waitress or Gunicorn.
- Add CSRF protection, rate limiting, login lockout, audit logs, backups, and a secure password-reset/admin-management process.
- Restrict certificate registration and revocation to authorized issuer personnel.
- Define data retention and privacy rules; do not put unnecessary sensitive personal data into certificates or notes.
- Consider immutable audit logs and digitally signed issuer records if stronger assurance is needed.
- Make the public base URL configurable when generating QR codes for a deployed site.

## Project structure

```text
certificate_verification_system/
├── app.py
├── requirements.txt
├── README.md
├── instance/              # SQLite database created at runtime
├── generated_qr/          # reserved for QR image storage if needed
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── verify.html
│   ├── login.html
│   ├── dashboard.html
│   ├── certificate_form.html
│   ├── certificate_detail.html
│   └── 404.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Current limitations

- No direct integration with university, employer, or government certificate registries.
- No file upload or AI-based document-forgery detection in this version; it verifies registered records by ID/QR.
- No email/SMS verification, public API, multi-organization tenancy, or admin user-management UI.
- Expiry is checked against the server's local date.
