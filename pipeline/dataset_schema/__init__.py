"""Python-side validation harness for the dataset schema (spec/00-overview.md: "Python output
validated against it in CI").

`schema/` holds the JSON Schema source of truth — five files: `common.schema.json` (shared
`$defs`, referenced by `$ref` from the rest, never duplicated) and one schema per artefact
(`base-dataset`, `empire-overlay`, `detail-payload`, `search-index`, `diagnostics`). This module
loads them once, wires local `$ref`s together via a `referencing.Registry`, and exposes one
`validate_*` function per artefact — each raises `jsonschema.ValidationError` (with the standard
library's own message, which already names the failing path and reason) rather than swallowing
or reformatting it.

Deliberately thin: this module does not know how to *build* a dataset, only how to check one
against its contract. Stage 2's dataset-emission code is the producer; this is the gate it must
pass before anything is shipped, per CLAUDE.md's "the build fails rather than emitting a partial
dataset" rule.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schema"

# The schemaVersion(s) THIS build of the pipeline/client currently supports, per artefact. JSON
# Schema's "pattern" can check that schemaVersion looks like a semver string, but "is this
# specific version one we still support" is an application-level check, not a structural one --
# spec/00-overview.md: "The client MUST refuse to render an unsupported version with a clear
# message rather than degrading silently." This is that check's Python-side counterpart, so the
# same rejection is exercised in CI, not only in the browser.
SUPPORTED_SCHEMA_VERSIONS = {
    "base-dataset.schema.json": {"1.0.0"},
    "empire-overlay.schema.json": {"1.0.0"},
    "detail-payload.schema.json": {"1.0.0"},
    "search-index.schema.json": {"1.0.0"},
    "diagnostics.schema.json": {"1.0.0"},
}


class UnsupportedSchemaVersionError(Exception):
    """Raised when a document is otherwise well-formed but declares a `schemaVersion` this build
    doesn't support -- kept distinct from `jsonschema.ValidationError` so a caller (or a test)
    can tell "malformed" apart from "valid shape, wrong/future/past version" at a glance."""

    def __init__(self, artefact: str, found: str, supported: set[str]):
        self.artefact = artefact
        self.found = found
        self.supported = supported
        super().__init__(
            f"{artefact}: schemaVersion {found!r} is not supported by this build "
            f"(supported: {sorted(supported)})"
        )

_SCHEMA_FILES = [
    "common.schema.json",
    "base-dataset.schema.json",
    "empire-overlay.schema.json",
    "detail-payload.schema.json",
    "search-index.schema.json",
    "diagnostics.schema.json",
]


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _build_registry() -> Registry:
    resources = []
    for name in _SCHEMA_FILES:
        contents = _load_schema(name)
        resource = Resource(contents=contents, specification=DRAFT202012)
        # Register under both the schema's own $id and its bare filename, so a $ref written as
        # a plain relative filename ("common.schema.json#/$defs/X") resolves the same as one
        # written against the full $id -- whichever style a given schema file uses.
        resources.append((contents["$id"], resource))
        resources.append((name, resource))
    return Registry().with_resources(resources)


_REGISTRY = _build_registry()


def _validator_for(schema_filename: str) -> Draft202012Validator:
    schema = _load_schema(schema_filename)
    return Draft202012Validator(schema, registry=_REGISTRY)


_VALIDATORS = {name: None for name in _SCHEMA_FILES}


def _get_validator(schema_filename: str) -> Draft202012Validator:
    if _VALIDATORS[schema_filename] is None:
        _VALIDATORS[schema_filename] = _validator_for(schema_filename)
    return _VALIDATORS[schema_filename]


def _validate(schema_filename: str, document: dict) -> None:
    """Structural validation first (so a malformed document fails with the standard
    ValidationError, naming the offending path), then the schemaVersion support check --
    deliberately in that order: a document with an unsupported version AND a missing required
    field should report the structural problem, not mask it behind a version rejection."""
    _get_validator(schema_filename).validate(document)
    found = document.get("schemaVersion")
    supported = SUPPORTED_SCHEMA_VERSIONS[schema_filename]
    if found not in supported:
        raise UnsupportedSchemaVersionError(schema_filename, found, supported)


def validate_base_dataset(document: dict) -> None:
    _validate("base-dataset.schema.json", document)


def validate_empire_overlay(document: dict) -> None:
    _validate("empire-overlay.schema.json", document)


def validate_detail_payload(document: dict) -> None:
    _validate("detail-payload.schema.json", document)


def validate_search_index(document: dict) -> None:
    _validate("search-index.schema.json", document)


def validate_diagnostics(document: dict) -> None:
    _validate("diagnostics.schema.json", document)
