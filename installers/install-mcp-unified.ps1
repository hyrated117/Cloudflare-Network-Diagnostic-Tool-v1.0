# Unified MCP Server Installer for Windows PowerShell
# Installs Python and/or Node.js implementations when available.

[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:APPDATA "Cloudflare-MCP")
)

$ErrorActionPreference = "Stop"
$version = "1.0.0"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonSource = Join-Path $repoRoot "server\index.py"
$nodeSource = Join-Path $repoRoot "server\index.js"
$nodePackage = Join-Path $repoRoot "server\package.json"
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py.exe -ErrorAction SilentlyContinue }
$node = Get-Command node.exe -ErrorAction SilentlyContinue
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { $npm = Get-Command npm.exe -ErrorAction SilentlyContinue }

if (-not $python -and -not $node) {
    throw "Python 3 or Node.js is required. Install one and retry."
}
if ($node -and -not $npm) {
    throw "npm is required to install Node.js server dependencies. Install Node.js with npm and retry."
}

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$serverRoot = Join-Path $InstallDir "server"
$configDir = Join-Path $InstallDir "config"
New-Item -ItemType Directory -Path $serverRoot, $configDir -Force | Out-Null

$serverConfig = $null
$clientConfig = $null
if ($python) {
    if (-not (Test-Path -LiteralPath $pythonSource -PathType Leaf)) { throw "Python server source not found: $pythonSource" }
    $pythonDir = Join-Path $serverRoot "python"
    New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
    $pythonDestination = Join-Path $pythonDir "index.py"
    Copy-Item -LiteralPath $pythonSource -Destination $pythonDestination -Force
    $pythonCommand = $python.Source
    $serverConfig = @{
        name = "Cloudflare Network Diagnostic Tool"
        version = $version
        description = "MCP server for Cloudflare network diagnostics"
        type = "stdio"
        command = $pythonCommand
        args = @($pythonDestination)
        env = @{ PYTHONUNBUFFERED = "1" }
    }
    $clientConfig = @{
        name = "Cloudflare Diagnostic Client"
        version = $version
        description = "MCP Client configuration for Cloudflare Network Diagnostic Tool"
        servers = @{ "cloudflare-diagnostics" = @{ command = $pythonCommand; args = @($pythonDestination); env = @{ PYTHONUNBUFFERED = "1" } } }
    }
    Write-Host "Python server installed at $pythonDestination" -ForegroundColor Green
}

if ($node) {
    if (-not (Test-Path -LiteralPath $nodeSource -PathType Leaf)) { throw "Node server source not found: $nodeSource" }
    if (-not (Test-Path -LiteralPath $nodePackage -PathType Leaf)) { throw "Node package manifest not found: $nodePackage" }

    $nodeDir = Join-Path $serverRoot "node"
    New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null
    $nodeDestination = Join-Path $nodeDir "index.js"
    Copy-Item -LiteralPath $nodeSource -Destination $nodeDestination -Force
    # Copy the server manifest, not a placeholder, so npm installs the runtime dependencies.
    Copy-Item -LiteralPath $nodePackage -Destination (Join-Path $nodeDir "package.json") -Force

    Push-Location $nodeDir
    try {
        & $npm.Source install --omit=dev --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    if (-not $serverConfig) {
        $serverConfig = @{
            name = "Cloudflare Network Diagnostic Tool"
            version = $version
            description = "MCP server for Cloudflare network diagnostics"
            type = "stdio"
            command = $node.Source
            args = @($nodeDestination)
        }
        $clientConfig = @{
            name = "Cloudflare Diagnostic Client"
            version = $version
            description = "MCP Client configuration for Cloudflare Network Diagnostic Tool"
            servers = @{ "cloudflare-diagnostics" = @{ command = $node.Source; args = @($nodeDestination) } }
        }
    }
    Write-Host "Node.js server and dependencies installed at $nodeDir" -ForegroundColor Green
}

$serverConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $configDir "mcp-server.json") -Encoding utf8
$clientConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $configDir "mcp-client.json") -Encoding utf8
Write-Host "Installation v$version complete. Configuration files: $configDir" -ForegroundColor Green
