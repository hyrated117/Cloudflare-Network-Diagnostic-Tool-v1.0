# Performance Guide

## Overview

This guide provides best practices for optimizing the performance of the Cloudflare Network Diagnostic Tool.

## Performance Optimization

### 1. Concurrent Module Execution

Modules run in parallel for faster diagnostics:

```swift
async let dnsResult = dnsModule.run()
async let dohResult = dohModule.run()
async let traceResult = traceModule.run()

let results = await (dnsResult, dohResult, traceResult)
```

### 2. Result Caching

```swift
let cache = DiagnosticCache()
cache.set(key: "dns_example.com", value: result, ttl: 300)

if let cached = cache.get(key: "dns_example.com") {
    return cached
}
```

### 3. Network Optimization

- Configurable timeouts
- Connection pooling
- DNS prefetching
- HTTP/2 multiplexing

### 4. Memory Management

- Lazy loading of large datasets
- Automatic cleanup of old results
- Memory-efficient data structures
- Streaming for large exports

## Benchmarking

### Running Benchmarks

```swift
let benchmark = PerformanceBenchmark()
benchmark.start()

// Run diagnostics
let results = try await engine.runDiagnostics()

benchmark.stop()
print("Total time: \(benchmark.duration)ms")
```

### Performance Metrics

| Operation | Target | Typical |
|-----------|--------|----------|
| DNS Check | < 500ms | 200ms |
| DoH Test | < 1000ms | 400ms |
| Traceroute | < 5s | 2-3s |
| Health Score | < 2s | 1s |
| Full Diagnostic | < 10s | 5-7s |

## Configuration for Performance

### Aggressive (Fast)

```swift
let config = PerformanceConfig(
    timeout: 3000,
    retries: 1,
    cacheEnabled: true,
    concurrency: .aggressive
)
```

### Balanced (Default)

```swift
let config = PerformanceConfig(
    timeout: 5000,
    retries: 2,
    cacheEnabled: true,
    concurrency: .balanced
)
```

### Thorough (Comprehensive)

```swift
let config = PerformanceConfig(
    timeout: 10000,
    retries: 3,
    cacheEnabled: true,
    concurrency: .limited
)
```

## Best Practices

1. **Use appropriate timeouts** based on network conditions
2. **Enable caching** for repeated diagnostics
3. **Run modules concurrently** when possible
4. **Monitor memory usage** with large datasets
5. **Profile regularly** using Xcode Instruments

## Advanced Optimization

See [PERFORMANCE-OPTIMIZATION.md](./PERFORMANCE-OPTIMIZATION.md) for advanced techniques.
