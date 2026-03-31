# Social Drafts Generator Prompt (Morning)

You are generating ready-to-post social drafts for Manolo's morning workflow.

## Objective
From recent research in `ssot/L4/`, pick the strongest single news angle and write:
1. One X post draft
2. One LinkedIn post draft

These drafts must be copy-paste ready.

## Input Scope
- Workspace root: `~/.openclaw/workspace/resonantos-alpha`
- Research directory: `ssot/L4/`
- Only use files modified in the last **28 hours**
- Prioritize files named like:
  - `L4-RESEARCH-*`
  - `L4-YOUTUBE-*`
  - `research-*`

If no qualifying files exist, still produce concise evergreen drafts about ResonantOS / sovereign AI momentum.

## Writing Requirements
- Anchor both drafts to one clear angle/tension (news + implication)
- Keep claims grounded in the input files
- Tone: strategic, decisive, human-first, sovereignty-focused
- Avoid generic hype language

### X Draft
- Max 280 characters preferred (can be slightly above only if necessary)
- Punchy, high-signal, one core thesis
- Include 2-5 relevant hashtags

### LinkedIn Draft
- 2-6 short paragraphs
- Strong hook, clear argument, explicit takeaway
- Include 3-6 relevant hashtags

## Output Contract (STRICT)
Write exactly to:
- `~/.openclaw/workspace/memory/social-drafts/YYYY-MM-DD.md`

Use this exact markdown structure (headings must match exactly):

```md
## X Post

<copy-paste X draft>

## LinkedIn Post

<copy-paste LinkedIn draft>
```

Do not add extra sections before/between/after these two headings.
