"""The canonical `EmpireProfileIndex` derivation — the one place this function is defined.

See `schema/common.schema.json`'s `EmpireProfileIndex` `$comment` for the normative statement:
this is a pure, documented function of the three composed axes (P-1, D-6), used only to index
fixed-size 12-slot arrays (`availabilityMatrix`) compactly. **It is a storage encoding, not an
identity model** — the three axes remain the identity; nothing should come to treat this integer
as if it were a sanctioned flat enumeration of profiles. If that distinction ever gets blurry,
re-read `schema/common.schema.json`'s `$comment` before "simplifying" anything here.

Canonical axis order (fixed; changing it is a schema version bump, not a refactor):
`authority` ∈ [regular, hive_mind, machine_intelligence], `shipset` ∈ [mechanical, biological],
`nomadic` ∈ [no, yes]. Mixed-radix positional encoding, standard odometer-style: each axis's
*stride* (how much one step on that axis moves the index) is the product of the cardinalities of
every axis to its right. **Strides are derived from `AXES` below at import time, never
hardcoded** — a numeral like `4` or `2` baked into the formula is correct only for today's 3×2×2
axis shape; if an axis ever gains a value (e.g. a fourth authority type), a hardcoded stride
would silently start producing colliding indices instead of failing. An import-time assertion
(`_assert_bijection`, run once, at the bottom of this module) checks that the derived formula is
still a true bijection onto `range(TOTAL_PROFILE_COUNT)` for whatever `AXES` currently contains
— so a future axis change either recomputes correctly or fails loudly at import, never silently.
"""

from __future__ import annotations

AUTHORITY_ORDER = ["regular", "hive_mind", "machine_intelligence"]
SHIPSET_ORDER = ["mechanical", "biological"]
NOMADIC_ORDER = ["no", "yes"]

# Canonical axis order — (profile dict key, ordered value list). Changing the order of this list,
# or any axis's value list, changes what every EmpireProfileIndex means; that's a schema version
# bump, per the module docstring. Everything below (strides, TOTAL_PROFILE_COUNT, the index
# formula, the enumeration order) is derived from this one list, not restated.
AXES = [
    ("authority", AUTHORITY_ORDER),
    ("shipset", SHIPSET_ORDER),
    ("nomadic", NOMADIC_ORDER),
]


def _derive_strides(axes: list[tuple[str, list[str]]]) -> list[int]:
    """Stride of axis i = product of the cardinalities of every axis after it. The last axis
    always has stride 1 (its own units are the index's units)."""
    strides = [1] * len(axes)
    for i in range(len(axes) - 2, -1, -1):
        strides[i] = strides[i + 1] * len(axes[i + 1][1])
    return strides


def _total_count(axes: list[tuple[str, list[str]]]) -> int:
    total = 1
    for _, values in axes:
        total *= len(values)
    return total


def _index_for(profile: dict, axes: list[tuple[str, list[str]]], strides: list[int]) -> int:
    index = 0
    for (axis_name, order), stride in zip(axes, strides):
        index += order.index(profile[axis_name]) * stride
    return index


def _expand(axes: list[tuple[str, list[str]]]) -> list[dict]:
    if not axes:
        return [{}]
    (axis_name, values), *rest = axes
    tails = _expand(rest)
    return [{axis_name: v, **tail} for v in values for tail in tails]


def _check_bijection(axes: list[tuple[str, list[str]]]) -> None:
    """The actual check, parameterised over `axes` so it can be exercised in a test against a
    deliberately extended axis set without touching this module's real `AXES` — see
    tests/schema/test_empire_profile.py. Converts a silent data-corruption mode (a stride wrong
    for the current axis shape, producing colliding or sparse indices) into a loud one: every
    profile in the full axis product must map to a distinct index, and those indices must be
    exactly `range(total)` — dense from zero, no gaps, no collisions."""
    strides = _derive_strides(axes)
    total = _total_count(axes)
    profiles = _expand(axes)
    assert len(profiles) == total, (
        f"expansion produced {len(profiles)} profiles, expected total={total} -- axes and the "
        f"expected total have drifted apart"
    )
    indices = [_index_for(p, axes, strides) for p in profiles]
    if len(set(indices)) != len(indices):
        seen: dict[int, dict] = {}
        collisions = []
        for p, i in zip(profiles, indices):
            if i in seen:
                collisions.append((seen[i], p, i))
            else:
                seen[i] = p
        raise AssertionError(
            f"index function is not injective over these axes -- {len(collisions)} collision(s), "
            f"e.g. {collisions[0][0]} and {collisions[0][1]} both map to index {collisions[0][2]}. "
            f"A stride is wrong for this axis shape."
        )
    if set(indices) != set(range(total)):
        raise AssertionError(
            f"index function is injective but not dense over range(total) -- got indices "
            f"{sorted(set(indices))}, expected exactly range({total}). A stride is wrong for "
            f"this axis shape."
        )


_STRIDES = _derive_strides(AXES)
TOTAL_PROFILE_COUNT = _total_count(AXES)


def empire_profile_index(profile: dict) -> int:
    """`profile` is `{authority, shipset, nomadic}` (schema's `EmpireProfile`). Returns the
    canonical index in `range(TOTAL_PROFILE_COUNT)` (0-11 for today's 3×2×2 axes), computed from
    `AXES`/`_STRIDES` — never a hardcoded formula."""
    return _index_for(profile, AXES, _STRIDES)


def build_empire_profile_axes() -> dict:
    """Emits `schema/common.schema.json`'s `EmpireProfileAxes` shape -- the axis order,
    cardinalities and derived strides -- so the client can derive `EmpireProfileIndex` from
    dataset data instead of restating this module's formula as a second implementation (Item 1b,
    gate-classification survey session; CLAUDE.md's parallel-geometry rule, generalised from
    geometry to this indexing scheme). Derived from `AXES`/`_STRIDES`, never hand-restated."""
    return {
        "axes": [
            {"name": name, "values": list(values), "stride": stride}
            for (name, values), stride in zip(AXES, _STRIDES)
        ],
        "totalProfileCount": TOTAL_PROFILE_COUNT,
    }


def all_profiles_in_canonical_order() -> list[dict]:
    """Every profile in the full axis product, in the exact order `empire_profile_index` assigns
    0..TOTAL_PROFILE_COUNT-1 — index i of this list is always
    `empire_profile_index(this_list[i]) == i`. Generalises to however many axes/values `AXES`
    currently has, not just three."""
    return _expand(AXES)


def _assert_bijection() -> None:
    """Run once at import time (see the bottom of this module) against this module's real
    `AXES` — see `_check_bijection` for the parameterised logic this wraps."""
    _check_bijection(AXES)


class AvailabilityMatrixMismatchError(Exception):
    """Raised by `check_availability_matrix_matches_overlays` — see that function. Carries every
    mismatch found, not just the first, since a systematic bug (e.g. a swapped axis order) tends
    to produce many at once and seeing the full set is what makes the pattern visible."""

    def __init__(self, mismatches: list[tuple[str, dict, str, str]]):
        self.mismatches = mismatches
        lines = [
            f"  {tech_id} @ {profile}: availabilityMatrix says {matrix_state!r}, overlay says {overlay_state!r}"
            for tech_id, profile, matrix_state, overlay_state in mismatches
        ]
        super().__init__(f"{len(mismatches)} availabilityMatrix/overlay mismatch(es):\n" + "\n".join(lines))


def check_availability_matrix_matches_overlays(technologies: list[dict], overlays: list[dict]) -> None:
    """`technologies` is the base dataset's `technologies` array (each carrying
    `id`/`availabilityMatrix`); `overlays` is one empire-overlay document per profile (each
    carrying `profile`/`availability`). Raises `AvailabilityMatrixMismatchError` listing every
    `(technology, profile)` pair where the compact base-dataset matrix disagrees with the
    richer per-profile overlay's `state` — the two are redundant by design (see
    `schema/base-dataset.schema.json`'s `availabilityMatrix` description), so nothing should ever
    let them drift apart silently. Intended as a CI check over a real build's emitted artefacts,
    once Stage 2 exists to produce them."""
    mismatches: list[tuple[str, dict, str, str]] = []
    tech_by_id = {t["id"]: t for t in technologies}

    for overlay in overlays:
        profile = overlay["profile"]
        index = empire_profile_index(profile)
        for tech_id, availability in overlay["availability"].items():
            tech = tech_by_id.get(tech_id)
            if tech is None:
                continue
            matrix_state = tech["availabilityMatrix"][index]
            overlay_state = availability["state"]
            if matrix_state != overlay_state:
                mismatches.append((tech_id, profile, matrix_state, overlay_state))

    if mismatches:
        raise AvailabilityMatrixMismatchError(mismatches)


# Run at import time, not lazily — a broken bijection is a defect in this module's own constants
# (AXES), not something that should wait to surface until some caller happens to exercise it.
_assert_bijection()
