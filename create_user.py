"""
create_user.py - Creates a test user in PostgreSQL with a valid bcrypt password hash.

Run: python create_user.py
"""

import bcrypt
import subprocess

# ── User settings — change these if needed ────────────────────────────────────
EMAIL    = "admin@cnst.com"
PASSWORD = "admin"
ROLE     = "admin"   # options: public, inspector, admin

# ── Generate a valid bcrypt hash ───────────────────────────────────────────────
password_hash = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
print(f"Generated hash: {password_hash[:20]}...")

# ── Build the SQL ──────────────────────────────────────────────────────────────
sql = (
    f"INSERT INTO users (email, password_hash, role) "
    f"VALUES ('{EMAIL}', '{password_hash}', '{ROLE}') "
    f"ON CONFLICT (email) DO UPDATE SET password_hash='{password_hash}', role='{ROLE}';"
)

# ── Run it via docker exec ─────────────────────────────────────────────────────
print(f"Inserting user: {EMAIL} ({ROLE})...")
result = subprocess.run(
    ["docker", "exec", "-i", "cnst_postgres", "psql", "-U", "cnst_user", "-d", "cnst_rag", "-c", sql],
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    print(f"Success! User '{EMAIL}' created/updated.")
    print(f"Login with: email={EMAIL}  password={PASSWORD}")
else:
    print(f"Error: {result.stderr}")
