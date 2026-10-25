"""Optional LLM judge for the tailoring cases.

The deterministic graders catch invented numbers, untraceable lines and the
forbidden skills we planted. They can't catch a reworded bullet that inflates
scope without a number ("contributed to" -> "led"). A second model reads each
document against the bullet bank and lists unsupported claims.

A model grading a model is a weaker signal than a rule, so judge results are
reported separately and never change the deterministic pass rate.
"""
import json
import re
import subprocess

PROMPT = """You are auditing a resume and cover letter for honesty. You will get:
1. BULLETS: the candidate's verified achievements,
2. PROFILE: hard facts (years, degree, location),
3. MASTER RESUME: the resume the candidate wrote and verified themselves; its skills list,
   education, project titles and role dates are the candidate's own facts,
4. RESUME and COVER LETTER produced for a job.

List every claim in the RESUME or COVER LETTER that BULLETS, PROFILE or MASTER RESUME do not support.
Count as unsupported: a skill, tool, domain or responsibility the candidate never had;
inflated scope or seniority (e.g. "contributed" became "led", "a team" became "the org");
an invented number. Rewording that keeps the same meaning is fine. In the cover letter,
an honest sentence naming a gap ("I haven't built X") is fine and is NOT a claim.
A skill, tool, school or project name that appears in MASTER RESUME is supported.
Also count: attributing a skill or result to the wrong role or employer, and inventing
an order of events the sources don't give.

Reply with ONLY a JSON object, no prose:
{"unsupported": [{"document": "resume" | "cover_letter", "text": "<exact phrase>", "why": "<short>"}]}

BULLETS:
%s

PROFILE:
%s

MASTER RESUME:
%s

RESUME:
%s

COVER LETTER:
%s
"""


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in judge reply")
    return json.loads(m.group(0))


def judge(cmd_template: list[str], bullets: str, profile: str, master: str, resume: str, letter: str,
          timeout: int = 600) -> tuple[dict, float]:
    """Returns (verdict, cost_usd). cost is 0 when the agent doesn't report it."""
    prompt = PROMPT % (bullets, profile, master, resume, letter)
    cmd = [part.replace("{prompt}", prompt) for part in cmd_template]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    cost, text = 0.0, out.stdout
    try:
        wrapper = json.loads(out.stdout)
        cost = float(wrapper.get("total_cost_usd") or 0)
        text = wrapper.get("result") or ""
    except ValueError:
        pass
    return _extract_json(text), cost
