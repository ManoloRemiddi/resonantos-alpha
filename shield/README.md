# Shield

Security components for ResonantOS.

## Contents

| File/Directory | Purpose |
|----------------|---------|
| `daemon.py` | Shield daemon process |
| `data_leak_scanner.py` | Diff-based secret scanner for git pushes |
| `file_guard.py` | File protection |
| `install_pre_push_hook.sh` | Installs the managed pre-push scanner hook |
| `shield-gate.js` | Main security gate implementation |
| `shield-gate.index.js` | Security gate entry point (merged from shield-gate/) |
| `delegation-gate.js` | Delegation control |
| `update-yara-rules.sh` | YARA rule updates |
| `watchdog/` | Process watchdog subdirectory |

## Consolidation Notes

- `shield-gate/` directory was merged into this directory (2026-03-20)
- `shield-gate.index.js` is the entry point, `shield-gate.js` is the main implementation
- Run `python3 shield/file_guard.py install-hook .` to install the managed pre-push leak scanner in this repo
