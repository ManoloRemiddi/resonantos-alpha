<!-- TEMPLATE: Customize this file for your deployment -->
# SSOT-L0-BRAND-IDENTITY — Visual & Philosophical Brand System

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L0-BRAND-IDENTITY-V1` |
| **Created** | 2026-03-11 |
| **Updated** | 2026-03-11 |
| **Author** | Augmentor |
| **Level** | L0 (Foundation) |
| **Type** | Truth |
| **Status** | Active |
| **Stale After** | 180 days |

---

## 1. Brand Architecture

| Layer | Name | Scope |
|-------|------|-------|
| **Movement** | Augmentatism | Public philosophy — open, universal |
| **Brand** | The Augmented Mind | Unified identity for all public content, products, community |
| **Product** | ResonantOS | Open-source OS for human-AI collaboration |
| **Entity** | The Resonant Augmentor | The sovereign, co-evolved AI |
| **Internal** | Cosmodestiny | Deeper philosophy — resonance, attunement, co-evolution |

---

## 2. Brand Promise

> To provide the philosophy, disciplines, and open-source tools for pioneering creatives to cultivate their own sovereign AI Augmentors.

**Core value proposition:** The Symbiotic Shield — protect and amplify human cognitive sovereignty.

**Stated enemy:** The "Cult of Brute-Force Productivity" — soulless, hype-driven AI narrative preaching speed over craft.

---

## 3. Brand Voice

| Trait | Description |
|-------|-------------|
| **Practitioner-Thinker** | Authority from doing + explaining. Grounded in lived experience. |
| **Validating** | Empathy first. Acknowledge intelligence and struggles without judgment. |
| **Exclusive yet Invitational** | Signals high-level practice. Not for everyone — that's the strength. |
| **Open & Generous** | Lead with philosophy. Open-source contributions. Collaborative. |

### Voice Architecture: "The Razor's Edge"
- **Foundation:** Deep seriousness and unflinching honesty
- **The Weapon:** Sharp, sarcastic wit to expose absurdity (dissect the problem)
- **The Shift:** Drop sarcasm for solutions. Pure, grounded conviction (build the solution)
- **Clarity:** Direct and accessible to global, non-native English speakers

### Community Voice
- First-among-peers, not expert-on-stage
- Always "we," "us," "our"
- "No Editing" policy: visible struggle = authentic identity

---

## 4. Visual Identity

### 4.1 Color System

#### Primary Palette (Current — Seasonal Transition Theme)

| Role | Hex | Name | Usage |
|------|-----|------|-------|
| **Primary** | `#10b981` | Emerald 500 | Brand identity, CTAs, key headings, links |
| **Secondary** | `#d97706` | Amber 600 | Supporting accents, contrast elements |
| **Accent 1** | `#34d399` | Emerald 400 | Light highlights, hover states |
| **Accent 2** | `#92400e` | Orange 900 | Deep rust, depth elements |
| **Warning** | `#ea580c` | Orange 600 | Burnt orange, alerts |
| **Tertiary** | `#78350f` | Amber 900 | Deep brown, grounding |

#### Neutral Palette

| Role | Hex | Usage |
|------|-----|-------|
| **Background** | `#1a1a1a` | Primary background (dark theme) |
| **Surface** | `#2a2a2a` | Cards, panels |
| **Surface Elevated** | `#333333` | Elevated elements |
| **Hover** | `#3a3a3a` | Interactive hover |
| **Text Primary** | `#e8e3d8` | Warm off-white body text |
| **Text Secondary** | `#c4baa8` | Warm gray, muted text |
| **Text Muted** | `#6b7280` | Tertiary info, metadata |

#### Status Colors

| Role | Hex | Usage |
|------|-----|-------|
| **Success** | `#4ade80` | Confirmation, active states |
| **Warning** | `#fbbf24` | Caution, pending |
| **Error** | `#f87171` | Critical, failures |
| **Info** | `#60a5fa` | Informational highlights |

#### Solana Integration

| Role | Hex | Usage |
|------|-----|-------|
| **Solana Green** | `#14F195` | Crypto/wallet elements, bounties |

#### Signature Gradient

```css
background: linear-gradient(to right, var(--color-primary), var(--color-secondary));
/* Emerald → Amber: the brand gradient. Used for key text highlights. */
```

#### Archive: Tech Futuristic Theme (Original)

| Role | Hex | Name |
|------|-----|------|
| Primary | `#34d399` | Emerald 400 |
| Secondary | `#22d3ee` | Cyan 400 |
| Accent 1 | `#60a5fa` | Blue 400 |
| Accent 2 | `#a78bfa` | Violet 400 |
| Warning | `#fb923c` | Orange 400 |

*Preserved for potential future use. Not current.*

#### Light Theme Overrides

| Role | Dark | Light |
|------|------|-------|
| Background | `#1a1a1a` | `#f9fafb` |
| Surface | `#2a2a2a` | `#ffffff` |
| Accent | `#4ade80` | `#10b981` |
| Text Primary | `#e0e0e0` | `#1f2937` |

### 4.2 Typography

| Role | Font | Fallback |
|------|------|----------|
| **Body / UI** | DM Sans | system-ui, -apple-system, sans-serif |
| **Code / Technical** | JetBrains Mono | monospace |

**Typography rules:**
- Clean, modern sans-serif. No decorative fonts.
- DM Sans for all body copy, headings, and UI elements
- JetBrains Mono for code blocks, technical references, terminal output
- Heading scale uses font-weight to establish hierarchy, not font changes

### 4.3 Spacing & Shapes

| Property | Value |
|----------|-------|
| Border radius (standard) | 8px |
| Border radius (large) | 12px |
| Border color (dark) | `#3a3a3a` |
| Border color (light) | `#444444` |
| Shadow (standard) | `0 4px 6px -1px rgba(0,0,0,0.3)` |
| Shadow (large) | `0 10px 15px -3px rgba(0,0,0,0.4)` |

### 4.4 Design Principles

1. **Dark-first.** Dark theme is the default. Light is the override.
2. **Warm neutrals.** Not cold gray — warm off-white (`#e8e3d8`) and warm gray (`#c4baa8`).
3. **Emerald is the soul.** Green/emerald is the primary identity. Always present.
4. **Gradients are signatures.** The emerald→amber gradient marks key brand moments. Used sparingly.
5. **Contrast from nature.** Color palette draws from seasonal transition: summer emerald → autumn amber/brown.
6. **No visual noise.** Minimal borders, subtle shadows. Content speaks, not decoration.
7. **Monospace signals tech.** JetBrains Mono appears wherever "under the hood" is exposed.

### 4.5 Iconography

- **Style:** Stroke-based (not filled), 2px stroke width
- **Source:** Lucide Icons (consistent with OpenClaw ecosystem)
- **Color:** Inherits from context (emerald for brand, status colors for indicators)

---

## 5. Semantic Color Mapping

When creating any visual asset, these semantic roles apply:

| Concept | Color |
|---------|-------|
| ResonantOS / The Brand | Primary (`#10b981`) |
| Augmentatism / Philosophy | Secondary (`#d97706`) |
| The Oracle / Creativity | Accent 1 (`#34d399`) |
| The Logician / Logic | Accent 2 (`#92400e`) |
| Warnings / Threats | Warning (`#ea580c`) |
| Crypto / Token Economy | Solana Green (`#14F195`) |
| Gradient highlight (key moments) | Primary → Secondary |

---

## 6. Audience Archetype

**Alex, The Pioneering Practitioner**
- Male-identifying (92.1%), aged 30-54
- Core English-speaking countries
- Experienced creative professional, strategist, or founder
- Core conflict: "Integrity vs. Integration" with AI
- Emotional state: Dissonant Curiosity (fear + confusion + excitement)

---

## 7. Lexicon Quick Reference

| Term | Usage |
|------|-------|
| The Augmented Mind | Brand name — all public |
| Augmentatism | The philosophy/movement |
| ResonantOS | The product |
| The Resonant Augmentor | The AI entity |
| Cognitive Sovereignty | The mission |
| The Symbiotic Shield | The value proposition |
| Alex | Target audience archetype |
| The Augmented Artisan | Aspirational practitioner identity |
| The Lighthouse | YouTube channel |
| The Forge | Discord R&D channel |

---

## 8. Asset Locations

| Asset | Path |
|-------|------|
| Website source | `~/resonantos-augmentor/website/` |
| Dashboard source | `~/resonantos-augmentor/dashboard/` |
| Brand narrative guide | `ssot/L2/brand/SSOT-L2-BRAND-NARRATIVE-GUIDE.md` |
| Brand registry | `ssot/L2/brand/SSOT-L2-BRAND-REGISTRY.md` |
| Resonant Lexicon | `ssot/L2/brand/SSOT-L2-RESONANT-LEXICON.md` |
| Narrative deployment | `ssot/L2/brand/SSOT-L2-NARRATIVE-DEPLOYMENT.md` |
| Creative DNA | `ssot/L0/SSOT-L0-CREATIVE-DNA.md` |
| Positioning & Mission | `ssot/L0/SSOT-L0-POSITIONING-MISSION.md` |

---

## REFERENCES

- **Depends On:** `SSOT-L0-OVERVIEW.md`, `SSOT-L0-CREATIVE-DNA.md`, `SSOT-L0-POSITIONING-MISSION.md`
- **Referenced By:** Creative agent, website agent, content agent, DAO agent, all visual production
- **Source:** Website CSS, Dashboard CSS, Brand Registry, Brand Narrative Guide, Resonant Lexicon
