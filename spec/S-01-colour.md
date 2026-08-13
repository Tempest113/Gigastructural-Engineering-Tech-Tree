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
| Blokkats | `#2A6B2A`, pattern stroke `#63A85C` | Blokkat flag arrow, tiled, light green outline |
| Compound | `#2F137F` | fused overlapping cells |
| Sirenalia | `#B0338C` | soft sweeping bands, high-contrast |
| Katzenartig Imperium | `#2E3F98` with `#CC9429` | gold saltire lattice |

`#1C451C` — the authentic Blokkat flag green — is reserved for the tier-band or lane backing, not
the node fill; see below.

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
  low zoom, so below 7% zoom the renderer switches to a solid fill of the same background
  colour — S-3's level-of-detail table, "Pattern degradation" stage, is the single definition of
  this threshold; it is not decided independently here.
- **The degraded state is where the palette must still work.** Two identities that differ only
  by pattern become indistinguishable the moment the pattern sheds. **Every pair of background
  colours MUST differ by at least 15 CIEDE2000 units**, measured as flat fills (pattern removed).
  This is a measurable, CI-checkable replacement for "distinguishable" — the build MUST compute
  pairwise ΔE2000 across the full token set and fail if any pair is under threshold, the same way
  the WCAG AA text-contrast rule above is checked mechanically rather than eyeballed.
- Below S-3's coloured-block LOD threshold, colour is permitted to be the sole carrier — see
  S-3's level-of-detail table for that explicit, narrow exception to the rule above.

## Resolved — two palette conflicts

**Blokkat green was too dark.** `#1C451C` against a dark application background read as a
tinted hole rather than a green node once the pattern shed at low zoom. Resolved: the node fill
is lifted to `#2A6B2A`, with pattern stroke `#63A85C` for legible detail on the flat fill.
`#1C451C`, the authentic flag colour, is retained for the tier-band or lane backing rather than
dropped.

**Sirenalia and Aeternum collided.** The reference treatment's muted plum field sat adjacent to
Aeternum's `#823269` and the two merged once patterns shed. Resolved: Sirenalia moves to
`#B0338C`, a high-contrast magenta clear of Aeternum's hue, with the sweeping-band pattern
redrawn harder-edged so it stays visible against the brighter field.
