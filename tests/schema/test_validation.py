"""Validation harness tests for the dataset schema (spec/00-overview.md: "Python output
validated against it in CI").

Fixtures: a minimal valid document per artefact, plus the four required rejection shapes
(unsupported schemaVersion, missing required field, invalid edge kind, boolean-where-three-state)
— each fixture is asserted to fail for the *specific* reason it's named after, not just "fails
somehow", so a fixture accidentally passing (or failing for an unrelated reason) is caught.
"""

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
# A well-formed document must not be rejected on version grounds too.
# ---------------------------------------------------------------------------


def test_valid_document_is_not_flagged_as_unsupported_version():
    # Sanity check the two rejection paths are independent: the minimal-valid fixture's version
    # must actually be in SUPPORTED_SCHEMA_VERSIONS, or every "valid" test above would be
    # meaningless (passing structural validation but silently also failing the version check,
    # which validate_base_dataset would still raise on).
    validate_base_dataset(_load("minimal_valid_base_dataset.json"))  # must not raise at all
