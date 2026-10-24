"""Export current scores to a timestamped markdown shortlist under <home>/drafts/.

A new file every run, so nothing is overwritten when scoring runs again later.
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path

from . import db, paths, profile


def _clean(desc: str, limit: int = 1200) -> str:
    if not desc:
        return "(no description text available)"
    text = html.unescape(re.sub(r"<[^>]+>", " ", desc))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def export_shortlist(min_score: int | None = None) -> tuple[Path, int]:
    prof = profile.load()
    min_score = prof.search["shortlist_min_score"] if min_score is None else min_score
    max_age = int(prof.search["stale_after_days"])
    conn = db.connect()
    rows = conn.execute(
        f"""
        SELECT j.id, c.name AS company, j.title, j.location, j.remote_type, j.fit_score,
               j.fit_json, j.url, j.posted_at, j.source, j.description, j.status
        FROM jobs j JOIN companies c ON c.id = j.company_id
        -- 'shortlisted' = pinned with `sherpa shortlist`: always listed, whatever
        -- the score (e.g. a 6 you're pursuing through a referral).
        WHERE ((j.status = 'new' AND j.fit_score >= ?) OR j.status = 'shortlisted')
          AND {db.JOB_AGE_SQL} >= date('now', ?)
        ORDER BY j.fit_score DESC, j.id
        """,
        (min_score, f"-{max_age} days"),
    ).fetchall()
    conn.close()

    now = datetime.now()
    out_path = paths.drafts_dir() / f"application-shortlist-{now:%Y-%m-%d_%H%M%S}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Application shortlist: score {min_score}-10",
        "",
        f"Generated {now:%Y-%m-%d %H:%M}. {len(rows)} jobs, highest fit first; postings older "
        f"than {max_age} days are left out.",
        "",
        "Workflow: tailor (tailor-resume / draft-cover-letter playbooks) -> review -> apply "
        "yourself on the real site -> `sherpa apply --job-id N` to log it. Tick `- [x]` as you go.",
        "",
        "---",
        "",
    ]
    for r in rows:
        fit = {}
        try:
            fit = json.loads(r["fit_json"] or "{}")
        except ValueError:
            pass
        # Enriched jobs arrived via an aggregator, so j.url is its redirect;
        # jd_url is the company's own posting, the one to apply on.
        apply_url = fit.get("jd_url") or r["url"]
        flag = " ⚠️ restricted remote: check eligibility" if r["remote_type"] == "restricted_remote" else ""
        if r["status"] == "shortlisted":
            flag += " 📌 pinned"
        lines += [
            f"## [{r['fit_score'] if r['fit_score'] is not None else '-'}/10] {r['title']} — {r['company']}{flag}",
            "",
            "- [ ] Applied",
            f"- **job_id:** {r['id']}",
            f"- **Location:** {r['location']}  ({r['remote_type']})",
            f"- **Source:** {r['source']}",
            f"- **Posted:** {r['posted_at'] or '-'}",
            f"- **URL:** {apply_url}",
        ]
        if fit.get("angle"):
            lines.append(f"- **Angle:** {fit['angle']}")
        if fit.get("hard_blockers"):
            lines.append(f"- **Hard blockers:** {', '.join(fit['hard_blockers'])}")
        if fit.get("risks"):
            lines.append(f"- **Risks:** {', '.join(fit['risks'])}")
        lines += ["", "**JD excerpt:**", "", f"> {_clean(r['description'])}", "", "---", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, len(rows)
