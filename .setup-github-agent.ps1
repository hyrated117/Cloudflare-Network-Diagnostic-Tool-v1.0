# Cloudflare Network Diagnostic Tool
# GitHub Copilot/SWE Agent Repository Setup

Write-Host "Creating GitHub automation files..." -ForegroundColor Cyan

# Create folders
New-Item -ItemType Directory -Force -Path ".github" | Out-Null
New-Item -ItemType Directory -Force -Path ".github\ISSUE_TEMPLATE" | Out-Null
New-Item -ItemType Directory -Force -Path ".github\workflows" | Out-Null

# Copilot Instructions
@'
# Cloudflare Network Diagnostic Tool

## Project Overview

Windows-based network diagnostic utility focused on Cloudflare connectivity, DNS, latency, routing and troubleshooting.

## Development Guidelines

- Maintain compatibility with Windows 10 and Windows 11.
- Prefer PowerShell-native commands.
- Keep code readable and documented.
- Avoid unnecessary dependencies.
- Add error handling for all network operations.
- Preserve backwards compatibility.

## Testing Requirements

- Verify DNS tests function correctly.
- Verify Cloudflare endpoints are reachable.
- Verify traceroute operations complete successfully.
- Verify graceful handling of network failures.
'@ | Set-Content ".github\copilot-instructions.md"

# Bug Report Template
@'
---
name: Bug Report
about: Report a problem with the diagnostic tool
title: "[BUG] "
labels: bug
---

## Description

Describe the bug.

## Steps To Reproduce

1.
2.
3.

## Expected Behaviour

Describe what should happen.

## Actual Behaviour

Describe what happened.

## Environment

- Windows Version:
- PowerShell Version:
- Tool Version:

## Logs / Screenshots

Paste output here.
'@ | Set-Content ".github\ISSUE_TEMPLATE\bug_report.md"

# Feature Request Template
@'
---
name: Feature Request
about: Suggest a new feature
title: "[FEATURE] "
labels: enhancement
---

## Feature Summary

Describe the feature.

## Problem It Solves

Describe the problem.

## Proposed Solution

Describe the solution.

## Additional Notes

Add extra details here.
'@ | Set-Content ".github\ISSUE_TEMPLATE\feature_request.md"

# Pull Request Template
@'
## Summary

Brief description of changes.

## Type of Change

- [ ] Bug Fix
- [ ] New Feature
- [ ] Documentation Update
- [ ] Refactor
- [ ] Other

## Testing

Describe testing completed.

- [ ] DNS Tests
- [ ] Connectivity Tests
- [ ] Latency Tests
- [ ] Error Handling Tests

## Checklist

- [ ] Documentation updated
- [ ] Testing completed
- [ ] Existing functionality preserved
'@ | Set-Content ".github\pull_request_template.md"

# Contributing
@'
# Contributing

Thank you for contributing to Cloudflare Network Diagnostic Tool.

## Getting Started

1. Fork repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## Standards

- Maintain Windows compatibility
- Follow existing code style
- Add error handling
- Keep output user-friendly
'@ | Set-Content "CONTRIBUTING.md"

# GitHub Actions Workflow
@'
name: Validation

on:
  push:
  pull_request:

jobs:
  validate:
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Validate PowerShell Scripts
        shell: pwsh
        run: |
          Get-ChildItem -Recurse -Filter *.ps1 |
          ForEach-Object {
            Write-Host "Checking $($_.Name)"
            [System.Management.Automation.PSParser]::Tokenize(
              (Get-Content $_.FullName -Raw),
              [ref]$null
            ) | Out-Null
          }
'@ | Set-Content ".github\workflows\ci.yml"

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "git add ."
Write-Host "git commit -m 'Add Copilot and SWE-agent repository configuration'"
Write-Host "git push"