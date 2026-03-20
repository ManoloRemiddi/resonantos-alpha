# Legacy Paths

Archive for tracking old hardcoded path references.

## Issue

Multiple files contain hardcoded paths with the old repo name `resonantos-augmentor` which should be `resonantos-alpha`.

## Files with Old Paths

These files reference `resonantos-augmentor` in runtime paths:

| File | Status | Notes |
|------|--------|-------|
| `shield/shield-gate.js` | Runtime path | Log file location |
| `shield/shield-gate.index.js` | Runtime path | Log file location |
| `extensions/shield-gate/index.js` | Runtime path | Log file location |
| `extensions/coherence-gate/index.js` | Runtime path | Exclude paths |
| `experiments/watchdog/watchdog.py` | Runtime path | Shield log location |

## Note

These are runtime paths, not source code paths. They represent where files are written at runtime, not where source code lives. The actual source is in `shield/`, `extensions/`, and `experiments/`.

For the actual fix, see issues #41 and #42 (Replace hardcoded paths).

Archived: 2026-03-20
