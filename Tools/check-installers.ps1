#!/usr/bin/env pwsh
# Regression check for the PowerShell MCP installers.
#
# Each installer must write config files whose "command" and first "args" entry
# point at a real, absolute script that answers a JSON-RPC handshake.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$failures = @()

function Fail {
    param([string]$Message)

    Write-Host "FAIL: $Message" -ForegroundColor Red
    $script:failures += $Message
}

function Check-Config {
    param(
        [string]$Label,
        [string]$ConfigPath,
        [string[]]$PathKeys
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        Fail "$Label`: $ConfigPath was not written"
        return
    }

    $entry = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    foreach ($key in $PathKeys) {
        $entry = $entry.$key
    }

    $launcher = $entry.command
    $serverScript = @($entry.args)[0]

    if (-not [System.IO.Path]::IsPathRooted($serverScript)) {
        Fail "$Label`: args[0] must be an absolute path, got '$serverScript'"
        return
    }
    if (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) {
        Fail "$Label`: args[0] does not exist: $serverScript"
        return
    }

    $response = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | & $launcher $serverScript
    if (($response -join "`n") -notmatch '"serverInfo"') {
        Fail "$Label`: no initialize response from $launcher $serverScript"
        return
    }

    Write-Host "ok ${Label}: $launcher $serverScript" -ForegroundColor Green
}

function Invoke-Installer {
    param(
        [string]$Label,
        [string]$Installer,
        [string]$InstallDir
    )

    try {
        & $Installer -InstallDir $InstallDir | Out-Null
    }
    catch {
        Fail "$Label`: installer failed: $($_.Exception.Message)"
        return
    }

    Check-Config -Label "$Label server config" -ConfigPath (Join-Path $InstallDir "config\mcp-server.json") -PathKeys @()
    Check-Config -Label "$Label client config" -ConfigPath (Join-Path $InstallDir "config\mcp-client.json") -PathKeys @("servers", "cloudflare-diagnostics")
}

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mcp-installer-check-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

try {
    Invoke-Installer -Label "install-mcp-unified.ps1" -Installer (Join-Path $repoRoot "installers\install-mcp-unified.ps1") -InstallDir (Join-Path $workDir "unified")
    Invoke-Installer -Label "install-mcp-server.ps1" -Installer (Join-Path $repoRoot "installers\install-mcp-server.ps1") -InstallDir (Join-Path $workDir "server")
}
finally {
    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "$($failures.Count) installer check(s) failed" -ForegroundColor Red
    exit 1
}

Write-Host "All PowerShell installer configs point at a launchable server" -ForegroundColor Green
