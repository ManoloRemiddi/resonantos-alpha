#!/usr/bin/env python3
"""Memory Write Sanitizer - strips injection vectors from memory log files.

Usage:
    python3 sanitize-memory-write.py <file>       # Sanitize file in-place
    cat file | python3 sanitize-memory-write.py    # Stdin to stdout
    python3 sanitize-memory-write.py --test        # Run built-in tests
    python3 sanitize-memory-write.py --dry-run <f> # Show stats only
"""
from __future__ import annotations
import argparse, re, sys

_P1 = re.compile(r'<\s*(script|iframe|style|object|embed|form)\b[^>]*>.*?<\s*/\s*\1\s*>', re.I|re.DOTALL)
def strip_html_dangerous(t):
    m = _P1.findall(t); return _P1.sub('', t), len(m)

_P2 = re.compile(r'<\s*(link|meta|base)\b[^>]*/?\s*>', re.I)
def strip_html_standalone(t):
    m = _P2.findall(t); return _P2.sub('', t), len(m)

_P3 = re.compile(r'\s+on(?:click|error|load|mouseover|focus|blur|mouse\w+|key\w+|submit|change)\s*=\s*(?:"[^"]*"|' + r"'[^']*')", re.I)
def strip_event_handlers(t):
    m = _P3.findall(t); return _P3.sub('', t), len(m)

_P4 = re.compile(r'(?:javascript|data\s*:\s*text/html)\s*:[^\s"]+', re.I)
def strip_js_urls(t):
    m = _P4.findall(t); return _P4.sub('', t), len(m)

_P5 = re.compile(r'<\s*antml:function_calls\s*>.*?<\s*/\s*antml:function_calls\s*>', re.DOTALL)
def strip_tool_xml(t):
    c = len(_P5.findall(t)); return _P5.sub('', t), c

_P6 = re.compile(r'<\s*function_results\s*>.*?<\s*/\s*function_results\s*>', re.DOTALL)
def strip_tool_results(t):
    c = len(_P6.findall(t)); return _P6.sub('', t), c

_P7 = re.compile(r'<\s*thinking\s*>.*?<\s*/\s*thinking\s*>', re.DOTALL)
def strip_thinking(t):
    c = len(_P7.findall(t)); return _P7.sub('', t), c

_P8 = re.compile(r'[A-Za-z0-9+/=]{200,}')
def strip_base64_blobs(t):
    c = len(_P8.findall(t)); return _P8.sub('[base64-removed]', t), c

_P9 = re.compile(r'PRESERVE_VERBATIM|EXTERNAL_UNTRUSTED|A{10,}')
def strip_rmemory_noise(t):
    c = len(_P9.findall(t)); return _P9.sub('', t), c

_P10 = re.compile(r'^.*(?:new\s+instructions\s*:|system\s+prompt\s*:).*$', re.I|re.M)
def strip_injection_attempts(t):
    c = len(_P10.findall(t)); return _P10.sub('', t), c

_PALL = re.compile(r'<[^>]+>')
def strip_all_html(t):
    c = len(_PALL.findall(t)); return _PALL.sub('', t), c

def cleanup(t):
    t = re.sub(r'[ \t]+$', '', t, flags=re.M)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t

PIPELINE = [
    ('html_dangerous', strip_html_dangerous),
    ('html_standalone', strip_html_standalone),
    ('event_handlers', strip_event_handlers),
    ('js_urls', strip_js_urls),
    ('tool_xml', strip_tool_xml),
    ('tool_results', strip_tool_results),
    ('thinking', strip_thinking),
    ('base64_blobs', strip_base64_blobs),
    ('rmemory_noise', strip_rmemory_noise),
    ('injection', strip_injection_attempts),
]

def sanitize(text, strict=False):
    stats = {}
    for name, fn in PIPELINE:
        text, n = fn(text)
        stats[name] = n
    if strict:
        text, n = strip_all_html(text)
        stats['all_html'] = n
    return cleanup(text), stats

def run_tests():
    ok = fail = 0
    def chk(name, inp, key, absent=None, strict=False):
        nonlocal ok, fail
        cleaned, stats = sanitize(inp, strict=strict)
        hit = stats.get(key, 0) >= 1
        gone = absent is None or absent not in cleaned
        if hit and gone:
            ok += 1; print(f'  PASS: {name}')
        else:
            fail += 1; print(f'  FAIL: {name} (key={key} count={stats.get(key,0)})')

    print('Running built-in tests...\n')

    chk('1-script-tag', 'before<script>alert(1)</script>after', 'html_dangerous', '<script>')
    chk('2-iframe', 'x<iframe src="evil"></iframe>y', 'html_dangerous', '<iframe')
    chk('3-meta-tag', 'x<meta charset="utf-8">y', 'html_standalone', '<meta')
    chk('4-onclick', '<div onclick="evil()">x</div>', 'event_handlers', 'onclick')
    chk('5-js-url', 'visit javascript:alert(1) now', 'js_urls', 'javascript:')
    ns = 'antml:function_calls'
    chk('6-tool-xml', f'a<{ns}>x</{ns}>b', 'tool_xml', f'<{ns}')
    chk('7-tool-result', 'a<function_results>out</function_results>b', 'tool_results', '<function_results')
    chk('8-thinking', 'a<thinking>text</thinking>b', 'thinking', '<thinking')
    chk('9-base64', 'A'*250, 'base64_blobs', 'AAAAA')
    chk('10-noise', 'PRESERVE_VERBATIM x', 'rmemory_noise', 'PRESERVE')
    chk('11-new-instr', 'new instructions: do X\nx', 'injection', 'new instructions')
    chk('12-strict', '<div>x</div>', 'all_html', '<div>', strict=True)
    # 13: clean text passes through unchanged
    c13, s13 = sanitize('normal markdown text')
    if sum(s13.values()) == 0:
        ok += 1; print('  PASS: 13-clean-pass')
    else:
        fail += 1; print(f'  FAIL: 13-clean-pass ({s13})')

    print(f'\nResults: {ok} passed, {fail} failed')
    return fail == 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file", nargs="?")
    p.add_argument("--test", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strict", action="store_true")
    a = p.parse_args()

    if a.test:
        sys.exit(0 if run_tests() else 1)

    if a.file:
        with open(a.file, "r") as f: text = f.read()
    else:
        text = sys.stdin.read()

    cleaned, stats = sanitize(text, strict=a.strict)

    if a.dry_run:
        for k, v in stats.items():
            if v>0: print(f"{k}: {v}", file=sys.stderr)
    else:
        if a.file:
            with open(a.file, "w") as f: f.write(cleaned)
        else:
            sys.stdout.write(cleaned)
