# Architecture

## Overview
The system is composed of four major layers:

1. **Core Diagnostic Engine**  
2. **Cloudflare API Layer**  
3. **SwiftUI App Layer**  
4. **App‑Maker Platform**

Each layer is modular, testable, and independently deployable.

---

## High‑Level Architecture Diagram


---

## Diagnostic Engine
The engine orchestrates all diagnostic modules.  
It supports:

- Parallel execution  
- Structured results  
- Severity scoring  
- Plugin‑based module loading

See **[Modules](ca://s?q=Explain_diagnostic_modules)** for details.

---

## Cloudflare API Layer
A unified wrapper around Cloudflare endpoints:

- DNS  
- WAF  
- Firewall  
- Analytics  
- Radar  
- Zero Trust  

Features:

- Automatic authentication  
- Retry logic  
- Error normalization  
- JSON decoding with strict validation  

---

## SwiftUI App Layer
The app provides:

- Real‑time diagnostic UI  
- Result summaries  
- Export options  
- Theming + dark mode  
- Modular views for each diagnostic module  

---

## App‑Maker Platform
A generator that creates:

- SwiftUI apps  
- Diagnostic modules  
- Project scaffolding  
- GitHub‑ready repos  

See **[AppMaker.md](ca://s?q=Show_AppMaker_documentation)**.

---
