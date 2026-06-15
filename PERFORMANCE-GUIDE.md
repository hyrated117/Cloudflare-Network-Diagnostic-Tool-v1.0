# ⚡ Performance Guide  
Cloudflare Network Diagnostic Tool • MCP Server • AppMaker Generator

This guide defines the performance expectations, benchmarks, optimization strategies, and profiling workflows for all components of this repository.  
It ensures the diagnostic engine, SwiftUI app, MCP server, and AppMaker generator run efficiently across macOS, Linux, and Windows.

---

# 📊 Performance Objectives

The system is designed to meet the following performance targets:

### SwiftUI Diagnostic App
- App launch time: **< 500ms**
- Diagnostic engine execution: **< 2.5s average**
- JSON export: **< 50ms**
- UI frame rate: **60 FPS stable**
- Memory footprint: **< 150MB**

### MCP Server (Python/Node)
- Cold start: **< 200ms**
- Tool invocation latency: **< 100ms**
- Resource read latency: **< 10ms**
- Zero memory leaks across long sessions

### AppMaker Generator
- Project generation: **< 1.2s**
- Module injection: **< 200ms**
- ZIP compression: **< 300ms**

---

# 🧠 Architecture-Level Performance Principles

### 1. **Zero Blocking on Main Thread**
SwiftUI must never block the UI thread.  
All diagnostics run on background queues.

### 2. **Immutable Data Models**
`AllResults`, `DiagnosticResult`, and `ModuleConfig` use value semantics for predictable performance.

### 3. **Lazy Loading**
- Templates  
- Documentation  
- Assets  
- Large JSON structures  

Loaded only when needed.

### 4. **Streaming MCP Responses**
The MCP server streams results instead of buffering large payloads.

### 5. **No Redundant File I/O**
All file writes are atomic and deduplicated.

---

# 🚀 SwiftUI Performance Optimizations

### ✔ Use `@MainActor` only for UI  
All heavy work stays off the main thread.

### ✔ Avoid unnecessary view recomputation  
Use:
- `@StateObject`
- `@ObservedObject`
- `@EnvironmentObject`
- `EquatableView`

### ✔ Precompute expensive values  
DNS results, WARP status, and trace logs are preprocessed before UI binding.

### ✔ Asset optimization  
- App icons pre‑resized  
- Colorsets compressed  
- No runtime image scaling

---

# 🧩 MCP Server Performance Optimizations

### ✔ Persistent process model  
The server stays warm to avoid cold‑start penalties.

### ✔ Preloaded resources  
Templates and docs are cached in memory.

### ✔ Zero‑copy JSON  
Python uses:
- `orjson` (if available)  
- fallback to `json`  

Node uses:
- `JSON.stringify()` with stable ordering

### ✔ Minimal IPC overhead  
Transport: **stdio**  
No sockets, no HTTP overhead.

---

# 🛠️ AppMaker Generator Performance Optimizations

### ✔ Template caching  
Templates are loaded once and reused.

### ✔ Parallel file writing  
FileWriter uses concurrent queues.

### ✔ UUID batching  
UUIDs are generated in batches to reduce system calls.

### ✔ ZIP compression tuned  
Compression level optimized for speed, not maximum ratio.

---

# 📦 Installer Performance Guidelines

### ✔ No unnecessary downloads  
All installers operate locally.

### ✔ Dependency checks are O(1)  
Only `python3` and `swift` are validated.

### ✔ No global system modifications  
Everything installs into:

