# Export Functionality

The Cloudflare Network Diagnostic Tool supports multiple export formats for diagnostic results.

## Supported Formats

### JSON Export

**Format**: Standard JSON with nested structure

**Features**:
- Lossless data preservation
- Machine-readable format
- Schema validation
- Compression support

**Example**:
```json
{
  "diagnostic_run": {
    "timestamp": "2024-06-18T20:30:00Z",
    "version": "1.0.0",
    "modules": {
      "dns": { /* results */ },
      "doh": { /* results */ }
    }
  }
}
```

### CSV Export

**Format**: Comma-separated values for spreadsheet analysis

**Features**:
- Excel/Sheets compatibility
- Flattened structure
- Header row with field names
- Special character handling

**Use Cases**:
- Data analysis in spreadsheets
- Bulk reporting
- Historical comparison

### PDF Export

**Format**: Professional report with formatting

**Features**:
- Executive summary
- Visual charts and graphs
- Detailed findings
- Recommendations
- Branding customization

**Sections**:
1. Executive Summary
2. Diagnostic Results
3. Performance Metrics
4. Health Score
5. Recommendations
6. Appendix (Raw Data)

## Export API

```swift
let exporter = ExportService()

// JSON export
let jsonData = try exporter.exportAsJSON(results)

// CSV export
let csvString = try exporter.exportAsCSV(results)

// PDF export
let pdfData = try exporter.exportAsPDF(results, options: pdfOptions)
```

## Options and Customization

### General Options

```swift
struct ExportOptions {
    let format: ExportFormat
    let includeRawData: Bool
    let compression: CompressionType
    let filename: String?
    let includeMetadata: Bool
}
```

### PDF-Specific Options

```swift
struct PDFExportOptions {
    let pageSize: PDFPageSize
    let orientation: PDFOrientation
    let includeCharts: Bool
    let branding: BrandingInfo?
    let headerFooter: Bool
}
```

## Data Privacy in Exports

- Sensitive data can be redacted
- PII handling configurable
- Encryption support for sensitive exports
- GDPR compliance features

## Best Practices

1. **Choose appropriate format**:
   - JSON for data integration
   - CSV for analysis
   - PDF for sharing/documentation

2. **Secure sensitive exports**:
   - Use encryption for confidential data
   - Store securely
   - Set appropriate access controls

3. **Regular exports**:
   - Schedule periodic exports
   - Archive historical data
   - Monitor trends over time
