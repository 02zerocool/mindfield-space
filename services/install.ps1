# install.ps1 — Install Mindfield as Windows NSSM services
#
# Requirements:
#   - NSSM (Non-Sucking Service Manager) installed and on PATH
#     https://nssm.cc/  or  scoop install nssm
#   - Python 3.11+ on PATH
#   - llama-server on PATH (from llama.cpp)
#
# Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File services\install.ps1

param(
    [string]$PythonPath = (Get-Command python).Source,
    [string]$Root       = (Split-Path $PSScriptRoot -Parent),
    [string]$LanceDB    = "$Root\lancedb",
    [string]$Logs       = "$Root\logs",
    [string]$EmbedModel = "$Root\models\nomic-embed-text-v1.5.Q8_0.gguf",
    [int]   $EmbedPort  = 8082,
    [int]   $LeanPort   = 8018
)

$ErrorActionPreference = "Stop"

function Install-Service {
    param($Name, $Exe, $Args, $Dir, $Stdout, $Stderr, $DisplayName)

    $existing = nssm status $Name 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  SKIP  $Name (already installed)" -ForegroundColor Yellow
        return
    }

    nssm install   $Name $Exe $Args
    nssm set       $Name AppDirectory  $Dir
    nssm set       $Name AppStdout     $Stdout
    nssm set       $Name AppStderr     $Stderr
    nssm set       $Name DisplayName   $DisplayName
    nssm set       $Name AppExit       Default Restart
    nssm set       $Name Start         SERVICE_AUTO_START
    Write-Host "  OK    $Name" -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

Write-Host "`nMindfield — Installing NSSM services`n"

# ── Embedding server (llama-server) ──────────────────────────────────────────
$llamaServer = (Get-Command llama-server -ErrorAction SilentlyContinue)?.Source
if (-not $llamaServer) {
    Write-Host "  WARN  llama-server not found on PATH — skipping mindfield-embed" -ForegroundColor Yellow
} else {
    Install-Service `
        -Name        "mindfield-embed" `
        -Exe         $llamaServer `
        -Args        "--model `"$EmbedModel`" --port $EmbedPort --host 127.0.0.1 --embedding --ctx-size 2048" `
        -Dir         $Root `
        -Stdout      "$Logs\embed-out.log" `
        -Stderr      "$Logs\embed-error.log" `
        -DisplayName "Mindfield Embed :$EmbedPort"
}

# ── Lean memory API ───────────────────────────────────────────────────────────
Install-Service `
    -Name        "mindfield-lean" `
    -Exe         $PythonPath `
    -Args        "$Root\lean\lean_api.py" `
    -Dir         "$Root\lean" `
    -Stdout      "$Logs\lean-out.log" `
    -Stderr      "$Logs\lean-error.log" `
    -DisplayName "Mindfield Lean API :$LeanPort"

nssm set mindfield-lean AppEnvironmentExtra "LANCE_DB_PATH=$LanceDB"
nssm set mindfield-lean AppEnvironmentExtra "+LEAN_PORT=$LeanPort"
nssm set mindfield-lean AppEnvironmentExtra "+EMBED_URL=http://127.0.0.1:$EmbedPort"
nssm set mindfield-lean AppEnvironmentExtra "+HF_HUB_OFFLINE=1"

Write-Host "`nStarting services...`n"

$svc = @("mindfield-embed", "mindfield-lean")
foreach ($s in $svc) {
    $status = nssm status $s 2>&1
    if ($status -match "SERVICE_RUNNING") {
        Write-Host "  RUNNING  $s" -ForegroundColor Green
    } else {
        nssm start $s 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        $status = nssm status $s 2>&1
        if ($status -match "SERVICE_RUNNING") {
            Write-Host "  STARTED  $s" -ForegroundColor Green
        } else {
            Write-Host "  FAILED   $s — check $Logs" -ForegroundColor Red
        }
    }
}

Write-Host "`nDone. Test with:`n  curl http://127.0.0.1:$LeanPort/health`n"
