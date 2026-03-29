#!/usr/bin/env node
/**
 * extract.mjs - DynamicFetcher + Defuddle article extraction.
 *
 * Usage:
 *   node extract.mjs <url>
 *
 * Output (JSON to stdout):
 *   { title, content, description, author, site, published }
 *
 * Error: writes to stderr and exits non-zero.
 */
import { JSDOM } from 'jsdom';
import { Defuddle } from '/tmp/node_modules/defuddle/dist/node.js';

const url = process.argv[2];
if (!url) {
  console.error('Usage: extract.mjs <url>');
  process.exit(1);
}

// Fetch rendered HTML via Python DynamicFetcher
let html;
try {
  const pyScript = [
    `from scrapling import DynamicFetcher;`,
    `f = DynamicFetcher();`,
    `r = f.fetch('${url.replace(/'/g, "'\"'\"'")}', timeout=30000);`,
    `body = r.body.decode('utf-8', errors='replace') if isinstance(r.body, bytes) else str(r.body);`,
    `print(body, end='')`,
  ].join('\n');

  const { execSync } = await import('child_process');
  html = execSync(['python3', '-c', pyScript], {
    timeout: 35000,
    maxBuffer: 50 * 1024 * 1024,
  }).toString();
} catch (err) {
  console.error('DynamicFetcher failed:', err.message);
  process.exit(1);
}

// Parse with Defuddle via JSDOM
try {
  const dom = new JSDOM(html, { url, contentType: 'text/html' });
  const result = await Defuddle(dom.window.document, url);
  const out = {
    title: result.title || '',
    content: result.content || '',
    description: result.description || '',
    author: result.author || '',
    site: result.site || '',
    published: result.published || '',
  };
  console.log(JSON.stringify(out));
} catch (err) {
  console.error('Defuddle failed:', err.message);
  process.exit(1);
}
