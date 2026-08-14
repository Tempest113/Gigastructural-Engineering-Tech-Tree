"""Resolution-model tests: the four channels (explicit icon, swap's own icon, inherit_icon,
filename convention) and the override escape hatch. Synthetic fixtures built with `parse_text`,
each annotated with the real corpus evidence it's drawn from.
"""

from pathlib import Path

import pytest

from pipeline.clausewitz import parse_text
from pipeline.icons.overrides import IconOverride
from pipeline.icons.resolve import collect_candidates, resolve_all


def _candidates_from_text(text: str, kind: str, tmp_path: Path):
    path = tmp_path / "tech.txt"
    path.write_text(text, encoding="utf-8")
    return collect_candidates([("stellaris", path)], kind)


def test_filename_convention_is_the_default():
    def_text = 'tech_foo = {\n\tarea = physics\n}\n'
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "t.txt"
        p.write_text(def_text)
        candidates = collect_candidates([("stellaris", p)], "technology")
    assert len(candidates) == 1
    assert candidates[0].key == "tech_foo"
    assert candidates[0].resolved_name == "tech_foo"
    assert candidates[0].channel == "filename_convention"


def test_explicit_icon_field_overrides_filename(tmp_path):
    # 00_ancient_relics_tech.txt:48 -- tech_archeology_lab_ancrel's icon points at a different
    # tech's own icon, tech_archeology_lab.
    candidates = _candidates_from_text(
        'tech_archeology_lab_ancrel = {\n\ticon = "tech_archeology_lab"\n}\n', "technology", tmp_path
    )
    assert candidates[0].resolved_name == "tech_archeology_lab"
    assert candidates[0].channel == "explicit_icon"


def test_swap_own_name_filename_convention(tmp_path):
    text = (
        "tech_ring_world = {\n"
        "\ttechnology_swap = {\n"
        "\t\tname = giga_tech_ring_world_swap_no_habitables\n"
        "\t\tinherit_icon = no\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "technology", tmp_path)
    swap = next(c for c in candidates if "swap" in c.key)
    assert swap.key == "tech_ring_world/swap:giga_tech_ring_world_swap_no_habitables"
    assert swap.resolved_name == "giga_tech_ring_world_swap_no_habitables"
    assert swap.channel == "swap_filename_convention"


def test_swap_inherit_icon_yes_uses_owner_icon(tmp_path):
    text = (
        "tech_ring_world = {\n"
        "\ttechnology_swap = {\n"
        "\t\tname = giga_tech_ring_world_swap\n"
        "\t\tinherit_icon = yes\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "technology", tmp_path)
    swap = next(c for c in candidates if "swap" in c.key)
    assert swap.resolved_name == "tech_ring_world"
    assert swap.channel == "inherit_icon"


def test_swap_with_no_inherit_icon_field_defaults_to_filename_convention(tmp_path):
    # All 6 real cases with the field entirely absent (00_grand_archive_tech.txt) have their own
    # matching icon file -- confirmed default behaves like an explicit `inherit_icon = no`.
    text = (
        "tech_voidworm_immunity = {\n"
        "\ttechnology_swap = {\n"
        "\t\tname = tech_voidworm_immunity\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "technology", tmp_path)
    swap = next(c for c in candidates if "swap" in c.key)
    assert swap.resolved_name == "tech_voidworm_immunity"
    assert swap.channel == "swap_filename_convention"


def test_swap_own_explicit_icon_field_wins_over_inherit(tmp_path):
    text = (
        "tech_x = {\n"
        "\ttechnology_swap = {\n"
        "\t\tname = tech_x_swap\n"
        "\t\ticon = \"tech_x_custom_icon\"\n"
        "\t\tinherit_icon = yes\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "technology", tmp_path)
    swap = next(c for c in candidates if "swap" in c.key)
    assert swap.resolved_name == "tech_x_custom_icon"
    assert swap.channel == "explicit_icon"


def test_tradition_swap_used_for_ascension_perks(tmp_path):
    text = (
        "ap_foo = {\n"
        "\ttradition_swap = {\n"
        "\t\tname = ap_foo_swap\n"
        "\t\tinherit_icon = yes\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "ascension_perk", tmp_path)
    assert len(candidates) == 2
    swap = next(c for c in candidates if "swap" in c.key)
    assert swap.resolved_name == "ap_foo"
    assert swap.channel == "inherit_icon"


# ---------------------------------------------------------------------------
# resolve_all: files, overrides, and never silently substituting a refused icon.
# ---------------------------------------------------------------------------


def test_resolved_against_available_icon_files(tmp_path):
    candidates = _candidates_from_text("tech_foo = {\n\tarea = physics\n}\n", "technology", tmp_path)
    icon_files = {"tech_foo": ("stellaris", Path("/fake/tech_foo.dds"))}
    result = resolve_all(candidates, icon_files, {})
    assert len(result.resolved) == 1
    assert result.unresolved == []


def test_unresolved_without_override(tmp_path):
    candidates = _candidates_from_text("tech_foo = {\n\tarea = physics\n}\n", "technology", tmp_path)
    result = resolve_all(candidates, {}, {})
    assert len(result.unresolved) == 1
    assert result.resolved == []


def test_inherit_icon_no_with_no_own_file_is_unresolved_not_fallback(tmp_path):
    # The exact real shape: inherit_icon=no is an explicit refusal, never silently redirected to
    # the owner's icon even though the owner's icon file DOES exist.
    text = (
        "tech_ring_world = {\n"
        "\ttechnology_swap = {\n"
        "\t\tname = giga_tech_ring_world_swap_no_habitables\n"
        "\t\tinherit_icon = no\n"
        "\t}\n"
        "}\n"
    )
    candidates = _candidates_from_text(text, "technology", tmp_path)
    swap = next(c for c in candidates if "swap" in c.key)
    icon_files = {"tech_ring_world": ("gigastructures", Path("/fake/tech_ring_world.dds"))}
    result = resolve_all(candidates, icon_files, {})
    assert swap in result.unresolved
    # the owner's own candidate resolves fine (it has its own icon file) -- what must NOT
    # happen is the swap borrowing that same resolution despite its explicit refusal.
    resolved_keys = {c.key for c, _path, _channel in result.resolved}
    assert swap.key not in resolved_keys
    assert "tech_ring_world" in resolved_keys


def test_override_resolves_an_otherwise_unresolved_candidate(tmp_path):
    candidates = _candidates_from_text(
        (
            "tech_ring_world = {\n"
            "\ttechnology_swap = {\n"
            "\t\tname = giga_tech_ring_world_swap_no_habitables\n"
            "\t\tinherit_icon = no\n"
            "\t}\n"
            "}\n"
        ),
        "technology",
        tmp_path,
    )
    swap = next(c for c in candidates if "swap" in c.key)
    icon_files = {"tech_ring_world": ("gigastructures", Path("/fake/tech_ring_world.dds"))}
    overrides = {
        swap.key: IconOverride(
            key=swap.key, icon_name="tech_ring_world", justification="reviewed placeholder", line=1
        )
    }
    result = resolve_all(candidates, icon_files, overrides)
    swap_resolution = next((c, p, ch) for c, p, ch in result.resolved if c.key == swap.key)
    assert swap_resolution[2] == "override"
    assert result.overridden[0][1].icon_name == "tech_ring_world"


# ---------------------------------------------------------------------------
# Real corpus (vendor-backed, skipped if absent) -- confirms the corrected counts.
# ---------------------------------------------------------------------------

from tests.conftest import REPO_ROOT  # noqa: E402

VENDOR_ROOT = REPO_ROOT / "vendor"
_vendor_populated = VENDOR_ROOT.is_dir()


@pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated")
def test_real_corpus_resolution_counts():
    from pipeline.icons.build import resolve_kind
    from pipeline.icons.overrides import load_overrides

    overrides = load_overrides()
    tech_result = resolve_kind("technology", VENDOR_ROOT, overrides)
    assert len(tech_result.unresolved) == 19, (
        f"expected 19 unresolved technology/swap icon candidates (see resolve.py's module "
        f"docstring), found {len(tech_result.unresolved)}"
    )


@pytest.mark.skipif(not _vendor_populated, reason="vendor/ not populated")
def test_cross_source_icon_file_collision_count():
    from pipeline.icons.resolve import resolve_icon_files
    from pipeline.icons.sources import default_source_configs

    configs = default_source_configs(VENDOR_ROOT)
    seen_by_name: dict[str, list[str]] = {}
    for config in configs:
        for path in config.resolve("technologies"):
            seen_by_name.setdefault(path.name, []).append(config.name)
    collisions = sum(1 for sources in seen_by_name.values() if len(sources) > 1)
    assert collisions == 31, f"expected 31 cross-source technology icon collisions, found {collisions}"
