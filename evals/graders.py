"""Checks for the Job Sherpa eval. Each returns a list of Check results.

Deterministic checks only: they read what the agent left behind (the database,
the rendered Markdown next to each PDF, bullets.yaml, profile.toml) and compare
it with the expectations in cases/cases.json. The optional LLM judge lives in
judge.py and is reported separately, because a model grading a model is a
weaker signal than a rule.
"""
import difflib
import json
import re
import sqlite3
import tomllib
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from sherpa import yaml_lite
from sherpa.claims import numbers_in


@dataclass
class Check:
    case: str
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self):
        return asdict(self)


# ── helpers ────────────────────────────────────────────────────────────────

def _db(home: Path):
    """Read everything needed, then close: an open handle blocks temp-folder
    cleanup on Windows. Callers use `with closing(_db(home)) as conn:`."""
    conn = sqlite3.connect(home / "sherpa.db")
    conn.row_factory = sqlite3.Row
    return conn


def _bullets(home: Path) -> dict[str, dict]:
    path = home / "bullets.yaml"
    if not path.exists():
        return {}
    return {b["id"]: b for b in yaml_lite.load_flat_list(path) if b.get("id")}


def _corpus_numbers(home: Path) -> set[str]:
    nums = set()
    for b in _bullets(home).values():
        nums |= numbers_in(b.get("text", "")) | numbers_in(b.get("metric", ""))
    prof = home / "profile.toml"
    if prof.exists():
        nums |= numbers_in(prof.read_text(encoding="utf-8"))
    return nums


def resume_lines(md: str) -> dict[str, list[str]]:
    """Split a rendered resume .md into bullets, projects, summary and skills."""
    out = {"bullets": [], "projects": [], "summary": "", "skills": []}
    section = "head"
    head_lines = []
    for line in md.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section == "head":
            head_lines.append(line)
        elif section == "experience" and line.startswith("- "):
            out["bullets"].append(line[2:].strip())
        elif section == "projects" and line.startswith("- "):
            out["projects"].append(re.sub(r"^\*\*.*?:\*\*\s*", "", line[2:]).strip())
        elif section == "skills" and line.startswith("- "):
            out["skills"].append(line[2:].strip())
    # header: name, contact line, blank, summary
    text = [l for l in head_lines if l.strip() and not l.startswith("# ")]
    out["summary"] = text[-1] if len(text) >= 2 else ""
    return out


def best_match(text: str, bullets: dict) -> tuple[str, float]:
    best_id, best = "", 0.0
    for bid, b in bullets.items():
        r = difflib.SequenceMatcher(None, text.lower(), b.get("text", "").lower()).ratio()
        if r > best:
            best_id, best = bid, r
    return best_id, best


def _term_re(term: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE)


SHORTFALL_RE = re.compile(
    r"\b\d+\+?\s*years?\b[^.]{0,60}?\b(against|versus|vs\.?|compared|short of|shy of|less than|"
    r"instead of|rather than|fall short|below)\b[^.]{0,40}?\b\d+\+?\s*years?"
    r"|\b(?:while|although|though)\b[^.]{0,40}?\b(?:you|the role|this role|the posting)\b[^.]{0,30}?"
    r"\b(?:ask|asks|require|requires|look|looks|want|wants)\b[^.]{0,20}?\b\d+\+?\s*years?",
    re.IGNORECASE)


# ── scoring ────────────────────────────────────────────────────────────────

def grade_scoring(case: dict, home: Path, job_ids: dict[str, int]) -> list[Check]:
    checks = []
    with closing(_db(home)) as conn:
        rows = {j["file"]: conn.execute("SELECT fit_score, fit_json, status FROM jobs WHERE id = ?",
                                        (job_ids[j["file"]],)).fetchone() for j in case["jobs"]}
    for job in case["jobs"]:
        name = job["file"].removesuffix(".md")
        row = rows[job["file"]]
        score = row["fit_score"]
        try:
            fit = json.loads(row["fit_json"] or "{}")
        except ValueError:
            fit = {}
        exp = job["expect"]
        if score is None:
            checks.append(Check(case["id"], f"{name}: scored", False, f"not scored (status {row['status']})"))
            continue
        ok, why = True, []
        if "min_score" in exp and score < exp["min_score"]:
            ok, why = False, why + [f"score {score} < expected min {exp['min_score']}"]
        if "max_score" in exp and score > exp["max_score"]:
            ok, why = False, why + [f"score {score} > expected max {exp['max_score']}"]
        checks.append(Check(case["id"], f"{name}: score in range", ok,
                            "; ".join(why) or f"score {score}"))
        blockers = fit.get("hard_blockers") or []
        if exp.get("hard_blockers") == "some":
            checks.append(Check(case["id"], f"{name}: hard blocker named", bool(blockers),
                                json.dumps(blockers)[:160] or "none listed"))
        elif exp.get("hard_blockers") == "none":
            checks.append(Check(case["id"], f"{name}: no false hard blocker", not blockers,
                                json.dumps(blockers)[:160] if blockers else "none"))
        if exp.get("risks_mention"):
            risks = json.dumps(fit.get("risks", "")).lower()
            hit = any(w in risks for w in exp["risks_mention"])
            checks.append(Check(case["id"], f"{name}: location flagged in risks", hit,
                                risks[:160] or "no risks listed"))
    return checks


# ── tailoring ──────────────────────────────────────────────────────────────

def _latest_doc(conn, job_id: int, kind: str):
    return conn.execute("SELECT * FROM documents WHERE job_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
                        (job_id, kind)).fetchone()


def _pages(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf.read_bytes())) if pdf.exists() else 0


def _doc_path(home: Path, stored: str) -> Path:
    """documents.path_* are stored relative to the repo or absolute; find the file."""
    p = Path(stored)
    if p.is_absolute() and p.exists():
        return p
    for cand in home.rglob(p.name):
        return cand
    return p


def grade_tailoring(case: dict, home: Path, job_id: int, jd_text: str) -> list[Check]:
    cid = case["id"]
    checks = []
    bullets = _bullets(home)
    corpus = _corpus_numbers(home)
    with closing(_db(home)) as conn:
        doc = _latest_doc(conn, job_id, "resume")
        letter = _latest_doc(conn, job_id, "cover_letter")
    if not doc:
        return [Check(cid, "resume rendered", False, "no resume recorded for this job")]
    md_path, pdf_path = _doc_path(home, doc["path_md"]), _doc_path(home, doc["path_pdf"])
    md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    pages = _pages(pdf_path)
    checks.append(Check(cid, "resume rendered on one page", pages == 1, f"{pages} page(s)"))

    parts = resume_lines(md)
    untraced, new_nums = [], []
    for line in parts["bullets"] + parts["projects"]:
        bid, ratio = best_match(line, bullets)
        if ratio < 0.5:
            untraced.append(f"{line[:70]}… (best {bid} {ratio:.2f})")
            continue
        extra = numbers_in(line) - numbers_in(bullets[bid]["text"])
        if extra:
            new_nums.append(f"{bid}: {sorted(extra)}")
    checks.append(Check(cid, "every resume bullet traces to bullets.yaml", not untraced,
                        "; ".join(untraced)[:300] or f"{len(parts['bullets'])} bullets traced"))
    checks.append(Check(cid, "no number added to any bullet", not new_nums, "; ".join(new_nums)[:300] or "ok"))
    extra_summary = numbers_in(parts["summary"]) - corpus
    checks.append(Check(cid, "summary numbers exist in the corpus", not extra_summary,
                        str(sorted(extra_summary)) if extra_summary else "ok"))

    hits = [t for t in case.get("forbidden_in_resume", []) if _term_re(t).search(md)]
    checks.append(Check(cid, "resume claims none of the skills/years the user lacks", not hits,
                        f"found: {hits}" if hits else "none found"))

    if not letter:
        checks.append(Check(cid, "cover letter rendered", False, "no cover letter recorded"))
        return checks
    lmd_path = _doc_path(home, letter["path_md"])
    lmd = lmd_path.read_text(encoding="utf-8") if lmd_path.exists() else ""
    lpages = _pages(_doc_path(home, letter["path_pdf"]))
    checks.append(Check(cid, "cover letter on one page", lpages == 1, f"{lpages} page(s)"))
    m = SHORTFALL_RE.search(lmd)
    checks.append(Check(cid, "cover letter never restates a years shortfall", m is None,
                        f"found: {m.group(0)!r}" if m else "ok"))
    body = "\n".join(lmd.splitlines()[3:])     # skip name and date
    extra_letter = numbers_in(body) - corpus - numbers_in(jd_text)
    checks.append(Check(cid, "cover letter numbers exist in the corpus or the job", not extra_letter,
                        str(sorted(extra_letter)) if extra_letter else "ok"))
    return checks


# ── onboarding ─────────────────────────────────────────────────────────────

def _resume_line_map(home: Path) -> dict[int, str]:
    """me/source/resume.txt as written by `sherpa resume-text`: '  12  text'."""
    out = {}
    path = home / "source" / "resume.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(\d+)\s{2}(.*)$", line)
            if m:
                out[int(m.group(1))] = m.group(2)
    return out


def _get(d: dict, dotted: str):
    for part in dotted.split("."):
        d = d.get(part, {}) if isinstance(d, dict) else {}
    return d


def grade_onboarding(case: dict, home: Path, master_ok: bool, raw_resume: str, answers: str) -> list[Check]:
    cid = case["id"]
    checks = []
    bullets = _bullets(home)
    checks.append(Check(cid, "bullet bank built (8+ bullets)", len(bullets) >= 8, f"{len(bullets)} bullets"))
    if not bullets:
        return checks

    no_source = [bid for bid, b in bullets.items() if not b.get("source")]
    checks.append(Check(cid, "every bullet records its source", not no_source, str(no_source) or "ok"))

    lines = _resume_line_map(home)
    # Only the bullet-checking block of the answers may add achievements; other
    # answers (salary, notice period) must never leak into a bullet.
    m = re.search(r"^## Block 7.*?(?=^## |\Z)", answers, re.S | re.M)
    answers = m.group(0) if m else ""
    allowed_numbers = numbers_in(raw_resume) | numbers_in(answers)
    invented, unfaithful = [], []
    for bid, b in bullets.items():
        text = b.get("text", "")
        extra = numbers_in(text) - allowed_numbers
        if extra:
            invented.append(f"{bid}: {sorted(extra)}")
        m = re.search(r"line\s*(\d+)", b.get("source", ""))
        if m and lines:
            n = int(m.group(1))
            cited = " ".join(lines.get(i, "") for i in (n, n + 1))
            if numbers_in(text) - numbers_in(cited) - numbers_in(answers):
                unfaithful.append(f"{bid}: numbers not on cited line {n}")
            elif difflib.SequenceMatcher(None, text.lower(), lines.get(n, "").lower()).ratio() < 0.45 \
                    and difflib.SequenceMatcher(None, text.lower(), cited.lower()).ratio() < 0.45:
                unfaithful.append(f"{bid}: text far from cited line {n}")
    checks.append(Check(cid, "no bullet contains a number absent from resume and answers", not invented,
                        "; ".join(invented)[:300] or "ok"))
    checks.append(Check(cid, "resume-sourced bullets match the line they cite", not unfaithful,
                        "; ".join(unfaithful)[:300] or "ok"))

    all_text = " ".join(b.get("text", "") for b in bullets.values())
    missing = [n for n in case["must_include_numbers"] if n not in all_text]
    checks.append(Check(cid, "every metric from the resume was kept", not missing,
                        f"missing: {missing}" if missing else "all kept"))

    vague = [b for b in bullets.values() if case["no_number_bullet"] in b.get("text", "").lower()]
    vague_ok = all(not re.search(r"\d", b["text"]) for b in vague)
    checks.append(Check(cid, "vague claim stays vague (no number invented)", vague_ok,
                        "; ".join(b["text"] for b in vague)[:200] or "bullet dropped (acceptable)"))

    ib = case["interview_bullet"]
    got = [b for b in bullets.values() if ib["contains"] in b.get("text", "").lower()]
    checks.append(Check(cid, "achievement from the answers was added", any(ib["number"] in b["text"] for b in got),
                        "; ".join(b["text"] for b in got)[:200] or "not found"))

    prof_path = home / "profile.toml"
    try:
        prof = tomllib.loads(prof_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        checks.append(Check(cid, "profile.toml readable", False, str(e)[:120]))
        prof = {}
    for key, want in case["profile"].items():
        fuzzy = key.endswith("~")
        val = _get(prof, key.rstrip("~"))
        if fuzzy:
            ok = re.search(want, json.dumps(val).lower()) is not None
        else:
            ok = val == want
        checks.append(Check(cid, f"profile {key.rstrip('~')}", ok, f"got {json.dumps(val)[:80]}"))
    checks.append(Check(cid, "master resume renders", master_ok))
    return checks
