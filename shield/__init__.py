"""
Symbiotic Shield - Runtime Security Agent

A security monitoring agent that runs alongside AI agents to detect
attacks and prevent sensitive data exposure.

See README.md for full documentation.
"""

try:
    from .a2a_monitor import A2AMonitor, A2ASecurityResult, A2ATask, A2AThreatType, AgentCard  # noqa: F401
    from .classifier import (  # noqa: F401
        ClassificationResult,
        DataClassifier,
        SensitivityLevel,
        can_egress,
        classify,
        redact,
    )
    from .logician_bridge import (  # noqa: F401
        LogicianResult,
        LogicianShieldBridge,
        can_use_tool,
        check_injection,
        get_bridge,
        is_forbidden_output,
        verify_spawn,
    )
    from .scanner import Scanner, ScanResult, ThreatType, scan  # noqa: F401
    from .shield import (  # noqa: F401
        Alert,
        AlertSeverity,
        BlockedError,
        InterventionMode,
        Shield,
        ShieldConfig,
        check_a2a,
        get_shield,
        scan_input,
        scan_output,
    )
except ImportError:
    pass

__version__ = "1.0.0"
__all__ = [
    n
    for n in [
        "Scanner",
        "ScanResult",
        "ThreatType",
        "scan",
        "DataClassifier",
        "ClassificationResult",
        "SensitivityLevel",
        "classify",
        "can_egress",
        "redact",
        "A2AMonitor",
        "A2ASecurityResult",
        "AgentCard",
        "A2ATask",
        "A2AThreatType",
        "LogicianShieldBridge",
        "LogicianResult",
        "get_bridge",
        "verify_spawn",
        "is_forbidden_output",
        "check_injection",
        "can_use_tool",
        "Shield",
        "ShieldConfig",
        "BlockedError",
        "Alert",
        "AlertSeverity",
        "InterventionMode",
        "get_shield",
        "scan_input",
        "scan_output",
        "check_a2a",
    ]
    if n in globals()
]
