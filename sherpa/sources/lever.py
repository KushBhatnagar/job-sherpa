"""Lever public job-board API adapter.

Public, documented, intended-for-syndication endpoint — no auth, no scraping:
https://api.lever.co/v0/postings/{token}?mode=json
"""
import json
from datetime import datetime, timezone

from ._http import get_json

SOURCE = "lever"


def fetch(token: str) -> list[dict]:
    data = get_json(f"https://api.lever.co/v0/postings/{token}?mode=json")

    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        posted_at = None
        if j.get("createdAt"):
            posted_at = datetime.fromtimestamp(
                j["createdAt"] / 1000, tz=timezone.utc
            ).date().isoformat()
        jobs.append({
            "source": SOURCE,
            "source_job_id": str(j.get("id", "")),
            "title": j.get("text", ""),
            "location": cats.get("location", "") or "",
            "url": j.get("hostedUrl", ""),
            "description": j.get("descriptionPlain", "") or j.get("description", ""),
            "posted_at": posted_at,
            "raw_json": json.dumps(j),
        })
    return jobs
