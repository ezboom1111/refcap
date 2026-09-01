#!/usr/bin/env python
"""check_skill_staleness.py — enforce skill freshness via last_verified frontmatter.

Scans all SKILL.md files under skills/, checks last_verified date, warns if older than TTL.
Exits 0 = all fresh, 1 = stale skills found.

Usage:
    python check_skill_staleness.py                    # default 30-day TTL
    python check_skill_staleness.py --ttl 14           # 14-day TTL
    python check_skill_staleness.py --json
    python check_skill_staleness.py --fix --yes-unverified   # date-only stamp (NO content check; false-green risk)
"""
import os, sys, json, argparse, re, glob
from datetime import datetime, timezone

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
    # Operate ONLY inside the frontmatter block (first `---\n ... \n---`). A whole-file regex would (a) match a
    # literal `last_verified:` line in the markdown BODY before the frontmatter and rewrite that instead (leaving
    # the skill permanently 'missing'), and (b) its `\s*\S+` form once ate the closing `---`. Line-anchored within
    # the block, the value is rewritten to end-of-line (never crossing the newline / delimiter).
    m = re.match(r"(?s)^(---\s*\n)(.*?)(\n---)", content)
    if not m:
        # No frontmatter block — create one (defensive; real SKILL.md files always have frontmatter).
        new = f"---\nlast_verified: {today_str}\n---\n\n" + content
    else:
        head, fm_body, tail = m.group(1), m.group(2), m.group(3)
        if re.search(r"(?m)^last_verified:.*$", fm_body):
            fm_body = re.sub(r"(?m)^last_verified:.*$", f"last_verified: {today_str}", fm_body, count=1)
        else:
            fm_body = fm_body + f"\nlast_verified: {today_str}"
        new = head + fm_body + tail + content[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


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
    out = {"pass": not has_stale, "ttl_days": ttl_days, "checked": today_str, "skills": results}
    stamped = [r["skill"] for r in results if r["status"] == "fixed"]
    if stamped:
        # A date-only stamp with NO content re-verification. Surfaced so a green result
        # produced by --fix is never mistaken for a verified-fresh result (false green).
        out["unverified_datestamp"] = stamped
    return out


def main():
    parser = argparse.ArgumentParser(description="Check skill SKILL.md staleness")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_DAYS, help="Max days since last_verified")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--fix", action="store_true",
                        help="Stamp last_verified=today. This does NOT verify content — it only rewrites the "
                             "date, which can create a green with zero re-measurement. Requires --yes-unverified.")
    parser.add_argument("--yes-unverified", action="store_true",
                        help="Acknowledge that --fix is a date-only stamp with no content verification.")
    args = parser.parse_args()

    # False-green guard: --fix rewrites the date without re-verifying anything, so a bare --fix
    # would silently turn a stale skill green. Require an explicit unsafe acknowledgment.
    if args.fix and not args.yes_unverified:
        parser.error("--fix only stamps last_verified=today WITHOUT re-verifying the skill (false-green risk). "
                     "Re-verify the skill content yourself, then pass --fix --yes-unverified to stamp the date.")

    result = check_staleness(args.ttl, args.fix)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in result["skills"]:
            icon = {"fresh": "OK", "stale": "STALE", "missing": "NO-DATE", "invalid-date": "BAD-DATE", "fixed": "DATE-ONLY(UNVERIFIED)"}
            age_str = f"{s['age_days']}d" if s["age_days"] is not None else "?"
            print(f"  [{icon.get(s['status'], '?')}] {s['skill']:30s} verified={s['last_verified'] or 'NONE':12s} age={age_str}")
        status = "ALL FRESH" if result["pass"] else "STALE SKILLS FOUND"
        print(f"\n[{status}] ttl={args.ttl}d checked={result['checked']}")
    if result.get("unverified_datestamp"):
        print("WARNING: date-only stamp (no verification) applied to: "
              f"{', '.join(result['unverified_datestamp'])}. 'fresh' here means 'date rewritten', "
              "not 'content re-verified'.", file=sys.stderr)
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
