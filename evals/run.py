"""Run the Job Sherpa eval: real agent sessions on fictional users, graded by rules.

    python3 evals/run.py                       # everything, with Claude Code
    python3 evals/run.py --suite scoring       # one suite: scoring | tailoring | onboarding
    python3 evals/run.py --agent codex         # another agent (see AGENTS below)
    python3 evals/run.py --grade-only RUN_DIR  # re-grade a finished run, no agent calls

Each case gets a throwaway private folder (SHERPA_HOME) built from a fictional
persona. The agent follows the real playbooks, headless; the graders then check
what it left behind. Nothing touches your own me/ folder.

It costs real model usage: a full run is 6 agent sessions plus 3 judge calls.
Each Claude Code session is capped with --max-budget-usd.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import graders  # noqa: E402
import judge as judge_mod  # noqa: E402

CASES = REPO / "evals" / "cases"

# Command templates. {prompt}, {home} and {budget} are filled in per run.
AGENTS = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "json", "--no-session-persistence",
               "--max-budget-usd", "{budget}", "--permission-mode", "acceptEdits", "--add-dir", "{home}",
               "--allowedTools", "Bash(bin/sherpa:*)", "Bash(python3 -m sherpa:*)", "Bash(ls:*)",
               "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cd:*)", "Read", "Write", "Edit", "Glob", "Grep"],
    # Untested so far: contributions welcome.
    "codex": ["codex", "exec", "--full-auto", "--cd", str(REPO), "{prompt}"],
}
JUDGES = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "json", "--no-session-persistence",
               "--max-budget-usd", "1", "--allowedTools", "Read"],
}

PREAMBLE = """This is an automated evaluation run of Job Sherpa, on a FICTIONAL user. Rules for this run:
- Work fully non-interactively. Never ask questions or wait for answers. Where a playbook says to ask
  the user, use the answers in {home}/questionnaire.md if it exists; otherwise leave that item out.
- The user's private folder is {home} (SHERPA_HOME is set to it). Wherever the playbooks say me/,
  use that folder instead. Do not touch me/ in the repo.
- You are already in the repo root and SHERPA_HOME is already set. Run Job Sherpa exactly as
  `bin/sherpa <command>`, with no `cd` and no environment-variable prefix in front (the run only
  allows commands in that form). Never modify files in the repo itself; write only inside {home}.
- No web access is needed or allowed.

Task:
"""

TASKS = {
    "scoring": "Follow playbooks/score-fit.md: score every job in the inbox, then export the shortlist.",
    "tailoring": ("Follow playbooks/tailor-resume.md to write a tailored resume for job 1, then "
                  "playbooks/draft-cover-letter.md to write its cover letter. Both must render."),
    "onboarding": ("Follow playbooks/onboard.md to set this user up. Their resume is "
                   "{home}/source/original-resume.txt (plain text; run `bin/sherpa resume-text` on it "
                   "to get numbered lines) and their questionnaire answers are in "
                   "{home}/questionnaire.md. Skip section 5 (company list) and the git hook suggestion. "
                   "Build profile.toml, bullets.yaml, master-resume.json and master-cover-letter.json, "
                   "and render the master resume."),
}


def sherpa(home: Path, *args, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, SHERPA_HOME=str(home))
    return subprocess.run([sys.executable, "-m", "sherpa", *args], cwd=REPO, env=env, input=stdin,
                          capture_output=True, text=True)


def make_home(base: Path, case_id: str, persona: str | None, gold: bool) -> Path:
    home = base / case_id / "home"
    home.mkdir(parents=True)
    sherpa(home, "init")
    if gold and persona:
        src = REPO / persona
        for name in ("profile.toml", "bullets.yaml", "master-resume.json"):
            if (src / name).exists():
                shutil.copy2(src / name, home / name)
    (home / "companies.yaml").write_text("# eval: no discovery\n")
    return home


def add_job(home: Path, job: dict) -> int:
    out = sherpa(home, "add-job", "--company", job["company"], "--title", job["title"],
                 "--location", job["location"], "--file", str(CASES / "jobs" / job["file"]))
    if out.returncode:
        raise RuntimeError(out.stdout + out.stderr)
    return int(out.stdout.split("#")[1].split(":")[0])


def run_agent(template: list[str], home: Path, task: str, log: Path, budget: float) -> dict:
    prompt = PREAMBLE.format(home=home) + task.format(home=home)
    cmd = [p.replace("{prompt}", prompt).replace("{home}", str(home)).replace("{budget}", str(budget))
           for p in template]
    env = dict(os.environ, SHERPA_HOME=str(home))
    start = time.time()
    try:
        out = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=1800)
        stdout, rc = out.stdout, out.returncode
        stderr = out.stderr
    except subprocess.TimeoutExpired as e:
        stdout, stderr, rc = (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout", -1
    log.write_text(stdout + ("\n--- stderr ---\n" + stderr if stderr else ""), encoding="utf-8")
    info = {"returncode": rc, "seconds": round(time.time() - start), "cost_usd": 0.0}
    try:
        data = json.loads(stdout)
        info["cost_usd"] = float(data.get("total_cost_usd") or 0)
        info["turns"] = data.get("num_turns")
        info["models"] = sorted((data.get("modelUsage") or {}).keys())
    except ValueError:
        pass
    return info


def main():
    ap = argparse.ArgumentParser(description="Run the Job Sherpa eval.")
    ap.add_argument("--agent", default="claude", choices=AGENTS)
    ap.add_argument("--suite", choices=["scoring", "tailoring", "onboarding"], action="append")
    ap.add_argument("--case", help="only this case id")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    ap.add_argument("--budget", type=float, default=3.0, help="max USD per agent session (Claude Code)")
    ap.add_argument("--out", help="results folder (default: evals/results/<timestamp>-<agent>)")
    ap.add_argument("--grade-only", metavar="RUN_DIR", help="re-grade an existing run; no agent calls")
    args = ap.parse_args()

    cases = json.loads((CASES / "cases.json").read_text())
    suites = args.suite or ["scoring", "tailoring", "onboarding"]
    run_dir = Path(args.grade_only or args.out or
                   REPO / "evals" / "results" / f"{datetime.now():%Y-%m-%d_%H%M}-{args.agent}")
    work = run_dir / "work"
    if not args.grade_only:
        if work.exists():
            sys.exit(f"{run_dir} already exists; pass another --out")
        work.mkdir(parents=True)
    template = AGENTS[args.agent]
    checks, runs, judged = [], {}, []

    for suite in suites:
        for case in cases[suite]:
            if args.case and case["id"] != args.case:
                continue
            cid = case["id"]
            print(f"[{suite}] {cid}", flush=True)
            home = work / cid / "home"
            meta_path = work / cid / "meta.json"
            if not args.grade_only:
                home = make_home(work, cid, cases["personas"][case["persona"]], gold=(suite != "onboarding"))
                meta = {}
                if suite == "scoring":
                    meta["job_ids"] = {j["file"]: add_job(home, j) for j in case["jobs"]}
                elif suite == "tailoring":
                    meta["job_id"] = add_job(home, case["job"])
                else:
                    shutil.copy2(REPO / case["resume"], home / "source" / "original-resume.txt")
                    shutil.copy2(REPO / case["answers"], home / "questionnaire.md")
                meta_path.write_text(json.dumps(meta))
                task = TASKS[suite]
                runs[cid] = run_agent(template, home, task, work / cid / "agent.log", args.budget)
                print(f"   agent: {runs[cid]}", flush=True)
            meta = json.loads(meta_path.read_text())

            if suite == "scoring":
                checks += graders.grade_scoring(case, home, meta["job_ids"])
            elif suite == "tailoring":
                jd = (CASES / "jobs" / case["job"]["file"]).read_text()
                checks += graders.grade_tailoring(case, home, meta["job_id"], jd)
                if not args.no_judge and args.agent in JUDGES:
                    judged.append(run_judge(case, home, meta["job_id"], runs))
            else:
                master_ok = sherpa(home, "master-resume").returncode == 0
                checks += graders.grade_onboarding(case, home, master_ok,
                                                   (REPO / case["resume"]).read_text(),
                                                   (REPO / case["answers"]).read_text())

    write_report(run_dir, args.agent, checks, runs, judged)


def run_judge(case, home, job_id, runs):
    from contextlib import closing
    with closing(graders._db(home)) as conn:
        docs = {k: graders._latest_doc(conn, job_id, k) for k in ("resume", "cover_letter")}
    if not all(docs.values()):
        return {"case": case["id"], "error": "documents missing", "unsupported": []}
    read = lambda d: graders._doc_path(home, d["path_md"]).read_text(encoding="utf-8")
    try:
        master = home / "master-resume.json"
        verdict, cost = judge_mod.judge(JUDGES["claude"], (home / "bullets.yaml").read_text(),
                                        (home / "profile.toml").read_text(),
                                        master.read_text() if master.exists() else "(none)",
                                        read(docs["resume"]),
                                        read(docs["cover_letter"]))
    except Exception as e:  # a broken judge must not hide the deterministic results
        return {"case": case["id"], "error": str(e)[:200], "unsupported": []}
    runs.setdefault(f"judge:{case['id']}", {})["cost_usd"] = cost
    return {"case": case["id"], "unsupported": verdict.get("unsupported", [])}


def write_report(run_dir: Path, agent: str, checks, runs, judged):
    passed = sum(c.passed for c in checks)
    cost = sum(r.get("cost_usd", 0) for r in runs.values())
    (run_dir / "results.json").write_text(json.dumps(
        {"agent": agent, "checks": [c.to_dict() for c in checks], "runs": runs, "judge": judged}, indent=2))
    models = sorted({m for r in runs.values() for m in r.get("models", [])})
    lines = [f"# Job Sherpa eval: {agent}, {datetime.now():%Y-%m-%d}", "",
             f"**Rule checks: {passed}/{len(checks)} passed.**"
             + (f" Agent cost: ${cost:.2f}." if cost else "")
             + (f" Model(s): {', '.join(models)}." if models else ""), ""]
    by_case: dict[str, list] = {}
    for c in checks:
        by_case.setdefault(c.case, []).append(c)
    for cid, items in by_case.items():
        ok = sum(c.passed for c in items)
        lines += [f"## {cid} ({ok}/{len(items)})", "", "| Check | Result | Detail |", "|---|---|---|"]
        for c in items:
            lines.append(f"| {c.name} | {'✅' if c.passed else '❌'} | {c.detail.replace('|', '/')[:160]} |")
        lines.append("")
    if judged:
        lines += ["## LLM judge (tailoring; reported separately)", ""]
        for j in judged:
            if j.get("error"):
                lines.append(f"- **{j['case']}**: judge error: {j['error']}")
            elif not j["unsupported"]:
                lines.append(f"- **{j['case']}**: no unsupported claims found")
            else:
                lines.append(f"- **{j['case']}**: {len(j['unsupported'])} unsupported claim(s)")
                for u in j["unsupported"]:
                    lines.append(f"  - {u.get('document')}: \"{u.get('text')}\": {u.get('why')}")
        lines.append("")
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{passed}/{len(checks)} checks passed. Report: {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
