"""pipeline.scripted_triggers run against the real vendored corpus -- catalog size, cycle/depth
safety over EVERY real trigger (not just rendered-technology-reachable ones), and the measured
effect on D-10's uncertainty figures. Skipped when vendor/ isn't populated, same posture as
tests/test_overwrites_corpus.py and tests/test_availability_corpus.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.clausewitz import Assignment, Block, parse_file
from pipeline.inline_scripts import collect_scripts, expand_document
from pipeline.overwrite_overrides import load_overrides
from pipeline.overwrites import collect_technology_definitions, resolve_technology_overwrites
from pipeline.rendering_scope import rendered_technology_keys
from pipeline.scripted_triggers import (
    ExpansionDepthExceededError,
    MAX_EXPANSION_DEPTH,
    ScriptedTriggerCycleError,
    collect_scripted_trigger_definitions,
    expand_scripted_triggers,
    load_scripted_trigger_catalog,
    resolve_scripted_triggers,
)
from pipeline.variables import build_variable_table

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = REPO_ROOT / "vendor"

_SOURCES_IN_LOAD_ORDER = [
    ("Vanilla", VENDOR_ROOT / "stellaris"),
    ("Gigastructural Engineering", VENDOR_ROOT / "mods" / "gigastructures"),
    ("ACOT", VENDOR_ROOT / "mods" / "acot"),
    ("AoT", VENDOR_ROOT / "mods" / "aot"),
]

_vendor_populated = VENDOR_ROOT.is_dir() and any(root.is_dir() for _, root in _SOURCES_IN_LOAD_ORDER)

pytestmark = pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated locally")


def _script_entries():
    entries = []
    for name, root in _SOURCES_IN_LOAD_ORDER:
        base = root / "common" / "inline_scripts"
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.txt")):
            rel = f.relative_to(base).with_suffix("")
            entries.append((str(rel).replace("\\", "/"), str(f), f.read_text(encoding="utf-8")))
    return entries


def _potential_block(block: Block) -> Block | None:
    assignment = None
    for item in block.items:
        if isinstance(item, Assignment) and item.key_name == "potential":
            assignment = item
    if assignment is None or not isinstance(assignment.value, Block):
        return None
    return assignment.value


@pytest.fixture(scope="module")
def scripts():
    return collect_scripts(_script_entries())


@pytest.fixture(scope="module")
def catalog(scripts):
    return load_scripted_trigger_catalog(VENDOR_ROOT, scripts, _SOURCES_IN_LOAD_ORDER)


def test_catalog_size_and_overwrite_count(scripts):
    # Corpus-size drift guard, same posture as HANDOFF.md's "273 Clausewitz files" etc: a
    # meaningfully different count means the vendored corpus (or overwrite resolution) drifted --
    # re-derive the expected number before trusting anything measured against it.
    history = collect_scripted_trigger_definitions([
        (name, _docs_for(scripts, root)) for name, root in _SOURCES_IN_LOAD_ORDER
    ])
    resolved = resolve_scripted_triggers(history)
    assert len(resolved) == 3463
    overwritten = [name for name, occurrences in history.items() if len(occurrences) > 1]
    assert len(overwritten) == 135


def _docs_for(scripts, root: Path):
    d = root / "common" / "scripted_triggers"
    if not d.is_dir():
        return []
    docs = []
    for f in sorted(d.glob("*.txt")):
        from pipeline.inline_scripts import InlineScriptError

        try:
            doc, _report = expand_document(parse_file(f), scripts)
        except InlineScriptError:
            doc = parse_file(f)
        docs.append(doc)
    return docs


def test_has_research_building_survives_via_raw_fallback_parse(catalog):
    # See pipeline.scripted_triggers' own module docstring: zzz_overwrites.txt's
    # has_research_building can't be inline_script-expanded (a dynamic @[...] file-path
    # computation), but the catalog loader falls back to that one file's raw parse rather than
    # losing every other definition the file carries.
    assert "has_research_building" in catalog
    assert "has_galactic_wonders" in catalog  # defined later in the SAME file -- must survive too


def test_no_cycles_and_depth_bound_never_hit_across_the_whole_catalog(catalog):
    """Corpus regression guard: every one of the 3,463 real scripted triggers must expand cleanly
    on its own (seeded as its own chain root), never hitting a cycle or the depth ceiling. Real
    corpus: zero cycles, max observed reference-chain depth 8 (well under MAX_EXPANSION_DEPTH=12)
    -- if this ever fails, it's either a genuine new cycle/deep chain in a corpus refresh or (if
    it fails on this test itself, not real content) a bug in the detector, not something to bump
    past."""
    from pipeline.scripted_triggers import _expand_items  # internal, test-only

    for name, definition in catalog.items():
        # Each trigger's own body, expanded starting from itself as the chain root -- mirrors how
        # expand_scripted_triggers would expand a `name = yes` leaf referencing it.
        _expand_items(definition.body.items, catalog, (name,), 1)


def test_a_synthetic_cycle_injected_into_the_real_catalog_is_caught():
    """Prove the detector CAN fail before trusting the clean corpus-wide run above -- this
    project's own 'prove a negative before believing it' standing rule."""
    from pipeline.scripted_triggers import ScriptedTriggerDefinition
    from pipeline.clausewitz import parse_text

    def _body(text: str) -> Block:
        return parse_text(f"name = {text}\n", path="synthetic.txt").items[0].value

    fake_catalog = {
        "fake_a": ScriptedTriggerDefinition("fake_a", "Vanilla", "synthetic.txt", 1, _body("{ fake_b = yes }")),
        "fake_b": ScriptedTriggerDefinition("fake_b", "Vanilla", "synthetic.txt", 1, _body("{ fake_a = yes }")),
    }
    block = _body("{ fake_a = yes }")
    with pytest.raises(ScriptedTriggerCycleError):
        expand_scripted_triggers(block, fake_catalog)


@pytest.fixture(scope="module")
def rendered_expanded_potentials(scripts, catalog):
    tech_docs = [
        (name, [expand_document(parse_file(f), scripts)[0] for f in sorted((root / "common" / "technology").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "technology").is_dir()
    ]
    var_docs = [
        (name, [expand_document(parse_file(f), scripts)[0] for f in sorted((root / "common" / "scripted_variables").glob("*.txt"))])
        for name, root in _SOURCES_IN_LOAD_ORDER
        if (root / "common" / "scripted_variables").is_dir()
    ]
    all_docs = [d for _, docs in tech_docs for d in docs] + [d for _, docs in var_docs for d in docs]
    variable_table = build_variable_table(all_docs)
    technology_history = collect_technology_definitions(tech_docs)
    overrides = load_overrides()
    resolve_technology_overwrites(technology_history, variable_table, overrides)
    rendered_keys = rendered_technology_keys(technology_history)

    result: dict[str, Block | None] = {}
    for key, occurrences in technology_history.items():
        if key not in rendered_keys:
            continue
        winner = occurrences[-1]
        result[key] = _potential_block(winner.block)
    return {key: expand_scripted_triggers(block, catalog) for key, block in result.items()}


def test_expansion_never_raises_over_the_real_rendered_corpus(rendered_expanded_potentials):
    # If this test collects at all without raising, expansion succeeded for all 973 rendered
    # technologies' real potential blocks -- the fixture itself is the assertion.
    assert len(rendered_expanded_potentials) == 973


def test_zero_residual_is_ai_leaves_after_expansion(rendered_expanded_potentials):
    """The is_ai-stripping treatment (module docstring) must generalise across the whole real
    corpus, not just the two triggers it was originally hardcoded for."""

    def contains_is_ai(node) -> bool:
        if not isinstance(node, Assignment):
            return False
        if node.key_name == "is_ai":
            return True
        if isinstance(node.value, Block):
            return any(contains_is_ai(item) for item in node.value.items if isinstance(item, Assignment))
        return False

    for key, block in rendered_expanded_potentials.items():
        if block is None:
            continue
        assert not any(contains_is_ai(item) for item in block.items), f"{key} still carries an is_ai leaf after expansion"
