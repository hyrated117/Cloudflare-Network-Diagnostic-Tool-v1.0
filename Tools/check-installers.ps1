#!/usr/bin/env pwsh
# Regression check for the PowerShell MCP installers.
#
# Each installer must write config files whose "command" and first "args" entry
# point at a real, absolute script that answers a JSON-RPC session.
#
# By default the installers in this repository are checked. Pass -InstallersRoot to
# check the copy inside an extracted release archive instead:
#
#   python Tools/check-archive.py dist/v1.0.0/mcp-installer-pack.tar.gz --extract-to dist/pack
#   ./Tools/check-installers.ps1 -InstallersRoot dist/pack

[CmdletBinding()]
param(
    [string]$InstallersRoot
)

$ErrorActionPreference = "Stop"
$root = if ($InstallersRoot) { (Resolve-Path -LiteralPath $InstallersRoot).Path } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$installersDir = Join-Path $root "installers"
$failures = @()
$expectedTools = @("dns_check", "doh_test", "export_results", "health_score", "trace_route" | Sort-Object)
$protocolVersion = "2024-11-05"

function Fail {
    param([string]$Message)

    Write-Host "FAIL: $Message" -ForegroundColor Red
    $script:failures += $Message
}

function Invoke-Session {
    param(
        [string]$Label,
        [string]$Command,
        [string[]]$Arguments,
        [hashtable]$Environment = @{}
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Command
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    foreach ($key in $Environment.Keys) { $startInfo.Environment[$key] = [string]$Environment[$key] }

    $process = $null
    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)

        $initialize = @{
            jsonrpc = "2.0"
            id      = 1
            method  = "initialize"
            params  = @{
                protocolVersion = $protocolVersion
                capabilities    = @{}
                clientInfo      = @{ name = "check-installers"; version = "0" }
            }
        }
        $process.StandardInput.WriteLine(($initialize | ConvertTo-Json -Compress -Depth 10))
        $process.StandardInput.Flush()
        $line = $process.StandardOutput.ReadLine()
        if (-not $line) {
            throw "no reply to initialize; stderr: $($process.StandardError.ReadToEnd())"
        }
        $reply = $line | ConvertFrom-Json
        if ($reply.result.protocolVersion -ne $protocolVersion) {
            throw "answered protocol '$($reply.result.protocolVersion)', expected $protocolVersion"
        }

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        $process.StandardInput.Flush()

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
        $process.StandardInput.Flush()
        $line = $process.StandardOutput.ReadLine()
        if (-not $line) { throw "no reply to tools/list" }
        $actual = @(($line | ConvertFrom-Json).result.tools | ForEach-Object { $_.name } | Sort-Object)
        if (($actual -join ",") -ne ($expectedTools -join ",")) {
            throw "tools/list returned '$($actual -join ', ')', expected '$($expectedTools -join ', ')'"
        }

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","id":3,"method":"ping"}')
        $process.StandardInput.Flush()
        $line = $process.StandardOutput.ReadLine()
        if (-not $line -or $null -eq ($line | ConvertFrom-Json).result) { throw "ping failed" }

        Write-Host "ok ${Label}: $Command $($Arguments[0]) ($($actual.Count) tools)" -ForegroundColor Green
    }
    catch {
        Fail "$Label`: $($_.Exception.Message)"
    }
    finally {
        if ($process) {
            try { $process.StandardInput.Close() } catch { }
            if (-not $process.WaitForExit(15000)) {
                try { $process.Kill() } catch { }
                Fail "$Label`: did not exit after stdin closed"
            }
            elseif ($process.ExitCode -ne 0) {
                Fail "$Label`: exited with code $($process.ExitCode)"
            }
        }
    }
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
    if (-not [System.IO.Path]::IsPathRooted($launcher) -or -not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        Fail "$Label`: command is not an absolute executable: '$launcher'"
        return
    }

    $environment = @{}
    if ($entry.env) {
        $entry.env.PSObject.Properties | ForEach-Object { $environment[$_.Name] = $_.Value }
    }
    Invoke-Session -Label $Label -Command $launcher -Arguments @($serverScript) -Environment $environment
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

    Check-Config -Label "$Label server config" -ConfigPath (Join-Path (Join-Path $InstallDir "config") "mcp-server.json") -PathKeys @()
    Check-Config -Label "$Label client config" -ConfigPath (Join-Path (Join-Path $InstallDir "config") "mcp-client.json") -PathKeys @("servers", "cloudflare-diagnostics")
}

if (-not (Test-Path -LiteralPath $installersDir -PathType Container)) {
    Write-Host "FAIL: $root has no installers directory" -ForegroundColor Red
    exit 1
}
Write-Host "checking installers in $root"

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mcp-installer-check-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

try {
    Invoke-Installer -Label "install-mcp-unified.ps1" -Installer (Join-Path $installersDir "install-mcp-unified.ps1") -InstallDir (Join-Path $workDir "unified")
    Invoke-Installer -Label "install-mcp-server.ps1" -Installer (Join-Path $installersDir "install-mcp-server.ps1") -InstallDir (Join-Path $workDir "server")
}
finally {
    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "$($failures.Count) installer check(s) failed" -ForegroundColor Red
    exit 1
}

Write-Host "All PowerShell installer configs point at a launchable server" -ForegroundColor Green
