#!/usr/bin/env node

/** Cloudflare network diagnostics over newline-delimited JSON-RPC on stdio. */
import { execFileSync } from 'node:child_process';
import dns from 'node:dns';
import net from 'node:net';

const PROTOCOL_VERSION = '2024-11-05';
const timestamp = () => new Date().toISOString();
const log = (...args) => console.error(...args);

class DiagnosticServer {
  constructor() {
    this.version = '1.0.0';
    this.name = 'Cloudflare Network Diagnostic Tool';
    this.tools = {
      dns_check: {
        description: 'Resolve IPv4 and IPv6 addresses for a domain.',
        inputSchema: { type: 'object', properties: { domain: { type: 'string' } }, required: ['domain'], additionalProperties: false },
        run: (args) => this.dnsCheck(args.domain),
      },
      doh_test: {
        description: 'Send a request to a DNS-over-HTTPS endpoint.',
        inputSchema: { type: 'object', properties: { url: { type: 'string', format: 'uri' } }, required: ['url'], additionalProperties: false },
        run: (args) => this.dohTest(args.url),
      },
      trace_route: {
        description: 'Run traceroute or tracepath to a destination when available.',
        inputSchema: { type: 'object', properties: { destination: { type: 'string' } }, required: ['destination'], additionalProperties: false },
        run: (args) => this.traceRoute(args.destination),
      },
      health_score: {
        description: 'Check TCP connectivity to Cloudflare DNS and return a basic health result.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
        run: () => this.healthScore(),
      },
      export_results: {
        description: 'Format diagnostic results as JSON or CSV.',
        inputSchema: { type: 'object', properties: { format: { type: 'string', enum: ['json', 'csv'] }, results: { type: 'object' } }, additionalProperties: false },
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
      const body = await response.text();
      let data;
      try { data = JSON.parse(body); } catch { data = { raw: body.slice(0, 4096) }; }
      return { tool: 'doh_test', url: url.toString(), status: response.ok ? 'ok' : 'error', statusCode: response.status, response: data, timestamp: timestamp() };
    } catch (error) {
      return { tool: 'doh_test', url: url.toString(), status: 'error', error: error.message, timestamp: timestamp() };
    }
  }

  async traceRoute(destination) {
    if (typeof destination !== 'string' || !destination.trim() || /[\s\0]/.test(destination)) {
      throw new TypeError('destination must be a non-empty host or IP without whitespace');
    }
    for (const command of ['traceroute', 'tracepath']) {
      try {
        const output = execFileSync(command, [destination], { encoding: 'utf8', timeout: 20000, stdio: ['ignore', 'pipe', 'pipe'] });
        return { tool: 'trace_route', destination, status: 'ok', output: output.trim(), timestamp: timestamp() };
      } catch (error) {
        if (error.code === 'ENOENT') continue;
        return { tool: 'trace_route', destination, status: 'error', error: error.stderr?.toString().trim() || error.message, timestamp: timestamp() };
      }
    }
    return { tool: 'trace_route', destination, status: 'unavailable', message: 'No traceroute or tracepath utility available on this system.', timestamp: timestamp() };
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
      const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
      content = ['name,value', ...Object.entries(results).map(([key, value]) => `${escape(key)},${escape(typeof value === 'object' ? JSON.stringify(value) : value)}`)].join('\n');
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
    return tool.run(args);
  }

  async processMessage(message) {
    if (!message || typeof message !== 'object' || Array.isArray(message) || message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
      return { jsonrpc: '2.0', id: message?.id ?? null, error: { code: -32600, message: 'Invalid Request' } };
    }
    const notification = !Object.hasOwn(message, 'id');
    const id = message.id ?? null;
    const params = message.params ?? {};
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

if (import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  new DiagnosticServer().run().catch((error) => {
    log('Server error:', error);
    process.exitCode = 1;
  });
}

export default DiagnosticServer;
