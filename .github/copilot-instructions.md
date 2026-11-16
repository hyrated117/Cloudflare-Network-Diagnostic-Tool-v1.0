# Copilot Instructions

- Prefer small, focused changes.
- Validate with the repo's CI commands before finalizing:
  - `python -m compileall -q server installers Tools reference`
  - `python -m json.tool server/mcp-server.json >/dev/null`
  - `python -m json.tool server/mcp-client.json >/dev/null`
  - `python -m json.tool installers/package.json >/dev/null`
  - `node --check server/index.js`
  - `node --check installers/cli.js`
- Keep Node server files as ES modules when using `import` syntax.
- Avoid broad or unnecessary network calls in diagnostic code.
- Document non-obvious logic and any security-sensitive behavior.
