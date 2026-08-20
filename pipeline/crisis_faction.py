"""P-5/D-7: crisis-faction membership derivation.

Three steps, in order, per spec/decisions.md's D-7: technology ID, then `potential`/prerequisite
inspection, then a checked-in manual override file for the remainder. This module is the first
real implementation of that rule — CLAUDE.md's "Colour and pattern" section previously only
stated the rule; the layout survey (Task 3, "P-16 rendering-scope closure" precedent) found a
provisional ID-only classifier is not enough to trust for layout sizing, so this exists to
produce the real, evidenced counts.

**Step 2 is prerequisite-chain inheritance ONLY, not `potential`-flag inspection — a deliberate,
evidenced narrowing of D-7's "potential and prerequisite inspection" wording.** Both were tried
against the real corpus. Prerequisite inheritance (a technology with no ID hint whose entire
rendered prerequisite set belongs to exactly one crisis faction) found zero qualifying cases in
the current corpus, but is a sound, low-risk mechanism kept for future corpus growth.
`potential`-block flag inspection (a technology referencing a crisis-fragment `has_country_flag`/
`has_global_flag` anywhere in its `potential`) was tried and, of the two candidates it surfaced,
produced one confirmed FALSE POSITIVE and one case that turned out to need the manual-override
step after all -- not the same finding for both, despite both starting from the same mechanism:

- `giga_tech_tetradimensional_engineering` (a standard-progression, `field_manipulation`
  physics tech) has `potential = { OR = { has_gigastructural_constructs = yes,
  has_country_flag = blokkat_bureau_unlocked } }` -- an ALTERNATE unlock path through Blokkat
  crisis progress, not evidence the technology itself belongs to the Blokkats lane. Classifying
  it as Blokkats would have misplaced a mainline tech into a crisis lane. Confirmed a real false
  positive; not an override entry, since standard lane is already the correct outcome without one.
- `tech_sm_autocannons` references `giga_special_tech_compound_weapon_bypass` and was originally
  recorded here as a false positive too, on identity grounds: the technology itself is
  EHOF/Urmazin-trader content (`ehof_disabled`, `@ehof_tier7cost3`), an entirely different
  Gigastructures minor-faction mechanic unrelated to the 5 P-5 crisis factions, and the flag reads
  like a weapon-compatibility bypass check rather than a membership signal. **That verdict was
  corrected in a later session**, on a different axis: identity was never the right test for this
  flag -- reachability was. `giga_special_tech_compound_weapon_bypass`'s sole setter anywhere in
  the vendored corpus is `giga_compound_situation_09.txt:113`, inside the Compound situation's own
  event chain, so the flag opens a real, Compound-exclusive research path regardless of what
  mechanic the technology's own cost/weight variables belong to. A second technology in the same
  file, `tech_qnm_disruptors`, carries the byte-identical `potential` shape and was found the same
  session. Both are now handled via `config/crisis_faction_overrides.txt` (Compound), not by
  widening this module's automatic derivation -- see that file's header comment for why this is a
  two-node override rather than a general rule (the evidence lives in `events/`, a directory this
  project has never declared a required extraction source).

Both confirmed by reading the actual technology block and, for the corrected case, by reading the
raw event file that sets the flag -- not inferred from a name or a first-pass verdict alone.

**Compound's "own" technology content is a confirmed real zero, distinct from Compound's rendered
count.** `giga_08_ehof_components.txt` contains seven `tech_compound_*` technologies
(`tech_compound_armor`, `_computers`, `_drives`, `_reactors`, `_sensors`, `_shields`,
`_thrusters`), each gated on `has_global_flag = compound_invasion_happened` -- but every one of
the seven blocks is commented out in the vendored source (confirmed by reading the raw lines, all
prefixed `#`). None of that content is live, parseable data in this corpus snapshot; steps 1-2 of
this module's own derivation still find zero technologies there, and that remains a real finding,
not a classifier gap. Compound's RENDERED count is nonetheless 2, not 0, entirely via the step-3
override above (`tech_sm_autocannons`, `tech_qnm_disruptors`) -- two nodes this module's automatic
derivation does not and, per the override file's own reasoning, should not be extended to find on
its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .clausewitz.nodes import Assignment, Block, Identifier, StringLiteral
from .overwrites import TechnologyDefinition, ordered_prerequisites

_BOOLEAN_WRAPPERS = {"AND", "OR", "NOT", "NOR"}

if TYPE_CHECKING:
    from .crisis_faction_flags import CrisisFactionFlagOverride
    from .crisis_faction_overrides import CrisisFactionOverride

# D-7's five factions, exact spelling.
CRISIS_FACTIONS = ("Aeternum", "Blokkats", "Compound", "Sirenalia", "Katzenartig Imperium")

# Step 1: technology-ID name fragments, confirmed against the real corpus (not invented) --
# every rendered node whose key contains one of these, case-insensitive, is that faction's.
# Faction-name variants ("aeternite", "katzen") are corpus-observed alternate stems for the same
# faction, not guesses (see e.g. giga_012_katzen.txt, aeternum_planetary_deposits.txt).
_ID_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "Aeternum": ("aeternum", "aeternite"),
    "Blokkats": ("blokkat",),
    "Compound": ("compound",),
    "Sirenalia": ("sirenalia", "siren"),
    "Katzenartig Imperium": ("katzenartig", "katzen"),
}


def classify_by_tech_id(technology_key: str) -> str | None:
    """D-7 step 1."""
    lowered = technology_key.lower()
    for faction, fragments in _ID_FRAGMENTS.items():
        if any(fragment in lowered for fragment in fragments):
            return faction
    return None


def _field(block: Block, name: str) -> Assignment | None:
    result = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == name:
            result = item
    return result


def _target_name(value) -> str | None:
    if isinstance(value, Identifier):
        return value.name
    if isinstance(value, StringLiteral):
        return value.value
    return None


def _scoped_has_country_flag(node: Block, negated: bool) -> list[tuple[str | None, bool]]:
    """Mirrors `pipeline.edges._scoped_has_technology`'s scope discipline exactly (only descend
    into AND/OR/NOT/NOR; every other block-valued field is an opaque leaf) so this module's flag
    lookup can't be fooled by a flag reference nested inside an opaque sub-scope the way P-14's
    edge extraction was originally fooled by `count_country`."""
    results: list[tuple[str | None, bool]] = []
    for item in node.items:
        if not isinstance(item, Assignment):
            continue
        key_upper = item.key_name.upper()
        if item.key_name == "has_country_flag":
            results.append((_target_name(item.value), negated))
        elif key_upper in ("NOT", "NOR") and isinstance(item.value, Block):
            results.extend(_scoped_has_country_flag(item.value, not negated))
        elif key_upper in ("AND", "OR") and isinstance(item.value, Block):
            results.extend(_scoped_has_country_flag(item.value, negated))
    return results


def classify_by_flag(
    definition: TechnologyDefinition,
    flag_overrides: dict[str, CrisisFactionFlagOverride],
) -> str | None:
    """D-7 step 1.5 (see module docstring): a technology whose `potential` references a
    non-negated `has_country_flag` present in `config/crisis_faction_flag_overrides.txt` is
    classified to that flag's faction. Runs before step 2's prerequisite-inheritance fixed point
    so a technology classified here can seed inheritance for whatever depends on it, the same way
    a step-1 ID match already does. A flag referenced only inside a `NOT`/`NOR` (an odd number of
    negations) does not classify -- that shape means "must NOT have this flag," the opposite of
    evidence for membership."""
    if not flag_overrides:
        return None
    potential = _field(definition.block, "potential")
    if potential is None or not isinstance(potential.value, Block):
        return None
    for flag_name, negated in _scoped_has_country_flag(potential.value, False):
        if negated or flag_name is None:
            continue
        override = flag_overrides.get(flag_name)
        if override is not None:
            return override.faction
    return None


def classify_by_prerequisite_inheritance(
    technology_key: str,
    rendered_prerequisites: list[str],
    known_classifications: dict[str, str | None],
) -> str | None:
    """D-7 step 2 (prerequisite-chain inheritance only -- see module docstring for why
    `potential`-flag inspection is deliberately not implemented here). A technology with no ID
    hint of its own inherits a crisis faction only when EVERY one of its rendered prerequisites
    is already classified to the same single faction -- a technology with a mixed or
    partially-unclassified prerequisite set inherits nothing, since that's not strong enough
    evidence either way."""
    if not rendered_prerequisites:
        return None
    factions = {known_classifications.get(p) for p in rendered_prerequisites}
    if len(factions) == 1:
        (only,) = factions
        return only
    return None


def classify_crisis_factions(
    rendered_technologies: dict[str, TechnologyDefinition],
    overrides: dict[str, CrisisFactionOverride] | None = None,
    flag_overrides: dict[str, CrisisFactionFlagOverride] | None = None,
) -> dict[str, str | None]:
    """Full D-7 derivation over every rendered technology. `rendered_technologies` is technology
    key -> its winning `TechnologyDefinition` (P-15), restricted to the rendered set (P-16) --
    the same shape `pipeline.rendering_scope`/`pipeline.overwrites` already produce. Returns
    technology key -> faction name, or `None` for the standard-progression lane.

    Step 3 (override) always wins when present, including over a step 1/2 result -- D-7's
    override file is permitted to correct an automatic classification, not just fill a gap."""
    overrides = overrides or {}
    flag_overrides = flag_overrides or {}

    result: dict[str, str | None] = {}
    for key in rendered_technologies:
        result[key] = classify_by_tech_id(key)

    # Step 1.5: flag-map classification (config/crisis_faction_flag_overrides.txt) runs before
    # step 2's fixed point, exactly like step 1, so a technology it classifies can itself seed
    # prerequisite-chain inheritance for whatever depends on it.
    if flag_overrides:
        for key, definition in rendered_technologies.items():
            if result[key] is None:
                result[key] = classify_by_flag(definition, flag_overrides)

    # Step 2 needs step 1's results for every rendered technology before it can check whether a
    # prerequisite set is homogeneous. Iterated to a fixed point (not a single pass) so a chain
    # of inherited classifications (B inherits from A in the same pass A itself was inherited)
    # propagates fully, regardless of declaration order -- capped at len(rendered_technologies)
    # iterations, which is always enough for a DAG (P-16) and guarantees termination even if a
    # future corpus change ever broke that guarantee.
    for _ in range(len(rendered_technologies)):
        changed = False
        for key, definition in rendered_technologies.items():
            if result[key] is not None:
                continue
            prereqs = [
                p for p in ordered_prerequisites(definition.block) if p in rendered_technologies
            ]
            inherited = classify_by_prerequisite_inheritance(key, prereqs, result)
            if inherited is not None:
                result[key] = inherited
                changed = True
        if not changed:
            break

    for key, override in overrides.items():
        if key in result:
            result[key] = override.faction

    return result
