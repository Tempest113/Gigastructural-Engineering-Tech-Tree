"""P-16 icon-atlas scope filtering (pipeline.icons.build.filter_result_to_rendered_scope) --
closes the "Atlas content scope" TODO(Stage 2) in pipeline/icons/resolve.py. Synthetic mechanism
tests; the real-corpus figures are measured in tests/icons/test_icon_corpus.py.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.icons.build import candidate_owner_key, filter_result_to_rendered_scope
from pipeline.icons.resolve import IconCandidate, IconResolutionResult


def _candidate(key: str) -> IconCandidate:
    return IconCandidate(
        key=key, kind="technology", resolved_name=key, channel="filename_convention",
        definition_source="stellaris", file="x.txt", line=1,
    )


def test_candidate_owner_key_is_bare_for_a_plain_technology():
    assert candidate_owner_key("tech_a") == "tech_a"


def test_candidate_owner_key_strips_the_swap_suffix():
    assert candidate_owner_key("tech_a/swap:giga_tech_a_swap_nomad") == "tech_a"


def test_filter_keeps_only_candidates_whose_owner_is_rendered():
    rendered = _candidate("tech_rendered")
    unrendered = _candidate("tech_unrendered")
    swap_of_rendered = _candidate("tech_rendered/swap:some_swap")
    swap_of_unrendered = _candidate("tech_unrendered/swap:other_swap")

    result = IconResolutionResult(
        candidates=[rendered, unrendered, swap_of_rendered, swap_of_unrendered],
        icon_files={},
        resolved=[(rendered, Path("a.dds"), "filename_convention"), (swap_of_rendered, Path("b.dds"), "filename_convention")],
        unresolved=[unrendered, swap_of_unrendered],
        overridden=[],
    )

    filtered = filter_result_to_rendered_scope(result, {"tech_rendered"})

    assert {c.key for c, _p, _ch in filtered.resolved} == {"tech_rendered", "tech_rendered/swap:some_swap"}
    assert filtered.unresolved == []  # both unresolved candidates' owners are unrendered
    assert {c.key for c in filtered.candidates} == {"tech_rendered", "tech_rendered/swap:some_swap"}


def test_filter_drops_unresolved_candidate_whose_owner_is_unrendered_but_keeps_a_rendered_one():
    rendered_unresolved = _candidate("tech_rendered")
    unrendered_unresolved = _candidate("tech_unrendered")
    result = IconResolutionResult(
        candidates=[rendered_unresolved, unrendered_unresolved],
        icon_files={},
        resolved=[],
        unresolved=[rendered_unresolved, unrendered_unresolved],
        overridden=[],
    )
    filtered = filter_result_to_rendered_scope(result, {"tech_rendered"})
    assert filtered.unresolved == [rendered_unresolved]


def test_filter_keeps_overridden_candidates_whose_owner_is_rendered():
    from pipeline.icons.overrides import IconOverride

    c = _candidate("tech_rendered")
    override = IconOverride(key="tech_rendered", icon_name="some_icon", line=1, justification="x")
    result = IconResolutionResult(
        candidates=[c], icon_files={}, resolved=[(c, Path("a.dds"), "override")], unresolved=[],
        overridden=[(c, override)],
    )
    filtered = filter_result_to_rendered_scope(result, {"tech_rendered"})
    assert len(filtered.overridden) == 1

    filtered_out = filter_result_to_rendered_scope(result, {"tech_other"})
    assert filtered_out.overridden == []
