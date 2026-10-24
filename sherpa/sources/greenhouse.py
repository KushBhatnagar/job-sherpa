"""Greenhouse public job-board API adapter.

Public, documented, intended-for-syndication endpoint — no auth, no scraping:
https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""
import html
import json
import re

from ._http import get_json

SOURCE = "greenhouse"


def _strip_html(content: str) -> str:
    # Some boards (e.g. MongoDB) return content that's HTML-entity-escaped
    # HTML — literally the text "&lt;p&gt;", not a real "<p>" tag — so the
    # tag-stripping regex below silently does nothing until entities are
    # unescaped first. Unescape, strip tags, then unescape again to catch
    # entities (e.g. "&#39;" for an apostrophe) that were inside the
    # original real HTML, not just the double-escaped wrapper.
    unescaped = html.unescape(content or "")
    stripped = re.sub(r"<[^>]+>", " ", unescaped)
    return html.unescape(stripped)


def fetch(token: str) -> list[dict]:
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")

    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "source": SOURCE,
            "source_job_id": str(j.get("id", "")),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "description": _strip_html(j.get("content", "")),
            "posted_at": (j.get("updated_at") or "")[:10] or None,
            "raw_json": json.dumps(j),
        })
    return jobs
