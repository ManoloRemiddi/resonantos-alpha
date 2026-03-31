#!/usr/bin/env python3
"""
DEV4 Alpha Audit Reviewer

Interactive triage UI for public-alpha extraction work.
Focuses on component-first review, with file-level exceptions.

Run:
  python3 tools/dev4_audit_server.py
Open:
  http://localhost:9877
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

ALPHA_ROOT = Path('/Users/augmentor/resonantos-alpha')
PRIVATE_ROOT = Path('/Users/augmentor/resonantos-augmentor')
OUTPUT_PATH = ALPHA_ROOT / 'docs' / 'dev4-audit-data.json'
HOST = '127.0.0.1'
PORT = 9877

CLASSIFICATIONS = ['CORE', 'TEMPLATE', 'PLACEHOLDER', 'PRIVATE', 'DEFER']
ACTIONS = [
    'KEEP',
    'SANITIZE',
    'REPLACE_WITH_EXISTING_TEMPLATE',
    'CREATE_TEMPLATE',
    'REMOVE_CODE_KEEP_UI_REFERENCE',
    'EXCLUDE',
    'REVIEW',
]
REVIEW_STATUSES = ['MUST_CHANGE', 'NEEDS_DECISION', 'AUTO_SAFE']
SEVERITIES = ['P0', 'P1', 'P2', 'P3']

IGNORE_NAMES = {
    '.git', '.DS_Store', 'node_modules', '.pytest_cache', '.ruff_cache',
    '__pycache__', '.venv', 'target', 'dist', 'build', '.mypy_cache',
}
EXPAND_DEPTHS = {
    'dashboard': 4,
    'ssot': 5,
    'docs': 3,
    'agents': 3,
    'extensions': 3,
    'logician': 3,
    'shield': 3,
    'tools': 3,
    'config': 3,
}
PRIVATE_EXACT = {
    'MEMORY.md', 'SOUL.md', 'USER.md', 'TOOLS.md', 'HEARTBEAT.md',
    'IDENTITY.md', '.env.local', 'secrets', 'memory', '.codex',
}
PLACEHOLDER_CANDIDATES = {'r-memory', 'guardian', 'watchdog', 'shield-gate', 'skills'}
TEMPLATE_EXACT = {'workspace-templates', 'templates', 'ssot-template'}
CORE_EXACT = {
    'agents', 'assets', 'bin', 'config', 'dashboard', 'data', 'docs',
    'extensions', 'install.js', 'logician', 'mcp-server', 'r-awareness',
    'scripts', 'shield', 'solana-toolkit', 'ssot', 'tools', 'VERSION',
    'README.md', 'INSTALLATION_COMPONENTS.md', 'DELEGATION_PROTOCOL.md',
}
SSOT_TEMPLATE_PATTERNS = [re.compile(r'ssot-template', re.I), re.compile(r'templates?', re.I)]
LEAKY_DOC_PATTERNS = [
    re.compile(r'memory\.md', re.I),
    re.compile(r'soul\.md', re.I),
    re.compile(r'user\.md', re.I),
    re.compile(r'heartbeat\.md', re.I),
    re.compile(r'r-memory', re.I),
    re.compile(r'shield-gate', re.I),
    re.compile(r'watchdog', re.I),
    re.compile(r'r-awareness', re.I),
]
ALPHA_IDENTITY_PATTERNS = [
    re.compile(r'augmentatism', re.I),
    re.compile(r'cosmodestiny', re.I),
    re.compile(r'manifesto', re.I),
    re.compile(r'philosophy', re.I),
    re.compile(r'constitution', re.I),
    re.compile(r'proto-', re.I),
    re.compile(r'protocol', re.I),
]
ADDON_MODULE_IDS = {
    'coding_agents', 'chatbots', 'todo', 'projects', 'tribes', 'bounties', 'protocol_store'
}
ADDON_ROUTE_PATTERNS = [
    re.compile(r'^dashboard/routes/(chatbots|todo|projects|tribes|bounties)\.py$', re.I),
    re.compile(r'^dashboard/routes/protocols\.py$', re.I),
    re.compile(r'^dashboard/templates/(chatbots|todo|projects|tribes|bounties)\.html$', re.I),
    re.compile(r'^dashboard/templates/protocols?\.html$', re.I),
    re.compile(r'^dashboard/static/addon-screenshots/', re.I),
]
ADDON_UI_KEEP_PATTERNS = [
    re.compile(r'^dashboard/templates/settings\.html$', re.I),
    re.compile(r'^dashboard/routes/system\.py$', re.I),
    re.compile(r'^dashboard/server_v2\.py$', re.I),
]
COST_OPERATIONS_TARGETS = {
    'dashboard/templates/index.html',
}
ALPHA_AGENT_DIRS = {
    'agents/setup',
}
DOCS_ALPHA_EXACT = {
    'docs/DEV4-ALPHA-SPEC.md',
    'docs/GETTING-STARTED.md',
}
DOCS_ALPHA_PATTERNS = [
    re.compile(r'^docs/.*\.(md|ai\.md)$', re.I),
]
DOCS_PRIVATE_PATTERNS = [
    re.compile(r'^docs/REFACTORING-SUMMARY-', re.I),
]
EXTENSIONS_PRIVATE_PATTERNS = [
    re.compile(r'manolo', re.I),
    re.compile(r'/users/augmentor', re.I),
    re.compile(r'resonantdoer', re.I),
    re.compile(r'r-nas1', re.I),
    re.compile(r'memory_trusted_agents', re.I),
]
SHIELD_LOGICIAN_PRIVATE_PATTERNS = [
    re.compile(r'can_spawn\([^)]*(augmentor|deputy|r-nas1|resonantdoer)', re.I),
    re.compile(r'allowlist\([^)]*(augmentor|deputy|r-nas1|resonantdoer)', re.I),
    re.compile(r'memory_trusted_agents', re.I),
    re.compile(r'/users/augmentor', re.I),
    re.compile(r'manolo', re.I),
    re.compile(r'resonantos-augmentor', re.I),
]
RESIDUE_EXCLUDE_PATTERNS = [
    re.compile(r'(^|/)logs?($|/)', re.I),
    re.compile(r'\.log$', re.I),
    re.compile(r'\.bak($|[-.])', re.I),
    re.compile(r'(^|/)TASK[^/]*\.md$', re.I),
    re.compile(r'(^|/)alerts?($|/)', re.I),
    re.compile(r'(^|/)bin($|/)', re.I),
    re.compile(r'(^|/)poc/.*mangle-server$', re.I),
]
PRIVATE_BOUNDARY_PATTERNS = [
    re.compile(r'\bmemory/shared-log\b', re.I),
    re.compile(r'\bmemory/\d{4}-\d{2}-\d{2}\.md\b', re.I),
    re.compile(r'\bsecrets\b', re.I),
    re.compile(r'\bauth-profiles\.json\b', re.I),
    re.compile(r'\bopenclaw\.json\b', re.I),
    re.compile(r'\bheartbeat\.md\b', re.I),
]


@dataclass
class Row:
    path: str
    component: str
    subcomponent: str
    doctrine: str
    doctrine_reason: str
    kind: str
    in_private: bool
    in_alpha: bool
    private_type: str
    alpha_type: str
    suggested_classification: str
    suggested_action: str
    confidence: str
    review_status: str
    severity: str
    reason: str
    notes: str
    template_exists: bool
    template_hint: str
    leak_risk: bool
    override_classification: str = ''
    override_action: str = ''
    override_review_status: str = ''
    comment: str = ''


def rel_children(root: Path) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    if not root.exists():
        return out
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.name in IGNORE_NAMES:
            continue
        out[child.name] = child
    return out


def iter_component_paths(root: Path, component: str, max_depth: int):
    base = root / component
    if not base.exists():
        return
    stack = [(base, component, 0)]
    while stack:
        current, rel, depth = stack.pop()
        yield rel, current
        if current.is_dir() and depth < max_depth:
            children = [p for p in sorted(current.iterdir(), key=lambda p: p.name.lower()) if p.name not in IGNORE_NAMES]
            for child in reversed(children):
                stack.append((child, f'{rel}/{child.name}', depth + 1))


def path_type(p: Optional[Path]) -> str:
    if p is None or not p.exists():
        return 'missing'
    return 'dir' if p.is_dir() else 'file'


def get_component(rel_path: str) -> str:
    return rel_path.split('/', 1)[0]


def get_subcomponent(rel_path: str) -> str:
    parts = rel_path.split('/')
    if len(parts) >= 2:
        return '/'.join(parts[:2])
    return parts[0]


def dashboard_addon_placeholder(rel_path: str) -> bool:
    lower = rel_path.lower()
    return any(p.search(rel_path) for p in ADDON_ROUTE_PATTERNS)


def dashboard_addon_ui_keep(rel_path: str) -> bool:
    return any(p.search(rel_path) for p in ADDON_UI_KEEP_PATTERNS)


def is_cost_operations_center(rel_path: str) -> bool:
    lower = rel_path.lower()
    if rel_path.replace('\\', '/').lower() in COST_OPERATIONS_TARGETS:
        return True
    return 'cost operations center' in lower or 'cost-operations-center' in lower or 'cost_operations_center' in lower



def file_contains_private_patterns(rel_path: str, patterns) -> bool:
    candidates = [
        Path('/Users/augmentor/resonantos-alpha') / rel_path,
        Path('/Users/augmentor/resonantos-augmentor') / rel_path,
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                txt = p.read_text(errors='ignore')
                return any(pat.search(txt) for pat in patterns)
        except Exception:
            continue
    return False



def is_residue_exclude(rel_path: str) -> bool:
    norm = rel_path.replace('\\', '/')
    return any(p.search(norm) for p in RESIDUE_EXCLUDE_PATTERNS)

def is_alpha_agent(rel_path: str) -> bool:
    norm = rel_path.replace('\\', '/')
    return norm == 'agents' or norm in ALPHA_AGENT_DIRS or any(norm.startswith(a + '/') for a in ALPHA_AGENT_DIRS)


def is_private_agent(rel_path: str) -> bool:
    norm = rel_path.replace('\\', '/')
    return norm.startswith('agents/') and not is_alpha_agent(norm)

def component_intent(rel_path: str) -> tuple[str, str]:
    comp = get_component(rel_path)
    sub = get_subcomponent(rel_path)
    lower = rel_path.lower()

    if is_cost_operations_center(rel_path):
        return 'REMOVE', 'Cost Operations Center is deprecated and should be removed from both private and Alpha.'

    if dashboard_addon_placeholder(rel_path):
        return 'PLACEHOLDER_ONLY', 'One of the 7 Settings/Add-ons modules: keep visible in catalog UI, do not ship its active implementation code in DEV4.'

    if dashboard_addon_ui_keep(rel_path):
        return 'KEEP_ADDON_CATALOG_UI', 'Keep the Add-ons catalog UI and module registry plumbing so DEV4 can show add-ons without shipping their code.'

    if comp == 'dashboard':
        return 'KEEP_DASHBOARD', 'Dashboard should mostly remain as in the private system, excluding deprecated surfaces and add-on code that should live only as catalog entries.'

    if comp in {'memory', 'secrets'}:
        return 'PRIVATE_ONLY', 'Identity, memory, and secret-bearing material remain private.'

    if is_residue_exclude(rel_path):
        return 'DEVELOPMENT_RESIDUE', 'Logs, backups, task scratchpads, alerts, and local binaries are development residue and should not ship in Alpha.'

    if lower == 'agents' or lower.startswith('agents/'):
        if is_alpha_agent(rel_path):
            return 'ALPHA_AGENT_CORE', 'Alpha ships exactly two agent roles: the main Augmentor behavior layer and the Setup agent. The explicit agent folder in Alpha is Setup.'
        if is_private_agent(rel_path):
            return 'PRIVATE_AGENT', 'All agents beyond main/default behavior and Setup are private.'

    if lower == 'docs' or lower.startswith('docs/'):
        norm = rel_path.replace('\\', '/')
        if norm in DOCS_ALPHA_EXACT:
            return 'DOCS_ALPHA', 'User-facing product docs and Alpha spec belong in Alpha.'
        if any(p.search(norm) for p in DOCS_PRIVATE_PATTERNS):
            return 'DOCS_PRIVATE', 'Internal refactoring summaries are development residue, not Alpha product docs.'
        if any(p.search(norm) for p in DOCS_ALPHA_PATTERNS):
            return 'DOCS_ALPHA', 'Architecture, protocol, and product docs belong in Alpha unless they are explicitly internal residue.'

    if lower == 'extensions' or lower.startswith('extensions/'):
        if file_contains_private_patterns(rel_path, EXTENSIONS_PRIVATE_PATTERNS):
            return 'EXTENSION_PRIVATE_COUPLING', 'Extensions are Alpha unless coupled to private agents, identity, or machine-specific logic.'
        return 'EXTENSION_ALPHA', 'Generic ResonantOS extensions belong in Alpha.'

    if lower == 'shield' or lower.startswith('shield/') or lower == 'logician' or lower.startswith('logician/'):
        if file_contains_private_patterns(rel_path, SHIELD_LOGICIAN_PRIVATE_PATTERNS):
            return 'REASONING_PRIVATE_COUPLING', 'Shield/Logician are Alpha unless a rule is coupled to a specific private agent, private workflow, or private machine state.'
        return 'REASONING_ALPHA', 'Shield and Logician are core ResonantOS systems and belong in Alpha by default.'

    if lower == 'ssot/l0' or lower.startswith('ssot/l0/'):
        return 'SSOT_PUBLIC_TEMPLATE', 'SSoT L0 is part of the public template seed and should stay in Alpha as generalized template material.'

    if lower == 'ssot/l1' or lower.startswith('ssot/l1/'):
        return 'SSOT_PUBLIC_TEMPLATE', 'SSoT L1 is mainly public architecture/protocol template material and should stay in Alpha unless a file is explicitly private.'

    if lower == 'ssot/l2' or lower.startswith('ssot/l2/') or lower == 'ssot/l3' or lower.startswith('ssot/l3/') or lower == 'ssot/l4' or lower.startswith('ssot/l4/'):
        return 'SSOT_PRIVATE_LAYER', 'SSoT L2/L3/L4 are private working layers and should not ship in Alpha.'

    if comp == 'ssot':
        return 'ALPHA_ARCHITECTURE', 'SSoT architecture, philosophy, and protocols belong to Alpha unless they are identity-bound.'

    return 'GENERAL_REVIEW', 'Apply Alpha doctrine: keep generalizable product value, remove private dependence.'


def find_template_for(rel_path: str) -> Tuple[bool, str]:
    path = rel_path.replace('\\', '/')
    if path.startswith('ssot/'):
        suffix = path.split('/', 1)[1]
        candidate = ALPHA_ROOT / 'ssot-template' / suffix
        if candidate.exists():
            return True, str(candidate.relative_to(ALPHA_ROOT))
    for pattern in SSOT_TEMPLATE_PATTERNS:
        if pattern.search(path):
            return True, 'path itself is already a template container'
    if Path(path).name in {'SOUL.md', 'USER.md', 'MEMORY.md', 'TOOLS.md', 'HEARTBEAT.md', 'IDENTITY.md'}:
        for container in ['workspace-templates', 'templates']:
            candidate = ALPHA_ROOT / container / Path(path).name
            if candidate.exists():
                return True, str(candidate.relative_to(ALPHA_ROOT))
    return False, ''


def has_leak_signal(rel_path: str) -> bool:
    return any(p.search(rel_path) for p in LEAKY_DOC_PATTERNS)


def has_alpha_identity_signal(rel_path: str) -> bool:
    return any(p.search(rel_path) for p in ALPHA_IDENTITY_PATTERNS)


def has_private_boundary_signal(rel_path: str) -> bool:
    return any(p.search(rel_path) for p in PRIVATE_BOUNDARY_PATTERNS)


def classify_review(sc: str, sa: str, rel_path: str, alpha_exists: bool, private_exists: bool, template_exists: bool) -> Tuple[str, str, str]:
    leak = has_leak_signal(rel_path)
    if sa in {'SANITIZE', 'EXCLUDE', 'REPLACE_WITH_EXISTING_TEMPLATE', 'CREATE_TEMPLATE', 'REMOVE_CODE_KEEP_UI_REFERENCE'}:
        severity = 'P0' if leak or (alpha_exists and sc in {'PRIVATE', 'TEMPLATE'}) else 'P1'
        return 'MUST_CHANGE', severity, 'high'
    if sc == 'DEFER' or sa == 'REVIEW':
        return 'NEEDS_DECISION', 'P2', 'low'
    if sc == 'CORE' and sa == 'KEEP' and private_exists and alpha_exists:
        return 'AUTO_SAFE', 'P3', 'medium'
    if sc == 'TEMPLATE' and sa == 'KEEP':
        return 'AUTO_SAFE', 'P3', 'high'
    return 'NEEDS_DECISION', 'P2', 'medium'


def suggest(rel_path: str, priv: Optional[Path], alpha: Optional[Path]) -> Tuple[str, str, str, str, bool, str, bool, str, str]:
    name = Path(rel_path).name
    lower = rel_path.lower()
    template_exists, template_hint = find_template_for(rel_path)
    leak_risk = has_leak_signal(rel_path)
    alpha_identity = has_alpha_identity_signal(rel_path)
    private_boundary = has_private_boundary_signal(rel_path)

    if name in PRIVATE_EXACT or lower.startswith('memory/') or lower.startswith('secrets/') or private_boundary:
        classification = 'PRIVATE' if not template_exists else 'TEMPLATE'
        action = 'REPLACE_WITH_EXISTING_TEMPLATE' if template_exists else 'EXCLUDE'
        reason = 'personal identity/state or secret-bearing path'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if lower.startswith('ssot/'):
        if template_exists:
            classification, action = 'TEMPLATE', 'REPLACE_WITH_EXISTING_TEMPLATE'
            reason = 'private/local SSoT should map to sanitized template'
        elif alpha_identity:
            classification, action = 'CORE', 'KEEP'
            reason = 'shared philosophy/protocol architecture is part of ResonantOS Alpha, not private by default'
        else:
            classification, action = 'CORE', 'SANITIZE'
            reason = 'architecture doc candidate; likely needs sanitization or templating decision'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if name in TEMPLATE_EXACT:
        classification, action, reason = 'TEMPLATE', 'KEEP', 'template container belongs in public alpha'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if name in PLACEHOLDER_CANDIDATES:
        classification, action = 'PLACEHOLDER', 'REMOVE_CODE_KEEP_UI_REFERENCE'
        reason = 'likely add-on or not-ready subsystem; keep visible but not shipped as active code'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if name in CORE_EXACT:
        classification, action, reason = 'CORE', 'KEEP', 'baseline runtime/install/docs surface'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if alpha_identity:
        classification, action, reason = 'CORE', 'KEEP', 'manifesto/philosophy/protocol material belongs to Alpha unless clearly identity-bound'
        if leak_risk or private_boundary:
            action = 'SANITIZE'
            reason = 'shared philosophy/protocol material with private residue; keep concept, remove personal dependence'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if lower.startswith(('dashboard/', 'agents/', 'extensions/', 'scripts/', 'docs/', 'assets/', 'bin/', 'config/', 'data/')):
        classification, action = 'CORE', 'KEEP'
        reason = 'subtree belongs to baseline runnable system unless file-level review says otherwise'
        if alpha_identity:
            reason = 'philosophy/protocol material is presumed public Alpha surface unless clearly personal'
        if leak_risk and alpha is not None:
            action = 'SANITIZE'
            reason = 'public-facing doc/code path with private-architecture signals'
        rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if priv is not None and alpha is None:
        classification, action, reason = 'DEFER', 'REVIEW', 'exists only in private source; decide whether it is missing core or correctly excluded'
        rs, sev, conf = classify_review(classification, action, rel_path, False, True, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    if alpha is not None and priv is None:
        classification, action, reason = 'DEFER', 'REVIEW', 'exists only in alpha; verify whether it is valid public packaging or stale/leaked artifact'
        rs, sev, conf = classify_review(classification, action, rel_path, True, False, template_exists)
        return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf

    classification, action, reason = 'DEFER', 'REVIEW', 'no heuristic confidence'
    rs, sev, conf = classify_review(classification, action, rel_path, alpha is not None, priv is not None, template_exists)
    return classification, action, reason, '', template_exists, template_hint, leak_risk, rs, sev, conf


def make_row(rel_path: str, kind: str, priv: Optional[Path], alpha: Optional[Path]) -> Row:
    sc, sa, reason, notes, te, th, leak, review_status, severity, confidence = suggest(rel_path, priv, alpha)
    doctrine, doctrine_reason = component_intent(rel_path)

    if doctrine == 'REMOVE':
        sc, sa, review_status, severity, confidence = 'DEFER', 'EXCLUDE', 'MUST_CHANGE', 'P0', 'high'
        reason = doctrine_reason
    elif doctrine == 'PLACEHOLDER_ONLY':
        sc, sa, review_status, severity, confidence = 'PLACEHOLDER', 'REMOVE_CODE_KEEP_UI_REFERENCE', 'MUST_CHANGE', 'P1', 'high'
        reason = doctrine_reason
    elif doctrine == 'KEEP_ADDON_CATALOG_UI':
        sc, sa = 'CORE', 'KEEP'
        if review_status == 'NEEDS_DECISION':
            review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'high'
        reason = doctrine_reason
    elif doctrine == 'SSOT_PUBLIC_TEMPLATE':
        sc, sa = 'TEMPLATE', 'KEEP'
        review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'high'
        reason = doctrine_reason
    elif doctrine == 'SSOT_PRIVATE_LAYER':
        sc, sa = 'PRIVATE', 'EXCLUDE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P1', 'high'
        reason = doctrine_reason
    elif doctrine == 'DEVELOPMENT_RESIDUE':
        sc, sa = 'PRIVATE', 'EXCLUDE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P2', 'high'
        reason = doctrine_reason
    elif doctrine == 'ALPHA_AGENT_CORE':
        sc, sa = 'CORE', 'KEEP'
        review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'high'
        reason = doctrine_reason
    elif doctrine == 'PRIVATE_AGENT':
        sc, sa = 'PRIVATE', 'EXCLUDE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P1', 'high'
        reason = doctrine_reason
    elif doctrine == 'DOCS_ALPHA':
        sc, sa = 'CORE', 'KEEP'
        review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'high'
        reason = doctrine_reason
    elif doctrine == 'DOCS_PRIVATE':
        sc, sa = 'PRIVATE', 'EXCLUDE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P2', 'high'
        reason = doctrine_reason
    elif doctrine == 'EXTENSION_ALPHA':
        sc, sa = 'CORE', 'KEEP'
        review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'medium'
        reason = doctrine_reason
    elif doctrine == 'EXTENSION_PRIVATE_COUPLING':
        sc, sa = 'REVIEW', 'SANITIZE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P1', 'medium'
        reason = doctrine_reason
    elif doctrine == 'REASONING_ALPHA':
        sc, sa = 'CORE', 'KEEP'
        review_status, severity, confidence = 'AUTO_SAFE', 'P3', 'medium'
        reason = doctrine_reason
    elif doctrine == 'REASONING_PRIVATE_COUPLING':
        sc, sa = 'REVIEW', 'SANITIZE'
        review_status, severity, confidence = 'MUST_CHANGE', 'P1', 'medium'
        reason = doctrine_reason
    elif doctrine == 'KEEP_DASHBOARD' and get_component(rel_path) == 'dashboard' and not leak:
        if 'cost operations center' not in rel_path.lower():
            sc = 'CORE'
            if sa == 'REVIEW':
                sa = 'KEEP'
            if review_status == 'NEEDS_DECISION':
                review_status = 'AUTO_SAFE'
                severity = 'P3'
                confidence = 'medium'
            reason = doctrine_reason

    return Row(
        path=rel_path,
        component=get_component(rel_path),
        subcomponent=get_subcomponent(rel_path),
        doctrine=doctrine,
        doctrine_reason=doctrine_reason,
        kind=kind,
        in_private=priv is not None and priv.exists(),
        in_alpha=alpha is not None and alpha.exists(),
        private_type=path_type(priv),
        alpha_type=path_type(alpha),
        suggested_classification=sc,
        suggested_action=sa,
        confidence=confidence,
        review_status=review_status,
        severity=severity,
        reason=reason,
        notes=notes,
        template_exists=te,
        template_hint=th,
        leak_risk=leak,
    )


def collect_rows() -> List[Row]:
    rows: List[Row] = []
    seen = set()
    private_children = rel_children(PRIVATE_ROOT)
    alpha_children = rel_children(ALPHA_ROOT)
    all_names = sorted(set(private_children) | set(alpha_children), key=str.lower)

    def emit(rel: str, kind: str):
        if rel in seen:
            return
        priv = PRIVATE_ROOT / rel
        alpha = ALPHA_ROOT / rel
        rows.append(make_row(rel, kind, priv if priv.exists() else None, alpha if alpha.exists() else None))
        seen.add(rel)

    for name in all_names:
        emit(name, 'top-level')
        max_depth = EXPAND_DEPTHS.get(name, 1)
        if max_depth <= 0:
            continue
        for rel, path_obj in iter_component_paths(PRIVATE_ROOT, name, max_depth):
            if rel == name:
                continue
            emit(rel, 'descendant')
        for rel, path_obj in iter_component_paths(ALPHA_ROOT, name, max_depth):
            if rel == name:
                continue
            emit(rel, 'descendant')
    return rows


def build_component_summary(rows: List[Row]) -> List[Dict]:
    comps: Dict[str, Dict] = {}
    for r in rows:
        c = comps.setdefault(r.component, {
            'component': r.component,
            'rows': 0,
            'must_change': 0,
            'needs_decision': 0,
            'auto_safe': 0,
            'p0': 0,
            'p1': 0,
            'p2': 0,
            'p3': 0,
            'leak_risk': 0,
            'top_level_paths': [],
        })
        c['rows'] += 1
        c[r.review_status.lower()] += 1
        c[r.severity.lower()] += 1
        c['leak_risk'] += 1 if r.leak_risk else 0
        if r.kind == 'top-level':
            c['top_level_paths'].append(r.path)
    return sorted(comps.values(), key=lambda x: (-x['must_change'], -x['needs_decision'], x['component']))


def build_payload() -> Dict:
    rows = collect_rows()
    summary = {'byClassification': {}, 'byReviewStatus': {}, 'bySeverity': {}}
    for r in rows:
        summary['byClassification'][r.suggested_classification] = summary['byClassification'].get(r.suggested_classification, 0) + 1
        summary['byReviewStatus'][r.review_status] = summary['byReviewStatus'].get(r.review_status, 0) + 1
        summary['bySeverity'][r.severity] = summary['bySeverity'].get(r.severity, 0) + 1
    return {
        'meta': {
            'privateRoot': str(PRIVATE_ROOT),
            'alphaRoot': str(ALPHA_ROOT),
            'outputPath': str(OUTPUT_PATH),
            'rowCount': len(rows),
            'classifications': CLASSIFICATIONS,
            'actions': ACTIONS,
            'reviewStatuses': REVIEW_STATUSES,
            'severities': SEVERITIES,
        },
        'summary': summary,
        'components': build_component_summary(rows),
        'rows': [asdict(r) for r in rows],
    }


HTML = r'''<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DEV4 Alpha Audit Reviewer</title>
  <style>
    :root {
      --bg:#0b0f14; --panel:#101722; --panel2:#15202b; --text:#e5edf6; --muted:#93a4b8;
      --line:#243345; --accent:#5eead4; --warn:#facc15; --danger:#fb7185; --ok:#4ade80;
      --blue:#60a5fa; --purple:#a78bfa; --orange:#fb923c;
    }
    *{box-sizing:border-box}
    body{margin:0;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:var(--bg);color:var(--text)}
    .topbar{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:center;justify-content:space-between;position:sticky;top:0;background:rgba(11,15,20,.96);backdrop-filter:blur(8px);z-index:20}
    .title{font-size:20px;font-weight:700}.subtitle{color:var(--muted);font-size:13px;max-width:980px}
    .controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    button,select,input,textarea{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px}
    button{padding:10px 12px;cursor:pointer} button:hover{border-color:var(--accent)} input,select{padding:10px 12px}
    .wrap{padding:16px}
    .cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px}
    .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
    .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.value{font-size:22px;font-weight:700;margin-top:6px}
    .layout{display:grid;grid-template-columns:380px 1fr;gap:16px}
    .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;min-height:200px}
    .panel h3{margin:4px 0 12px 0;font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
    .component-list{display:flex;flex-direction:column;gap:8px;max-height:70vh;overflow:auto}
    .component{border:1px solid var(--line);border-radius:10px;padding:10px;cursor:pointer;background:#0f1620}
    .component.active{border-color:var(--accent);box-shadow:0 0 0 1px rgba(94,234,212,.2) inset}
    .component .name{font-weight:700}.component .meta{color:var(--muted);font-size:12px;margin-top:6px;display:flex;gap:8px;flex-wrap:wrap}
    .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;border:1px solid var(--line)}
    .P0{color:var(--danger)} .P1{color:var(--orange)} .P2{color:var(--warn)} .P3{color:var(--ok)}
    .CORE{color:var(--ok)} .TEMPLATE{color:var(--warn)} .PLACEHOLDER{color:var(--purple)} .PRIVATE{color:var(--danger)} .DEFER{color:var(--blue)}
    .MUST_CHANGE{color:var(--danger)} .NEEDS_DECISION{color:var(--warn)} .AUTO_SAFE{color:var(--ok)}
    .tablewrap{overflow:auto;border:1px solid var(--line);border-radius:12px}
    table{width:100%;border-collapse:collapse;min-width:1900px} th,td{border-bottom:1px solid var(--line);padding:10px;vertical-align:top}
    th{position:sticky;top:0;background:var(--panel2);z-index:2;text-align:left;font-size:12px;color:var(--muted);text-transform:uppercase}
    tr:hover td{background:#0f1620}
    .path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.small{color:var(--muted);font-size:12px}
    textarea{width:260px;min-height:64px;padding:8px}.yes{color:var(--ok);font-weight:700}.no{color:var(--danger)}
    .queuebar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
    .queuebtn.active{border-color:var(--accent);background:#0f1620}
    @media (max-width: 1200px){ .layout{grid-template-columns:1fr} .component-list{max-height:none} }
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <div class="title">DEV4 Alpha Audit Reviewer</div>
      <div class="subtitle">Component-first triage. Default workflow: review MUST_CHANGE and NEEDS_DECISION only. AUTO_SAFE stays hidden unless explicitly requested.</div>
    </div>
    <div class="controls">
      <input id="search" placeholder="Filter path / reason / note" />
      <select id="queueFilter">
        <option value="MUST_CHANGE">Must change</option>
        <option value="NEEDS_DECISION">Needs decision</option>
        <option value="ALL">All queues</option>
        <option value="AUTO_SAFE">Auto-safe</option>
      </select>
      <select id="severityFilter">
        <option value="">All severities</option>
        <option value="P0">P0</option>
        <option value="P1">P1</option>
        <option value="P2">P2</option>
        <option value="P3">P3</option>
      </select>
      <select id="classFilter"><option value="">All classes</option></select>
      <button onclick="exportJson()">Export JSON</button>
      <button onclick="saveServer()">Save to repo</button>
    </div>
  </div>
  <div class="wrap">
    <div class="cards" id="cards"></div>
    <div class="layout">
      <div class="panel">
        <h3>Components</h3>
        <div class="small" style="margin-bottom:10px">Review by system/component first. File table shows only rows in the selected queue for the selected component.</div>
        <div class="component-list" id="componentList"></div>
      </div>
      <div>
        <div class="queuebar" id="queueSummary"></div>
        <div class="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Path</th><th>Doctrine</th><th>Queue</th><th>Severity</th><th>Suggested</th><th>Action</th><th>Template</th><th>Reason</th><th>Override Class</th><th>Override Action</th><th>Override Queue</th><th>Comment</th>
              </tr>
            </thead>
            <tbody id="tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
<script>
let payload=null, rows=[], selectedComponent='ALL';
function esc(s){ return (s ?? '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function effectiveClass(r){ return r.override_classification || r.suggested_classification; }
function effectiveAction(r){ return r.override_action || r.suggested_action; }
function effectiveQueue(r){ return r.override_review_status || r.review_status; }
function presence(r){ if(r.in_private && r.in_alpha) return 'both'; if(r.in_private) return 'private-only'; if(r.in_alpha) return 'alpha-only'; return 'none'; }

async function load(){
  payload = await fetch('/api/data').then(r=>r.json());
  rows = payload.rows.map((r,i)=>({...r,_id:i}));
  const cf = document.getElementById('classFilter');
  payload.meta.classifications.forEach(c=>cf.insertAdjacentHTML('beforeend', `<option value="${c}">${c}</option>`));
  hydrateLocal();
  renderCards(); renderComponents(); renderQueueSummary(); renderTable();
}

function hydrateLocal(){
  const saved = localStorage.getItem('dev4-audit-overrides-v2');
  if(!saved) return;
  try {
    const prior = JSON.parse(saved);
    const byPath = new Map(prior.map(r => [r.path, r]));
    rows = rows.map(r => ({...r, ...(byPath.get(r.path) || {})}));
  } catch(e) {}
}
function persist(repaint=true){ localStorage.setItem('dev4-audit-overrides-v2', JSON.stringify(rows)); if(repaint){ renderCards(); renderComponents(); renderQueueSummary(); renderTable(); } }

function setOverrideClass(id, value){ rows.find(r=>r._id===id).override_classification=value; persist(); }
function setOverrideAction(id, value){ rows.find(r=>r._id===id).override_action=value; persist(); }
function setOverrideQueue(id, value){ rows.find(r=>r._id===id).override_review_status=value; persist(); }
function setComment(id, value){ rows.find(r=>r._id===id).comment=value; persist(false); }

function renderCards(){
  const counts={rows:rows.length, MUST_CHANGE:0, NEEDS_DECISION:0, AUTO_SAFE:0, P0:0, P1:0, P2:0, P3:0};
  rows.forEach(r=>{ counts[effectiveQueue(r)]++; counts[r.severity]++; });
  const items=[['Rows',counts.rows],['Must change',counts.MUST_CHANGE],['Needs decision',counts.NEEDS_DECISION],['Auto-safe',counts.AUTO_SAFE],['P0',counts.P0],['P1',counts.P1]];
  document.getElementById('cards').innerHTML = items.map(([label,value])=>`<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
}

function componentRows(name){ return rows.filter(r => name==='ALL' || r.component===name); }

function renderComponents(){
  const comps = payload.components.map(c => {
    const subset = componentRows(c.component);
    const must = subset.filter(r=>effectiveQueue(r)==='MUST_CHANGE').length;
    const need = subset.filter(r=>effectiveQueue(r)==='NEEDS_DECISION').length;
    return {...c, must_live: must, need_live: need};
  });
  const all = {component:'ALL', rows:rows.length, must_live: rows.filter(r=>effectiveQueue(r)==='MUST_CHANGE').length, need_live: rows.filter(r=>effectiveQueue(r)==='NEEDS_DECISION').length, p0: rows.filter(r=>r.severity==='P0').length};
  const list=[all, ...comps].sort((a,b)=> a.component==='ALL' ? -1 : b.component==='ALL' ? 1 : (b.must_live-a.must_live)||(b.need_live-a.need_live)||a.component.localeCompare(b.component));
  document.getElementById('componentList').innerHTML = list.map(c=>`
    <div class="component ${selectedComponent===c.component?'active':''}" onclick="selectComponent('${c.component.replace(/'/g, "\\'")}')">
      <div class="name">${esc(c.component)}</div>
      <div class="meta">
        <span class="pill MUST_CHANGE">must ${c.must_live || 0}</span>
        <span class="pill NEEDS_DECISION">decision ${c.need_live || 0}</span>
        <span class="pill P0">p0 ${c.p0 || 0}</span>
        <span class="pill P1">rows ${c.rows || 0}</span>
      </div>
    </div>`).join('');
}
function selectComponent(name){ selectedComponent=name; renderQueueSummary(); renderTable(); renderComponents(); }

function renderQueueSummary(){
  const subset = componentRows(selectedComponent);
  const counts = {MUST_CHANGE:0, NEEDS_DECISION:0, AUTO_SAFE:0};
  subset.forEach(r=>counts[effectiveQueue(r)]++);
  const current = document.getElementById('queueFilter').value;
  document.getElementById('queueSummary').innerHTML = ['MUST_CHANGE','NEEDS_DECISION','AUTO_SAFE'].map(q => `<button class="queuebtn ${current===q?'active':''}" onclick="document.getElementById('queueFilter').value='${q}'; renderTable();">${q.replace('_',' ')} (${counts[q]})</button>`).join('') + `<span class="small" style="align-self:center">Component: ${esc(selectedComponent)}</span>`;
}

function filteredRows(){
  const q = document.getElementById('search').value.trim().toLowerCase();
  const queue = document.getElementById('queueFilter').value;
  const sev = document.getElementById('severityFilter').value;
  const cls = document.getElementById('classFilter').value;
  return componentRows(selectedComponent).filter(r => {
    if(queue !== 'ALL' && effectiveQueue(r) !== queue) return false;
    if(sev && r.severity !== sev) return false;
    if(cls && effectiveClass(r) !== cls && r.suggested_classification !== cls) return false;
    if(q){
      const blob = [r.path, r.reason, r.comment, r.template_hint, r.component].join(' ').toLowerCase();
      if(!blob.includes(q)) return false;
    }
    return true;
  }).sort((a,b)=> {
    const severityOrder = {P0:0,P1:1,P2:2,P3:3};
    const queueOrder = {MUST_CHANGE:0,NEEDS_DECISION:1,AUTO_SAFE:2};
    return (queueOrder[effectiveQueue(a)]-queueOrder[effectiveQueue(b)]) || (severityOrder[a.severity]-severityOrder[b.severity]) || a.path.localeCompare(b.path);
  });
}

function renderTable(){
  const body = document.getElementById('tbody');
  const rowsNow = filteredRows();
  body.innerHTML = rowsNow.map(r => {
    const classOptions = payload.meta.classifications.map(c=>`<option value="${c}" ${r.override_classification===c?'selected':''}>${c}</option>`).join('');
    const actionOptions = payload.meta.actions.map(a=>`<option value="${a}" ${r.override_action===a?'selected':''}>${a}</option>`).join('');
    const queueOptions = payload.meta.reviewStatuses.map(q=>`<option value="${q}" ${r.override_review_status===q?'selected':''}>${q}</option>`).join('');
    return `<tr>
      <td class="path">${esc(r.path)}<div class="small">${esc(r.component)} / ${esc(r.subcomponent)} · ${presence(r)} ${r.leak_risk ? '· leak-signal' : ''}</div></td>
      <td><span class="pill">${esc(r.doctrine)}</span><div class="small">${esc(r.doctrine_reason)}</div></td>
      <td><span class="pill ${effectiveQueue(r)}">${effectiveQueue(r)}</span><div class="small">${esc(r.confidence)}</div></td>
      <td><span class="pill ${r.severity}">${r.severity}</span></td>
      <td><span class="pill ${r.suggested_classification}">${r.suggested_classification}</span><div class="small">effective: ${esc(effectiveClass(r))}</div></td>
      <td>${esc(r.suggested_action)}<div class="small">effective: ${esc(effectiveAction(r))}</div></td>
      <td>${r.template_exists?'<span class="yes">yes</span>':'<span class="no">no</span>'}<div class="small">${esc(r.template_hint || '')}</div></td>
      <td class="small" style="max-width:280px">${esc(r.reason)}</td>
      <td><select onchange="setOverrideClass(${r._id}, this.value)"><option value="">—</option>${classOptions}</select></td>
      <td><select onchange="setOverrideAction(${r._id}, this.value)"><option value="">—</option>${actionOptions}</select></td>
      <td><select onchange="setOverrideQueue(${r._id}, this.value)"><option value="">—</option>${queueOptions}</select></td>
      <td><textarea oninput="setComment(${r._id}, this.value)" placeholder="Decision / note">${esc(r.comment || '')}</textarea></td>
    </tr>`;
  }).join('');
}

function exportJson(){
  const blob = new Blob([JSON.stringify({meta:payload.meta, rows}, null, 2)], {type:'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'dev4-audit-review.json'; a.click();
}
async function saveServer(){
  const res = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({meta: payload.meta, rows})});
  const out = await res.json(); alert(out.message || 'saved');
}
['search','queueFilter','severityFilter','classFilter'].forEach(id => document.addEventListener('DOMContentLoaded', () => document.getElementById(id).addEventListener(id==='search' ? 'input' : 'change', ()=>{ renderQueueSummary(); renderTable(); })));
document.addEventListener('DOMContentLoaded', load);
</script>
</body>
</html>
'''


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: Dict):
        data = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, code: int, text: str):
        data = text.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self._html(200, HTML)
        if parsed.path == '/api/data':
            return self._json(200, build_payload())
        if parsed.path == '/api/health':
            return self._json(200, {'ok': True, 'port': PORT})
        return self._json(404, {'error': 'not found'})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/save':
            return self._json(404, {'error': 'not found'})
        length = int(self.headers.get('Content-Length', '0'))
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            return self._json(200, {'ok': True, 'message': f'Saved to {OUTPUT_PATH}'})
        except Exception as e:
            return self._json(400, {'ok': False, 'message': str(e)})


def main():
    server = HTTPServer((HOST, PORT), Handler)
    print(f'Running DEV4 audit reviewer on http://{HOST}:{PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
