"""Ashby public job-board API adapter.

Needs a browser-like User-Agent (see _http.py) — Ashby returns 403 Forbidden
to Python's default urllib User-Agent even though the endpoint itself needs
no auth.
https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
"""
import json

from ._http import get_json

SOURCE = "ashby"


def fetch(token: str) -> list[dict]:
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")

    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "source": SOURCE,
            "source_job_id": str(j.get("id", "")),
            "title": j.get("title", ""),
            "location": j.get("location", "") or j.get("addressLocality", ""),
            "url": j.get("jobUrl", "") or j.get("applyUrl", ""),
            "description": j.get("descriptionPlain", "") or j.get("description", ""),
            "posted_at": (j.get("publishedAt") or "")[:10] or None,
            "raw_json": json.dumps(j),
        })
    return jobs
