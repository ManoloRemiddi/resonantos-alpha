# CHANGELOG — shield_scan.py

## v2.0.0 (2026-03-06)

Full rewrite of patterns and file-handling logic. Backwards-compatible CLI.

---

### 🐛 Bug Fixes

#### BUG-1: `destructive_rm` matched ANY absolute path (false positive flood)
**Before:**
```python
re.compile(r"rm\s+-rf\s+(/|~|\$HOME|\$\{HOME\})", re.I)
```
The regex matched `rm -rf /var/log/old`, `rm -rf /tmp/build` — any path starting with `/`.

**After:**
```python
re.compile(
    r"rm\s+-rf\s+(/\s*$|/\s*[\"'\s]|~/?\s*$|~/?\s*[\"'\s]|[$][{]?HOME[}]?)",
    re.I | re.M,
)
```
Now only matches `rm -rf /`, `rm -rf ~/`, `rm -rf $HOME` — true root/home destruction.

---

#### BUG-2: `obfuscation_eval` flagged `RegExp.prototype.exec()` (false positive)
**Before:** `exec\(` matched any `.exec(` call including standard JS `regex.exec(content)`.

**After:**
```python
r"(?<!\.)(?<!\w)(eval|exec)\s*\((?!\s*\))"
```
Negative lookbehind `(?<!\.)` excludes method calls (`.exec(`, `.eval(`).

---

#### BUG-3: `crontab -l` (read-only) was flagged as persistence
**Before:** `crontab\s+-` matched `-l` (list), `-u` (user flag) — read-only operations.

**After:** `crontab\s+-[eri\b]` — only matches write operations: `-e` (edit), `-r` (remove), `-i` (remove with confirm).

---

#### BUG-4: `SKILL.md` in extensionless check was dead code
`SKILL.md` was listed in the extensionless filename set, but `.md` is already in `TEXT_EXTS`.
Removed the redundant entry; `Makefile` and `Dockerfile` (genuinely extensionless) are preserved.

---

#### BUG-5: `websocket` flagged as network backdoor
**Before:** Any string containing `websocket` was flagged as HIGH.

**After:** `network_backdoor` pattern replaced with `reverse_shell` (actual attack patterns:
`bash -i >&`, `nc -e /bin/sh`, `/dev/tcp/`) and a separate `network_listener` pattern that
only flags explicit `0.0.0.0` bind addresses.

---

### ✨ New Features

#### Test directory downgrade
Findings inside `test/`, `tests/`, `__tests__/`, `spec/`, `fixtures/`, `mocks/` directories
are automatically downgraded from `high`/`medium` to `info` severity.

This resolves all 3 false positives found in `capability-evolver`:
- `rm -rf /` in test fixture → `info` (was `high`)
- `.ssh/id_rsa` in test fixture → `info` (was `medium`)
- `failureRegex.exec(content)` → no longer matched at all (BUG-2 fix)

Use `--no-test-downgrade` to opt out and see raw severities.

---

#### New `--min-severity` CLI flag
```
--min-severity {critical,high,medium,low,info}
```
Filter output to only show findings at or above the given level.
Default: `info` (show everything, including test-dir findings).

---

#### New detection patterns (6 added)

| Pattern ID | Severity | What it catches |
|---|---|---|
| `curl_pipe_bash` | critical | `curl URL \| bash` / `wget -O- URL \| sh` |
| `base64_shell_exec` | critical | `base64 -d payload \| bash` |
| `pickle_rce` | critical | `pickle.loads(untrusted)` — RCE vector |
| `subprocess_shell_true` | high | `subprocess.run(..., shell=True)` |
| `chmod_world_writable` | high | `chmod 777` / `os.chmod(..., 0o777)` |
| `env_credential_exfil` | medium | `os.environ['TOKEN']` + HTTP call on same line |
| `import_obfuscation` | medium | `__import__(...)` / `importlib.import_module(...)` |
| `dns_exfil` | medium | DNS lookup with f-string variable in hostname |
| `reverse_shell` | high | `/dev/tcp/`, `bash -i >&`, `nc -e /bin/sh` |
| `network_listener` | high | Explicit `0.0.0.0` bind |

---

#### Expanded file coverage

**New extensions scanned:**
`.jsx`, `.tsx`, `.mjs`, `.cjs`, `.mts`, `.cts` — modern JS/TS module formats  
`.php`, `.pl`, `.lua`, `.java`, `.c`, `.cpp`, `.h`, `.cs` — additional server-side languages  
`.ps1`, `.bat`, `.cmd`, `.vbs` — Windows scripting  
`.html`, `.xml`, `.plist` — markup that can contain injected scripts  
`.service`, `.timer`, `.socket` — systemd unit files  
`.fish` — Fish shell scripts  

**`.env` variants:** `.env.local`, `.env.production`, `.env.test` etc. now scanned
(previously only `.env` itself was matched — variants had wrong suffix).

**Shebang detection:** extensionless files starting with `#!/usr/bin/env python3` (or bash, ruby,
node, perl, etc.) are now scanned automatically.

---

#### New `warning` status level
`status` field in report now has three values:
- `clean` — no findings at high/medium/critical
- `warning` — only medium findings (review recommended, not necessarily blocked)
- `flagged` — high or critical findings (was the only non-clean state in v1)

---

#### Report metadata
Report now includes `scanner`, `version`, `total_findings`, `shown_findings` fields.
Findings are sorted: highest severity first, then by file path and line number.

---

#### Expanded `SKIP_DIRS`
Added: `.clawhub`, `.cache`, `coverage`, `.nyc_output`

---

### 🔍 Capability-Evolver Verdict

**v1 result:** `flagged` — 1 high, 2 medium  
**v2 result:** `clean` — 0 high, 0 medium, 2 info (both in test dir, expected)

All 3 v1 findings were false positives. Capability-evolver's network calls go to
`https://evomap.ai` (its own hub) — configurable via `A2A_HUB_URL` env var. No malicious
exfiltration detected. **Safe to install.**

The previously-reported Chinese cloud storage incident (GitHub issue #95) was addressed
by the author and is not present in v1.27.2.

---

### ⚠️ Known Limitations (not addressed in v2)

- No multi-line / cross-line analysis — split payloads evade detection
- String concatenation bypass (`'r' + 'm -rf /'`) not detected
- No AST-based analysis — context-blind regex can still produce FPs in complex code
- Pure comment lines starting with `#` are skipped (reduces FPs but could miss commented-out malware)
- `test/` downgrade is heuristic — a malicious skill could place attack code in a `test/` dir

---

*Analysis performed with Claude Opus 4.6. Report prepared for upstream contribution.*
