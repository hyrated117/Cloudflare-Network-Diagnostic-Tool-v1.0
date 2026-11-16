#!/usr/bin/env node

import { EventEmitter } from 'events';
import axios from 'axios';
import { execFileSync } from 'node:child_process';
import dns from 'node:dns';

class DiagnosticServer extends EventEmitter {
  constructor() {
    super();
    this.version = '1.0.0';
    this.name = 'Cloudflare Network Diagnostic Tool';
    this.tools = {
      dns_check: this.dnsCheck.bind(this),
      doh_test: this.dohTest.bind(this),
      trace_route: this.traceRoute.bind(this),
      health_score: this.healthScore.bind(this),
      export_results: this.exportResults.bind(this),
    };
    console.log(`${this.name} v${this.version} initialized`);
  }

  listTools() {
    return Object.entries(this.tools).map(([name, fn]) => ({
      name,
      description: fn.description || 'No description provided.',
      inputSchema: {
        type: 'object',
        properties: {},
        additionalProperties: true,
      },
    }));
  }

  async dnsCheck(domain) {
    console.log(`Running DNS check for ${domain}`);
    try {
      const addresses = await dns.promises.resolve4(domain);
      return {
        tool: 'dns_check',
        domain,
        status: 'ok',
        addresses: [...new Set(addresses)],
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        tool: 'dns_check',
        domain,
        status: 'error',
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  async dohTest(url) {
    console.log(`Testing DoH endpoint: ${url}`);
    try {
      const response = await axios.get(url, {
        headers: { Accept: 'application/dns-json' },
        timeout: 5000,
      });
      return {
        tool: 'doh_test',
        url,
        status: 'ok',
        statusCode: response.status,
        timestamp: new Date().toISOString(),
        response: response.data,
      };
    } catch (error) {
      return {
        tool: 'doh_test',
        url,
        status: 'error',
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  async traceRoute(destination) {
    console.log(`Tracing route to ${destination}`);
    const candidates = ['traceroute', 'tracepath'];
    const available = candidates.find((command) => {
      try {
        execFileSync('which', [command], { stdio: 'ignore' });
        return true;
      } catch {
        return false;
      }
    });

    if (!available) {
      return {
        tool: 'trace_route',
        destination,
        status: 'unavailable',
        message: 'No traceroute utility available on this system.',
        timestamp: new Date().toISOString(),
      };
    }

    try {
      const output = execFileSync(available, [destination], {
        encoding: 'utf8',
        timeout: 20000,
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      return {
        tool: 'trace_route',
        destination,
        status: 'ok',
        output: output.trim() || 'No output captured',
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      return {
        tool: 'trace_route',
        destination,
        status: 'error',
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  async healthScore() {
    console.log('Calculating health score');
    try {
      await dns.promises.lookup('1.1.1.1', { family: 4 });
      return {
        tool: 'health_score',
        score: 95,
        status: 'healthy',
        reachable: true,
        timestamp: new Date().toISOString(),
      };
    } catch {
      return {
        tool: 'health_score',
        score: 64,
        status: 'degraded',
        reachable: false,
        timestamp: new Date().toISOString(),
      };
    }
  }

  async exportResults(format = 'json', results = {}) {
    console.log(`Exporting results in ${format} format`);
    let content;
    if (format === 'json') {
      content = JSON.stringify(results, null, 2);
    } else if (format === 'csv') {
      const rows = Object.entries(results).map(([key, value]) => `${key},${value}`);
      content = ['tool,name,value', ...rows].join('\n');
    } else {
      content = String(results);
    }

    return {
      tool: 'export_results',
      format,
      status: 'ok',
      content,
      timestamp: new Date().toISOString(),
    };
  }

  async callTool(name, args = {}) {
    if (!this.tools[name]) {
      throw new Error(`Unknown tool '${name}'`);
    }

    switch (name) {
      case 'dns_check':
        return this.tools[name](args.domain);
      case 'doh_test':
        return this.tools[name](args.url);
      case 'trace_route':
        return this.tools[name](args.destination);
      case 'health_score':
        return this.tools[name]();
      case 'export_results':
        return this.tools[name](args.format || 'json', args.results || {});
      default:
        return this.tools[name](args);
    }
  }

  processMessage(message) {
    const id = message?.id ?? null;
    const method = message?.method;
    const params = message?.params ?? {};

    if (method === 'initialize') {
      return {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: this.name, version: this.version },
        },
      };
    }

    if (method === 'tools/list') {
      return {
        jsonrpc: '2.0',
        id,
        result: { tools: this.listTools() },
      };
    }

    if (method === 'tools/call') {
      const toolName = params.name;
      const argumentsObject = params.arguments ?? {};
      return this.callTool(toolName, argumentsObject)
        .then((result) => ({
          jsonrpc: '2.0',
          id,
          result: { content: [{ type: 'json', json: result }] },
        }))
        .catch((error) => ({
          jsonrpc: '2.0',
          id,
          error: { code: -32602, message: error.message },
        }));
    }

    if (method === 'ping') {
      return {
        jsonrpc: '2.0',
        id,
        result: { ok: true },
      };
    }

    return {
      jsonrpc: '2.0',
      id,
      error: { code: -32601, message: `Method not found: ${method}` },
    };
  }

  async run() {
    console.log(`Starting ${this.name} v${this.version}`);
    console.log(`Available tools: ${Object.keys(this.tools).join(', ')}`);
    console.log('Server running. Waiting for requests...');

    let buffer = '';
    for await (const chunk of process.stdin) {
      buffer += chunk;
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const payload = JSON.parse(line);
          const response = await this.processMessage(payload);
          process.stdout.write(`${JSON.stringify(response)}\n`);
          process.stdout.flush?.();
        } catch (error) {
          process.stdout.write(`${JSON.stringify({
            jsonrpc: '2.0',
            id: null,
            error: { code: -32700, message: error.message },
          })}\n`);
          process.stdout.flush?.();
        }
      }
    }
  }
}

const server = new DiagnosticServer();
server.run().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});

export default DiagnosticServer;
