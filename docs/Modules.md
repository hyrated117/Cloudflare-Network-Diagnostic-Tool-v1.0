# Modules Documentation

This document provides a comprehensive overview of all diagnostic modules available in the Cloudflare Network Diagnostic Tool.

## Available Modules

### 1. DNS Module

**Purpose**: Diagnose DNS resolution and configuration issues.

**Features**:
- DNS A, AAAA, MX, NS, SOA record lookups
- Multiple resolver support
- Response time measurement
- Cache analysis
- DNSSEC validation

**Usage**:
```swift
let dnsModule = DNSModule()
let results = try await dnsModule.resolveDomain("example.com")
```

### 2. DoH (DNS-over-HTTPS) Module

**Purpose**: Test and validate DNS-over-HTTPS endpoints.

**Features**:
- Endpoint availability checking
- Query performance measurement
- Response validation
- TLS certificate verification
- RFC compliance testing

**Configuration**:
```json
{
  "endpoint": "https://1.1.1.1/dns-query",
  "timeout": 5000,
  "retries": 3
}
```

### 3. Trace Module

**Purpose**: Perform network path analysis and traceroute.

**Features**:
- ICMP/TCP traceroute
- Hop-by-hop latency measurement
- ASN identification
- Geographic mapping
- Route optimization suggestions

### 4. WARP Module

**Purpose**: Diagnose Cloudflare WARP connection health.

**Features**:
- Connection status verification
- Split tunneling configuration
- DNS settings validation
- Performance metrics
- Fallback mechanism testing

### 5. Resolver Benchmark Module

**Purpose**: Compare DNS resolver performance.

**Features**:
- Multi-resolver performance testing
- Query speed comparison
- Consistency validation
- Load distribution analysis
- Recommendations for optimal resolver

### 6. Health Score Module

**Purpose**: Calculate overall network health metrics.

**Features**:
- Composite health calculation
- Component-wise scoring
- Trend analysis
- Alert generation
- Recommendations engine

---

## Module Configuration

Each module can be configured via `ModuleConfig.swift`:

```swift
struct ModuleConfig {
    let enabled: Bool
    let timeout: TimeInterval
    let retryCount: Int
    let cacheDuration: TimeInterval
    let customSettings: [String: Any]
}
```

## Adding Custom Modules

To create a custom diagnostic module:

1. Create a new file in `SwiftUI-App/Engine/`
2. Implement the `DiagnosticModule` protocol
3. Register in `DiagnosticEngine.swift`
4. Add configuration to `ModuleConfig.swift`

## Module Performance Considerations

- Modules run concurrently for optimal performance
- Results are cached to reduce redundant operations
- Large datasets are paginated
- Network operations have configurable timeouts
