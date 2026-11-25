# Export

The only export feature in this repository is the `export_results` MCP tool. It
formats a result object the caller passes in and returns the text — it does not
write, compress or encrypt files.

Two formats are supported: `json` and `csv`.

## JSON

`format: "json"` (the default) pretty-prints the object with two-space indentation.

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call",
 "params":{"name":"export_results","arguments":{"format":"json","results":{"ok":true}}}}
```

```json
{"tool":"export_results","format":"json","status":"ok",
 "content":"{\n  \"ok\": true\n}","timestamp":"…"}
```

## CSV

`format: "csv"` writes a `name,value` table, one row per top-level key. Objects and
arrays are JSON-encoded inside the cell.

```json
{"name":"export_results","arguments":{"format":"csv","results":{"dns":"ok","trace":2}}}
```

```csv
name,value
dns,ok
trace,2
```

Node builds the CSV by hand, quoting `"` as `""`; Python uses the `csv` module. Both
quote a cell containing a comma, a double quote, LF or CR, so the two servers produce
byte-identical CSV. Both flatten only the top level, so nested structures arrive as
JSON text in a single cell.

## Constraints

- `results` must be a JSON object (arrays are rejected).
- `format` must be `json` or `csv`; any other value returns a `-32602` error.
- Nothing is written to disk and no size limit is applied to the formatted output.

## Planned (not implemented)

Earlier documentation described PDF reports, compression, encryption, scheduled
exports and a SwiftUI `ExportService`/`ExportOptions` API. None of that exists in
this repository — there is no PDF code path and no export service outside the
`export_results` tool.
