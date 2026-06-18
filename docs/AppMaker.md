# AppMaker Generator

The AppMaker is a powerful tool for generating complete SwiftUI applications on demand. It allows you to create customized diagnostic applications with your own branding and module selections.

## Overview

AppMaker simplifies the process of:
- Creating new SwiftUI projects
- Injecting diagnostic modules
- Applying custom branding
- Packaging complete applications

## Project Generation

### Basic Generation

```swift
let generator = ProjectGenerator()
let config = GenerationConfig(
    projectName: "MyDiagnosticApp",
    bundleIdentifier: "com.example.diagnostics",
    deploymentTarget: "13.0"
)
let projectPath = try generator.generateProject(config: config)
```

### Advanced Configuration

```swift
var config = GenerationConfig(
    projectName: "Enterprise Diagnostics",
    bundleIdentifier: "com.enterprise.diagnostics",
    deploymentTarget: "14.0"
)

config.modules = [
    .dns,
    .doh,
    .trace,
    .warp,
    .healthScore
]

config.branding = BrandingConfig(
    appName: "Enterprise Diagnostics",
    organizationName: "Acme Corp",
    primaryColor: Color(red: 0.2, green: 0.4, blue: 0.8),
    accentColor: Color(red: 0.8, green: 0.2, blue: 0.2)
)

config.features = [
    .export,
    .scheduling,
    .notifications,
    .cloudSync
]
```

## Module Injection

### Selecting Modules

```swift
config.modules = [
    .dns,              // DNS resolution diagnostics
    .doh,              // DNS-over-HTTPS testing
    .trace,            // Traceroute analysis
    .warp,             // WARP connection health
    .resolverBench,    // Resolver performance
    .healthScore       // Overall health metrics
]
```

### Custom Module Injection

```swift
let customModule = ModuleDefinition(
    name: "Custom Performance Test",
    identifier: "custom_perf_test",
    icon: "gauge",
    description: "Custom performance testing module"
)

try moduleInjector.injectModule(customModule, into: projectPath)
```

## File Generation

### Project Structure

The generator creates a complete Xcode project with:
```
GeneratedApp.xcodeproj/
├── GeneratedApp.swift              # App entry point
├── ContentView.swift               # Main UI
├── Models/
│   ├── DiagnosticResult.swift
│   ├── ModuleConfig.swift
│   └── AppDefinition.swift
├── Engine/
│   └── DiagnosticEngine.swift
├── Services/
│   ├── NetworkService.swift
│   ├── LogService.swift
│   └── ExportService.swift
├── Theme/
│   └── ThemeManager.swift
├── Utilities/
│   └── Extensions.swift
└── Assets.xcassets/
```

### Generated Files

```swift
let fileWriter = FileWriter()
try fileWriter.writeFile(
    content: swiftCode,
    to: "App.swift",
    in: projectPath
)
```

## Build and Packaging

### Compression

```swift
let compressor = ZipCompressor()
let zipPath = try compressor.compress(
    projectPath,
    to: "GeneratedApp.zip"
)
```

### Output Structure

```
output/
├── GeneratedApp.xcodeproj/
├── GeneratedApp.zip
└── metadata.json
```

## UUID Management

AppMaker automatically generates unique identifiers:

```swift
let uuidGenerator = UUIDGenerator()
let projectId = uuidGenerator.generateProjectUUID()
let moduleIds = uuidGenerator.generateModuleUUIDs(count: moduleCount)
```

## Customization Options

### Branding

- App name and description
- Primary and accent colors
- Custom icons and assets
- Organization information
- Support URLs and contacts

### Features

- Export functionality
- Scheduled diagnostics
- Push notifications
- Cloud synchronization
- Advanced analytics

### UI Customization

- Theme selection (light/dark/auto)
- Font preferences
- Layout options
- Custom views and components

## Workflow Example

```swift
// 1. Create generator
let generator = ProjectGenerator()

// 2. Configure project
var config = GenerationConfig(projectName: "MyApp")
config.modules = [.dns, .trace, .healthScore]
config.branding = customBranding

// 3. Generate project
let projectPath = try generator.generateProject(config: config)

// 4. Compress output
let compressor = ZipCompressor()
let outputZip = try compressor.compress(projectPath, to: "MyApp.zip")

// 5. Return to user
return outputZip
```

## CLI Usage

```bash
# Generate app with default settings
cloudflare-mcp appmaker generate --name "MyApp"

# Generate with custom modules
cloudflare-mcp appmaker generate \
  --name "MyApp" \
  --modules dns,trace,warp \
  --theme dark

# Generate with branding
cloudflare-mcp appmaker generate \
  --name "MyApp" \
  --org "Acme Corp" \
  --color-primary "#0066ff" \
  --color-accent "#ff0066"
```

## Best Practices

1. **Version Management**: Always specify deployment targets
2. **Module Selection**: Choose only needed modules for smaller app size
3. **Branding**: Use official colors and guidelines
4. **Testing**: Build and test generated apps before distribution
5. **Documentation**: Provide users with setup instructions
