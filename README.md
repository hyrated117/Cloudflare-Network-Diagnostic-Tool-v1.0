# Cloudflare-Network-Diagnostic-Tool-v1.0 (Pre-release)

---

## 🚀 **Overview**

The **Cloudflare Network Diagnostic Tool** is a high‑precision, privacy‑first diagnostic engine designed to give users **real insight** into their network performance.

Built for:

- Network engineers  
- Power users  
- Developers  
- Security analysts  
- Everyday users who want clarity  

All processing happens **on‑device**.  
No tracking.  
No analytics.  
No external servers.  
Ever.

---

## ⚡ **Features**

- DNS latency benchmarking  
- DoH (DNS‑over‑HTTPS) performance testing  
- Cloudflare Trace analysis  
- WARP detection & mode identification  
- Resolver benchmarking (Cloudflare, Google, Quad9, NextDNS)  
- Network health scoring  
- Developer console mode  
- JSON / JSONL / Minified / Pretty export  
- Encrypted‑style log storage  
- Automatic log cleanup  
- Cross‑platform output compatibility  
- Error‑resilient fallback logic  

Explore more:  
- **[Feature breakdown](ca://s?q=Explain_all_features_in_detail)**  
- **[Module system](ca://s?q=Generate_module_system_logic)**  

---

## 🧠 **Architecture**

The tool is built on a modular diagnostic engine:

- **Network Layer** — URLSession‑based tests  
- **Trace Layer** — Cloudflare PoP + WARP parsing  
- **Benchmark Layer** — Multi‑resolver timed tests  
- **Health Layer** — Weighted scoring system  
- **Export Layer** — JSON encoder with multiple formats  
- **Logging Layer** — Base64‑encoded encrypted‑style logs  

View architecture:  
- **[SwiftUI engine architecture](ca://s?q=Generate_SwiftUI_app_architecture)**  

---

## 📦 **Output Formats**

The tool supports:

- JSON  
- JSONL  
- Minified JSON  
- Pretty JSON  
- MasterDict structured output  
- Developer console output  

Export logic:  
- **[Export system](ca://s?q=Generate_full_ExportService_swift)**  

---

## 🔐 **Privacy**

This tool is designed with **absolute privacy** in mind:

- No analytics  
- No tracking  
- No external data collection  
- No identifiers  
- No remote logging  
- All logs stored locally  
- All exports user‑controlled  

---

## 🛠️ **Installation**

### iOS Shortcut Version  
Import the `.shortcut` file directly into the Shortcuts app.

### App Version (SwiftUI)  
Clone the repository:

