"""Validation harness tests for the dataset schema (spec/00-overview.md: "Python output
validated against it in CI").

Fixtures: a minimal valid document per artefact, plus the four required rejection shapes
(unsupported schemaVersion, missing required field, invalid edge kind, boolean-where-three-state)
— each fixture is asserted to fail for the *specific* reason it's named after, not just "fails
somehow", so a fixture accidentally passing (or failing for an unrelated reason) is caught.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from pipeline.dataset_schema import (
    UnsupportedSchemaVersionError,
    validate_base_dataset,
    validate_empire_overlay,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Minimal valid documents.
# ---------------------------------------------------------------------------


def test_minimal_valid_base_dataset_passes():
    validate_base_dataset(_load("minimal_valid_base_dataset.json"))


def test_minimal_valid_empire_overlay_passes():
    validate_empire_overlay(_load("minimal_valid_empire_overlay.json"))


# ---------------------------------------------------------------------------
# Required rejection shapes.
# ---------------------------------------------------------------------------


def test_unsupported_schema_version_is_rejected():
    doc = _load("rejected_unsupported_schema_version.json")
    with pytest.raises(UnsupportedSchemaVersionError) as excinfo:
        validate_base_dataset(doc)
    assert excinfo.value.found == "2.0.0"


def test_missing_required_field_is_rejected():
    doc = _load("rejected_missing_required_field.json")
    with pytest.raises(ValidationError) as excinfo:
        validate_base_dataset(doc)
    assert "metadata" in str(excinfo.value)


def test_invalid_edge_kind_is_rejected():
    doc = _load("rejected_invalid_edge_kind.json")
    with pytest.raises(ValidationError) as excinfo:
        validate_base_dataset(doc)
    assert "unlocks" in str(excinfo.value) or "kind" in str(excinfo.value).lower()


def test_boolean_where_three_state_is_rejected():
    doc = _load("rejected_boolean_where_three_state.json")
    with pytest.raises(ValidationError) as excinfo:
        validate_empire_overlay(doc)
    assert "True" in str(excinfo.value) or "true" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# 'repeatable' field: D-13's tri-shape (not repeatable / finite / unbounded).
# ---------------------------------------------------------------------------


def test_null_repeatable_is_valid():
    doc = _load("minimal_valid_base_dataset.json")
    assert doc["technologies"][0]["repeatable"] is None
    validate_base_dataset(doc)  # must not raise


def test_finite_level_repeatable_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["repeatable"] = {"levels": 5, "costPerLevel": 100}
    validate_base_dataset(doc)  # must not raise


def test_unbounded_repeatable_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["repeatable"] = {"levels": None, "costPerLevel": 100}
    validate_base_dataset(doc)  # must not raise


def test_repeatable_with_unresolvable_cost_per_level_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["repeatable"] = {"levels": 5, "costPerLevel": None}
    validate_base_dataset(doc)  # must not raise


def test_zero_level_repeatable_is_rejected():
    # 'levels' minimum is 1 -- a repeatable technology with a zero-level cap is meaningless;
    # 'not repeatable at all' is expressed as 'repeatable': null, not 'levels': 0.
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["repeatable"] = {"levels": 0, "costPerLevel": 100}
    with pytest.raises(ValidationError):
        validate_base_dataset(doc)


def test_repeatable_missing_cost_per_level_is_rejected():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["repeatable"] = {"levels": 5}
    with pytest.raises(ValidationError):
        validate_base_dataset(doc)


# ---------------------------------------------------------------------------
# 'cost' field: a real number, or null when unresolvable -- never guessed/defaulted.
# ---------------------------------------------------------------------------


def test_null_cost_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["cost"] = None
    validate_base_dataset(doc)  # must not raise


def test_missing_cost_field_is_rejected():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    del doc["technologies"][0]["cost"]
    with pytest.raises(ValidationError):
        validate_base_dataset(doc)


# ---------------------------------------------------------------------------
# 'config-gated' AvailabilityState (D-10, spec/decisions.md) -- a technology whose potential
# resolved definitively FALSE because of a mod-configuration toggle, not the empire.
# ---------------------------------------------------------------------------


def test_config_gated_availability_matrix_entry_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_base_dataset.json"))
    doc["technologies"][0]["availabilityMatrix"][0] = "config-gated"
    validate_base_dataset(doc)  # must not raise


def test_config_gated_overlay_state_with_reason_is_valid():
    doc = copy.deepcopy(_load("minimal_valid_empire_overlay.json"))
    doc["availability"]["tech_example"] = {
        "state": "config-gated",
        "reason": "has_global_flag = giga_tech_repeatable_dyson_swarm_capped_r",
    }
    validate_empire_overlay(doc)  # must not raise


def test_config_gated_overlay_state_with_null_reason_currently_passes_structurally():
    # NOT a validated invariant: the schema documents "reason required (non-null) when state is
    # 'locked'/'uncertain'/'config-gated'" in prose only -- there is no if/then conditional
    # enforcing it, for ANY of those three states (pre-existing, not introduced by config-gated).
    # This test records that gap honestly rather than asserting a rejection the schema doesn't
    # actually perform.
    doc = copy.deepcopy(_load("minimal_valid_empire_overlay.json"))
    doc["availability"]["tech_example"] = {"state": "config-gated", "reason": None}
    validate_empire_overlay(doc)  # does NOT raise today -- see note above


# ---------------------------------------------------------------------------
# A well-formed document must not be rejected on version grounds too.
# ---------------------------------------------------------------------------


def test_valid_document_is_not_flagged_as_unsupported_version():
    # Sanity check the two rejection paths are independent: the minimal-valid fixture's version
    # must actually be in SUPPORTED_SCHEMA_VERSIONS, or every "valid" test above would be
    # meaningless (passing structural validation but silently also failing the version check,
    # which validate_base_dataset would still raise on).
    validate_base_dataset(_load("minimal_valid_base_dataset.json"))  # must not raise at all
