# Troubleshooting Guide

## Common Issues and Solutions

### DNS Module

**Issue**: DNS queries timing out

**Solutions**:
1. Check internet connectivity
2. Verify DNS server configuration
3. Increase timeout value
4. Try alternative DNS resolver

**Code**:
```swift
let config = ModuleConfig(
    enabled: true,
    timeout: 10000, // Increase timeout
    retryCount: 3
)
```

### DoH Module

**Issue**: DoH endpoint returns 403 Forbidden

**Causes**:
- Rate limiting
- Invalid query format
- Endpoint authentication required

**Solutions**:
1. Implement backoff strategy
2. Verify query format compliance
3. Check endpoint documentation
4. Contact endpoint provider

### Trace Module

**Issue**: Traceroute incomplete or hanging

**Common Causes**:
- Firewall blocking ICMP
- TTL limit too low
- Network unreachable

**Solutions**:
```swift
let config = TraceConfig(
    maxHops: 30,
    timeout: 3000,
    useTCP: true // Try TCP if ICMP blocked
)
```

### WARP Module

**Issue**: WARP not connecting

**Solutions**:
1. Check WARP installation
2. Verify network connectivity
3. Check firewall rules
4. Review WARP logs

### Export Issues

**Issue**: PDF export failing

**Solutions**:
1. Check available disk space
2. Verify file permissions
3. Reduce data size
4. Update PDFKit

**Code**:
```swift
do {
    let pdfData = try exporter.exportAsPDF(results)
} catch let error as ExportError {
    switch error {
    case .insufficientSpace:
        // Handle space issue
    case .permissionDenied:
        // Handle permission issue
    default:
        break
    }
}
```

## Logging and Diagnostics

### Enable Debug Logging

```swift
LogService.setLevel(.debug)
LogService.enableFileLogging()
```

### Access Logs

```swift
let logFile = LogService.getLogFilePath()
print("Logs available at: \(logFile)")
```

## Performance Issues

### Slow Diagnostics

**Causes**:
- Network congestion
- High concurrency
- Large dataset processing

**Solutions**:
1. Reduce module count
2. Lower concurrency
3. Enable caching
4. Check network connectivity

### High Memory Usage

**Solutions**:
1. Reduce batch size
2. Enable result streaming
3. Clear cache periodically
4. Monitor with Instruments

## Getting Help

1. **Check existing issues**: [GitHub Issues](https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/issues)
2. **Review documentation**: [Docs](./)
3. **File new issue**: Provide logs and reproduction steps
4. **Contact support**: See SECURITY.md for contact methods

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| ERR_001 | Network timeout | Increase timeout, check connectivity |
| ERR_002 | DNS resolution failed | Check DNS configuration |
| ERR_003 | Permission denied | Check file/network permissions |
| ERR_004 | Invalid configuration | Review config file syntax |
| ERR_005 | Resource unavailable | Check disk space, memory |

## Debugging Tips

1. **Use Xcode Debugger**: Set breakpoints and inspect state
2. **Enable Console Logging**: View real-time output
3. **Check Network Tab**: Inspect HTTP requests
4. **Profile Memory**: Use Instruments for memory leaks
5. **Review Logs**: Check application logs for errors
