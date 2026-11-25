# 🔐 Security Policy  
Cloudflare Network Diagnostic Tool • MCP Server • AppMaker Generator

This document defines the security expectations, reporting process, and hardening guidelines for this repository.  
The goal is to ensure safe execution of diagnostics, secure MCP server behavior, and protection of user systems.

---

## 📣 Reporting a Vulnerability

If you discover a security issue, **DO NOT** open a public GitHub Issue.

Instead, please report it privately using [GitHub's private vulnerability reporting](https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/security/advisories/new).

Please include:

- A clear description of the issue  
- Steps to reproduce  
- Impact assessment  
- Proof‑of‑concept (if applicable)  
- Suggested remediation (optional)

You will receive an acknowledgment within **48 hours** and a full response within **7 days**.

---

## 🧩 Supported Components

Security coverage applies to:

- **Python MCP Server** (`server/index.py`)
- **Node MCP Server** (`server/index.js`)
- **Installer Pack** (shell, PowerShell, Python, Node CLI)
- **Templates, Docs, and Tools**

---

## 🛠️ MCP Server Security Model

The MCP server is designed with a **restricted execution model**:

### ✔ Limited Execution Surface  
- Network access happens only through the tools below: DNS resolution, the
  caller-supplied DoH URL, a TCP connect to `1.1.1.1:443`, and the system trace utility  
- No arbitrary file system writes  
- No privileged system calls  
- No remote code execution pathways (no shell, no `eval`, no dynamic imports)  

### ✔ Tools Are Explicitly Whitelisted  
Only the tools implemented in `server/index.py` and `server/index.js` are exposed:

- `dns_check` — resolves IPv4/IPv6 addresses for a caller-supplied domain  
- `doh_test` — sends a request to a caller-supplied HTTP(S) DNS-over-HTTPS URL  
- `trace_route` — runs the system `traceroute` or `tracepath` for a host or IP  
- `health_score` — TCP connectivity check against `1.1.1.1:443`  
- `export_results` — formats a caller-supplied result object as JSON or CSV  

Every tool validates its arguments (types, required keys, no whitespace in
destinations, no credentials in URLs), and every network or process operation
has an explicit timeout.

### ✔ No Resource or Prompt Access  
The servers expose tools only. No MCP resources, prompts, or file templates are
served, and `trace_route` invokes its utility with an argv array rather than a
shell.

### ✔ No User Data Retention  
The MCP server does **not** store:

- personal data  
- diagnostic history  
- IP addresses  
- logs outside the local session  

---

## 🧰 Installer Security

All installers (shell, PowerShell, Python, Node CLI):

- Perform **local installation only**  
- Do **not** elevate privileges  
- Do **not** modify system files  
- Verify required dependencies (Python 3, Node.js)  
- Register MCP configs in user‑scoped directories only  

### Integrity Verification  
Each release includes:

- `mcp-installer-pack.tar.gz`
- `SHA256SUMS`

Users should verify:

```bash
sha256sum -c SHA256SUMS
```
