# deploy_skills.ps1 — deploy canonical refcap\skills\* to the Claude Code and Codex skill dirs.
#
# Source of truth = <repo>\skills\ (versioned in git). Deploy copies = ~\.claude\skills\ and ~\.codex\skills\.
# Per-skill mirror (md5-verified): only the skills refcap OWNS are touched; other skills in the target dirs
# (e.g. leesearch-video-heavy, whose canonical lives elsewhere) are left untouched.
#
# Usage:
#   .\deploy_skills.ps1            deploy + md5-verify (idempotent; writes only what differs, prunes stale)
#   .\deploy_skills.ps1 -Check     verify only, NO writes; exits 1 on drift (CI / pre-commit guard)
param([switch]$Check)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Src  = Join-Path $Repo 'skills'
$Targets = @((Join-Path $HOME '.claude\skills'), (Join-Path $HOME '.codex\skills'))

function Md5($p) { (Get-FileHash -Algorithm MD5 -LiteralPath $p).Hash.ToLower() }

$drift = 0; $synced = 0; $verified = 0; $pruned = 0
foreach ($skillDir in (Get-ChildItem -Directory $Src)) {
  $skill = $skillDir.Name
  $base  = $skillDir.FullName
  foreach ($tgt in $Targets) {
    # Skip a target whose tool isn't installed (don't fabricate skill dirs for an absent agent).
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $tgt))) {
      Write-Host "  skip $tgt (parent missing)"; continue
    }
    $dest = Join-Path $tgt $skill
    # 1) push every source file (write only on md5 mismatch)
    foreach ($f in (Get-ChildItem -Recurse -File $base)) {
      $rel = $f.FullName.Substring($base.Length).TrimStart('\', '/')
      $df  = Join-Path $dest $rel
      $h   = Md5 $f.FullName
      $match = (Test-Path -LiteralPath $df) -and ((Md5 $df) -eq $h)
      if (-not $match) {
        if ($Check) { Write-Host "  DRIFT  $skill/$rel -> $tgt"; $drift++ }
        else {
          $dd = Split-Path -Parent $df
          if (-not (Test-Path -LiteralPath $dd)) { New-Item -ItemType Directory -Force -Path $dd | Out-Null }
          Copy-Item -LiteralPath $f.FullName -Destination $df -Force
          if ((Md5 $df) -ne $h) { throw "md5 mismatch after copy: $df" }
          $synced++
        }
      }
      $verified++
    }
    # 2) prune dest files no longer in source (exact mirror)
    if (Test-Path -LiteralPath $dest) {
      $destBase = (Resolve-Path -LiteralPath $dest).Path
      foreach ($df in (Get-ChildItem -Recurse -File $dest)) {
        $rel = $df.FullName.Substring($destBase.Length).TrimStart('\', '/')
        if (-not (Test-Path -LiteralPath (Join-Path $base $rel))) {
          if ($Check) { Write-Host "  STALE  $skill/$rel in $tgt"; $drift++ }
          else { Remove-Item -LiteralPath $df.FullName -Force; Write-Host "  pruned $skill/$rel ($tgt)"; $pruned++ }
        }
      }
    }
  }
}
Write-Host '---'
if ($Check) {
  if ($drift -gt 0) { Write-Host "DRIFT: $drift file(s) out of sync (run .\deploy_skills.ps1 to fix)"; exit 1 }
  else { Write-Host "IN SYNC: $verified file checks OK across $($Targets.Count) targets"; exit 0 }
} else {
  Write-Host "DEPLOYED: wrote $synced, pruned $pruned, verified $verified across $($Targets.Count) targets"; exit 0
}
