#!/usr/bin/env python3
"""Generates TypeScript types from schema/*.json into schema/generated/dataset-types.ts.

**TODO(Stage 3) — this output is unverified as TypeScript.** `tests/schema/test_typescript_drift.py`
proves the checked-in file matches what this generator currently produces — it catches hand-editing,
which is what it was built for. It CANNOT catch this generator emitting TypeScript that fails to
compile: there is no Node in this environment, so no `tsc`, so nothing has ever actually
typechecked `schema/generated/dataset-types.ts`. Add a `tsc --noEmit` CI step over this file when
the Node toolchain lands with the PixiJS renderer (Stage 3) — do not treat the drift test as
sufficient proof the generator is correct, only that it's self-consistent.

Why hand-written in Python rather than running an off-the-shelf `json-schema-to-typescript`
generator: this environment has no Node/npm toolchain, and D-12 already commits the pipeline to
Python end to end — adding a Node-only codegen dependency just for this one step would be the
first thing in the entire pipeline to require it. The schemas in schema/ are also written in a
deliberately narrow subset of JSON Schema (object/array/string/integer/number/boolean, enum,
const, $ref, oneOf, additionalProperties: false) specifically so this generator doesn't need to
handle the full spec — see each schema file's own restraint on constructs used.

This is the *only* thing allowed to hand-edit schema/generated/dataset-types.ts. The file is
checked in (spec/00-overview.md: "TypeScript types generated from it"), and
tests/schema/test_typescript_drift.py re-runs this generator and diffs the result against the
checked-in file — so the two sides of the cross-language contract cannot drift by hand-editing
either end (per this repo's standing rule against exactly that).

Usage:
    python tools/generate_typescript_types.py            # regenerate schema/generated/dataset-types.ts
    python tools/generate_typescript_types.py --check     # exit 1 if the checked-in file is stale
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
OUTPUT_PATH = SCHEMA_DIR / "generated" / "dataset-types.ts"

# Order matters for readability of the generated file, not for correctness (every $ref is
# resolved by name lookup, not by file position).
SCHEMA_FILES = [
    "common.schema.json",
    "base-dataset.schema.json",
    "empire-overlay.schema.json",
    "detail-payload.schema.json",
    "search-index.schema.json",
    "diagnostics.schema.json",
]

# schema filename -> generated top-level TS interface name, for the artefact root object itself
# (every $defs entry gets its own named type regardless of which file requests it).
ROOT_TYPE_NAMES = {
    "base-dataset.schema.json": "BaseDataset",
    "empire-overlay.schema.json": "EmpireOverlay",
    "detail-payload.schema.json": "DetailPayload",
    "search-index.schema.json": "SearchIndex",
    "diagnostics.schema.json": "Diagnostics",
}


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _ref_type_name(ref: str) -> str:
    # e.g. "common.schema.json#/$defs/ThreeState" or "#/$defs/ThreeState" -> "ThreeState"
    return ref.rsplit("/", 1)[-1]


def _ts_scalar(schema: dict) -> str | None:
    t = schema.get("type")
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    return None


def _ts_type(schema: dict, indent: int = 0) -> str:
    if "$ref" in schema:
        return _ref_type_name(schema["$ref"])

    if "const" in schema:
        return json.dumps(schema["const"])

    if "enum" in schema:
        return " | ".join(json.dumps(v) for v in schema["enum"])

    if "oneOf" in schema:
        return " | ".join(_ts_type(s, indent) for s in schema["oneOf"])

    t = schema.get("type")

    if t == "array":
        item_type = _ts_type(schema.get("items", {}), indent)
        return f"({item_type})[]"

    if t == "object":
        return _ts_object_literal(schema, indent)

    scalar = _ts_scalar(schema)
    if scalar is not None:
        return scalar

    return "unknown"


def _ts_object_literal(schema: dict, indent: int) -> str:
    properties = schema.get("properties")
    pad = "  " * (indent + 1)
    closing_pad = "  " * indent

    if properties is None:
        # additionalProperties-only object (a map/dict), e.g. availability keyed by tech id.
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            value_type = _ts_type(additional, indent)
            return f"{{ [key: string]: {value_type} }}"
        return "Record<string, unknown>"

    required = set(schema.get("required", []))
    lines = ["{"]
    for prop_name, prop_schema in properties.items():
        optional = "" if prop_name in required else "?"
        prop_type = _ts_type(prop_schema, indent + 1)
        description = prop_schema.get("description")
        if description:
            lines.append(f"{pad}/** {description} */")
        lines.append(f"{pad}{prop_name}{optional}: {prop_type};")
    lines.append(f"{closing_pad}}}")
    return "\n".join(lines)


def _generate_defs_section(schema: dict) -> list[str]:
    out = []
    for name, def_schema in schema.get("$defs", {}).items():
        description = def_schema.get("description")
        comment = def_schema.get("$comment")
        if description:
            out.append(f"/** {description} */")
        if comment:
            out.append(f"// {comment}")
        body = _ts_type(def_schema, indent=0)
        if def_schema.get("type") == "object" and "properties" in def_schema:
            out.append(f"export interface {name} {body}")
        else:
            out.append(f"export type {name} = {body};")
        out.append("")
    return out


def _generate_root_section(filename: str, schema: dict) -> list[str]:
    root_name = ROOT_TYPE_NAMES[filename]
    description = schema.get("description")
    out = []
    if description:
        out.append(f"/** {description} */")
    body = _ts_object_literal(schema, indent=0)
    out.append(f"export interface {root_name} {body}")
    out.append("")
    return out


def generate() -> str:
    lines = [
        "// GENERATED FILE — DO NOT EDIT BY HAND.",
        "// Produced by tools/generate_typescript_types.py from schema/*.json.",
        "// Re-run that script after changing any schema/*.json file; the checked-in copy of",
        "// this file and a fresh run must be byte-identical (see",
        "// tests/schema/test_typescript_drift.py) — that identity is what stops the Python and",
        "// TypeScript sides of the dataset contract from drifting apart by hand-editing either.",
        "",
    ]

    common = _load("common.schema.json")
    lines.extend(_generate_defs_section(common))

    for filename in SCHEMA_FILES:
        if filename == "common.schema.json":
            continue
        schema = _load(filename)
        lines.extend(_generate_root_section(filename, schema))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    check = "--check" in sys.argv
    generated = generate()
    if check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != generated:
            print(f"STALE: {OUTPUT_PATH} does not match a fresh generation. Run without --check to update.")
            return 1
        print("OK: generated TypeScript types are up to date.")
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
