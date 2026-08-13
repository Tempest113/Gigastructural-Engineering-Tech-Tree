# Specification

Version 2.0. Supersedes the single-file v1.0 draft.

Split per requirement so a session reads only what it needs. Requirement IDs are stable —
issues, commits and tests reference them directly. RFC 2119 language throughout.

## Contents

| File | Covers |
| --- | --- |
| `00-overview.md` | Purpose, scope, sources, glossary, architecture |
| `decisions.md` | Resolved open questions, with rationale |
| `P-01-empire-types.md` | Empire profiles and the axis model |
| `P-02-layout.md` | Tier columns, DAG layout, unbounded tier range |
| `P-03-gates.md` | Ascension perk and technology gates |
| `P-04-category-filtering.md` | Category filters |
| `P-05-crisis-techs.md` | Crisis faction separation and filtering |
| `P-06-search.md` | Search |
| `P-07-isolation.md` | Middle-click and long-press isolation |
| `P-08-connectors.md` | Circuit-trace edge routing |
| `P-09-mobile.md` | Touch and mobile parity |
| `P-10-performance-automation.md` | Budgets, CI/CD, upstream sync |
| `P-11-user-guide.md` | User guide |
| `P-12-detail-popup.md` | Technology detail popup |
| `P-13-empire-locking.md` | Locked-state rendering |
| `P-14-unconventional-prereqs.md` | Dependencies inside trigger blocks |
| `P-15-overwrites.md` | Vanilla overwrite accounting |
| `P-16-mod-requirements.md` | External mod dependencies (new in 2.0) |
| `S-01-colour.md` | Colour, pattern and outline encoding |
| `S-02-diagnostics.md` | `?dev` overlay |
| `S-03-tier-differentiation.md` | Low-zoom tier legibility |
| `implementation-notes.md` | Pipeline, rendering architecture, delivery sequence |

## Changes in 2.0

| Change | Affects | Cause |
| --- | --- | --- |
| Tier range is unbounded, enumerated from data | P-02, S-03 | ACOT pushes tiers past T9; v1 assumed T0–T5 |
| Repeatable status shown on the card, not popup-only | P-12, S-03 | Reference implementation shows `T5 ∞` on the card |
| Primary prerequisite concept removed entirely | P-12 | Multiple prerequisites are all equally required |
| Outline encodes rare/dangerous, overriding area | S-01 | Confirmed rendering rule |
| Crisis factions expanded from two to five | P-05, S-01 | Aeternum, Compound, Katzenartig added |
| Mod requirement added as a first-class dimension | P-16 (new), P-12 | ACOT-tier tensiles are placeholder techs in Gigastructures |
| Scheduled upstream sync limited to Gigastructures | P-10 | ACOT and AoT are Steam Workshop only, not pinnable |
| Repository link falls back to the Stellaris wiki | P-12 | Unmodified vanilla techs are not in the Gigastructures repo |
| English only for v1, pipeline language-parameterised | P-11, P-12 | Non-English localisation cannot be quality-checked |

## Unresolved

- **Scope of ACOT and AoT.** See `P-16-mod-requirements.md`. Does the tree render their
  technologies, or vendor them only to resolve Gigastructures placeholder techs?
- **Palette hex values.** See `S-01-colour.md`. Blokkat green is too dark to survive the
  low-zoom LOD; Sirenalia and Aeternum collide if Sirenalia stays muted.
