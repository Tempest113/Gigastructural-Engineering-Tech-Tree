# Handoff — Stage 1 (Extract) and Stage 2 (Compute) complete, Stage 3 (Render) in progress

Paste this at the start of a new conversation to carry context over.

This tells you what exists, what's guaranteed about it, what's been deliberately left undecided
and why, how this project is worked on, and where to start.

`spec/` is authoritative; `CLAUDE.md` is the running summary. This file is neither — it's a
point-in-time status report. If it goes stale, trust `spec/` and `CLAUDE.md` over this file, and
update or delete this file rather than letting it drift.

---

## What this is

An interactive web tech tree visualiser for the Stellaris mod *Gigastructural Engineering &
More*. Static site, no backend, deployed to GitHub Pages at
`github.com/Tempest113/Gigastructural-Engineering-Tech-Tree`. This is v2 — v1 existed and is
being rebuilt properly.

## How we work

The build happens in **Claude Code** (IntelliJ plugin). This chat is for design decisions,
visual review, reasoning through a problem before committing to it, and writing prompts to
paste into Claude Code. Keeping implementation out of chat is deliberate — v1 became
prohibitively expensive because the whole transcript was resent every turn.

**Standing instructions for Claude in this chat:**

- End every message with a short numbered list of actions the user needs to take, after
  explaining them in more detail above. Where an action is a question, include a simplified
  version of it plus any relevant suggestions.
- Never act without confirmation of intent. Don't produce files or run work speculatively.
- Draft every Claude Code prompt explicitly and in full, ready to paste without further
  composition.

The user defers technical and visual judgement calls to Claude, and contributes the
mod-specific domain knowledge. Claude is expected to make the call and justify it, not to
present a menu of options. **This is a standing instruction, restated explicitly by the user
mid-project**: "We'll proceed with your recommendation for these sorts of things here on out."
Do not hand technical decisions back to him — make the call, state the reasoning, and flag
separately when something is genuinely a *game or mod* question rather than a technical one.

**The user's domain knowledge and screenshots have repeatedly caught bugs no test could.** This
is not a courtesy — it is the single most productive input channel in the project, and it works
because he is asked specific, answerable questions:
- A v1 screenshot showing a card badged "T5 ×5" exposed `is_repeatable`'s `levels < 0` bug (12
  misplaced technologies, full green suite).
- Pasting the `giga_mega_repeatable` inline_script template surfaced both the `cost_per_level`
  display gap and the lowercase-`not` operator question.
- Clarifying that `$name$_capped_r` is a **mod-configuration** flag, not a progress flag —
  correcting Claude's stated assumption — reclassified 50 nodes and produced the `config-gated`
  state.
- Clarifying that no core preset sets a cap to "1 + Repeatables" turned those 50 from *uncertain*
  into *determinate*.
- Correcting Claude's reading of v1's second failure (the research path, not card text — see
  CLAUDE.md's "Research path" section) prevented an entire wasted design effort on untruncatable
  card text.
When a corpus finding is ambiguous, **ask him a specific game question** rather than inferring.

---

## Current headline figures

Full detail, provenance and every historical correction live in `docs/BUILD-LOG.md`; this is
just the current, reconciled snapshot so a fresh session doesn't have to hunt for it.

- **Rendered nodes: 973** (Vanilla 673 + Gigastructures 300 + ACOT/AoT depth-1 closure, minus 4
  permanently-`always = no` technologies — D-18 then Item 2c in CLAUDE.md's "Scope of ACOT and
  AoT"). Edges: 977 (876 prerequisite + 76 alternative + 25 potential-gate).
- **D-10 uncertainty** (after Item 2b's zero-weight-gate fold-in): worst profile-dependent 58/973
  (5.96%, over the 3% warn threshold, under the 10% ceiling); unconditional 115/973 (11.8%); union
  (uncertain for ≥1 profile) 180/973. See CLAUDE.md's "Research weight" section for why.
- **Gates (P-3)**: DIRECT 107 instances (48 ascension_perk + 14 origin + 24 ethics_or_civic + 21
  technology) over 83 technologies. TOTAL (direct + inherited down `prerequisite` chains) 214
  instances over 147 technologies, 47 with more than one.
- **Canvas**: 30,060 × 13,448px at `subgrid_width=6` (D-17, settled).
- **Base dataset**: ~64 KB compressed. Largest empire overlay (with research paths): 63.5 KB
  gzip. Both comfortably inside the ≤2 MB budget.
- Full pytest suite, `tsc --noEmit`, `vite build`: clean as of the last session that touched
  pipeline or client code (see `docs/BUILD-LOG.md`'s most recent entry for the exact test count).

**Always rebuild before trusting any number above.** `client/public/dataset/` is gitignored
(D-15) — run `tools/build_dataset.py` (needs `vendor/` populated) before `npm run dev`/`build` in
`client/`, and re-derive figures from the fresh build rather than trusting this section, which is
a snapshot that goes stale the moment new pipeline code lands.

## Open items

See CLAUDE.md's own "Open items" section — kept there, not duplicated here, so there is exactly
one place a session needs to check for what's still genuinely open. `docs/BUILD-LOG.md` has the
full historical record of everything already closed.

## Where to look for what

- **`spec/`** — normative requirements, one file per concern (P-numbers) plus `decisions.md`
  (D-numbers) for settled trade-offs. Authoritative; nothing here or in CLAUDE.md should
  contradict it.
- **`CLAUDE.md`** — the running summary: architecture, stack, source data, locked decisions
  (empire model, scope, prerequisites, trigger evaluation, gates, tiers, colour, repeatables,
  research weight/path), the project's working rules, and current open items. Read this before
  making any design call.
- **`docs/BUILD-LOG.md`** — full historical build record: every session's findings, measured
  figures, and defects, organised by component/stage. Read this when you need to know *why* a
  number is what it is, or whether something was already tried and rejected.
- **`docs/DEFECTS.md`** — recurring bug *shapes* (raw-vs-expanded, parallel geometry, dict-keying,
  the green-suite lesson), organised by class rather than chronologically. Read this before
  fixing something that smells familiar.
- **This file (`HANDOFF.md`)** — a point-in-time status snapshot and the standing "how we work"
  instructions above. Not authoritative on anything `spec/`/`CLAUDE.md` also cover. Update or trim
  it rather than letting it accumulate a session log again — that drift has already happened once
  and been reversed; don't let it happen a third time.
