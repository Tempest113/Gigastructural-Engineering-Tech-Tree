"""Determinism tests: packing twice from the same input produces byte-identical output, and
changing one source icon changes only the sheet containing it — not any other sheet's pixel
content, and not the assignment of any other icon to a sheet or its position within one.
"""

from __future__ import annotations

from pipeline.icons.decode import DecodedIcon
from pipeline.icons.pack import MAX_SHEET_DIMENSION, encode_png, encode_webp, pack_sheets, sheet_content_hash


def _icon(width: int, height: int, fill: tuple[int, int, int, int]) -> DecodedIcon:
    rgba = bytes(fill) * (width * height)
    return DecodedIcon(path=None, width=width, height=height, rgba=rgba, used_fallback=False)


def _sample_icons() -> dict[str, DecodedIcon]:
    return {
        "tech_a": _icon(52, 52, (10, 20, 30, 255)),
        "tech_b": _icon(29, 29, (40, 50, 60, 128)),
        "tech_c": _icon(58, 58, (70, 80, 90, 0)),
        "tech_d": _icon(52, 52, (100, 110, 120, 255)),
    }


def _tile_map(sheets) -> dict[str, tuple[str, int, int]]:
    """name -> (sheet_name, x, y), for comparing tile assignment across two packs."""
    out = {}
    for sheet in sheets:
        for tile in sheet.tiles:
            out[tile.name] = (sheet.sheet_name, tile.x, tile.y)
    return out


def test_packing_twice_is_byte_identical():
    icons = _sample_icons()
    sheets1 = pack_sheets("technologies", icons, target_width=256)
    sheets2 = pack_sheets("technologies", icons, target_width=256)
    assert len(sheets1) == len(sheets2) == 1
    assert sheets1[0].rgba == sheets2[0].rgba
    assert sheets1[0].width == sheets2[0].width and sheets1[0].height == sheets2[0].height
    assert encode_webp(sheets1[0]) == encode_webp(sheets2[0])
    assert encode_png(sheets1[0]) == encode_png(sheets2[0])


def test_packing_is_independent_of_input_dict_order():
    icons = _sample_icons()
    reordered = {k: icons[k] for k in reversed(list(icons.keys()))}
    sheets1 = pack_sheets("technologies", icons, target_width=256)
    sheets2 = pack_sheets("technologies", reordered, target_width=256)
    assert sheets1[0].rgba == sheets2[0].rgba


def test_single_icon_change_only_changes_its_own_sheet_and_no_other_tile_assignment():
    icons_before = _sample_icons()
    icons_after = dict(icons_before)
    icons_after["tech_b"] = _icon(29, 29, (255, 255, 255, 255))  # changed pixel content only

    other_icons = {"ap_x": _icon(29, 29, (1, 2, 3, 255))}

    before_tech = pack_sheets("technologies", icons_before, target_width=256)
    after_tech = pack_sheets("technologies", icons_after, target_width=256)
    before_perk = pack_sheets("ascension_perks", other_icons, target_width=256)
    after_perk = pack_sheets("ascension_perks", other_icons, target_width=256)

    assert sheet_content_hash(before_tech[0]) != sheet_content_hash(after_tech[0])
    assert sheet_content_hash(before_perk[0]) == sheet_content_hash(after_perk[0])

    # Same dimensions (nothing changed shape), and every OTHER icon keeps the exact same
    # sheet/position -- a pixel-content change to one icon must not reshuffle anything else.
    assert before_tech[0].width == after_tech[0].width
    assert before_tech[0].height == after_tech[0].height
    before_map = _tile_map(before_tech)
    after_map = _tile_map(after_tech)
    for name in ("tech_a", "tech_c", "tech_d"):
        assert before_map[name] == after_map[name], f"{name}'s sheet/position changed when only tech_b's pixels did"
    # tech_b itself keeps the same sheet and position too -- only its pixel content differs.
    assert before_map["tech_b"][:1] == after_map["tech_b"][:1]  # same sheet_name
    assert before_map["tech_b"] == after_map["tech_b"]


def test_extrusion_pads_every_side_with_clamped_edge_pixels():
    icons = {"solo": _icon(4, 4, (5, 6, 7, 255))}
    sheets = pack_sheets("technologies", icons, target_width=64)
    sheet = sheets[0]
    tile = sheet.tiles[0]
    assert tile.width == 4 and tile.height == 4
    # top-left padding pixel (outside the addressable tile rect) must be the clamped corner
    # colour, not transparent/black -- proves extrusion actually ran, not just a gutter.
    top_left_padding_offset = ((tile.y - 1) * sheet.width + (tile.x - 1)) * 4
    assert sheet.rgba[top_left_padding_offset : top_left_padding_offset + 4] == bytes((5, 6, 7, 255))


def test_shelf_packer_places_no_overlapping_tiles_within_a_sheet():
    icons = {f"icon_{i}": _icon(20 + (i % 5), 20 + (i % 3), (i, i, i, 255)) for i in range(30)}
    sheets = pack_sheets("technologies", icons, target_width=200)
    for sheet in sheets:
        occupied = [[False] * sheet.width for _ in range(sheet.height)]
        for tile in sheet.tiles:
            for y in range(tile.y, tile.y + tile.height):
                for x in range(tile.x, tile.x + tile.width):
                    assert not occupied[y][x], f"tile {tile.name} overlaps another tile at ({x},{y})"
                    occupied[y][x] = True


# ---------------------------------------------------------------------------
# MAX_SHEET_DIMENSION: the correctness bound (P-9 mobile-GPU texture upload), not an optimisation.
# ---------------------------------------------------------------------------


def test_no_sheet_exceeds_max_dimension_on_either_axis():
    # 200 icons at 52x52 (+2px extrusion each side = 56x56 padded) on a 256-wide target packs 4
    # per shelf (56*4=224 <= 256): ceil(200/4)*56 = 2800px of height, comfortably past
    # MAX_SHEET_DIMENSION -- must split into more sheets rather than produce one oversized one.
    icons = {f"tech_{i}": _icon(52, 52, (i % 256, 0, 0, 255)) for i in range(200)}
    sheets = pack_sheets("technologies", icons, target_width=256)
    assert len(sheets) > 1
    for sheet in sheets:
        assert sheet.width <= MAX_SHEET_DIMENSION
        assert sheet.height <= MAX_SHEET_DIMENSION


def test_multi_sheet_split_is_deterministic_and_every_icon_placed_exactly_once():
    icons = {f"tech_{i:03d}": _icon(52, 52, (i % 256, i % 256, i % 256, 255)) for i in range(120)}
    sheets1 = pack_sheets("technologies", icons, target_width=512)
    sheets2 = pack_sheets("technologies", icons, target_width=512)

    assert [s.sheet_name for s in sheets1] == [s.sheet_name for s in sheets2]
    assert [s.rgba for s in sheets1] == [s.rgba for s in sheets2]

    all_placed = [t.name for s in sheets1 for t in s.tiles]
    assert sorted(all_placed) == sorted(icons.keys())
    assert len(all_placed) == len(set(all_placed))  # placed exactly once, no duplicates

    # Sheet names are always suffixed, 0-indexed in pack order.
    assert [s.sheet_name for s in sheets1] == [f"technologies_{i}" for i in range(len(sheets1))]


def test_single_sheet_case_still_gets_a_suffixed_name():
    icons = {"solo": _icon(4, 4, (1, 2, 3, 255))}
    sheets = pack_sheets("ascension_perks", icons, target_width=64)
    assert len(sheets) == 1
    assert sheets[0].sheet_name == "ascension_perks_0"
