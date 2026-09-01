#!/usr/bin/env python
"""check_skill_staleness.py — enforce skill freshness via last_verified frontmatter.

Scans all SKILL.md files under skills/, checks last_verified date, warns if older than TTL.
Exits 0 = all fresh, 1 = stale skills found.

--fix stamps last_verified=today WITHOUT verifying content. To keep that from silently aging into
a real-looking "fresh", it also persists `verified_by: date-stamp-unverified` in the frontmatter;
later runs then report those skills as `stamped-unverified` (not `fresh`) until a human re-verifies
the content and sets `verified_by: <how>` (or removes the marker).

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


def _set_fm_field(fm_body, field, value):
    if re.search(rf"(?m)^{re.escape(field)}:.*$", fm_body):
        return re.sub(rf"(?m)^{re.escape(field)}:.*$", f"{field}: {value}", fm_body, count=1)
    return fm_body + f"\n{field}: {value}"


def _update_last_verified(path, today_str, verified_by="date-stamp-unverified"):
    """Stamp last_verified AND persist `verified_by` provenance. A bare --fix writes
    `verified_by: date-stamp-unverified`, so the NEXT run can tell an unverified date stamp from a
    real verification (Codex 3rd/4th review: the false-green must not survive silently)."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Operate ONLY inside the frontmatter block (first `---\n ... \n---`) — see history note below.
    m = re.match(r"(?s)^(---\s*\n)(.*?)(\n---)", content)
    if not m:
        new = f"---\nlast_verified: {today_str}\nverified_by: {verified_by}\n---\n\n" + content
    else:
        head, fm_body, tail = m.group(1), m.group(2), m.group(3)
        fm_body = _set_fm_field(fm_body, "last_verified", today_str)
        fm_body = _set_fm_field(fm_body, "verified_by", verified_by)
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
                if stale:
                    status = "stale"
                elif fm.get("verified_by", "").strip("'\"") == "date-stamp-unverified":
                    # Within TTL, but the date was written by a bare --fix (no content check). Report this
                    # distinctly and PERSISTENTLY (the marker lives in the frontmatter), so a later run — and
                    # any reader — can tell an unverified stamp from a real verification. Not "fresh".
                    status = "stamped-unverified"
                else:
                    status = "fresh"
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
        # A date-only stamp with NO content re-verification, applied in THIS run. Surfaced so a green
        # result produced by --fix is never mistaken for a verified-fresh result (false green).
        out["unverified_datestamp"] = stamped
    # PERSISTENT provenance: skills whose date was previously written by --fix (never content-verified).
    # Unlike unverified_datestamp (this-run-only), this survives across runs via the frontmatter marker,
    # so the false-green cannot silently age into looking verified.
    persisted = [r["skill"] for r in results if r["status"] == "stamped-unverified"]
    if persisted:
        out["stamped_unverified"] = persisted
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
            icon = {"fresh": "OK", "stale": "STALE", "missing": "NO-DATE", "invalid-date": "BAD-DATE",
                    "fixed": "DATE-ONLY(UNVERIFIED)", "stamped-unverified": "STAMPED(UNVERIFIED)"}
            age_str = f"{s['age_days']}d" if s["age_days"] is not None else "?"
            print(f"  [{icon.get(s['status'], '?')}] {s['skill']:30s} verified={s['last_verified'] or 'NONE':12s} age={age_str}")
        status = "ALL FRESH" if result["pass"] else "STALE SKILLS FOUND"
        print(f"\n[{status}] ttl={args.ttl}d checked={result['checked']}")
    if result.get("unverified_datestamp"):
        print("WARNING: date-only stamp (no verification) applied to: "
              f"{', '.join(result['unverified_datestamp'])}. 'fresh' here means 'date rewritten', "
              "not 'content re-verified'.", file=sys.stderr)
    if result.get("stamped_unverified"):
        print("WARNING: these skills carry a persisted date-stamp-unverified marker (a prior --fix "
              f"stamped the date but never verified content): {', '.join(result['stamped_unverified'])}. "
              "Re-verify the content, then set 'verified_by: <how>' (or remove it) in the frontmatter.",
              file=sys.stderr)
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
