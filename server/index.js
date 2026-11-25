#!/usr/bin/env node

/** Cloudflare network diagnostics over newline-delimited JSON-RPC on stdio. */
import { execFileSync } from 'node:child_process';
import dns from 'node:dns';
import net from 'node:net';
import { pathToFileURL } from 'node:url';

const PROTOCOL_VERSION = '2024-11-05';
const TRACE_TIMEOUT_MS = 20000;
const MAX_DOH_BYTES = 65536;
const timestamp = () => new Date().toISOString();
const log = (...args) => console.error(...args);

// Windows ships tracert rather than traceroute. -d skips reverse DNS and -h/-w
// bound a full run well inside the timeout.
const traceCandidates = (platform = process.platform) => (platform === 'win32'
  ? [['tracert', ['-d', '-h', '15', '-w', '300']]]
  : [['traceroute', []], ['tracepath', []]]);

const isDirectExecution = () => {
  const argv1 = process.argv[1];
  if (!argv1) return false;
  try {
    return import.meta.url === pathToFileURL(argv1).href;
  } catch {
    return false;
  }
};

class DiagnosticServer {
  constructor() {
    this.version = '1.0.1';
    this.name = 'Cloudflare Network Diagnostic Tool';
    this.tools = {
      dns_check: {
        description: 'Resolve IPv4 and IPv6 addresses for a domain.',
        inputSchema: { type: 'object', properties: { domain: { type: 'string', description: 'Domain name to resolve' } }, required: ['domain'], additionalProperties: false },
        run: (args) => this.dnsCheck(args.domain),
      },
      doh_test: {
        description: 'Send a request to a DNS-over-HTTPS endpoint.',
        inputSchema: { type: 'object', properties: { url: { type: 'string', format: 'uri', description: 'HTTP(S) DoH endpoint URL' } }, required: ['url'], additionalProperties: false },
        run: (args) => this.dohTest(args.url),
      },
      trace_route: {
        description: 'Run traceroute or tracepath to a destination when available.',
        inputSchema: { type: 'object', properties: { destination: { type: 'string', description: 'Host or IP address' } }, required: ['destination'], additionalProperties: false },
        run: (args) => this.traceRoute(args.destination),
      },
      health_score: {
        description: 'Check TCP connectivity to Cloudflare DNS and return a basic health result.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
        run: () => this.healthScore(),
      },
      export_results: {
        description: 'Format diagnostic results as JSON or CSV.',
        inputSchema: { type: 'object', properties: { format: { type: 'string', enum: ['json', 'csv'] }, results: { type: 'object', description: 'Diagnostic payload to export' } }, additionalProperties: false },
        run: (args) => this.exportResults(args.format, args.results),
      },
    };
  }

  async dnsCheck(domain) {
    if (typeof domain !== 'string' || !domain.trim()) throw new TypeError('domain must be a non-empty string');
    const host = domain.trim();
    const results = await Promise.allSettled([
      dns.promises.resolve4(host),
      dns.promises.resolve6(host),
    ]);
    const addresses = [...new Set(results.flatMap((result) => result.status === 'fulfilled' ? result.value : []))];
    const errors = results.filter((result) => result.status === 'rejected').map((result) => result.reason.message);
    return { tool: 'dns_check', domain: host, status: addresses.length ? 'ok' : 'error', addresses, ...(addresses.length ? {} : { error: errors.join('; ') || 'No addresses found' }), timestamp: timestamp() };
  }

  async dohTest(input) {
    let url;
    try {
      url = new URL(input);
    } catch {
      throw new TypeError('url must be a valid HTTP(S) URL');
    }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
      throw new TypeError('url must use HTTP or HTTPS and must not contain credentials');
    }
    try {
      const response = await fetch(url, {
        headers: { Accept: 'application/dns-json', 'User-Agent': 'Cloudflare-Diagnostic-Tool/1.0' },
        signal: AbortSignal.timeout(5000),
      });
      // Stop reading at the cap so a remote endpoint cannot make this process
      // buffer an unbounded body; the over-cap case is a tool result, not a
      // protocol error, the same way a timeout is.
      const chunks = [];
      let size = 0;
      for await (const chunk of response.body ?? []) {
        size += chunk.length;
        if (size > MAX_DOH_BYTES) {
          return { tool: 'doh_test', url: url.toString(), status: 'error', statusCode: response.status, error: 'DoH response exceeded 64 KiB limit', timestamp: timestamp() };
        }
        chunks.push(chunk);
      }
      const body = Buffer.concat(chunks, size).toString('utf8');
      let data;
      try { data = JSON.parse(body); } catch { data = { raw: body.slice(0, 4096) }; }
      return { tool: 'doh_test', url: url.toString(), status: response.ok ? 'ok' : 'error', statusCode: response.status, response: data, timestamp: timestamp() };
    } catch (error) {
      return { tool: 'doh_test', url: url.toString(), status: 'error', error: error.message, timestamp: timestamp() };
    }
  }

  async traceRoute(destination) {
    if (typeof destination !== 'string' || !destination.trim() || /[\s\0]/.test(destination) || destination.trim().startsWith('-')) {
      throw new TypeError("destination must be a non-empty host or IP without whitespace and must not start with '-'");
    }
    const target = destination.trim();
    for (const [command, fixedArgs] of traceCandidates()) {
      try {
        const output = execFileSync(command, [...fixedArgs, target], { encoding: 'utf8', timeout: TRACE_TIMEOUT_MS, stdio: ['ignore', 'pipe', 'pipe'] });
        return { tool: 'trace_route', destination: target, status: 'ok', output: output.trim(), timestamp: timestamp() };
      } catch (error) {
        if (error?.code === 'ENOENT') continue;
        return { tool: 'trace_route', destination: target, status: 'error', error: error?.stderr?.toString().trim() || error?.message, timestamp: timestamp() };
      }
    }
    return { tool: 'trace_route', destination: target, status: 'unavailable', message: 'No traceroute, tracepath or tracert utility available on this system.', timestamp: timestamp() };
  }

  async healthScore() {
    const reachable = await new Promise((resolve) => {
      const socket = net.createConnection({ host: '1.1.1.1', port: 443, timeout: 3000 });
      socket.once('connect', () => { socket.destroy(); resolve(true); });
      socket.once('timeout', () => { socket.destroy(); resolve(false); });
      socket.once('error', () => resolve(false));
    });
    return { tool: 'health_score', score: reachable ? 95 : 64, status: reachable ? 'healthy' : 'degraded', reachable, timestamp: timestamp() };
  }

  async exportResults(format = 'json', results = {}) {
    if (!['json', 'csv'].includes(format)) throw new TypeError("format must be 'json' or 'csv'");
    if (results === null || typeof results !== 'object' || Array.isArray(results)) throw new TypeError('results must be an object');
    let content;
    if (format === 'json') {
      content = JSON.stringify(results, null, 2);
    } else {
      // Strings verbatim, every other value as compact JSON, matching the Python server.
      const cell = (value) => {
        const text = typeof value === 'string' ? value : JSON.stringify(value);
        return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
      };
      content = ['name,value', ...Object.entries(results).map(([key, value]) => `${cell(key)},${cell(value)}`)].join('\n');
    }
    return { tool: 'export_results', format, status: 'ok', content, timestamp: timestamp() };
  }

  async callTool(name, args) {
    const tool = this.tools[name];
    if (!tool) throw new Error(`Unknown tool '${name}'`);
    if (!args || typeof args !== 'object' || Array.isArray(args)) throw new TypeError('arguments must be a JSON object');
    for (const key of tool.inputSchema.required || []) {
      if (!(key in args)) throw new TypeError(`Missing required argument '${key}'`);
    }
    const allowed = new Set(Object.keys(tool.inputSchema.properties ?? {}));
    const unexpected = Object.keys(args).filter((key) => !allowed.has(key)).sort();
    if (unexpected.length) throw new TypeError(`Unexpected argument '${unexpected[0]}'`);
    return tool.run(args);
  }

  async processMessage(message) {
    if (!message || typeof message !== 'object' || Array.isArray(message) || message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
      return { jsonrpc: '2.0', id: message?.id ?? null, error: { code: -32600, message: 'Invalid Request' } };
    }
    const notification = !Object.hasOwn(message, 'id');
    const id = message.id ?? null;
    const params = message.params === undefined ? {} : message.params;
    if (params === null || typeof params !== 'object' || Array.isArray(params)) {
      return notification ? null : { jsonrpc: '2.0', id, error: { code: -32602, message: 'params must be an object' } };
    }

    let result;
    try {
      switch (message.method) {
        case 'initialize':
          result = { protocolVersion: PROTOCOL_VERSION, capabilities: { tools: {} }, serverInfo: { name: this.name, version: this.version } };
          break;
        case 'notifications/initialized':
          return null;
        case 'ping':
          result = {};
          break;
        case 'tools/list':
          result = { tools: Object.entries(this.tools).map(([name, tool]) => ({ name, description: tool.description, inputSchema: tool.inputSchema })) };
          break;
        case 'tools/call': {
          const output = await this.callTool(params.name, params.arguments ?? {});
          result = { content: [{ type: 'text', text: JSON.stringify(output) }], structuredContent: output, isError: output.status === 'error' };
          break;
        }
        default:
          if (notification) return null;
          return { jsonrpc: '2.0', id, error: { code: -32601, message: `Method not found: ${message.method}` } };
      }
      return notification ? null : { jsonrpc: '2.0', id, result };
    } catch (error) {
      return notification ? null : { jsonrpc: '2.0', id, error: { code: -32602, message: error.message } };
    }
  }

  async run(input = process.stdin, output = process.stdout) {
    let buffer = '';
    for await (const chunk of input) {
      buffer += chunk;
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? '';
      for (const line of lines) await this.handleLine(line, output);
    }
    if (buffer.trim()) await this.handleLine(buffer, output);
  }

  async handleLine(line, output) {
    if (!line.trim()) return;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      output.write(`${JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error' } })}\n`);
      return;
    }
    const response = await this.processMessage(message);
    if (response !== null) output.write(`${JSON.stringify(response)}\n`);
  }
}

if (isDirectExecution()) {
  new DiagnosticServer().run().catch((error) => {
    log('Server error:', error);
    process.exitCode = 1;
  });
}

export default DiagnosticServer;
