# Ask-a-Friend installer (Windows)
$ErrorActionPreference = "Stop"
$RepoDir   = Split-Path -Parent $PSScriptRoot
$SkillSrc  = Join-Path $RepoDir "skills\ask-a-friend"
$RuleSrc   = Join-Path $RepoDir "rules\ask-a-friend-activate.md"
$Begin = "# DO NOT EDIT: BEGIN ASK-A-FRIEND SKILL"
$End   = "# DO NOT EDIT: END ASK-A-FRIEND SKILL"

function Log($m) { Write-Host "[ask-a-friend] $m" }

function Inject($f, $src) {
  $dir = Split-Path -Parent $f
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  if (Test-Path $f) {
    $content = Get-Content $f -Raw
    $content = $content -replace "(?s)$([regex]::Escape($Begin)).*?$([regex]::Escape($End))\r?\n?", ""
    Set-Content $f $content -NoNewline
  }
  Add-Content $f "`n$Begin`n$(Get-Content $src -Raw)`n$End"
  Log "injected -> $f"
}

$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { "$HOME\.claude" }
$CfgDir = "$HOME\.config\ask-a-friend"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null

if (Test-Path $ClaudeDir) {
  Log "Claude Code detected."
  Copy-Item -Recurse -Force $SkillSrc "$ClaudeDir\skills\ask-a-friend"
  Inject "$ClaudeDir\CLAUDE.md" $RuleSrc
} else { Log "Claude Code not found. Skipping." }

if (!(Test-Path "$CfgDir\config.json")) {
  '{ "vertex_project": "your-gcp-project-id", "vertex_location": "global", "default_model": "claude-sonnet-4-6", "require_approval": true, "cost_cap_usd": 5.0, "cost_cap_mode": "warn", "use_cache": true, "custom_endpoint": "", "max_retries": 3, "timeout_ms": 30000 }' | Set-Content "$CfgDir\config.json"
  Log "wrote default config"
}
Log "Done. Friend ready."
