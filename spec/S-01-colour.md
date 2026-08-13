# S-1 — Colour, pattern and outline encoding

**Requirement.** Technologies MUST be encoded by research area, crisis faction, and rarity or
danger, across three separate visual channels.

## Channel assignment

| Channel | Encodes |
| --- | --- |
| Card background | Research area, or crisis faction where the technology belongs to one |
| Card outline | Research area, **overridden** by rare or dangerous where applicable |
| Card badges | Rare, dangerous, repeatable, gate, mod requirement, tier |

**Outline priority: dangerous outranks rare.** A technology that is both renders a 45° split
outline, dangerous red occupying the top-left half so it reads first on a left-to-right scan.

## Background palette

| Classification | Colour | Pattern |
| --- | --- | --- |
| Physics | blue | flat |
| Society | green | flat |
| Engineering | orange | flat |
| Aeternum | `#823269` | honeycomb, regular hexagons |
| Blokkats | `#1C451C` (see below) | Blokkat flag arrow, tiled, light green outline |
| Compound | `#2F137F` | fused overlapping cells |
| Sirenalia | *unresolved, see below* | soft sweeping bands |
| Katzenartig Imperium | `#2E3F98` with `#CC9429` | gold saltire lattice |

## Acceptance criteria

- Colours and patterns are defined as design tokens in a single source of truth consumed by
  both node rendering and connector rendering (P-8). No component hard-codes a colour.
- **Colour MUST NOT be the sole carrier of any information required to use the tool.** Every
  classification is also conveyed by a non-colour channel:
  - Crisis faction — background pattern
  - Rare — badge
  - Dangerous — badge, plus the warning treatment in P-12.3
  - Research area — the category filter list and the popup
- Patterns MUST NOT reduce the legibility of node text, icons or badges.
- Every background colour MUST clear WCAG AA contrast against the card's text colour.
- Pattern stroke colours are defined explicitly per faction, not derived by lightening the
  background — dark backgrounds do not yield legible derived strokes.
- The user guide legend (P-11) documents both channels.

## Implied technical decisions

- Patterns MUST degrade gracefully. Per-node pattern fills become prohibitively expensive at
  low zoom, so below a defined threshold the renderer switches to a solid treatment. That
  threshold lives in the shared LOD table with S-3 and the badge-shedding rules.
- **The degraded state is where the palette must still work.** Two identities that differ only
  by pattern become indistinguishable the moment the pattern sheds. Every pair of background
  colours MUST remain distinguishable as flat fills.

## UNRESOLVED — two palette conflicts

**Blokkat green is too dark.** `#1C451C` against a dark application background reads as a
tinted hole rather than a green node once the pattern sheds at low zoom. Proposed resolution:
lift the node fill to approximately `#2A6B2A` and retain `#1C451C` for the tier-band or lane
backing, so the authentic flag colour still appears.

**Sirenalia and Aeternum collide.** The reference treatment uses a muted plum field on which
the soft sweeping bands are visible; the bands disappear against a bright magenta. But muted
plum is adjacent to Aeternum's `#823269`, and the two merge once patterns shed. Resolution
requires choosing one of: bright magenta with harder-edged waves, or muted plum with Aeternum
moved to a different hue.
