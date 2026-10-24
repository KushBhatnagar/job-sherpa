"""Traceability: every resume line must come from a real bullet in bullets.yaml.

The tailoring playbook may align vocabulary ("A/B testing" -> "experimentation")
but may never change a number, invent scope or add an outcome. This module
checks that mechanically before anything is rendered:

  - every bullet referenced by id must exist in bullets.yaml;
  - a reworded bullet ({"id": ..., "text": ...}) may not contain any number
    that isn't in the original bullet;
  - a reworded bullet that drifts far from its original is flagged for a human
    to read (a warning, not an error: short rewrites legitimately differ);
  - a bullet given as free text with no id is an error: it can't be traced.

Numbers in the summary and cover letter must appear somewhere in bullets.yaml or
profile.toml (a cover letter may also quote numbers from the job description).
"""
import difflib
import re

from . import paths, yaml_lite

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
DRIFT_RATIO = 0.45


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER_RE.findall(text or "")}


def load_bullets() -> dict[str, dict]:
    path = paths.bullets_path()
    if not path.exists():
        return {}
    return {b["id"]: b for b in yaml_lite.load_flat_list(path) if b.get("id")}


class Resolved:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.used_ids: list[str] = []


def resolve_bullet(item, bullets: dict, result: Resolved, where: str) -> str:
    """item is "b-001" (use verbatim) or {"id": "b-001", "text": "reworded"}."""
    if isinstance(item, str):
        if item in bullets:
            result.used_ids.append(item)
            return bullets[item]["text"]
        result.errors.append(f"{where}: {item[:60]!r} is not a bullet id. Every resume line "
                             "needs an id from bullets.yaml (use {\"id\", \"text\"} to reword).")
        return item
    bid, text = item.get("id", ""), item.get("text", "")
    if bid not in bullets:
        result.errors.append(f"{where}: unknown bullet id {bid!r}")
        return text
    result.used_ids.append(bid)
    original = bullets[bid]["text"]
    if not text:
        return original
    new_numbers = numbers_in(text) - numbers_in(original)
    if new_numbers:
        result.errors.append(f"{where} ({bid}): numbers not in the original bullet: "
                             f"{', '.join(sorted(new_numbers))}. Never change or add a number.")
    if difflib.SequenceMatcher(None, original.lower(), text.lower()).ratio() < DRIFT_RATIO:
        result.warnings.append(f"{where} ({bid}): reworded text is far from the original. "
                               "Check it claims nothing new.")
    return text


def check_free_text(text: str, bullets: dict, profile_raw: str, result: Resolved, where: str,
                    job_description: str = ""):
    """Summary / cover-letter paragraphs: numbers must exist in the corpus (or, for
    a cover letter quoting the posting, in the job description)."""
    corpus_numbers = set().union(*(numbers_in(b.get("text", "")) | numbers_in(b.get("metric", ""))
                                   for b in bullets.values())) if bullets else set()
    corpus_numbers |= numbers_in(profile_raw) | numbers_in(job_description)
    unknown = numbers_in(text) - corpus_numbers
    if unknown:
        result.errors.append(f"{where}: numbers not found in bullets.yaml or profile.toml: "
                             f"{', '.join(sorted(unknown))}")
