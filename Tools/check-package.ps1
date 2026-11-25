#!/usr/bin/env pwsh
# Regression check for the Windows installers inside the release archive.
#
# Takes mcp-installer-pack.tar.gz, checks it carries the files a release needs,
# extracts it with tar, runs installers\install-mcp-unified.ps1 against the extracted
# copy with a temporary install directory, then handshakes with the installed Python
# and Node servers. The Linux half is Tools/check-package.py.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Archive
)

$ErrorActionPreference = "Stop"
$failures = @()
$expectedTools = @("dns_check", "doh_test", "export_results", "health_score", "trace_route")
$protocolVersion = "2024-11-05"

function Fail {
    param([string]$Message)

    Write-Host "FAIL: $Message" -ForegroundColor Red
    $script:failures += $Message
}

function Invoke-Handshake {
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
                clientInfo      = @{ name = "check-package"; version = "0" }
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
        $serverName = $reply.result.serverInfo.name

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        $process.StandardInput.Flush()

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
        $process.StandardInput.Flush()
        $line = $process.StandardOutput.ReadLine()
        if (-not $line) { throw "no reply to tools/list" }
        $reply = $line | ConvertFrom-Json
        $actual = @($reply.result.tools | ForEach-Object { $_.name } | Sort-Object)
        $expected = @($expectedTools | Sort-Object)
        if (($actual -join ",") -ne ($expected -join ",")) {
            throw "tools/list returned '$($actual -join ', ')', expected '$($expected -join ', ')'"
        }

        $process.StandardInput.WriteLine('{"jsonrpc":"2.0","id":3,"method":"ping"}')
        $process.StandardInput.Flush()
        $line = $process.StandardOutput.ReadLine()
        if (-not $line -or $null -eq ($line | ConvertFrom-Json).result) { throw "ping failed" }

        Write-Host "ok ${Label}: $serverName, $($actual.Count) tools, ping ok" -ForegroundColor Green
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

if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    Write-Host "FAIL: archive not found: $Archive" -ForegroundColor Red
    exit 1
}
$archivePath = (Resolve-Path -LiteralPath $Archive).Path

$entries = & tar -tzf $archivePath
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: tar could not read $archivePath" -ForegroundColor Red
    exit 1
}

$required = @(
    "LICENSE",
    "README.md",
    "installers/install-mcp-unified.ps1",
    "installers/install-mcp-server.ps1",
    "server/index.py",
    "server/index.js",
    "docs/README.md"
)
foreach ($item in $required) {
    if ($entries -notcontains $item) { Fail "archive is missing $item" }
}
$junk = @($entries | Where-Object { $_ -match '__pycache__/|node_modules/|(^|/)\.git/|\.DS_Store$' })
if ($junk.Count -gt 0) { Fail "archive carries generated files: $($junk[0])" }
if ($failures.Count -gt 0) { exit 1 }

Write-Host "archive: $($entries.Count) entries, required files present, no build junk" -ForegroundColor Green

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mcp-package-check-" + [guid]::NewGuid())
$packDir = Join-Path $workDir "pack"
$installDir = Join-Path $workDir "install"
New-Item -ItemType Directory -Path $packDir -Force | Out-Null

try {
    & tar -xzf $archivePath -C $packDir
    if ($LASTEXITCODE -ne 0) {
        Fail "tar could not extract $archivePath"
        exit 1
    }

    $installer = Join-Path (Join-Path $packDir "installers") "install-mcp-unified.ps1"
    try {
        & $installer -InstallDir $installDir | Out-Null
        Write-Host "installer: exit 0" -ForegroundColor Green
    }
    catch {
        Fail "installer failed: $($_.Exception.Message)"
    }

    $installed = @(
        @("config", "mcp-server.json"),
        @("config", "mcp-client.json"),
        @("server", "python", "index.py"),
        @("server", "node", "index.js"),
        @("server", "node", "package.json")
    )
    foreach ($segments in $installed) {
        $candidate = $installDir
        foreach ($segment in $segments) { $candidate = Join-Path $candidate $segment }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            Fail "installer did not create $($segments -join '/')"
        }
    }

    $serverConfigPath = Join-Path (Join-Path $installDir "config") "mcp-server.json"
    if (Test-Path -LiteralPath $serverConfigPath -PathType Leaf) {
        $entry = Get-Content -LiteralPath $serverConfigPath -Raw | ConvertFrom-Json
        $launcher = $entry.command
        $serverScript = @($entry.args)[0]

        if (-not [System.IO.Path]::IsPathRooted($serverScript)) {
            Fail "server config: args[0] must be an absolute path, got '$serverScript'"
        }
        elseif (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) {
            Fail "server config: args[0] does not exist: $serverScript"
        }
        elseif (-not [System.IO.Path]::IsPathRooted($launcher) -or -not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
            Fail "server config: command is not an absolute executable: '$launcher'"
        }
        else {
            $environment = @{}
            if ($entry.env) {
                $entry.env.PSObject.Properties | ForEach-Object { $environment[$_.Name] = $_.Value }
            }
            Invoke-Handshake -Label "python server" -Command $launcher -Arguments @($serverScript) -Environment $environment
        }
    }

    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $nodeScript = Join-Path (Join-Path (Join-Path $installDir "server") "node") "index.js"
    if (-not $node) {
        Write-Host "node server: skipped, no node.exe on PATH" -ForegroundColor Yellow
    }
    elseif (-not (Test-Path -LiteralPath $nodeScript -PathType Leaf)) {
        Fail "node server: $nodeScript was not installed"
    }
    else {
        Invoke-Handshake -Label "node server" -Command $node.Source -Arguments @($nodeScript)
    }
}
finally {
    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "$($failures.Count) package check(s) failed" -ForegroundColor Red
    exit 1
}

Write-Host "Windows release package: installs and launches from the extracted archive" -ForegroundColor Green
