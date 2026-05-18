#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

let raw = '';
process.stdin.on('data', chunk => { raw += chunk; });
process.stdin.on('end', () => {
  try {
    const payload = JSON.parse(raw);
    const { tool_name, tool_input, tool_response, cwd } = payload;

    const query = tool_input?.query ?? null;
    const url = tool_input?.url ?? null;
    const responseText = typeof tool_response === 'string'
      ? tool_response
      : JSON.stringify(tool_response);
    const snippet = responseText.slice(0, 1500);

    const entry = {
      ts: new Date().toISOString(),
      source: 'web',
      skill: null,
      query,
      url,
      note: null,
      snippet,
      reviewed: false,
    };

    const dir = path.join(cwd || process.cwd(), '.claude');
    const file = path.join(dir, 'findings.jsonl');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(file, JSON.stringify(entry) + '\n', 'utf8');
  } catch (_) {
    // Silent — never interrupt the session
  }
});
