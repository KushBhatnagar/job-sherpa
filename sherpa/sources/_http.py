"""Shared HTTP fetch for every source adapter.

Ashby returns 403 to Python's default urllib User-Agent (`Python-urllib/3.x`)
on requests that work from curl: an anti-bot check, not an auth requirement.
A normal-looking User-Agent fixes it, so every adapter uses one.
"""
import json
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; job-sherpa/0.1; personal job search tool)"


def get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())
