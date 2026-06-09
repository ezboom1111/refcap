#!/usr/bin/env python
"""check_skill_staleness.py — enforce skill freshness via last_verified frontmatter.

Scans all SKILL.md files under skills/, checks last_verified date, warns if older than TTL.
Exits 0 = all fresh, 1 = stale skills found.

Usage:
    python check_skill_staleness.py                    # default 30-day TTL
    python check_skill_staleness.py --ttl 14           # 14-day TTL
    python check_skill_staleness.py --json
    python check_skill_staleness.py --fix              # update last_verified to today
"""
import os, sys, json, argparse, re, glob
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(HERE, "skills")
DEFAULT_TTL_DAYS = 30


def _parse_frontmatter(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}, content
    fm_text = m.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line and not line.startswith(" "):
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm, content


def _update_last_verified(path, today_str):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Anchor to a LINE (^...$, MULTILINE) and rewrite only the value to end-of-line — NOT `\s*\S+`, whose `\s*`
    # crossed the newline and `\S+` swallowed the YAML closing `---` when the value was empty (unrecoverable
    # corruption). count=1 so a literal `last_verified:` in the body/docs is never touched.
    if re.search(r"(?m)^last_verified:.*$", content):
        content = re.sub(r"(?m)^last_verified:.*$", f"last_verified: {today_str}", content, count=1)
    else:
        content = content.replace("\n---\n", f"\nlast_verified: {today_str}\n---\n", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def check_staleness(ttl_days=DEFAULT_TTL_DAYS, fix=False):
    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()

    results = []
    skill_files = glob.glob(os.path.join(SKILLS_DIR, "*/SKILL.md"))

    for path in sorted(skill_files):
        skill_name = os.path.basename(os.path.dirname(path))
        fm, _ = _parse_frontmatter(path)
        last_verified = fm.get("last_verified", "")

        if not last_verified:
            status = "missing"
            age_days = None
            stale = True
        else:
            try:
                lv_date = datetime.strptime(last_verified.strip("'\""), "%Y-%m-%d").date()
                age_days = (today - lv_date).days
                # "Max days since last_verified" → reaching the TTL (age == ttl) IS stale, not just exceeding it.
                stale = age_days >= ttl_days
                status = "stale" if stale else "fresh"
            except ValueError:
                status = "invalid-date"
                age_days = None
                stale = True

        if fix and stale:
            _update_last_verified(path, today_str)
            status = "fixed"
            last_verified = today_str   # reflect the POST-fix state in the returned dict (was the stale/None value)
            age_days = 0

        results.append({
            "skill": skill_name,
            "path": path,
            "last_verified": last_verified or None,
            "age_days": age_days,
            "status": status,
        })

    has_stale = any(r["status"] in ("stale", "missing", "invalid-date") for r in results)
    return {"pass": not has_stale, "ttl_days": ttl_days, "checked": today_str, "skills": results}


def main():
    parser = argparse.ArgumentParser(description="Check skill SKILL.md staleness")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, help="Max days since last_verified")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--fix", action="store_true", help="Update last_verified to today for stale skills")
    args = parser.parse_args()

    result = check_staleness(args.ttl, args.fix)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in result["skills"]:
            icon = {"fresh": "OK", "stale": "STALE", "missing": "NO-DATE", "invalid-date": "BAD-DATE", "fixed": "FIXED"}
            age_str = f"{s['age_days']}d" if s["age_days"] is not None else "?"
            print(f"  [{icon.get(s['status'], '?')}] {s['skill']:30s} verified={s['last_verified'] or 'NONE':12s} age={age_str}")
        status = "ALL FRESH" if result["pass"] else "STALE SKILLS FOUND"
        print(f"\n[{status}] ttl={args.ttl}d checked={result['checked']}")
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
