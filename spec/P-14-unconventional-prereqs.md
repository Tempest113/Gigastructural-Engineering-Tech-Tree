# P-14 — Unconventional prerequisite handling

**Requirement.** The tool MUST correctly parse and represent unconventional prerequisite
definitions: `has_technology = x` checks appearing inside a `potential` block rather than a
`prerequisites` block, and nested `OR` groups appearing inside a `prerequisites` block itself.
**Both are real, distinct patterns in the corpus and both MUST be represented as their own typed
edge kind, never silently folded into an ordinary prerequisite.**

**Three edge kinds, and what each one is** (settled after an earlier draft of this section
described `alternative` in a way that turned out to be architecturally impossible — see the note
at the end of this section for why, so it is not re-litigated):

- **`prerequisite`** — a technology's `prerequisites` block, true (AND-required) members. All
  entries are equally required; there is no primary prerequisite.
- **`potential-gate`** — every `has_technology` check inside a `potential` block, extracted
  **universally**, with no allowlist. This is the mechanism that represents "a different empire
  type can access this technology under different conditions" (e.g. nomads, for whom the normal
  prerequisite chain is inaccessible, gated in via a `has_technology` check in `potential`
  instead) — that access path is a `potential-gate` edge, not a separate "alternative route"
  concept. P-3 layers a second, curated pass on top: a subset of these edges additionally match a
  recognised pattern in the gate-pattern registry and get a card badge as well as the edge. A
  technology being both an edge and a badge is expected, not a classification conflict — see P-3.
- **`alternative`** — a nested `OR` group inside a `prerequisites` block itself (e.g.
  `prerequisites = { tech_z OR = { tech_y tech_x } }`: satisfying the block requires `tech_z`
  AND (`tech_y` OR `tech_x`)). Each `OR` group is its own group, identified by `Edge.groupId` —
  a technology can carry more than one independent group.

## Acceptance criteria

- The parser extracts technology dependencies from `prerequisites` blocks (true members and `OR`
  groups, kept as two distinct lists — never flattened back into one) **and** from
  `has_technology` checks located within a `potential` block.
- Each extracted dependency records: the technology it depends on, its edge kind, and (for
  `alternative`) its group id.
- Dependencies extracted from `potential` are visually distinguishable from formal prerequisites
  and from `alternative`-group members by edge kind, since all three behave differently in game.
  P-8 owns the concrete line style for each edge kind; this file only owns the classification.
- Every `has_technology` check inside a `potential` block produces a `potential-gate` edge,
  **universally** — this extraction is unconditional and has no allowlist.
- **Edge-kind membership is NOT mutually exclusive per `(from, to)` pair.** The same dependency
  can legitimately be encoded twice — a formal `prerequisites` entry AND a redundant
  `has_technology` check in `potential` for the same target (4 real corpus pairs do this, e.g.
  `tech_mega_engineering -> giga_tech_arkship_neutronium_harvester`). Both edges MUST be emitted;
  dropping either corrupts one of the two traversals that consume that kind (P-12.9's research
  path uses `prerequisite` only, P-7's isolation uses all three). Collapsing the two into one
  visual line for display, if ever wanted, is a Stage 3 rendering decision made over the emitted
  data — it is not a data-model decision and does not belong in this file's acceptance criteria.

**Why the "profile-relative relabeling" reading was dropped.** An earlier draft of this
Requirement described a technology reachable by two different routes for two different empire
types as: the applicable route renders as `prerequisite` for the selected profile, and the other
route renders as `alternative`. That reading is architecturally impossible: `Edge.kind` is a
fixed property of the profile-invariant base dataset (`spec/00-overview.md`'s dataset structure —
only the *active edge set* varies per profile, in the empire-overlay artefact, never `Edge.kind`
itself). A single edge cannot be `prerequisite` for one profile and `alternative` for another. The
two-different-empire-types scenario this prose was trying to describe is already fully handled by
`potential-gate`'s universal extraction (above) — no third, profile-relative kind is needed or
possible. `alternative` is, and has always operationally been, the nested-`OR`-inside-`prerequisites`
construct (P-08 independently defines edge direction the same way: "the alternative prerequisite
is the tail"). This paragraph exists so a future session doesn't re-derive the old prose from
this file's history and reintroduce the conflict.

## Implied technical decisions

- The edge model MUST support **typed, conditional edges**: `{ from, to, kind: "prerequisite" |
  "potential-gate" | "alternative", groupId, appliesToEmpireTypes: [...], backward, bandSpan }`.
  A plain unlabelled adjacency list cannot satisfy this requirement.
- `potential-gate` extraction is **`potential`-only**, not "`potential` and other trigger blocks"
  as an earlier draft of this file's acceptance criteria said. Checked directly against the real
  corpus, not assumed: `allow` never occurs on any rendered technology (0/980), and
  `weight_modifier`/`ai_weight` — the only other blocks containing `has_technology` at all —
  contribute zero occurrences once scoped correctly (854 of the corpus's 879 raw `has_technology`
  occurrences sit inside an opaque non-boolean sub-scope like `count_country`, checking OTHER
  empires for a scarcity mechanic, not the researching empire's own state — extracting those as
  dependencies would be wrong). `pipeline/edges.py`'s scope discipline — only descend into
  `AND`/`OR`/`NOT`/`NOR`; any other block-valued field is an opaque leaf, never searched inside —
  matches `pipeline/availability.py`'s own established discipline exactly, for the same reason. A
  standing diagnostic (never a build failure) fires if `has_technology` ever appears under an
  `allow` block on a rendered technology, so a future mod update that introduces one is surfaced.
- Trigger blocks may contain arbitrary boolean structure (`OR`, `AND`, `NOT`, `NOR`) — but the
  real corpus's nested-`OR`-inside-`prerequisites` construct (the `alternative` edge kind) uses
  only `OR`; 0 `AND`/`NOR`/`NOT` occur there (checked, not assumed — CLAUDE.md previously stated
  the general case before this was verified). The extractor MUST preserve boolean structure rather
  than flattening it, because a `has_technology` inside a `NOT` is a *negative* dependency and
  inverting it silently would produce a wrong graph. The real corpus has zero negated
  `has_technology` under `potential` today; since `EdgeKind` has no representation for a negative
  dependency, one is excluded from edge output and recorded as a diagnostic rather than emitted as
  a wrong-polarity positive edge — a real occurrence needs a schema decision, not a guess.
- **P-16's rendering-scope closure stays prerequisite-only** (decided on evidence, not by
  default): recomputing the closure with `alternative` edges treated as traversable makes zero
  difference on the real corpus (identical 7-technology closure, identical 980 rendered nodes, and
  all four of Gigastructures' "supertensile" trigger technologies reach ACOT/AoT content via a true
  prerequisite chain, never an `OR` branch). Admitting `alternative` would be scope creep against
  P-16's own stated rationale (keeping a research *chain* unbroken — an `OR`-branch member is
  definitionally not a required link in that chain) for zero measured benefit. The mitigation for
  the risk this carries forward (a future corpus revision adding an ACOT/AoT technology reachable
  ONLY via an `alternative` branch, which this rule would then silently exclude) is a standing
  diagnostic, not a closure change: `pipeline.rendering_scope.compute_alternative_only_gaps`
  recomputes the closure with `alternative` treated as traversable and reports anything the real
  (prerequisite-only) closure misses. Never a build failure, empty on the real corpus today.
- Conditions the evaluator cannot resolve MUST be recorded as `unknown` and reported, never
  assumed true or false (`implementation-notes.md`).
