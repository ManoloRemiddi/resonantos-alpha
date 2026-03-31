# ResonantOS Alpha DEV4 — Scope and Build Specification

## Purpose

DEV4 is the **public alpha baseline** of ResonantOS.

It must be:
- a **sanitized derivative** of Manolo's working local system
- **self-sufficient** on a fresh OpenClaw installation
- **free of personal data, private credentials, private memory, and unfinished add-on code**
- **sourced from Manolo's machine**, not reconstructed from external forks or third-party repo variants

## Core Principle

**Manolo's local system is the source build.**

DEV4 is not an independent product invented from scratch.
DEV4 is a **clean public extraction** of the working local system:

> local working system
> minus personal/private/sensitive content
> minus unfinished add-on code
> plus templates where private files currently exist

## Target Outcome

A user should be able to install DEV4 onto a fresh OpenClaw setup and get a working ResonantOS foundation without needing Manolo's personal system.

That means DEV4 must contain all code required for:
- installation
- basic operation
- setup/onboarding
- dashboard/core interface
- core architecture docs/templates
- public-safe defaults

But DEV4 must not contain Manolo-specific operational state.

---

## What DEV4 IS

DEV4 is:
- a **self-sufficient alpha distribution**
- a **clean extraction** from Manolo's real working installation
- a **public-safe baseline**
- a **template-driven system** where personal files are replaced with generic versions

## What DEV4 IS NOT

DEV4 is not:
- a mirror of Manolo's private repo
- a minimal toy demo disconnected from the real system
- a dump of unfinished internal add-ons
- a branch assembled from mixed external repo states
- a container for personal memory, identity, credentials, or private project material

---

## Build Rule

### Source of truth
The contents for DEV4 must come from:
- Manolo's current machine
- Manolo's working local ResonantOS/OpenClaw system
- the actual files/codepaths currently used there

Not from:
- stale forks
- older public branches
- experimental external variants
- guessed reconstructions

### Translation rule
For every file/path in the local system, classify it as one of:
- **KEEP** — ship in DEV4 as code/docs
- **SANITIZE** — ship after removing personal/private details
- **TEMPLATE** — replace with generic starter template
- **HIDE** — mention in UI/setup only, but do not ship code yet
- **EXCLUDE** — do not include in DEV4 at all

---

## DEV4 MUST INCLUDE

### 1. Core runnable system
DEV4 must include the code required to be operational on a fresh OpenClaw install:
- installer logic
- setup/onboarding flow
- dashboard/core UI
- core scripts required for installation or operation
- required extensions/plugins that are already part of the real working baseline
- public-safe docs needed to understand and operate the system

### 2. Template-based personal file replacements
Where Manolo's system contains personal files, DEV4 should provide templates instead.

Examples:
- `SOUL.md` → template/generic starter
- `USER.md` → template
- `MEMORY.md` → template or empty starter
- `TOOLS.md` → template
- `HEARTBEAT.md` → template/default
- identity/setup docs → generic starter versions
- SSoTs that are personal/private → templates instead of originals

### 3. Public-safe architecture documentation
DEV4 should explain the architecture clearly enough that users can install and operate it.

This includes:
- what ResonantOS is
- how it sits on top of OpenClaw
- what the setup process does
- what files the user is expected to customize
- what components are core vs optional

---

## DEV4 MUST NOT INCLUDE

### 1. Personal/private material
Do not ship:
- passwords
- tokens
- private keys
- secrets
- personal emails
- personal names where not intended for public docs
- private memory logs
- Manolo's MEMORY.md contents
- daily memory files
- personal device configs
- personal crons
- personal node/device pairings
- private infrastructure details
- local machine-specific operational state

### 2. Custom agents from Manolo's private system
Do not ship Manolo's custom agents as active product code unless explicitly productized.

If needed:
- replace with generic examples/templates
- or exclude entirely

### 3. Unfinished add-ons as live code
Any add-on shown in the setup page/add-ons page but not ready for alpha must:
- appear only as **UI placeholders / coming soon items**
- not be present as active shipped code
- not be installed by default
- not appear as functioning production components

This is a critical DEV4 rule.

If an add-on is not ready, its state must be:
- visible in product positioning
- absent from shipped implementation

### 4. Private SSoTs and internal docs
Do not ship:
- Manolo's private SSoTs
- internal-only project docs
- strategy docs
- private architecture notes
- private memory-linked docs

Instead:
- create templates for the SSoTs meant to be user-customizable
- include only public-safe architectural docs

---

## Add-on Policy for DEV4

### Rule
Add-ons listed in setup/add-ons UI may exist as:
- labels
- descriptions
- roadmap placeholders
- disabled selections

But if they are not ready, they must **not** ship as actual implementation code in DEV4.

### Implication
For each add-on currently represented in code, decide:
- **Promote to core** if DEV4 needs it to be self-sufficient
- **Ship as add-on** only if it is actually ready
- **UI-only placeholder** if not ready
- **Remove entirely** if premature/confusing

### Current intent
The add-ons page is allowed to describe future capabilities.
The repository must not pretend these are production-ready if they are not.

---

## Architectural Standard for DEV4

DEV4 should be understood as:

### Core layer
The minimum runnable ResonantOS foundation required for a clean public alpha.

### Template layer
User-customizable files replacing Manolo-specific content.

### Placeholder layer
Roadmap/add-on items visible in UI but not implemented in shipped code.

This separation must be explicit in both:
- repository structure
- installer/setup behavior
- documentation

---

## Repository Discipline for DEV4

### Branch target
DEV4 will be prepared on:
- `dev4`

### Construction method
DEV4 should be built by auditing Manolo's local working system path-by-path and classifying each item.

Not by:
- blindly copying `dev3`
- blindly diffing against external forks
- assuming existing alpha content is correct

### Practical rule
DEV3 is a reference for what exists now.
It is **not** the canonical definition of what alpha should be.

Manolo's local system defines the source.
DEV4 is the cleaned extraction.

---

## Proposed Classification Framework

Every top-level component should be reviewed under these labels:

- **CORE** — required for self-sufficient alpha
- **TEMPLATE** — user-specific but should exist as starter file
- **PLACEHOLDER** — visible in UI only, no backend/live code
- **PRIVATE** — never ship
- **DEFER** — not for DEV4 yet

---

## Immediate Working Questions for DEV4 Audit

We need to answer these systematically:

1. What exact directories/files from Manolo's local system are part of the core runnable baseline?
2. Which files are personal state versus reusable product code?
3. Which SSoTs become templates?
4. Which current DEV3 components are unfinished add-ons and must be removed from shipped code?
5. Which components are required for fresh-install self-sufficiency and therefore must remain?
6. What should the add-ons page show versus what the repository should actually contain?
7. Which docs must be rewritten to reflect this separation clearly?

---

## Initial Decision Statements

These are the current decisions captured from Manolo:

1. **DEV3 is not correct.**
2. **DEV4 must be based on Manolo's actual working local system.**
3. **DEV4 = local system minus private data/state plus templates.**
4. **Unready add-ons should appear only in setup/add-ons UI, not as shipped code.**
5. **DEV4 must be self-sufficient on a fresh OpenClaw install.**
6. **Templates replace private SSoTs and personal workspace files.**
7. **Custom agents, memory, secrets, passwords, private keys, and private docs must not ship.**

---

## Next Step

Build a path-by-path audit table from Manolo's local system with columns:

| Path | Current Role in Local System | DEV4 Classification | Action | Notes |
|------|-------------------------------|---------------------|--------|-------|
| example/path | core runtime | CORE | keep | needed for fresh install |
| example/private-file | personal identity | TEMPLATE | replace | generic starter |
| example/addon | unfinished addon | PLACEHOLDER | remove code / keep UI note | not ready |

This audit table should become the implementation plan for branch `dev4`.
