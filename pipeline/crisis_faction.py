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
`has_global_flag` anywhere in its `potential`) was tried and produced two confirmed FALSE
POSITIVES, not just noise:

- `tech_sm_autocannons` references `giga_special_tech_compound_weapon_bypass` -- but the
  technology itself is EHOF/Urmazin-trader content (`ehof_disabled`, `@ehof_tier7cost3`), an
  entirely different Gigastructures minor-faction mechanic unrelated to the 5 P-5 crisis
  factions. The flag is a weapon-compatibility bypass check, not a membership signal.
- `giga_tech_tetradimensional_engineering` (a standard-progression, `field_manipulation`
  physics tech) has `potential = { OR = { has_gigastructural_constructs = yes,
  has_country_flag = blokkat_bureau_unlocked } }` -- an ALTERNATE unlock path through Blokkat
  crisis progress, not evidence the technology itself belongs to the Blokkats lane. Classifying
  it as Blokkats would have misplaced a mainline tech into a crisis lane.

Both confirmed by reading the actual technology block, not inferred from the flag name alone --
exactly the kind of case D-7's manual-override step exists for, if a human ever wants to record
an exception; it does not currently need one for these two, since the correct classification
(standard lane) is what happens by leaving them unmatched.

**Compound's count is a confirmed real zero, not a classifier gap.** `giga_08_ehof_components.txt`
contains seven `tech_compound_*` technologies (`tech_compound_armor`, `_computers`, `_drives`,
`_reactors`, `_sensors`, `_shields`, `_thrusters`), each gated on
`has_global_flag = compound_invasion_happened` -- but every one of the seven blocks is commented
out in the vendored source (confirmed by reading the raw lines, all prefixed `#`). The Compound
crisis's technology content does not exist as live, parseable data in this corpus snapshot; it
is disabled/unfinished upstream content, not a gap in this module's derivation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .overwrites import TechnologyDefinition, ordered_prerequisites

if TYPE_CHECKING:
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
) -> dict[str, str | None]:
    """Full D-7 derivation over every rendered technology. `rendered_technologies` is technology
    key -> its winning `TechnologyDefinition` (P-15), restricted to the rendered set (P-16) --
    the same shape `pipeline.rendering_scope`/`pipeline.overwrites` already produce. Returns
    technology key -> faction name, or `None` for the standard-progression lane.

    Step 3 (override) always wins when present, including over a step 1/2 result -- D-7's
    override file is permitted to correct an automatic classification, not just fill a gap."""
    overrides = overrides or {}

    result: dict[str, str | None] = {}
    for key in rendered_technologies:
        result[key] = classify_by_tech_id(key)

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
