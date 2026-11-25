# Python-specific MCP Server Installer for Windows

[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:APPDATA "Cloudflare-MCP")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source = Join-Path $repoRoot "server\index.py"
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Python server source not found: $source"
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py.exe -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3 is required but was not found on PATH." }

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$serverDir = Join-Path $InstallDir "server"
$configDir = Join-Path $InstallDir "config"
New-Item -ItemType Directory -Path $serverDir, $configDir -Force | Out-Null
$destination = Join-Path $serverDir "index.py"
Copy-Item -LiteralPath $source -Destination $destination -Force

$pythonCommand = $python.Source
$serverConfig = @{
    name = "Cloudflare Network Diagnostic Tool"
    version = "1.0.1"
    description = "MCP server for Cloudflare network diagnostics"
    type = "stdio"
    command = $pythonCommand
    args = @($destination)
    env = @{ PYTHONUNBUFFERED = "1" }
}
$clientConfig = @{
    name = "Cloudflare Diagnostic Client"
    version = "1.0.1"
    description = "MCP Client configuration for Cloudflare Network Diagnostic Tool"
    servers = @{
        "cloudflare-diagnostics" = @{
            command = $pythonCommand
            args = @($destination)
            env = @{ PYTHONUNBUFFERED = "1" }
        }
    }
}
$serverConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $configDir "mcp-server.json") -Encoding utf8
$clientConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $configDir "mcp-client.json") -Encoding utf8
Write-Host "Python MCP server installed at $destination" -ForegroundColor Green
Write-Host "MCP configuration files are in $configDir" -ForegroundColor Green
