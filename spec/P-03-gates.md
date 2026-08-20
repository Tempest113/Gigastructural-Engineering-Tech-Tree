# P-3 — Gate indicators

**Requirement.** Every technology gated behind a non-prerequisite unlock condition MUST display
a visually prominent gate indicator on its node, rendering the associated icon alongside the
gate's localised name — for example the Cosmogenesis perk icon paired with "Needs Cosmogenesis".

Gates include, at minimum: Cosmogenesis, Galactic Wonders and Gigastructural Constructs
ascension perks, and a technology-gates-technology example, corrected below.

**Corrected technology-gate example (gate-classification survey session).** An earlier draft of
this section cited "the Tetradimensional Engineering technology" as an example of one technology
gating another via `has_technology` inside `potential`. The survey that preceded implementation
checked this directly against the real corpus and found it **false**:
`giga_tech_tetradimensional_engineering` gates several *ascension perks*
(`common/ascension_perks/giga_ascension_perks.txt`'s `custom_tooltip`/`has_technology` pairs) —
out of P-3's scope, which is technology gates, not perk gates — and does not appear inside any
rendered technology's own `potential` block. Recorded here rather than silently swapped out, so
a future session finding the old example in git history learns it was checked and refuted, not
just replaced. **Real example, confirmed present in the corpus**:
`giga_tech_amb_supertensiles_acot_alpha` gates on `tech_dark_matter_power_core_ae` via
`has_technology` inside its own `potential` block — one of 22 rendered technologies carrying a
`has_technology` gate leaf (25 such edges total; 3 technologies name two targets each). See
`pipeline/gate_patterns.py` for the full registry this classification pass runs against.

A gate is a condition on **empire state**. A dependency on another mod is not a gate — see
P-16.

Every `has_technology` check inside a `potential` block produces a typed `potential-gate` edge,
universally, per P-14. Gate detection (below) is a curated display allowlist layered on top of
that universal edge pass: a technology whose `potential-gate` edge matches a recognised pattern
in the gate registry is **both** an edge and a badge. This is not double-classification — the
edge is the complete, mechanical record of the dependency; the badge is an editorial decision
that this particular dependency is important enough to surface prominently on the card. See P-14
for the edge side.

**Curation is at the MECHANISM level, not the occurrence level — badge every occurrence, no
curated subset (the user's decision, verbatim, gate-classification session).** The registry
RESOLVES gates — mapping a recognised trigger *pattern* to its icon and localised name, including
the two wrapper→perk mappings below — it does **not** SELECT which occurrences of a registered
pattern are "important enough" to badge. Once a pattern is registered — today
`has_ascension_perk`, `has_technology` (matching an already-extracted `potential-gate` edge), and
the two Gigastructures scripted-trigger wrappers `has_gigastructural_constructs`/
`has_galactic_wonders` — **every** real occurrence of it badges, unconditionally, with no further
per-technology editorial filter. This is an architectural rule, not a judgement call contingent
on how many occurrences exist: a hand-curated per-occurrence subset would be one more hand-
maintained surface this project has repeatedly had to reconcile (crisis-faction overrides, the
flag map, name overrides) for no evidenced benefit, and narrowing to one later is easy if badges
ever prove noisy in review — un-narrowing from a silently-dropped occurrence is not. (The real
corpus count at implementation time — 70 gate instances across 60 technologies — is recorded here
as a fact about the corpus, not as the reason for the rule; the rule holds regardless of count.)

## Acceptance criteria

- The gate indicator renders inside the node card and remains legible at default zoom.
- The gate icon renders as an image, never substituted with a glyph, emoji or text-only marker.
- Gate labels are localised strings sourced from the mod's localisation files, never hard-coded
  in application source.
- A technology with no gate renders no indicator and no empty placeholder row.
- A gate is displayed regardless of the selected empire profile. Selecting a profile never
  suppresses a gate indicator.

## Implied technical decisions

- **A technology may have more than one gate.** The model stores gates as an ordered list, the
  first element being the primary gate, surfaced in the popup per P-12.7. Node cards render the
  primary gate; where space permits, additional gates render as compact secondary badges.
- Ordering is by a checked-in priority table in the gate-pattern registry, with ascension perks
  outranking technology gates (D-3). Source declaration order is not used.
- Gate detection is a **classification pass** over trigger blocks, run after the universal
  `potential-gate` edge extraction of P-14: the build inspects each technology's `potential` and
  `allow` conditions for recognised gate patterns using a checked-in, extensible gate-pattern
  registry. Unrecognised conditions MUST NOT be silently dropped — the build reports them.
  Matching the registry never removes or alters the underlying edge; it only adds a badge.
- Gate icons MUST be extracted from mod and base-game assets during Stage 1 and packed into the
  atlases. Icon paths MUST NOT be manually maintained.
