#!/usr/bin/env node
/**
 * Resolve an OpenClaw config path from a running-process command line.
 * Goal: targeted, bounded search (no deep crawl).
 *
 * Usage:
 *   node resolve-openclaw-config-from-process.js "<commandLine>"
 */

const fs = require('fs');
const path = require('path');

function exists(p) {
  try { fs.accessSync(p); return true; } catch { return false; }
}

function extractPaths(cmd) {
  // naive but effective: grab tokens that look like absolute paths ending with .js/.mjs/.exe
  const out = new Set();
  const re = /([A-Za-z]:\\[^"\s]+\.(?:js|mjs|exe))/g;
  let m;
  while ((m = re.exec(cmd)) !== null) out.add(m[1]);
  return Array.from(out);
}

function candidateConfigsFromAnchor(anchor) {
  // anchor is an absolute file path from the cmdline (e.g., ...\repo\dist\entry.js)
  const dir = path.dirname(anchor);

  const candidates = [];
  // 1) direct common locations near the anchor
  //    repo\dist\entry.js  -> check sibling gateway/.openclaw and repo/.openclaw etc.
  const up = (p, n) => {
    let cur = p;
    for (let i = 0; i < n; i++) cur = path.dirname(cur);
    return cur;
  };

  // bounded ascent: try up to 6 levels and test a small set each time
  for (let i = 0; i <= 6; i++) {
    const root = up(dir, i);

    // check typical instance layouts (keep small + deterministic)
    candidates.push(path.join(root, '.openclaw', 'openclaw.json'));
    candidates.push(path.join(root, 'gateway', '.openclaw', 'openclaw.json'));
    candidates.push(path.join(root, 'Gateway', '.openclaw', 'openclaw.json'));
    candidates.push(path.join(root, 'gateway', 'config', 'openclaw.json'));
    candidates.push(path.join(root, 'config', 'openclaw.json'));
    candidates.push(path.join(root, 'state', 'openclaw.json'));

    // special: if we see a repo/dist pattern, try repo root and parent
    // e.g. D:\openclaw-backup\openclaw\repo\dist\entry.js
    if (root.toLowerCase().endsWith(path.join('repo','dist')) || dir.toLowerCase().includes(path.join('repo','dist'))) {
      const repoDistIdx = (dir.toLowerCase().split(path.sep).lastIndexOf('repo') >= 0) ? dir.toLowerCase().split(path.sep).lastIndexOf('repo') : -1;
      // keep it simple; no extra parsing beyond bounded ascent.
    }
  }

  // de-dupe
  return Array.from(new Set(candidates));
}

function main() {
  const cmd = process.argv.slice(2).join(' ').trim();
  if (!cmd) {
    console.error('Missing command line argument');
    process.exit(2);
  }

  const anchors = extractPaths(cmd);
  if (!anchors.length) {
    console.log(JSON.stringify({ ok: false, reason: 'no_anchor_paths_found', cmd }, null, 2));
    process.exit(0);
  }

  const hits = [];
  const tried = [];

  for (const a of anchors) {
    const cands = candidateConfigsFromAnchor(a);
    for (const c of cands) {
      tried.push(c);
      if (exists(c)) hits.push({ anchor: a, configPath: c });
    }
  }

  console.log(JSON.stringify({ ok: hits.length > 0, anchors, hits, triedCount: tried.length }, null, 2));
}

main();
