# SSOT-L1-R-AWARENESS — Context Injection System
Updated: {{GENERATED_DATE}}

## Purpose
R-Awareness automatically injects relevant SSoT documents into your agent's context when conversation keywords trigger them. This gives your agent "just-in-time" awareness without burning tokens on unused docs.

## How It Works

1. **Keywords in conversation** → R-Awareness checks `keywords.json`
2. **Match found** → Injects specified SSoT document(s)
3. **Agent sees the doc** → Can reference it in the response

**Example:** User says "update the dashboard" → R-Awareness injects `SSOT-L1-DASHBOARD.md`

## Configuration

### File: `keywords.json`
Located at: `{{R_AWARENESS_CONFIG_PATH}}/keywords.json`

**Format:**
```json
{
  "keyword": ["path/to/SSOT-FILE.md"],
  "compound keyword phrase": ["file1.md", "file2.md"],
  "trigger_word": ["SSOT-L1-COMPONENT.md"]
}
```

### Cold-Start Documents
Documents injected at session start (before any keywords):
```json
{
  "coldStartDocs": [
    "ssot/L1/RECENT-HEADERS.md",
    "ssot/L0/SSOT-L0-OVERVIEW.ai.md"
  ]
}
```

## Keyword Strategy

### Good Keywords
- Specific component names ("shield", "logician", "dashboard")
- Action verbs related to a component ("wallet", "bounty", "compress")
- Domain-specific terms ("SSoT", "protocol", "DAO")

### Bad Keywords
- Generic words ("update", "check", "fix") — too broad
- Overlapping keywords that trigger the same doc
- Keywords for rarely-used docs

## Document Selection

### Prefer `.ai.md` (Compressed)
- 50-80% token savings
- Enough detail for most tasks
- Faster to load

### Use `.md` (Full) When:
- Deep implementation work
- Debugging complex issues
- Writing detailed documentation

## Example Configuration

```json
{
  "dashboard": ["ssot/L1/SSOT-L1-DASHBOARD.ai.md"],
  "shield": ["ssot/L1/SSOT-L1-SHIELD.ai.md"],
  "logician": ["ssot/L1/SSOT-L1-LOGICIAN.ai.md"],
  "lcm": ["ssot/L1/SSOT-L1-LCM.md"],
  "memory": ["ssot/L1/SSOT-L1-MEMORY-ARCHITECTURE.ai.md"],
  "wallet": ["ssot/L1/SSOT-L1-SYMBIOTIC-WALLET.ai.md"],
  "dao": ["ssot/L2/SSOT-L2-DAO-ORCHESTRATION.ai.md"],
  "ssot system": ["ssot/L1/SSOT-L1-SSOT-SYSTEM.ai.md"],
  
  "coldStartDocs": [
    "ssot/L1/RECENT-HEADERS.md"
  ]
}
```

## Token Budget

R-Awareness-injected docs count toward your context window. Balance coverage vs cost:
- **Heavy injection (10-15 docs):** High token cost, always-ready agent
- **Light injection (3-5 docs):** Low token cost, agent asks for clarification more often

**Recommendation:** Start light, add keywords as needed based on actual usage.

## Maintenance

### Review Quarterly
- Which keywords trigger frequently?
- Are docs up-to-date?
- Any new components need keywords?

### Regenerate Compressed Docs
After updating a `.md` file:
1. Delete the old `.ai.md`
2. Regenerate via compression script
3. Update `keywords.json` if paths changed

---

_This document explains R-Awareness. Customize `keywords.json` to match your SSoT structure._
