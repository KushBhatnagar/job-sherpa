"""SQLite schema and helpers. The database lives at <home>/sherpa.db.

`connect()` applies the schema on every call (all statements are idempotent),
so a new table or column never silently fails to exist.
"""
import hashlib
import sqlite3

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    ats_type   TEXT,      -- greenhouse | lever | ashby | smartrecruiters
    ats_token  TEXT,
    tier       TEXT,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id             INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(id),
    source         TEXT NOT NULL DEFAULT 'manual',
    title          TEXT NOT NULL,
    location       TEXT,
    url            TEXT,
    discovered_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status         TEXT NOT NULL DEFAULT 'new',   -- new | shortlisted | applied | dismissed
    content_hash   TEXT NOT NULL UNIQUE,
    source_job_id  TEXT,
    description    TEXT,
    remote_type    TEXT,     -- local | ok_remote | world_remote | restricted_remote | onsite_other
    posted_at      DATE,
    fit_score      INTEGER,
    fit_json       TEXT,     -- the full score-fit judgment, kept for auditing
    dismiss_reason TEXT,
    seen_count     INTEGER DEFAULT 1,
    raw_json       TEXT      -- the untouched source payload
);

CREATE TABLE IF NOT EXISTS applications (
    id                INTEGER PRIMARY KEY,
    job_id            INTEGER NOT NULL REFERENCES jobs(id),
    applied_at        DATE NOT NULL,
    channel           TEXT,               -- portal | referral | email | ...
    referrer          TEXT,
    status            TEXT NOT NULL DEFAULT 'applied',
    outcome           TEXT,
    rejection_reason  TEXT,
    packet_path       TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY,
    application_id  INTEGER NOT NULL REFERENCES applications(id),
    type            TEXT NOT NULL,
    occurred_at     DATE NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_app ON events(application_id, occurred_at);

CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY,
    job_id       INTEGER NOT NULL REFERENCES jobs(id),
    kind         TEXT NOT NULL DEFAULT 'resume',  -- resume | cover_letter
    bullets_used TEXT,    -- JSON array of bullet ids (resume only)
    angle        TEXT,
    path_md      TEXT,
    path_pdf     TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

EVENT_TYPES = ("applied", "ack", "recruiter_screen", "hm_round", "assignment", "panel",
               "offer", "rejected", "ghosted", "withdrawn")
# Events that close an application one way or another. The rest are progress.
TERMINAL_EVENTS = {"rejected", "withdrawn", "ghosted", "offer"}

JOB_AGE_SQL = "COALESCE(j.posted_at, date(j.discovered_at))"


_OPEN: list[sqlite3.Connection] = []


def close_all() -> None:
    """Close every connection opened by connect(). Called after each command, so
    an early exit never leaves the database file locked (it matters on Windows)."""
    while _OPEN:
        try:
            _OPEN.pop().close()
        except sqlite3.Error:
            pass


def connect() -> sqlite3.Connection:
    path = paths.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    _OPEN.append(conn)
    return conn


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def content_hash(company_id: int, title: str, location: str) -> str:
    raw = f"{company_id}|{_norm(title)}|{_norm(location)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_or_create_company(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO companies (name) VALUES (?)", (name,)).lastrowid


def get_or_create_job(conn, company_id: int, title: str, location: str, url: str) -> int:
    h = content_hash(company_id, title, location)
    row = conn.execute("SELECT id FROM jobs WHERE content_hash = ?", (h,)).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO jobs (company_id, title, location, url, content_hash) VALUES (?,?,?,?,?)",
        (company_id, title, location, url, h)).lastrowid


def dismiss_stale(conn, days: int) -> int:
    """Dismiss 'new' jobs older than `days` (posted date, else discovery date).
    Shortlisted jobs are the user's call and are left alone."""
    cur = conn.execute(
        f"""UPDATE jobs SET status = 'dismissed',
                   dismiss_reason = 'stale: posted over {int(days)} days ago'
            WHERE id IN (SELECT j.id FROM jobs j WHERE j.status = 'new'
                         AND {JOB_AGE_SQL} < date('now', ?))""",
        (f"-{int(days)} days",))
    return cur.rowcount


def _same_role_overlapping_location(conn, company_id, title, location, description=""):
    """An existing row for the same company + title sharing at least one location.
    A merged multi-location row ('Ireland / Spain') changes whenever a country is
    added, so the exact hash misses; overlap catches it. Two full JDs that differ
    mean a different job that happens to share a title."""
    from .normalize import LOCATION_SEP, MIN_JD_CHARS, same_jd
    parts = {_norm(p) for p in (location or "").split(LOCATION_SEP) if p.strip()}
    if not parts:
        return None
    for row in conn.execute("SELECT id, title, location, description FROM jobs WHERE company_id = ?",
                            (company_id,)):
        if _norm(row["title"]) != _norm(title):
            continue
        theirs = {_norm(p) for p in (row["location"] or "").split(LOCATION_SEP) if p.strip()}
        if not parts & theirs:
            continue
        both_have_jd = min(len(description or ""), len(row["description"] or "")) >= MIN_JD_CHARS
        if both_have_jd and not same_jd(description, row["description"]):
            continue
        return row
    return None


def upsert_discovered_job(conn, *, company_id: int, source: str, title: str, location: str,
                          url: str, description: str = "", source_job_id: str = "",
                          posted_at: str | None = None, raw_json: str = "",
                          remote_type: str = "") -> tuple[int, bool]:
    """Insert a discovered job, or bump seen_count if it's already known.
    Returns (job_id, is_new)."""
    h = content_hash(company_id, title, location)
    row = conn.execute("SELECT id FROM jobs WHERE content_hash = ?", (h,)).fetchone()
    if not row:
        row = _same_role_overlapping_location(conn, company_id, title, location, description)
    if row:
        conn.execute("UPDATE jobs SET seen_count = seen_count + 1 WHERE id = ?", (row["id"],))
        return row["id"], False
    cur = conn.execute(
        """INSERT INTO jobs (company_id, source, title, location, url, description,
                             source_job_id, posted_at, raw_json, remote_type, content_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (company_id, source, title, location, url, description,
         source_job_id, posted_at, raw_json, remote_type, h))
    return cur.lastrowid, True
