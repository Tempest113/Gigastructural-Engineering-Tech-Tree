"""Loader/checker for `roundtrip_allowlist.json` — read that file first for what an entry means
and does not mean, and the rules for adding one. This module is deliberately thin: it does exact
structural matching only (file path + token index + both tokens' type and text) and refuses, by
construction, to consult the allowlist for anything but an adjacency-only divergence — see
`pipeline/clausewitz/roundtrip.is_adjacency_only_divergence`, which every caller here is expected
to have already checked before asking `is_allowlisted`.
"""

from __future__ import annotations

import json
from pathlib import Path

_ALLOWLIST_PATH = Path(__file__).with_name("roundtrip_allowlist.json")


def _token_repr(tok) -> dict:
    return {"type": tok[0].name, "text": tok[1]}


def _load() -> dict:
    data = json.loads(_ALLOWLIST_PATH.read_text())
    keyed = {}
    for entry in data["entries"]:
        key = (entry["file"], entry["token_index"])
        keyed[key] = (entry["source_token"], entry["serialized_token"])
    return keyed


_ALLOWLIST = _load()


def is_allowlisted(rel_file: str, token_index: int, source_token, serialized_token) -> bool:
    """`rel_file` is the file path as recorded in the allowlist (repo-root-relative, e.g.
    `vendor/stellaris/common/technology/00_apocalypse_tech.txt` or
    `tests/fixtures/gigastructures/giga_06_special_project_tech.txt`). Returns True only if an
    entry exists at this exact (file, index) *and* both recorded tokens still match — if the
    tokeniser or serialiser changes what appears at this site, the entry stops applying and this
    returns False, surfacing the site as a fresh, unreviewed divergence."""
    key = (rel_file, token_index)
    if key not in _ALLOWLIST:
        return False
    recorded_source, recorded_serialized = _ALLOWLIST[key]
    return recorded_source == _token_repr(source_token) and recorded_serialized == _token_repr(serialized_token)
