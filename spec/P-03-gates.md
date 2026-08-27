# P-3 — Gate indicators

**Requirement.** Every technology gated behind a non-prerequisite unlock condition MUST display
a visually prominent gate indicator on its node, rendering the associated icon alongside the
gate's localised name — for example the Cosmogenesis perk icon paired with "Needs Cosmogenesis".
A gate MUST also express EXCLUSION, not just requirement, when the underlying condition is
negative — e.g. `is_wilderness_empire = no` badges "Unavailable to Wilderness", never a silently
missing gate (see "Negative gates" below).

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

**Weight-condition gate extraction (a later session).** Gate classification is not scoped to
`potential`/`allow` alone: a zero-factor `weight_modifier` condition (D-10's Extension, "Research
weight") that itself classifies to a registered gate pattern (`pipeline.gate_patterns.
classify_weight_gate_condition`, run block-by-block over each `modifier` entry whose own `factor`
is a literal `0`) badges the card the same way a `potential`-derived match does, and does NOT also
read `weight-gated` for that condition — the `AvailabilityState` and the `Gate` are the same
underlying fact routed through two different display channels, never both. Deduped by
`(kind, refId)` against any `potential`-derived match on the same technology, not by kind alone.
D-3's priority ordering applies unchanged to the merged list — a weight-derived match is not
second-class and can displace a `potential`-derived match to secondary.

**Negative gates (a later session, "origins-are-gates" follow-up).** A gate can express either
requirement ("Needs X") or exclusion ("Unavailable to X") — `GateMatch.negated` (`pipeline.
gate_patterns`), derived from the condition's own structure (a `NOT`/`NOR` wrapper, a `!=`
operator, or a literal boolean-false value like `is_wilderness_empire = no`), never a per-
technology list; curation stays at the mechanism level exactly as the rest of this document
requires. Every registered kind can be negative, not only `origin`. `order_gates`' D-3 priority is
a KIND-only sort, unaffected by polarity — a negative gate of a higher-priority kind still
outranks a positive gate of a lower-priority kind.

A `weight_modifier` zero-factor condition's polarity means the OPPOSITE of what the identical leaf
shape would mean inside `potential`, because the condition describes when the technology's weight
becomes ZERO (unavailable), not when it IS available — `classify_weight_gate_condition` inverts
the raw leaf polarity once (`invert_polarity=True`) so `GateMatch.negated` always means the same
real-world fact ("this gate excludes X") regardless of which block produced it. The real corpus
"swap pair" this inversion was built against: `tech_housing_2`'s weight condition is
`has_valid_civic = civic_agrarian_idyll` UNWRAPPED (weight zero WHEN you have the civic — a
NEGATIVE gate, "Unavailable to Agrarian Idyll"), while its sibling `tech_housing_agrarian_idyll`'s
is `NOT { has_valid_civic = civic_agrarian_idyll }` (weight zero WITHOUT it — a POSITIVE "Needs
Agrarian Idyll"). Both still badge, now with correct, distinct wording instead of an ambiguous
shared one — polarity-aware display subsumes the older "both badge identically regardless of
polarity" treatment rather than needing to coexist with it as a separate mechanism.

The axis-pure-LOCKED path (D-10's Extension) is untouched by this: whether the gate's own target
(an ascension perk, most commonly) is itself obtainable at all for an empire type stays a real
`LOCKED` verdict, evaluated exactly as before — the gate badge is display metadata layered on top
of that fact, never a replacement for it.

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
