#!/usr/bin/env bash
# deploy_skills.sh — deploy canonical refcap/skills/* to the Claude Code and Codex skill dirs.
#
# Source of truth = <repo>/skills/ (versioned in git). Deploy copies = ~/.claude/skills/ and ~/.codex/skills/.
# Per-skill mirror (md5-verified): only the skills refcap OWNS are touched; other skills already in the target
# dirs (e.g. leesearch-video-heavy, whose canonical lives elsewhere) are left untouched.
#
# Usage:
#   ./deploy_skills.sh            deploy + md5-verify (idempotent; writes only what differs, prunes stale)
#   ./deploy_skills.sh --check    verify only, NO writes; exits 1 on drift (CI / pre-commit guard)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/skills"
TARGETS=("$HOME/.claude/skills" "$HOME/.codex/skills")
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1

md5() { md5sum "$1" | awk '{print $1}'; }

drift=0; synced=0; verified=0; pruned=0
for skilldir in "$SRC"/*/; do
  skill="$(basename "$skilldir")"
  for tgt in "${TARGETS[@]}"; do
    # Skip a target whose tool isn't installed (don't fabricate skill dirs for an absent agent).
    if [ ! -d "$(dirname "$tgt")" ]; then echo "  skip $tgt (parent missing)"; continue; fi
    dest="$tgt/$skill"
    # 1) push every source file (write only on md5 mismatch)
    while IFS= read -r -d '' f; do
      rel="${f#"$skilldir"}"
      df="$dest/$rel"
      if [ ! -f "$df" ] || [ "$(md5 "$f")" != "$(md5 "$df")" ]; then
        if [ "$CHECK" = 1 ]; then echo "  DRIFT  $skill/$rel -> $tgt"; drift=$((drift+1))
        else
          mkdir -p "$(dirname "$df")"; cp "$f" "$df"
          [ "$(md5 "$f")" = "$(md5 "$df")" ] || { echo "md5 mismatch after copy: $df"; exit 2; }
          synced=$((synced+1))
        fi
      fi
      verified=$((verified+1))
    done < <(find "$skilldir" -type f -print0)
    # 2) prune dest files no longer in source (exact mirror)
    if [ -d "$dest" ]; then
      while IFS= read -r -d '' df; do
        rel="${df#"$dest/"}"
        if [ ! -f "$skilldir/$rel" ]; then
          if [ "$CHECK" = 1 ]; then echo "  STALE  $skill/$rel in $tgt"; drift=$((drift+1))
          else rm -f "$df"; echo "  pruned $skill/$rel ($tgt)"; pruned=$((pruned+1)); fi
        fi
      done < <(find "$dest" -type f -print0)
    fi
  done
done
echo "---"
if [ "$CHECK" = 1 ]; then
  if [ "$drift" -gt 0 ]; then echo "DRIFT: $drift file(s) out of sync (run ./deploy_skills.sh to fix)"; exit 1
  else echo "IN SYNC: $verified file checks OK across ${#TARGETS[@]} targets"; fi
else
  echo "DEPLOYED: wrote $synced, pruned $pruned, verified $verified across ${#TARGETS[@]} targets"
fi
