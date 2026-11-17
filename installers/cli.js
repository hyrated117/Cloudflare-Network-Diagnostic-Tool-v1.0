#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const VERSION = '1.0.0';
const PROJECT_NAME = 'Cloudflare Network Diagnostic Tool';

class MCPServerCLI {
  constructor() {
    const homeDir = process.env.HOME || process.env.USERPROFILE || os.homedir();
    if (!homeDir) throw new Error('Unable to determine the user home directory');
    this.homeDir = homeDir;
    this.installDir = path.join(homeDir, '.local', 'cloudflare-mcp');
    this.serverDir = path.join(this.installDir, 'server');
    this.configDir = path.join(this.installDir, 'config');
    this.logFile = path.join(this.installDir, 'install.log');
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    const msg = `[${timestamp}] [${level}] ${message}`;
    console.log(msg);
    fs.mkdirSync(this.installDir, { recursive: true });
    fs.appendFileSync(this.logFile, `${msg}\n`, 'utf8');
  }

  error(message) {
    this.log(message, 'ERROR');
    process.exitCode = 1;
  }

  warning(message) {
    this.log(message, 'WARN');
  }

  install() {
    const sourceFile = path.resolve(__dirname, '../server/index.js');
    if (!fs.existsSync(sourceFile)) {
      this.error(`Server source not found: ${sourceFile}`);
      return false;
    }

    try {
      fs.mkdirSync(this.serverDir, { recursive: true });
      fs.mkdirSync(this.configDir, { recursive: true });
      const installedServer = path.join(this.serverDir, 'index.js');
      fs.copyFileSync(sourceFile, installedServer);
      fs.writeFileSync(
        path.join(this.serverDir, 'package.json'),
        `${JSON.stringify({ type: 'module' }, null, 2)}\n`,
        'utf8',
      );
      const config = {
        name: 'Cloudflare Network Diagnostic Tool',
        version: VERSION,
        description: 'Node.js MCP server for Cloudflare network diagnostics',
        type: 'stdio',
        command: process.execPath,
        args: [installedServer],
      };
      fs.writeFileSync(path.join(this.configDir, 'mcp-server.json'), `${JSON.stringify(config, null, 2)}\n`, 'utf8');
      this.log(`Installed Node.js MCP server to ${installedServer}`);
      return true;
    } catch (error) {
      this.error(`Installation failed: ${error.message}`);
      return false;
    }
  }

  showVersion() {
    console.log(`${PROJECT_NAME} v${VERSION}`);
  }

  showHelp() {
    console.log(`${PROJECT_NAME} - Node.js CLI

Usage: cloudflare-mcp [command]

Commands:
  install       Install the Node.js MCP server
  start         Start the installed MCP server
  status        Check installation status
  --version     Show version
  --help        Show this help message`);
  }

  checkInstallation() {
    const serverFile = path.join(this.serverDir, 'index.js');
    const configFile = path.join(this.configDir, 'mcp-server.json');
    const installed = fs.existsSync(serverFile) && fs.existsSync(configFile);
    if (installed) {
      this.log('Installation is complete');
    } else {
      this.warning('Installation appears incomplete; run `cloudflare-mcp install`');
    }
    return installed;
  }

  startServer() {
    const serverFile = path.join(this.serverDir, 'index.js');
    if (!fs.existsSync(serverFile)) {
      this.error(`Server file not found: ${serverFile}. Run 'cloudflare-mcp install' first.`);
      return;
    }

    this.log('Starting MCP server (stdio)...');
    const child = spawn(process.execPath, [serverFile], { stdio: 'inherit' });
    child.once('error', (error) => {
      this.error(`Unable to start MCP server: ${error.message}`);
    });
    child.once('exit', (code, signal) => {
      if (signal) {
        this.log(`MCP server stopped by signal ${signal}`);
      } else if (code !== 0) {
        this.error(`MCP server exited with code ${code}`);
      }
    });
  }
}

let cli;
try {
  cli = new MCPServerCLI();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}

if (cli) {
  const command = process.argv[2];
  switch (command) {
    case 'install':
      cli.install();
      break;
    case 'start':
      cli.startServer();
      break;
    case 'status':
      if (!cli.checkInstallation()) process.exitCode = 1;
      break;
    case '--version':
    case '-v':
      cli.showVersion();
      break;
    case '--help':
    case '-h':
    case undefined:
      cli.showHelp();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      cli.showHelp();
      process.exitCode = 1;
  }
}
