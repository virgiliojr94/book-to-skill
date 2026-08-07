#!/usr/bin/env node
// Wrapper de conveniência para usar @firecrawl/anydoc.
// Tenta require('@firecrawl/anydoc') primeiro; se não estiver instalada,
// tenta usar `npx @firecrawl/anydoc <file> --json` como fallback.

const fs = require('fs');
const { spawnSync } = require('child_process');

async function main() {
  const file = process.argv[2];
  if (!file) {
    console.error("Usage: anydoc_extractor.js <path>");
    process.exit(2);
  }

  // Try to require the module and use its API if available
  try {
    const anydoc = require('@firecrawl/anydoc');
    // NOTE: adjust the call below if the real API differs.
    if (typeof anydoc.parseFile === 'function') {
      try {
        const res = await anydoc.parseFile(file, { format: 'text' });
        const out = {
          text: res && (res.text || res.content || res.body) ? (res.text || res.content || res.body) : String(res),
          meta: res && res.meta ? res.meta : null,
        };
        console.log(JSON.stringify(out));
        return;
      } catch (err) {
        // Fall through to CLI fallback if API call fails
        // but print a short warning to stderr for diagnostics
        console.error('anydoc.parseFile failed:', String(err));
      }
    }
  } catch (e) {
    // require failed — will try npx fallback
  }

  // Fallback: run npx @firecrawl/anydoc <file> --json
  const npx = spawnSync('npx', ['@firecrawl/anydoc', file, '--json'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  if (npx.status !== 0) {
    process.stderr.write(npx.stderr || 'npx anydoc failed');
    process.exit(npx.status || 1);
  }

  // Assume the CLI prints JSON. If not, we still output stdout directly.
  try {
    console.log(npx.stdout);
  } catch (err) {
    process.stderr.write('Failed to print anydoc output: ' + String(err));
    process.exit(1);
  }
}

main();
