import pytest

from pipeline.dataset_schema.empire_profile import (
    AXES,
    AvailabilityMatrixMismatchError,
    _check_bijection,
    _derive_strides,
    _expand,
    _index_for,
    all_profiles_in_canonical_order,
    check_availability_matrix_matches_overlays,
    empire_profile_index,
)


def test_index_of_all_regular_mechanical_non_nomadic_is_zero():
    assert empire_profile_index({"authority": "regular", "shipset": "mechanical", "nomadic": "no"}) == 0


def test_index_matches_worked_example_from_schema_comment():
    # {authority: hive_mind, shipset: biological, nomadic: yes} -> 1*4 + 1*2 + 1 = 7
    assert empire_profile_index({"authority": "hive_mind", "shipset": "biological", "nomadic": "yes"}) == 7


def test_all_twelve_profiles_produce_a_bijection_onto_0_through_11():
    profiles = all_profiles_in_canonical_order()
    assert len(profiles) == 12
    indices = [empire_profile_index(p) for p in profiles]
    assert sorted(indices) == list(range(12))
    # each profile's position in the list IS its own index.
    for i, p in enumerate(profiles):
        assert empire_profile_index(p) == i


def test_axes_are_genuinely_independent_twelve_distinct_combinations():
    profiles = all_profiles_in_canonical_order()
    as_tuples = {(p["authority"], p["shipset"], p["nomadic"]) for p in profiles}
    assert len(as_tuples) == 12  # no duplicates -- confirms the axes really are a product.


# ---------------------------------------------------------------------------
# availabilityMatrix / overlay consistency check (decision 4).
# ---------------------------------------------------------------------------


def _tech(id_, matrix):
    return {"id": id_, "availabilityMatrix": matrix}


def _overlay(profile, availability):
    return {"profile": profile, "availability": availability}


def test_consistent_matrix_and_overlays_pass():
    profile0 = {"authority": "regular", "shipset": "mechanical", "nomadic": "no"}
    matrix = ["locked"] * 12
    matrix[0] = "available"
    technologies = [_tech("tech_a", matrix)]
    overlays = [_overlay(profile0, {"tech_a": {"state": "available", "reason": None}})]
    check_availability_matrix_matches_overlays(technologies, overlays)  # must not raise


def test_drifted_matrix_and_overlay_is_caught():
    profile0 = {"authority": "regular", "shipset": "mechanical", "nomadic": "no"}
    matrix = ["locked"] * 12  # index 0 says locked...
    technologies = [_tech("tech_a", matrix)]
    overlays = [_overlay(profile0, {"tech_a": {"state": "available", "reason": None}})]  # ...overlay says available
    with pytest.raises(AvailabilityMatrixMismatchError) as excinfo:
        check_availability_matrix_matches_overlays(technologies, overlays)
    assert len(excinfo.value.mismatches) == 1
    tech_id, profile, matrix_state, overlay_state = excinfo.value.mismatches[0]
    assert tech_id == "tech_a"
    assert matrix_state == "locked"
    assert overlay_state == "available"


def test_check_covers_all_twelve_profiles_not_just_one():
    profiles = all_profiles_in_canonical_order()
    matrix = ["available"] * 12
    technologies = [_tech("tech_a", matrix)]
    overlays = [_overlay(p, {"tech_a": {"state": "available", "reason": None}}) for p in profiles]
    check_availability_matrix_matches_overlays(technologies, overlays)  # must not raise

    # now drift exactly one of the twelve overlays.
    overlays[7]["availability"]["tech_a"]["state"] = "uncertain"
    with pytest.raises(AvailabilityMatrixMismatchError) as excinfo:
        check_availability_matrix_matches_overlays(technologies, overlays)
    assert len(excinfo.value.mismatches) == 1


# ---------------------------------------------------------------------------
# Strides are derived, not hardcoded -- proven by extending an axis and re-deriving, without
# touching this module's real AXES/index/bijection for the other tests in this file.
# ---------------------------------------------------------------------------


def test_real_module_axes_is_still_todays_3x2x2_shape():
    # Sanity check the premise of the tests below: if this ever fails, AXES itself changed and
    # the "deliberately extended" tests need a new baseline to extend from.
    assert [name for name, _ in AXES] == ["authority", "shipset", "nomadic"]
    assert [len(values) for _, values in AXES] == [3, 2, 2]


def test_strides_are_derived_correctly_for_todays_3x2x2_axes():
    # authority stride = shipset_count * nomadic_count = 2*2 = 4; shipset stride = nomadic_count
    # = 2; nomadic stride = 1 -- matches the hand-derived formula this replaces.
    assert _derive_strides(AXES) == [4, 2, 1]


def test_extended_shipset_axis_widens_authoritys_stride():
    # A widened axis only changes the STRIDE of axes to its LEFT -- extending the leftmost axis
    # (authority) changes no one's stride at all (nothing sits to its right that depends on it),
    # which would make for an unconvincing demo. Extending shipset (the middle axis) from 2 to 3
    # values is the interesting case: it must widen authority's stride from 4 to 3*2=6, while
    # leaving nomadic's own stride at 1 (nothing to nomadic's right changed).
    extended_axes = [
        ("authority", ["regular", "hive_mind", "machine_intelligence"]),
        ("shipset", ["mechanical", "biological", "gestalt_hybrid"]),  # 2 -> 3 values
        ("nomadic", ["no", "yes"]),
    ]
    strides = _derive_strides(extended_axes)
    assert strides == [6, 2, 1]  # authority stride widened 4->6; nomadic stride unchanged at 1.


def test_extended_axis_derivation_and_bijection_both_hold():
    """The actual proof the task asked for: extend an axis, re-derive strides from the extended
    shape (never hand-recompute the numeral), and confirm the resulting index function is still
    a true bijection over the full, larger product -- using the exact same `_check_bijection`
    logic the real module runs at import time, just against a local axis set instead of the
    module's real `AXES`."""
    extended_axes = [
        ("authority", ["regular", "hive_mind", "machine_intelligence"]),
        ("shipset", ["mechanical", "biological", "gestalt_hybrid"]),  # 2 -> 3
        ("nomadic", ["no", "yes"]),
    ]
    # Must not raise -- this IS the bijection proof for the extended shape.
    _check_bijection(extended_axes)

    strides = _derive_strides(extended_axes)
    profiles = _expand(extended_axes)
    assert len(profiles) == 3 * 3 * 2  # 18, not the old 12.
    indices = {_index_for(p, extended_axes, strides) for p in profiles}
    assert indices == set(range(18))

    # The new axis value slots in at the expected indices (shipset=gestalt_hybrid is index 2 on
    # that axis, stride 2 -- combined with nomadic's stride 1, its six profiles -- one per
    # authority value, times two nomadic values -- land at 4, 5, 10, 11, 16, 17).
    hybrid_indices = sorted(
        _index_for(p, extended_axes, strides) for p in profiles if p["shipset"] == "gestalt_hybrid"
    )
    assert hybrid_indices == [4, 5, 10, 11, 16, 17]


def test_bijection_check_catches_a_hardcoded_stride_style_bug():
    """Proves the assertion actually catches the failure mode the task describes: a stride
    correct for the old axis shape but wrong for an extended one, silently colliding instead of
    failing. Simulated by deriving strides for the OLD (3x2x2) shape and applying them to the
    NEW, extended (3x3x2) shape -- exactly what a hardcoded `*4`/`*2` formula does when the
    shipset axis grows, since a hardcoded formula can never re-derive.

    Contrast with test_extended_axis_derivation_and_bijection_both_hold above, which re-derives
    strides fresh from the extended shape and passes cleanly -- the difference between those two
    tests IS the bug this task asked to convert from silent to loud."""
    old_axes = [
        ("authority", ["regular", "hive_mind", "machine_intelligence"]),
        ("shipset", ["mechanical", "biological"]),
        ("nomadic", ["no", "yes"]),
    ]
    extended_axes = [
        ("authority", ["regular", "hive_mind", "machine_intelligence"]),
        ("shipset", ["mechanical", "biological", "gestalt_hybrid"]),
        ("nomadic", ["no", "yes"]),
    ]
    stale_strides = _derive_strides(old_axes)  # [4, 2, 1] -- correct for a 2-value shipset only.
    profiles = _expand(extended_axes)
    indices = [_index_for(p, extended_axes, stale_strides) for p in profiles]

    # The real module never lets this happen -- empire_profile_index always uses _STRIDES
    # derived from AXES at import time, so stale strides can only be constructed by hand, as
    # above. But if they ever were used, this is the corruption: not a bijection onto range(18).
    assert len(set(indices)) != len(indices) or set(indices) != set(range(18)), (
        "stale strides unexpectedly still formed a bijection -- this test's premise (that "
        "reusing old strides against a widened axis silently corrupts) no longer holds and "
        "needs re-examining, not deleting"
    )
