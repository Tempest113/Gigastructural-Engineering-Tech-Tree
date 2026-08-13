# Decisions

Resolved open questions from the v1.0 draft. Each is now normative in its requirement file;
this document records the reasoning so it is not relitigated.

## D-1 — Research path shape (was OQ-1)

The popup shows the **complete ancestor set in topological order**, presented by tier with
cumulative research cost, plus a "shortest chain" toggle offering the cheapest single chain by
cumulative cost.

The ancestor set is the only unambiguously correct answer for a DAG — a research path is
generally not a single chain. The toggle exists because the cheapest chain is what most users
actually want to read.

## D-2 — Multiple prerequisites (was OQ-2)

**The concept of a primary prerequisite is removed.** Where a technology declares several
prerequisites, all are equally required by the game. Designating one as primary would be a
fiction the data does not support.

The model carries a flat `prerequisites` list ordered deterministically by tier descending,
then cost descending, then technology key. The popup lists all of them.

## D-3 — Gate ordering (was OQ-3)

Ascension perks outrank technology gates. Ordering is defined by a checked-in priority table in
the gate-pattern registry, not by source declaration order.

## D-4 — Research weight presentation (was OQ-4)

Base weight shown prominently, with an expandable list of weight modifiers and their
conditions. **No evaluated weight.** Weight is modified at runtime by live empire state;
static analysis cannot produce a number that is right often enough to present authoritatively,
and a confidently wrong number is worse than an honest base plus conditions.

## D-5 — Repository links (was OQ-5)

The field is always rendered, with three branches:

- Where Gigastructures overrides the technology: a permalink pinned to the build's source
  commit, targeting the file and line range.
- Where the technology is ACOT- or AoT-sourced (P-16): a link to that mod's Steam Workshop item
  page. Workshop items have no commit-pinned line-range permalink, and the technology isn't
  vanilla, so neither of the other two branches applies.
- Otherwise (unmodified vanilla): a link to the Stellaris wiki.

Wiki anchors derive from the localised technology name, so they are right most of the time and
silently wrong occasionally. CI validates that each anchor resolves in the fetched page and
falls back to a wiki search URL where it does not. The field is never dead and never omitted.

## D-6 — Empire type enumeration (was OQ-6)

**Three independent axes composed at build time**, never a flat enumeration:

- Gestalt/authority: regular, hive mind, machine intelligence
- Shipset: mechanical, biological
- Nomadic: yes, no

Twelve profiles. A flat list combinatorially explodes and cannot express that any empire type
can be nomadic and that nomadic empires use either shipset.

Origins are not an axis for v1 — there is little or no origin-gated technology content. The
fact registry stays extensible, so if extraction surfaces origin-gated techs, adding a fact is
a configuration line rather than a restructure.

**Ascension perks are gates, not profile facts.** A perk-gated technology always displays its
gate. The tree shows what you would need; it never assumes you have it. Modelling perks as
facts would silently hide the requirement from a player who has not taken the perk.

## D-7 — Crisis faction coverage (was OQ-7)

Five factions: Aeternum, Blokkats, Compound, Sirenalia, Katzenartig Imperium.

Assignment is derived in order: technology ID, then `potential` and prerequisite inspection,
then a checked-in manual override file for the remainder. The override file is permitted
hand-maintained configuration under P-10.

## D-8 — Vanilla corpus provisioning (was OQ-8)

Contributor-local, gitignored, populated by `tools/collect_vanilla.py` from the local Steam
install. Never committed, never redistributed. The build fails with a clear message when the
corpus is absent rather than silently producing a mod-only graph.

## D-9 — Localisation scope (was OQ-9)

English only for v1. The pipeline is language-parameterised so additional languages are a build
flag. Non-English output cannot be quality-checked by the maintainer, and shipping unverifiable
translations is worse than shipping one verified language.

## D-10 — Unknown availability tolerance (was OQ-10)

Thresholds are measured **per empire profile**, not pooled across all twelve. Each profile's
build produces its own `unknown` percentage (unknown technologies for that profile ÷ total
technologies).

- Hard ceiling: 10% for any single profile. If the **worst** profile exceeds 10%, the build
  fails — one bad profile fails the build even if the other eleven are well under.
- Warn threshold: 3%, per profile.
- Ratchet: CI fails if any individual profile's `unknown` count rises against that same profile's
  figure in the previous dataset, even when the absolute figure is under 10%.

Pooling across profiles would let a bug that makes one specific profile (say, machine
intelligence) resolve badly hide inside an average dominated by the other eleven — exactly the
kind of profile-specific evaluator bug this threshold exists to catch. Measuring and ratcheting
per profile is the only way the ceiling means what it says for every profile a user can select,
not just the fleet average. Without the ratchet, 10% becomes the resting state rather than the
ceiling.

## D-11 — Rendering stack

PixiJS over a hand-rolled WebGL renderer. Hand-rolling a 2D renderer that meets the P-10
budgets at 10³–10⁴ nodes is weeks of work that is not the interesting part of this project, and
PixiJS still permits the custom fills and shaders the crisis patterns need.

## D-12 — Pipeline language

Python, continuing from the v1 implementation. The dataset schema becomes an explicit
cross-language contract as a result — see `00-overview.md`.
