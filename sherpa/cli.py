"""sherpa: the Job Sherpa command line.

Run as `python3 -m sherpa <command>` or `bin/sherpa <command>`.

The CLI stores, fetches, checks and renders. Judgment (is this job a fit, which
bullets to lead with, what to say in a letter) lives in the playbooks/, which
your coding agent follows and which call these commands.
"""
import argparse
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from . import audit, backup, claims, config, db, enrich, normalize, paths, profile, render, shortlist, yaml_lite
from .sources import adzuna, ashby, greenhouse, lever, smartrecruiters

ATS_ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "untitled"


def _die(msg: str):
    print(msg)
    raise SystemExit(1)


def _job_or_die(conn, job_id):
    row = conn.execute("SELECT j.*, c.name AS company_name FROM jobs j "
                       "JOIN companies c ON c.id = j.company_id WHERE j.id = ?", (job_id,)).fetchone()
    if not row:
        _die(f"No job #{job_id}")
    return row


def _draft_dir(job) -> Path:
    return paths.drafts_dir() / f"{job['id']}__{_slug(job['company_name'])}__{_slug(job['title'])}"


def _read_text_arg(file_arg: str | None) -> str:
    return (Path(file_arg).read_text(encoding="utf-8") if file_arg else sys.stdin.read()).strip()


# ── setup ──────────────────────────────────────────────────────────────────

def cmd_init(args):
    home = paths.home()
    home.mkdir(parents=True, exist_ok=True)
    created = []
    for src in sorted((paths.TEMPLATES / "me-skeleton").iterdir()):
        dest = home / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
            created.append(dest.name)
    companies = paths.companies_path()
    if not companies.exists():
        starter = paths.STARTER_LISTS / f"{args.starter}.yaml"
        if not starter.exists():
            names = ", ".join(p.stem for p in paths.STARTER_LISTS.glob("*.yaml"))
            _die(f"No starter list {args.starter!r}. Available: {names}")
        shutil.copy2(starter, companies)
        created.append(f"companies.yaml (from starter-lists/{starter.name})")
    for sub in ("drafts", "applications", "source"):
        (home / sub).mkdir(exist_ok=True)
    db.connect().close()
    print(f"Your private folder: {paths.show(home)}")
    for c in created:
        print(f"  created {c}")
    print("Next: ask your coding agent to run the onboard playbook (playbooks/onboard.md).")


def cmd_doctor(args):
    """Check the setup and say what's missing, in plain words."""
    ok = True

    def line(good, text, fix=""):
        nonlocal ok
        ok = ok and good
        print(("  ok    " if good else "  TODO  ") + text + ("" if good or not fix else f"\n          -> {fix}"))

    home = paths.home()
    print(f"Private folder: {paths.show(home)}")
    line(home.exists(), "private folder exists", "run `sherpa init`")
    prof_file = paths.profile_path()
    p = profile.load()
    line(prof_file.exists() and bool(p.contact.get("name")), "profile.toml has your name and contact",
         "run the onboard playbook, or edit profile.toml")
    line(bool(p.targets["titles"]), "target titles set (discovery keeps everything until they are)",
         "set [targets].titles in profile.toml")
    line(bool(p.targets["locations"]) or p.targets["remote"] == "anywhere",
         "locations set", "set [targets].locations in profile.toml")
    n_bullets = len(claims.load_bullets())
    line(n_bullets >= 8, f"bullets.yaml has {n_bullets} bullet(s) (aim for 8+)",
         "run the onboard playbook to build it from your resume")
    master = home / "master-resume.json"
    has_master = master.exists() and '"b-' in master.read_text(encoding="utf-8")
    line(has_master, "master-resume.json lists your roles and bullets", "the onboard playbook writes it")
    comp = paths.companies_path()
    n_comp = len(yaml_lite.load_flat_list(comp)) if comp.exists() else 0
    line(n_comp > 0, f"companies.yaml lists {n_comp} companies", "run `sherpa init` or add companies")
    backend = render.typst_backend()
    line(backend is not None, f"Typst available ({backend or 'missing'})", "pip install typst")
    env = config.load_env()
    adz = bool(env.get("ADZUNA_APP_ID") and p.search["adzuna_country"])
    print(f"  {'ok' if adz else 'opt'}   Adzuna {'configured' if adz else 'not configured (optional)'}")
    hook = (paths.REPO_ROOT / ".git" / "config")
    hooked = hook.exists() and ".githooks" in hook.read_text(encoding="utf-8", errors="replace")
    line(hooked or home != paths.REPO_ROOT / "me",
         "git hook that blocks committing me/ is on",
         "git config core.hooksPath .githooks")
    print("\nAll set." if ok else "\nFix the TODO lines above, then run `sherpa doctor` again.")


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ElementTree.fromstring(xml)
    paras = []
    for p in root.iter(f"{{{ns['w']}}}p"):
        paras.append("".join(t.text or "" for t in p.iter(f"{{{ns['w']}}}t")))
    return "\n".join(paras)


def cmd_resume_text(args):
    """Extract your resume's text with line numbers, so every bullet built from
    it can cite its source line ('resume line 12')."""
    src = Path(args.file)
    suffix = src.suffix.lower()
    if suffix == ".docx":
        text = _docx_text(src)
    elif suffix in (".txt", ".md"):
        text = src.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        if shutil.which("pdftotext"):
            import subprocess
            text = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True,
                                  text=True, check=True).stdout
        else:
            try:
                from pypdf import PdfReader
            except ImportError:
                _die("Can't read PDFs here: install poppler (pdftotext) or `pip install pypdf`,\n"
                     "or save your resume as .docx/.txt. Your coding agent may also read the PDF "
                     "directly and write the text to me/source/resume.txt.")
            text = "\n".join(page.extract_text() or "" for page in PdfReader(str(src)).pages)
    else:
        _die("Supported: .pdf, .docx, .txt, .md")
    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for i, ln in enumerate(lines) if ln.strip() or (i and lines[i - 1].strip())]
    out = paths.home() / "source" / "resume.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(f"{i + 1:4}  {ln}" for i, ln in enumerate(lines)) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} numbered lines to {paths.show(out)}")


# ── tracking ───────────────────────────────────────────────────────────────

def cmd_apply(args):
    conn = db.connect()
    if args.job_id:
        job = _job_or_die(conn, args.job_id)
        job_id = args.job_id
        company, title = job["company_name"], " ".join(job["title"].split())
        location, url = job["location"], job["url"]
    else:
        if not (args.company and args.title):
            _die("sherpa apply: give --job-id, or both --company and --title")
        company, title, location, url = args.company, args.title, args.location or "", args.url or ""
        job_id = db.get_or_create_job(conn, db.get_or_create_company(conn, company), title, location, url)
    conn.execute("UPDATE jobs SET status = 'applied' WHERE id = ?", (job_id,))
    applied_at = args.date or date.today().isoformat()
    app_id = conn.execute(
        "INSERT INTO applications (job_id, applied_at, channel, referrer, status) VALUES (?,?,?,?,'applied')",
        (job_id, applied_at, args.channel, args.referrer)).lastrowid
    conn.execute("INSERT INTO events (application_id, type, occurred_at) VALUES (?, 'applied', ?)",
                 (app_id, applied_at))

    packet = paths.applications_dir() / f"{applied_at}__{_slug(company)}__{_slug(title)}"
    packet.mkdir(parents=True, exist_ok=True)
    (packet / "application.md").write_text(
        f"# {title} — {company}\n\n- Applied: {applied_at}\n- Channel: {args.channel or '-'}\n"
        f"- Referrer: {args.referrer or '-'}\n- URL: {url or '-'}\n- Location: {location or '-'}\n",
        encoding="utf-8")
    drafts = list(paths.drafts_dir().glob(f"{job_id}__*")) if paths.drafts_dir().exists() else []
    if drafts:
        for f in drafts[0].iterdir():
            if f.is_file():
                shutil.copy2(f, packet / f.name)
        print(f"Copied tailored documents from {paths.show(drafts[0])}")
    conn.execute("UPDATE applications SET packet_path = ? WHERE id = ?", (paths.show(packet), app_id))
    conn.commit()
    conn.close()
    print(f"Application #{app_id} logged: {title} @ {company} ({applied_at})")
    print(f"Packet: {paths.show(packet)}")


def cmd_log(args):
    conn = db.connect()
    if not conn.execute("SELECT 1 FROM applications WHERE id = ?", (args.application_id,)).fetchone():
        _die(f"No application #{args.application_id}")
    occurred_at = args.date or date.today().isoformat()
    conn.execute("INSERT INTO events (application_id, type, occurred_at, notes) VALUES (?,?,?,?)",
                 (args.application_id, args.event, occurred_at, args.notes))
    if args.event in db.TERMINAL_EVENTS:
        conn.execute("UPDATE applications SET status = ?, outcome = ?, "
                     "rejection_reason = COALESCE(?, rejection_reason) WHERE id = ?",
                     (args.event, args.event, args.notes if args.event == "rejected" else None,
                      args.application_id))
    elif args.event != "applied":
        conn.execute("UPDATE applications SET status = 'in_progress' WHERE id = ? AND status = 'applied'",
                     (args.application_id,))
    conn.commit()
    conn.close()
    print(f"Logged '{args.event}' on application #{args.application_id} ({occurred_at})")


def cmd_followups(args):
    p = profile.load()
    lo, hi = int(p.search["followup_after_days"]), int(p.search["followup_until_days"])
    conn = db.connect()
    rows = conn.execute(
        """SELECT a.id, c.name AS company, j.title, a.applied_at,
                  CAST(julianday('now') - julianday(a.applied_at) AS INTEGER) AS days_silent
           FROM applications a JOIN jobs j ON j.id = a.job_id JOIN companies c ON c.id = j.company_id
           WHERE a.status = 'applied'
             AND NOT EXISTS (SELECT 1 FROM events e WHERE e.application_id = a.id AND e.type != 'applied')
             AND CAST(julianday('now') - julianday(a.applied_at) AS INTEGER) BETWEEN ? AND ?
           ORDER BY days_silent DESC""", (lo, hi)).fetchall()
    conn.close()
    if not rows:
        print(f"Nothing needs a follow-up right now ({lo}-{hi} days silent, no response).")
        return
    print(f"{'ID':<4} {'Company':<20} {'Title':<38} {'Applied':<12} {'Days silent':>11}")
    for r in rows:
        print(f"{r['id']:<4} {r['company'][:20]:<20} {r['title'][:38]:<38} {r['applied_at']:<12} {r['days_silent']:>11}")


def cmd_applications(args):
    """Every application with its id, so `log` and interview prep can refer to it."""
    conn = db.connect()
    sql = """SELECT a.id, a.applied_at, a.status, a.channel, j.id AS job_id, c.name AS company, j.title,
                    (SELECT e.type || ' ' || e.occurred_at FROM events e WHERE e.application_id = a.id
                     ORDER BY e.occurred_at DESC, e.id DESC LIMIT 1) AS last_event
             FROM applications a JOIN jobs j ON j.id = a.job_id JOIN companies c ON c.id = j.company_id"""
    where, params = [], []
    if args.status:
        where.append("a.status = ?")
        params.append(args.status)
    elif not args.all:
        where.append("a.status IN ('applied', 'in_progress')")
    if args.company:
        where.append("c.name LIKE ?")
        params.append(f"%{args.company}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = conn.execute(sql + " ORDER BY a.applied_at DESC, a.id DESC", params).fetchall()
    if not rows:
        print("No matching applications." + ("" if args.all or args.status else
                                              " (Showing open ones only; --all includes closed.)"))
        return
    print(f"{'App':<5} {'Job':<5} {'Applied':<11} {'Company':<20} {'Title':<34} {'Status':<12} Last event")
    for r in rows:
        print(f"{r['id']:<5} {r['job_id']:<5} {r['applied_at']:<11} {r['company'][:20]:<20} "
              f"{r['title'][:34]:<34} {r['status']:<12} {r['last_event'] or '-'}")
    if not (args.all or args.status):
        print("\nOpen applications only; --all includes rejected, withdrawn, ghosted and offers.")


def cmd_stats(args):
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) AS n FROM applications").fetchone()["n"]
    if total == 0:
        print("No applications logged yet. Use `sherpa apply` to log one.")
        return
    responded = conn.execute(
        "SELECT COUNT(DISTINCT application_id) AS n FROM events WHERE type != 'applied'").fetchone()["n"]
    print(f"Total applications: {total}")
    print(f"Got any response:   {responded} ({100 * responded / total:.0f}%)")
    print("\nBy status:")
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM applications GROUP BY status ORDER BY n DESC"):
        print(f"  {r['status']:<14} {r['n']}")
    if args.by == "company":
        print("\nBy company:")
        for r in conn.execute("""SELECT c.name, COUNT(*) AS n FROM applications a JOIN jobs j ON j.id = a.job_id
                                 JOIN companies c ON c.id = j.company_id GROUP BY c.name ORDER BY n DESC"""):
            print(f"  {r['name']:<20} {r['n']}")
    conn.close()


# ── discovery ──────────────────────────────────────────────────────────────

def _filter_relevant(raw_jobs, prof, report):
    """Postings with a target title in a reachable location. Records what was
    dropped so `discover` can say so: filters that fail silently hide jobs."""
    relevant = []
    for j in raw_jobs:
        title, loc = j["title"], j["location"]
        if not prof.title_matches(title):
            if prof.is_near_miss_title(title) and prof.location_in_range(loc):
                report["near_miss"][title.strip()] += 1
            continue
        if not prof.location_in_range(loc):
            report["dropped_loc"][(loc or "(blank)").strip()] += 1
            continue
        relevant.append(j)
    return relevant


def _print_filter_report(report, prof):
    dropped, near = report["dropped_loc"], report["near_miss"]
    if not dropped and not near:
        return
    print("\nWhat the filters dropped (nothing below was stored):")
    if dropped:
        top = ", ".join(f"{loc} x{n}" for loc, n in dropped.most_common(5))
        print(f"  {sum(dropped.values())} matching-title posting(s) outside your locations; top: {top}")
        maybe = [(loc, n) for loc, n in dropped.most_common() if prof.maybe_reachable(loc)]
        if maybe:
            print("  ! worth a look: these may be reachable but didn't match [targets] in profile.toml:")
            for loc, n in maybe[:8]:
                print(f"      {loc!r} x{n}")
    if near:
        print(f"  {sum(near.values())} near-miss title(s) (from targets.near_miss_titles), e.g.:")
        for title, n in near.most_common(5):
            print(f"      {title!r}" + (f" x{n}" if n > 1 else ""))


def _store_jobs(conn, jobs, company_id_for, prof, flag_needs_jd=False):
    new_count = 0
    for j in jobs:
        job_id, is_new = db.upsert_discovered_job(
            conn, company_id=company_id_for(j), source=j["source"], title=j["title"],
            location=j["location"], url=j["url"], description=j["description"],
            source_job_id=j["source_job_id"], posted_at=j["posted_at"], raw_json=j["raw_json"],
            remote_type=j.get("remote_type") or prof.classify_location(j["location"]))
        if is_new:
            if flag_needs_jd:
                conn.execute("UPDATE jobs SET fit_json = ? WHERE id = ?", (json.dumps({
                    "needs_full_jd": True,
                    "angle": "Description is an excerpt. Find the full JD before scoring."}), job_id))
            new_count += 1
    return new_count


def _merge_note(before, after):
    return f" -> {after} after merging multi-location postings" if after < before else ""


def cmd_discover(args):
    prof = profile.load()
    if not prof.targets["titles"]:
        print("Note: no [targets].titles in profile.toml, so every title is kept.")
    conn = db.connect()
    comp_file = paths.companies_path()
    companies = yaml_lite.load_flat_list(comp_file) if comp_file.exists() else []
    total_new = 0
    report = {"dropped_loc": Counter(), "near_miss": Counter()}
    # A failed run and a quiet day both end in "0 new": track failures so a dead
    # network can't pass for "nothing posted".
    attempted, failed = 0, []

    for co in companies:
        ats_type = co.get("ats_type", "")
        if args.source and ats_type != args.source:
            continue
        fetch = ATS_ADAPTERS.get(ats_type)
        if not fetch or not co.get("ats_token"):
            continue
        attempted += 1
        try:
            raw_jobs = fetch(co["ats_token"])
        except Exception as e:
            print(f"  {co['name']}: failed ({e})")
            failed.append(co["name"])
            continue
        relevant = _filter_relevant(raw_jobs, prof, report)
        merged = normalize.merge_multi_location(relevant, prof)
        company_id = db.get_or_create_company(conn, co["name"])
        conn.execute("UPDATE companies SET ats_type = ?, ats_token = ? WHERE id = ?",
                     (ats_type, co["ats_token"], company_id))
        new_count = _store_jobs(conn, merged, lambda j: company_id, prof)
        total_new += new_count
        if raw_jobs and (relevant or args.verbose):
            print(f"  {co['name']}: {len(raw_jobs)} postings, {len(relevant)} match"
                  f"{_merge_note(len(relevant), len(merged))}, {new_count} new")

    if not args.source or args.source == "adzuna":
        queries = prof.search["adzuna_queries"] or prof.targets["titles"][:2]
        for q in queries:
            attempted += 1
            try:
                raw_jobs = adzuna.fetch(prof.search["adzuna_country"], q, prof.search["adzuna_where"])
            except adzuna.MissingCredentials as e:
                attempted -= 1      # not configured is not a failure
                print(f"  Adzuna: skipped ({e})")
                break
            except Exception as e:
                print(f"  Adzuna ({q}): failed ({e})")
                failed.append(f"Adzuna ({q})")
                continue
            relevant = _filter_relevant(raw_jobs, prof, report)
            merged = normalize.merge_multi_location(relevant, prof, company_key=lambda j: j["company_name"])
            new_count = _store_jobs(conn, merged, lambda j: db.get_or_create_company(conn, j["company_name"]),
                                    prof, flag_needs_jd=True)
            total_new += new_count
            print(f"  Adzuna ({q}): {len(raw_jobs)} postings, {len(relevant)} match"
                  f"{_merge_note(len(relevant), len(merged))}, {new_count} new")

    stale = db.dismiss_stale(conn, prof.search["stale_after_days"])
    conn.commit()
    conn.close()
    _print_filter_report(report, prof)
    print(f"\n{total_new} new job(s) discovered.")
    if stale:
        print(f"{stale} inbox job(s) older than {prof.search['stale_after_days']} days dismissed as stale.")
    if failed:
        print(f"\n! {len(failed)} of {attempted} source(s) failed: {', '.join(failed)}")
        if len(failed) == attempted:
            sys.exit("Every source failed, so '0 new' means nothing was checked, not that nothing "
                     "was posted. Check the network, then rerun.")
        print("  Postings from those boards were NOT checked this run.")


def cmd_add_job(args):
    """Add a job you found yourself (LinkedIn, a referral, a careers page), with
    its JD pasted in. This is how sites that can't be fetched reach the pipeline."""
    text = _read_text_arg(None if args.file == "-" else args.file) if args.file else ""
    prof = profile.load()
    conn = db.connect()
    company_id = db.get_or_create_company(conn, args.company)
    job_id, is_new = db.upsert_discovered_job(
        conn, company_id=company_id, source="manual", title=args.title, location=args.location or "",
        url=args.url or "", description=text, remote_type=prof.classify_location(args.location or ""))
    if is_new and args.posted:
        conn.execute("UPDATE jobs SET posted_at = ? WHERE id = ?", (args.posted, job_id))
    if len(text) < 200:
        conn.execute("UPDATE jobs SET fit_json = ? WHERE id = ? AND fit_json IS NULL",
                     (json.dumps({"needs_full_jd": True}), job_id))
    conn.commit()
    conn.close()
    print(f"{'Added' if is_new else 'Already known as'} job #{job_id}: {args.title} @ {args.company}"
          + ("" if len(text) >= 200 else "  (no full JD yet: add one with `sherpa set-jd`)"))


def cmd_inbox(args):
    prof = profile.load()
    conn = db.connect()
    if db.dismiss_stale(conn, prof.search["stale_after_days"]):
        conn.commit()
    query = ("SELECT j.id, c.name AS company, j.title, j.location, j.fit_score, j.remote_type "
             "FROM jobs j JOIN companies c ON c.id = j.company_id WHERE j.status = 'new'")
    params: tuple = ()
    if args.min_score is not None:
        query += " AND (j.fit_score IS NULL OR j.fit_score >= ?)"
        params = (args.min_score,)
    rows = conn.execute(query + " ORDER BY j.fit_score IS NULL DESC, j.fit_score DESC, j.discovered_at DESC",
                        params).fetchall()
    conn.close()
    if not rows:
        print("Inbox is empty: run `sherpa discover`, or add a job with `sherpa add-job`.")
        return
    print(f"{'ID':<5} {'Score':<6} {'Company':<20} {'Title':<45} Where")
    for r in rows:
        score = r["fit_score"] if r["fit_score"] is not None else "-"
        where = r["location"] or ""
        if r["remote_type"] == "restricted_remote":
            where += " [!restricted remote]"
        print(f"{r['id']:<5} {str(score):<6} {r['company'][:20]:<20} {r['title'][:45]:<45} {where}")


def cmd_show(args):
    conn = db.connect()
    row = _job_or_die(conn, args.job_id)
    conn.close()
    print(f"#{row['id']} {row['title']} — {row['company_name']}")
    print(f"Location: {row['location'] or '-'}   ({row['remote_type'] or 'unclassified'})")
    print(f"URL: {row['url'] or '-'}")
    print(f"Status: {row['status']}   Fit score: {row['fit_score'] if row['fit_score'] is not None else '-'}")
    print(f"Posted: {row['posted_at'] or '-'}   Discovered: {row['discovered_at']}   Source: {row['source']}")
    if row["fit_json"]:
        print(f"\nFit detail:\n{row['fit_json']}")
    desc = row["description"] or ""
    if args.full or len(desc) <= 2000:
        print(f"\nDescription:\n{desc}")
    else:
        print(f"\nDescription (first 2000 of {len(desc)} chars; --full for all):\n{desc[:2000]}")


def cmd_set_jd(args):
    conn = db.connect()
    job = _job_or_die(conn, args.job_id)
    text = _read_text_arg(args.file)
    if len(text) < 200:
        _die(f"That's only {len(text)} characters, which looks like a partial paste. Nothing saved.")
    fit = json.loads(job["fit_json"]) if job["fit_json"] else {}
    fit.pop("needs_full_jd", None)
    fit["jd_source"] = args.source or "pasted by hand"
    if job["fit_score"] is not None:
        fit["rescore_needed"] = True
    conn.execute("UPDATE jobs SET description = ?, fit_json = ? WHERE id = ?",
                 (text, json.dumps(fit), args.job_id))
    conn.commit()
    conn.close()
    print(f"Saved {len(text)} chars to #{args.job_id} ({job['company_name']} — {job['title']}).")


def cmd_enrich_jd(args):
    """Find the full JD for excerpt/link-only jobs on the company's own board.
    Unmatched jobs are listed, never guessed at."""
    prof = profile.load()
    conn = db.connect()
    sql = ("SELECT j.*, c.name AS company_name FROM jobs j JOIN companies c ON c.id = j.company_id "
           "WHERE j.status = 'new' AND j.fit_json LIKE '%needs_full_jd%'")
    params = []
    if args.job_id:
        sql += " AND j.id = ?"
        params.append(args.job_id)
    elif args.source:
        sql += " AND j.source = ?"
        params.append(args.source)
    rows = conn.execute(sql + " ORDER BY j.id", params).fetchall()
    todo = [r for r in rows if prof.title_matches(r["title"])
            and (not r["location"] or prof.location_in_range(r["location"]))]
    skipped = len(rows) - len(todo)
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} job(s) need a full JD" + (f" ({skipped} skipped by title/location)" if skipped else ""))

    matched, unresolved = 0, []
    for row in todo:
        result = enrich.find_posting(row["company_name"], row["title"], row["location"])
        label = f"#{row['id']} {row['company_name']} — {row['title']}"
        if result["status"] == "matched":
            posting = result["posting"]
            fit = json.loads(row["fit_json"]) if row["fit_json"] else {}
            fit.pop("needs_full_jd", None)
            fit.pop("angle", None)
            fit.update(jd_source=f"{result['board']} ({result['confidence']})",
                       jd_url=posting.get("url", ""), rescore_needed=True)
            conn.execute("UPDATE jobs SET description = ?, fit_json = ? WHERE id = ?",
                         (posting.get("description", ""), json.dumps(fit), row["id"]))
            matched += 1
            print(f"  OK   {label}\n         <- {result['board']}, {result['confidence']}, {posting.get('url', '')}")
        else:
            unresolved.append(row)
            print(f"  --   {label}\n         {result['reason']}")
            for near in result["near_misses"]:
                print(f"         near-miss: {near}")
    conn.commit()
    conn.close()
    print(f"\n{matched} enriched, {len(unresolved)} unresolved.")
    if unresolved:
        print("Unresolved jobs keep needs_full_jd and are NOT scored. Paste a JD with `sherpa set-jd <id>`:")
        for row in unresolved:
            print(f"  #{row['id']}  {row['url']}")


def cmd_check_companies(args):
    results = audit.audit()
    bad = [r for r in results if r["status"] != "ok"]
    for r in sorted(results, key=lambda r: (r["status"] == "ok", r["name"].lower())):
        if r["status"] == "ok" and not args.all:
            continue
        print(f"[{r['status']:6}] {r['name']:28} {r['ats']}:{r['token']}"
              + (f"  {r['count']} postings" if r["count"] else "") + (f"  {r['detail']}" if r["detail"] else ""))
        for s in r["suggestions"]:
            print(f"           -> try instead: {s}")
    print(f"\n{len(results) - len(bad)} ok, {len(bad)} need attention (of {len(results)} with a token).")
    if results and len(bad) == len(results) and all("URLError" in r["detail"] for r in bad):
        sys.exit("Every board failed to connect, which means the network (a proxy or firewall), not "
                 "your list. Check your connection and run this again.")
    if bad:
        print("Nothing was changed. Edit companies.yaml by hand: a wrong 'fix' hides a company too.")


def cmd_shortlist(args):
    conn = db.connect()
    _job_or_die(conn, args.job_id)
    conn.execute("UPDATE jobs SET status = 'shortlisted' WHERE id = ?", (args.job_id,))
    conn.commit()
    print(f"Job #{args.job_id} shortlisted.")


def cmd_dismiss(args):
    conn = db.connect()
    _job_or_die(conn, args.job_id)
    conn.execute("UPDATE jobs SET status = 'dismissed', dismiss_reason = ? WHERE id = ?", (args.reason, args.job_id))
    conn.commit()
    print(f"Job #{args.job_id} dismissed" + (f" ({args.reason})." if args.reason else "."))


def cmd_score(args):
    if not 1 <= args.score <= 10:
        _die("Score must be 1-10.")
    try:
        fit = json.loads(args.json) if args.json else {}
    except ValueError as e:
        _die(f"--json is not valid JSON: {e}")
    prof = profile.load()
    cap = int(prof.search["hard_gate_cap"])
    if fit.get("hard_blockers") and args.score > cap:
        _die(f"This job has hard_blockers {fit['hard_blockers']}, so its score is capped at {cap} "
             "(see PRINCIPLES.md). Lower the score or remove the blocker if it's wrong.")
    conn = db.connect()
    job = _job_or_die(conn, args.job_id)
    old = json.loads(job["fit_json"]) if job["fit_json"] else {}
    if old.get("needs_full_jd"):
        _die(f"Job #{args.job_id} has no full JD yet. Run `sherpa enrich-jd --job-id {args.job_id}` "
             "or paste one with `sherpa set-jd`. Never score a job blind.")
    for keep in ("jd_source", "jd_url"):
        if keep in old and keep not in fit:
            fit[keep] = old[keep]
    conn.execute("UPDATE jobs SET fit_score = ?, fit_json = ? WHERE id = ?",
                 (args.score, json.dumps(fit), args.job_id))
    conn.commit()
    print(f"Job #{args.job_id} scored {args.score}/10.")


def cmd_shortlist_export(args):
    path, n = shortlist.export_shortlist(min_score=args.min_score)
    print(f"Wrote {paths.show(path)} ({n} jobs)")


# ── documents ──────────────────────────────────────────────────────────────

def cmd_bullets(args):
    bullets = list(claims.load_bullets().values())
    if not bullets:
        _die("No bullets yet. Run the onboard playbook to build bullets.yaml from your resume.")
    query = {t.strip().lower() for t in (args.tags or "").split(",") if t.strip()}
    rank = {"strong": 2, "moderate": 1, "supporting": 0}
    scored = []
    for b in bullets:
        tags = {t.lower() for t in yaml_lite.split_list(b.get("tags", ""))}
        words = set(re.findall(r"[a-z0-9+#.-]+", b.get("text", "").lower()))
        hits = len(query & tags) * 2 + len(query & words)
        scored.append((hits, rank.get(b.get("evidence_strength", ""), 0), b))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for hits, _, b in scored[:args.top]:
        if query and not hits:
            break
        print(f"[{b['id']}] {b.get('org', '')} — {b.get('role_title', '')}  ({b.get('period', '')})")
        print(f"    {b['text']}")
        print(f"    tags: {b.get('tags', '')}   strength: {b.get('evidence_strength', '')}"
              + (f"   notes: {b['notes']}" if b.get("notes") else ""))
        print()


def _build_resume(payload: dict, prof) -> tuple[dict, claims.Resolved]:
    bullets = claims.load_bullets()
    result = claims.Resolved()
    prof_raw = paths.profile_path().read_text(encoding="utf-8") if paths.profile_path().exists() else ""
    experience = []
    for org in payload.get("experience", []):
        roles = []
        for role in org.get("roles", []):
            where = f"{org.get('org')} / {role.get('title')}"
            roles.append({"title": role.get("title", ""), "dates": role.get("dates", ""),
                          "bullets": [claims.resolve_bullet(b, bullets, result, where)
                                      for b in role.get("bullets", role.get("bullet_ids", []))]})
        experience.append({"org": org.get("org", ""), "roles": roles})
    projects = []
    for p in payload.get("projects", []):
        ref = p.get("bullet") or p.get("bullet_id")
        item = {"id": ref, "text": p["text"]} if ref and p.get("text") else ref or p.get("text", "")
        projects.append({"title": p.get("title", ""),
                         "text": claims.resolve_bullet(item, bullets, result, f"project {p.get('title')}")})
    summary = payload.get("summary", "")
    claims.check_free_text(summary, bullets, prof_raw, result, "summary")
    data = {"contact": prof.contact, "paper": prof.documents.get("paper", "a4"), "summary": summary,
            "experience": experience, "projects": projects, "skills": payload.get("skills", []),
            "education": payload.get("education", []),
            "certifications": payload.get("certifications", []), "activities": payload.get("activities", [])}
    return data, result


def _build_letter(payload: dict, prof, job_description: str = "") -> tuple[dict, claims.Resolved]:
    bullets = claims.load_bullets()
    result = claims.Resolved()
    prof_raw = paths.profile_path().read_text(encoding="utf-8") if paths.profile_path().exists() else ""
    for i, para in enumerate(payload.get("paragraphs", []), 1):
        claims.check_free_text(para, bullets, prof_raw, result, f"paragraph {i}", job_description)
    today = date.today()
    data = {"contact": prof.contact, "paper": prof.documents.get("paper", "a4"),
            "date": payload.get("date") or f"{today:%B} {today.day}, {today.year}",
            "greeting": payload.get("greeting", "Dear Hiring Team,"),
            "paragraphs": payload.get("paragraphs", []),
            "closing": payload.get("closing", "Sincerely,")}
    if payload.get("sign_off"):
        data["sign_off"] = payload["sign_off"]
    return data, result


def _report_and_gate(result: claims.Resolved, force: bool):
    for w in result.warnings:
        print(f"  warning: {w}")
    for e in result.errors:
        print(f"  ERROR: {e}")
    if result.errors and not force:
        _die("Not rendered: fix the errors above (every claim must trace to bullets.yaml). "
             "--force exists for false alarms only; never use it to get an invented claim through.")


def _render_and_report(kind, data, out_dir, stem, prof):
    try:
        out = render.render(kind, data, out_dir, stem)
    except render.TypstMissing as e:
        _die(str(e))
    print(f"Rendered {paths.show(out['pdf'])} ({out['pages']} page{'s' if out['pages'] != 1 else ''})")
    if kind == "resume" and prof.documents.get("one_page_resume") and out["pages"] > 1:
        print("  ! Over one page. Cut the least relevant bullets and render again "
              "(don't shrink fonts or margins: every resume should keep the same look).")
    if kind == "cover_letter" and out["pages"] > 1:
        print("  ! Over one page. Tighten the paragraphs.")
    return out


def _payload(args) -> dict:
    try:
        return json.loads(Path(args.data).read_text(encoding="utf-8")) if args.data else json.loads(args.data_str)
    except (TypeError, ValueError) as e:
        _die(f"Couldn't read the JSON payload: {e}")


def cmd_check(args):
    """Check a resume or letter payload against bullets.yaml without rendering."""
    prof = profile.load()
    payload = _payload(args)
    if "paragraphs" in payload:
        _, result = _build_letter(payload, prof)
    else:
        _, result = _build_resume(payload, prof)
    _report_and_gate(result, force=False)
    print(f"OK: every claim traces to bullets.yaml ({len(result.used_ids)} bullets used).")


def cmd_tailor_resume(args):
    prof = profile.load()
    conn = db.connect()
    job = _job_or_die(conn, args.job_id)
    payload = _payload(args)
    data, result = _build_resume(payload, prof)
    _report_and_gate(result, args.force)
    out = _render_and_report("resume", data, _draft_dir(job), prof.file_stem("Resume"), prof)
    conn.execute("INSERT INTO documents (job_id, kind, bullets_used, angle, path_md, path_pdf) "
                 "VALUES (?, 'resume', ?, ?, ?, ?)",
                 (args.job_id, json.dumps(result.used_ids), payload.get("angle", ""),
                  paths.show(out["md"]), paths.show(out["pdf"])))
    conn.commit()


def cmd_tailor_cover_letter(args):
    prof = profile.load()
    conn = db.connect()
    job = _job_or_die(conn, args.job_id)
    payload = _payload(args)
    data, result = _build_letter(payload, prof, job["description"] or "")
    _report_and_gate(result, args.force)
    out = _render_and_report("cover_letter", data, _draft_dir(job), prof.file_stem("Cover Letter"), prof)
    conn.execute("INSERT INTO documents (job_id, kind, angle, path_md, path_pdf) VALUES (?, 'cover_letter', ?, ?, ?)",
                 (args.job_id, payload.get("angle", ""), paths.show(out["md"]), paths.show(out["pdf"])))
    conn.commit()


def cmd_master_resume(args):
    prof = profile.load()
    spec_path = paths.home() / "master-resume.json"
    if not spec_path.exists():
        _die(f"No {paths.show(spec_path)} yet. The onboard playbook writes it.")
    data, result = _build_resume(json.loads(spec_path.read_text(encoding="utf-8")), prof)
    _report_and_gate(result, args.force)
    _render_and_report("resume", data, paths.home() / "master", prof.file_stem("Resume"), prof)


def cmd_master_cover_letter(args):
    prof = profile.load()
    spec_path = paths.home() / "master-cover-letter.json"
    if not spec_path.exists():
        _die(f"No {paths.show(spec_path)} yet. The onboard playbook writes it.")
    data, result = _build_letter(json.loads(spec_path.read_text(encoding="utf-8")), prof)
    _report_and_gate(result, args.force)
    _render_and_report("cover_letter", data, paths.home() / "master", prof.file_stem("Cover Letter"), prof)


def cmd_backup(args):
    dest = backup.backup_dir()
    if dest is None:
        _die("SHERPA_BACKUP_DIR is not set. Add it to .env (see .env.example).")
    if args.list:
        found = backup.list_backups(dest)
        for b in found:
            print(f"{b.name}  ({b.stat().st_size / 1_048_576:.1f} MB)")
        if not found:
            print(f"No backups yet in {dest}")
        return
    print(f"Backup saved: {backup.make_backup(dest)}")


# ── parser ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sherpa", description="Job Sherpa: an honest job-search assistant.")
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name, func, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(func=func)
        return sp

    sp = add("init", cmd_init, "Create your private folder (me/) and database")
    sp.add_argument("--starter", default="tech-companies", help="starter company list in starter-lists/")
    add("doctor", cmd_doctor, "Check your setup and say what's missing")
    sp = add("resume-text", cmd_resume_text, "Extract your resume's text with line numbers (onboarding)")
    sp.add_argument("file", help=".pdf, .docx, .txt or .md")

    sp = add("apply", cmd_apply, "Log an application you submitted")
    sp.add_argument("--job-id", type=int, help="a job already in the database")
    sp.add_argument("--company")
    sp.add_argument("--title")
    sp.add_argument("--location")
    sp.add_argument("--url")
    sp.add_argument("--channel", help="e.g. portal, referral, email")
    sp.add_argument("--referrer")
    sp.add_argument("--date", help="YYYY-MM-DD, default today")
    sp = add("log", cmd_log, "Record what happened next on an application")
    sp.add_argument("application_id", type=int)
    sp.add_argument("--event", required=True, choices=db.EVENT_TYPES[1:])
    sp.add_argument("--date", help="YYYY-MM-DD, default today")
    sp.add_argument("--notes")
    add("followups", cmd_followups, "Applications that have gone quiet")
    sp = add("applications", cmd_applications, "Your applications with their ids (open ones by default)")
    sp.add_argument("--all", action="store_true", help="include closed ones (rejected, offer, ...)")
    sp.add_argument("--status", help="only this status, e.g. in_progress or rejected")
    sp.add_argument("--company", help="only companies whose name contains this")
    sp = add("stats", cmd_stats, "Your application funnel")
    sp.add_argument("--by", choices=["company"])

    sp = add("discover", cmd_discover, "Fetch new postings from your companies' boards (+ Adzuna)")
    sp.add_argument("--source", choices=[*ATS_ADAPTERS, "adzuna"], help="only one source")
    sp.add_argument("--verbose", action="store_true", help="list every company, even with no matches")
    sp = add("add-job", cmd_add_job, "Add a job you found yourself, with its JD (--file)")
    sp.add_argument("--company", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--location")
    sp.add_argument("--url")
    sp.add_argument("--posted", help="YYYY-MM-DD the job was posted, if known")
    sp.add_argument("--file", help="file holding the JD, or - for stdin (add one later with set-jd)")
    sp = add("inbox", cmd_inbox, "New jobs, unscored first")
    sp.add_argument("--min-score", type=int)
    sp = add("show", cmd_show, "One job: JD and fit detail")
    sp.add_argument("job_id", type=int)
    sp.add_argument("--full", action="store_true", help="the whole JD, not the first 2000 chars")
    sp = add("set-jd", cmd_set_jd, "Store a pasted JD on a job (stdin or --file)")
    sp.add_argument("job_id", type=int)
    sp.add_argument("--file")
    sp.add_argument("--source", help="where it came from")
    sp = add("enrich-jd", cmd_enrich_jd, "Find full JDs for excerpt-only jobs on the company's own board")
    sp.add_argument("--source")
    sp.add_argument("--job-id", type=int)
    sp.add_argument("--limit", type=int)
    sp = add("check-companies", cmd_check_companies, "Test every companies.yaml entry against its live board")
    sp.add_argument("--all", action="store_true", help="also list entries that are fine")
    sp = add("score", cmd_score, "Store a fit judgment (used by the score-fit playbook)")
    sp.add_argument("job_id", type=int)
    sp.add_argument("--score", type=int, required=True)
    sp.add_argument("--json", help="the fit judgment as a JSON string")
    sp = add("shortlist", cmd_shortlist, "Pin a job to the shortlist")
    sp.add_argument("job_id", type=int)
    sp = add("dismiss", cmd_dismiss, "Dismiss a job")
    sp.add_argument("job_id", type=int)
    sp.add_argument("--reason")
    sp = add("shortlist-export", cmd_shortlist_export, "Write a timestamped shortlist file from current scores")
    sp.add_argument("--min-score", type=int)

    sp = add("bullets", cmd_bullets, "Find bullets in bullets.yaml by tag or keyword")
    sp.add_argument("--tags", help="comma-separated, e.g. kafka,performance")
    sp.add_argument("--top", type=int, default=16)
    for name, func, help_ in (("check", cmd_check, "Check a resume/letter payload traces to bullets.yaml"),
                              ("tailor-resume", cmd_tailor_resume, "Render a tailored resume for a job"),
                              ("tailor-cover-letter", cmd_tailor_cover_letter, "Render a tailored cover letter")):
        sp = add(name, func, help_)
        if name != "check":
            sp.add_argument("job_id", type=int)
            sp.add_argument("--force", action="store_true", help="render despite claim errors (false alarms only)")
        sp.add_argument("--data", help="JSON file")
        sp.add_argument("--data-str", help="JSON string, instead of --data")
    for name, func, help_ in (("master-resume", cmd_master_resume, "Render your untailored master resume"),
                              ("master-cover-letter", cmd_master_cover_letter, "Render your untailored master cover letter")):
        sp = add(name, func, help_)
        sp.add_argument("--force", action="store_true")
    sp = add("backup", cmd_backup, "Back up the database to SHERPA_BACKUP_DIR")
    sp.add_argument("--list", action="store_true")
    return p


def main(argv=None):
    # Agents read output through a pipe; on Windows that defaults to a legacy
    # code page that can't print "—" or "⚠". Use UTF-8 everywhere.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if not paths.TEMPLATES.is_dir():
        _die("Job Sherpa runs from a clone of its repository (templates, playbooks and starter\n"
             "lists live there). Clone https://github.com/KushBhatnagar/job-sherpa and run\n"
             "bin/sherpa from it, or `pip install -e .` inside the clone.")
    if args.func not in (cmd_backup, cmd_init):
        backup.auto_backup()
    try:
        args.func(args)
    finally:
        db.close_all()
