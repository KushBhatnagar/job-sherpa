"""SmartRecruiters public postings API adapter.

The list endpoint doesn't return full descriptions (SmartRecruiters requires
a second per-posting call for that) — description is left blank here rather
than adding an N+1 call pattern nothing has asked for yet.
https://api.smartrecruiters.com/v1/companies/{company}/postings
"""
import json

from ._http import get_json

SOURCE = "smartrecruiters"


def fetch(token: str) -> list[dict]:
    data = get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings")

    jobs = []
    for j in data.get("content", []):
        loc = j.get("location") or {}
        location = ", ".join(filter(None, [loc.get("city"), loc.get("country")]))
        jobs.append({
            "source": SOURCE,
            "source_job_id": str(j.get("id", "")),
            "title": j.get("name", ""),
            "location": location,
            "url": j.get("ref", ""),
            "description": "",
            "posted_at": (j.get("releasedDate") or "")[:10] or None,
            "raw_json": json.dumps(j),
        })
    return jobs
