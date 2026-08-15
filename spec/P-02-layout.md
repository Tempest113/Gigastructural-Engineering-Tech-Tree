# P-2 — Tier-based band layout

**Requirement.** Technologies MUST be laid out left-to-right as a directed acyclic graph and
MUST be visually separated into bands by **declared** tier. This is a v1 design correction, made
from evidence: v1's layout was close to right, and its real failures were incorrect tier
placement and inadequate lock/prerequisite labelling — not the tier-banded reading. Tier is the
vocabulary this tree is read in (vanilla and Gigastructures both present it that way), so bands
MUST reflect the mod's own declared tier, not a computed position.

**The tier range is unbounded.** ACOT-tier content pushes tiers to T9 and beyond. Tier bands
MUST be enumerated from the dataset at build time. No fixed upper bound may appear anywhere in
layout, level-of-detail thresholds, band labelling, or the colour token set. Measured against the
real 980-node rendered corpus: ~10 declared-tier bands (T0–T9) plus the terminal Repeatables
band — not a computed-column count, which would be materially larger (see below).

Repeatable technologies occupy a dedicated terminal band labelled "Repeatables", positioned after
the highest declared tier.

Tier bands and crisis lanes (P-5) are **orthogonal**: bands run vertically and are assigned
identically regardless of lane; lanes run horizontally and partition the standard-progression
technologies from each crisis faction's. Every technology has exactly one band and one lane. A
crisis-faction technology that is also repeatable occupies the Repeatables band within its own
faction's lane — the two axes compose, neither one overrides the other.

**The band grid is global and single.** Every lane spans the full grid, from T0 (or the lowest
enumerated tier) through the Repeatables band, regardless of what that lane's own technologies
actually use. A lane whose technologies stop at T5 still has T6-through-Repeatables bands; they
render empty. This is required so the shared coordinate space (P-5) stays valid for cross-lane
edge routing (P-8) — a band index means the same declared tier in every lane, with no per-lane
renumbering — and it is also the honest representation: an empty band is a visible statement that
the faction has no content at that tier, not a gap papered over by compression. Lanes are fitted
**vertically** to their content only (a lane with five technologies is short; one with fifty is
tall); they are never fitted or compressed horizontally.

## Bands are declared tier; computed position is internal geometry only

**A node's band is its own declared `tier` field, full stop — never adjusted by graph depth.** A
technology declared T5 renders in the T5 band regardless of where its prerequisites sit. There is
no promotion of a node's *band*. (Earlier drafts of this spec had layout promote a node's
displayed position when a prerequisite's declared tier was at or above its own — that rule is
superseded; see "Backwards edges" below for what replaces it.)

**Computed position (longest-path depth from a topological ordering over the rendered
prerequisite graph) still exists, but purely as internal geometry**, used for two things and
never displayed as a number to the user:

- **Horizontal ordering within a band.** Multiple technologies sharing a declared tier are not
  interchangeable left-to-right — computed position (and the crossing-reduction pass below) orders
  them so within-band prerequisite chains still read left-to-right where the band is wide enough
  to show that (P-2's N-card-wide arrangement, see the "Card arrangement within a band" section).
- **Routing backwards edges across bands legibly** (see below) — the router needs *some* consistent
  ordering signal for a backwards edge's endpoints even though band placement itself doesn't move.

## Repeatable technologies: dedicated terminal band, badge exception

Repeatable technologies are D-13's one declared exception to "bands are declared tier, full
stop": they band into the terminal Repeatables band regardless of their own declared `tier`, and
the card badges **repeat count** in place of the tier badge — `Repeatable: ×N` for a finite cap,
`Repeatable: ∞` for unbounded. `tier` is still resolved, still validated
(`UnresolvedTierError` applies unchanged, no exemption for repeatables), and still emitted — it
remains meaningful for the sub-grid's internal `(category, computed position, key)` ordering and
for the detail popup, it simply isn't what the band header or card display. See D-13 in
`spec/decisions.md` for why this is not a repeat of v1's band-header bug: v1's header made a false
claim about the cards under it ("TIER 6" over T5-badged cards), while here the band header
("Repeatables") and the card badge (repeat count) each assert something true and non-contradictory
about a different aspect of the same node.

**Membership**: a technology is repeatable when its source declares a `levels` field at all —
`levels = -1` (unbounded) and a positive finite value (5, 20, or 40 in the real corpus) are both
repeatable; sign is not the signal, presence is (`pipeline.layout.is_repeatable`). This was
corrected mid-implementation, found by checking a user's v1 screenshot against the corpus rather
than by any test: the original rule tested `levels < 0` only, which is real for 76 of the corpus's
88 repeatable technologies but silently misclassified the other 12 — all declaring a positive
finite `levels` cap on an otherwise identical `cost_per_level` shape — as ordinary tier-banded
nodes. The screenshot's "T5 x5" card is exactly one of the 12,
`tech_repeatable_reduced_building_cost` ("Gravitational Analysis").

This 88-node membership set is deliberately **not** the same as the 50 `giga_tech_repeatable_*_cap`
nodes from CLAUDE.md's tier-source audit (the ones whose `tier` only exists after `inline_script`
expansion) — every `_cap` node is repeatable (a proper subset), but 38 of the 88 repeatables never
went through inline_script tier expansion at all. Treating the two sets as interchangeable is a
distinct bug from either finding alone; `tests/test_layout_corpus.py::
test_inline_script_tier_group_is_proper_subset_of_repeatable_group` guards against it.

**Declared tier is least meaningful precisely where it is least inferable from context — a finding
that supports the badge change, not just a coincidental aside.** 5 of the 88 repeatables declare a
tier other than T5 (`giga_tech_blokkat_scrap_damage` T1, `giga_tech_blokkat_scrap_research` T1,
`tech_repeatable_lcluster_clue` T2, `tech_cosmogenesis_thesis` T4,
`giga_tech_repeatable_increased_katzen_damage` T4), and these five are almost exactly the
prerequisite-isolated crisis/story-chain nodes in the repeatable set — technologies unlocked
through Blokkat scrap mechanics, the L-Cluster questline, or the Cosmogenesis ascension path,
rather than ordinary research progression. Their declared tier reflects where the mod's tier field
happened to place them structurally, not a meaningful "how advanced is this" signal a player would
recognise — reinforcing that the card should badge repeat count (a real, player-facing number)
rather than a tier value that is, for this subset, closer to noise than information.

**Sink property**: every prerequisite edge touching a repeatable node runs
non-repeatable → repeatable; zero run repeatable → non-repeatable and zero run
repeatable → repeatable (verified over the real corpus, not assumed). Measured: 881
non-repeatable-to-non-repeatable prerequisite edges, 83 non-repeatable → repeatable edges, 964
total — matching the 964 total from the earlier 891-vs-964 reconciliation once the corrected
membership is used (881 + 83 = 964). A repeatable node therefore never sources an edge, so it can
never source a backward edge either, and the Repeatables band requires no intra-band edge routing.
`tests/test_layout_corpus.py::test_repeatable_band_never_sources_an_edge` asserts this directly
rather than assuming it falls out of the backward-edge count.

## Backwards edges are expected, not an invariant violation

Because bands now reflect declared tier and computed depth is not applied to placement, a
prerequisite edge `(A → B)` can point from a **later** band to an **earlier** one whenever A's own
declared tier is higher than B's. This is common, not a corner case — see
`spec/decisions.md`'s layout-survey findings for the measured count, worst cases, and how far
back they reach. **The router (P-8) MUST route these legibly** (routed back through the
inter-band gutter, not hidden or approximated as forward) rather than the layout assuming they
don't occur. A build MUST NOT fail or warn merely because a backwards edge exists — it is real
graph structure, not a data error. (A dangling reference, a missing tier field, or a genuine
cycle are still hard build failures — see "Acceptance criteria" below and CLAUDE.md's tier-source
audit for the sourcing checks that back this.)

## Acceptance criteria

- Every node's band corresponds to its own declared `tier` field. Bands are contiguous and
  ordered ascending left to right by declared tier, with the Repeatables band last.
- Backwards edges (a prerequisite in a later band than its dependent) are rendered, not
  suppressed, and route through the inter-band gutter (P-8) — see "Backwards edges" above.
- Layout is deterministic: the same input dataset produces the same node positions every build.
- The rendered prerequisite graph contains no cycles. A detected cycle fails the build loudly.
- Every rendered node's declared tier MUST be resolvable to a definite value at build time (see
  CLAUDE.md's tier-source audit). A technology whose tier cannot be determined — whether because
  the field is absent even after `inline_script` expansion, or because a `@variable` it refers to
  is undefined — is a hard build failure (CLAUDE.md: "the build fails rather than emitting a
  partial dataset"), never a silent default tier.
- Adding a technology at a tier higher than any previously seen requires no code change.

## Card arrangement within a band

- A band is not one card wide. **Nothing in this rule constrains arrangement within a band** —
  only band ordering across declared tiers is constrained (backwards edges notwithstanding, see
  above). A densely populated band (Standard's T5, the corpus's worst case at 253 nodes — measured
  under the corrected repeatable-membership rule below; see the Repeatables section for what moved)
  renders
  as an **N-card-wide sub-grid** within its band, grouped by `category`/research area.
  **Implemented: N = 4**, chosen over 3 or 5 because the real build (`pipeline/layout.py`) ran
  cleanly at 4 with no reason surfaced to prefer another value — canvas dimensions land in the
  same "large but ordinary" range on both axes rather than either dominating (see CLAUDE.md's
  layout survey for the real measured canvas size).
- Within a band's sub-grid, nodes are ordered `(category, computed position, technology key)` —
  category first, so a dense band reads as labelled neighbourhoods rather than one undifferentiated
  wall; computed position (see above) second, so within-category prerequisite chains still read
  left-to-right where the sub-grid is wide enough to show it; technology key last, purely to make
  remaining ties deterministic. This ordering rule, not a general Sugiyama crossing-reduction
  pass, is what `pipeline/layout.py` implements — a full barycentre/median crossing-minimisation
  pass over the whole graph remains a possible refinement, not required for a correct first build.
- Layout MUST be computed at build time and stored as coordinates in the dataset — as typed-array
  side-files, JSON carrying only `GeometryRef` pointers (`00-overview.md`), never inlined
  coordinate arrays. `pipeline/geometry.py` packs `pipeline/layout.py`'s output this way: node
  positions and edge polylines are two separate `float32` side-files, matching
  `base-dataset.schema.json`'s `geometry.nodePositions`/`geometry.edgePolylines`. Runtime layout
  of a graph this size is incompatible with P-9 and P-10.
- The layout engine MUST support **multiple horizontal lanes** (the standard-progression lane
  plus one per crisis faction, P-5) sharing one band axis and one coordinate space, with
  independent vertical ordering within each lane, so cross-lane edges still route (P-8). The
  Repeatables band is not a separate zone — it is an ordinary terminal band, present within every
  lane that has repeatable technologies. **All five crisis lanes are always present, including at
  zero population** — Compound currently has none (confirmed real: its seven `tech_compound_*`
  technology blocks are commented out in the vendored source, not a classifier gap — see
  `pipeline/crisis_faction.py`), and still reserves a lane strip rather than being omitted.

## Card dimensions

**270×92px**, an implied technical decision recorded here rather than left implicit in layout
code. Sized against the tail, not the median, per two measured constraints:

- **Gate text, never truncated.** The real candidate-gate population (7 ascension perks + 21
  technology-gate targets referenced across rendered nodes' `potential` blocks) has a worst-case
  localised-name length of 41 chars including a "Needs " prefix; dropping that literal prefix (the
  gate icon already carries the "this is a requirement" semantic per P-3's own icon+text pairing)
  brings the worst case to 35 chars. The card is wide enough to fit that on one row, untruncated —
  gate-text truncation was v1's reported failure, and the candidate-gate set is small (28 possible
  strings, not one per node), so it's cheap to never truncate.
- **Names, truncated at p95 by design.** Rendered technology names measured over the real 980-node
  set: p50=21, p90=35, **p95=39**, p99=46, max=54 chars (markup-stripped). The card's name area (up
  to 2 lines) is designed to comfortably hold p95; names beyond that (~5% of nodes, dominated by
  `giga_tech_repeatable_*_cap`'s "X Management Protocols" pattern and a few Blokkat compound
  titles) truncate with an ellipsis. The full, untruncated name is always available in the detail
  popup (P-12) and as a native hover title — this is a stated decision, not a silent gap.

Font-metric assumptions behind these numbers (≈6.2px/char at an 11px UI font) are a reasonable
starting point, not verified against a real rendered font — revisit once Stage 3 has an actual
typeface chosen, but do not change the card's structural budget (35 chars for gate text, 39 for
names) without re-checking both constraints together, since they were sized as a pair.

## Cost display

**Base `cost` (first-level/declared cost) is the primary displayed figure; a repeatable
technology's `costPerLevel` (`schema/base-dataset.schema.json`'s `repeatable.costPerLevel`) is a
secondary indicator, never a replacement for it.** Both are emitted as base-dataset semantic
data (`pipeline/dataset_emit.py`); the exact visual treatment — badge text, iconography, whether
`costPerLevel` renders inline or only in the popup — is a Stage 3 rendering decision, out of
scope here.

**Rationale (v1 gap: a repeatable card showing only the bare first-level cost misrepresents what
the player is actually committing to).** In-game research cost shifts heavily with empire size
and other live modifiers the static build cannot see, so ANY absolute cost figure this tool shows
— base or otherwise — is approximate by nature, not a promise of what research will actually
cost. Given that, the number worth stating with confidence is the one that stays true regardless
of empire state: the **scaling rate**. `costPerLevel` is exact where the base `cost` was always
only approximate, and a repeatable technology's defining cost characteristic (that it gets more
expensive each time) is otherwise invisible on the card entirely. Showing base cost as primary
and `costPerLevel` as secondary keeps the familiar "how much does this cost" figure prominent
while surfacing the trajectory a player actually needs to plan a repeatable investment around.

**Measured, real corpus**: exactly the 88-node repeatable set (P-2/D-13's "Repeatables" exception)
carries a resolvable `costPerLevel` — 0 non-repeatable technologies declare one (checked, not
assumed). Separately, **15 of 980 rendered technologies have no statically-resolvable base `cost`
at all** — 5 with no `cost` field (apparently-free starting technologies) and 10 vanilla "cosmic
storm" technologies whose `cost` is a dynamic modifier block
(`cost = { factor = @var inline_script = {...} }`) rather than a scalar. Both cases emit
`cost: null`, per the same "never guess, never default to 0" discipline D-4 already applies to
weight — a null cost is an honest "this tool can't state one," not a claim the technology is
free. Stage 3 needs an explicit null-cost card treatment (distinct from showing "0"), not
designed here.
