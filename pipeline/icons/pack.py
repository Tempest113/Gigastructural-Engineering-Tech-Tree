"""Deterministic atlas packer.

Determinism (CLAUDE.md: "Icon atlases must pack deterministically. Unchanged icons produce
byte-identical output.") requires every source of nondeterminism to be pinned explicitly, not
assumed away:

- **Input order.** Icons are packed in ascending sort by `(height, name)` — an *explicit* stable
  sort on data the caller controls, never filesystem iteration order (`Path.glob` order is not
  guaranteed stable across platforms/filesystems) and never a `dict`/`set` iteration order (which
  depends on insertion history and, for `set`, hash seeding).
- **Packing algorithm.** A single-pass deterministic shelf packer (see `_pack_shelves`): given
  the same sorted input, it produces the same placement every time, with no random tie-breaking
  and no dependency on hash iteration anywhere in its own logic.
- **No timestamps or tool-version strings in the image bytes themselves.** Pillow's PNG/WebP
  writers do not embed a timestamp by default, but both can carry an ICC profile or EXIF block if
  one is present on the source image; every source DDS here decodes to a plain RGBA buffer with
  neither, and this module only ever encodes from that buffer, never re-opens the DDS as the
  encode source — so there is nothing to strip, but the invariant is enforced by construction
  (encoding from `DecodedIcon.rgba`, not from a re-opened file) rather than by hoping the encoder
  behaves.
- **Pinned encoder settings.** WebP: `lossless=True, method=6, exact=True` (exact=True fixes RGB
  values of fully-transparent pixels — different libwebp builds are otherwise free to slightly
  vary them, since they're invisible, which would break byte-identity for icons with any
  transparency at all). PNG: `optimize=False, compress_level=6` (fixed, not "best effort" or
  time-dependent). Any change to these settings, or a Pillow/libwebp version change, is expected
  to change output bytes — that's exactly why the encoder version is recorded in the atlas
  metadata (`_encoder_metadata`), so a future byte diff is attributable to a known cause instead
  of investigated as a mystery regression.
- **Padding and edge extrusion, not just empty gutters.** Each tile gets `PADDING` pixels of
  border on every side. A plain transparent gutter only stops *neighbour* bleed; it does nothing
  for a tile's *own* edge pixels being sampled past their true bounds at non-integer zoom (the
  renderer samples atlas tiles at arbitrary scale — spec/P-10). So the padding band is filled by
  clamping (extruding) the tile's own edge pixel outward, the standard atlas technique, rather
  than left transparent.

**`MAX_SHEET_DIMENSION` is a correctness bound, not a size optimisation.** WebGL only guarantees
`MAX_TEXTURE_SIZE >= 2048`; a single unbounded sheet (an early build produced 1008×6166 for the
technologies group) exceeds that floor and the 4096 many mid-range mobile GPUs report, so on a
guaranteed-minimum device the texture upload fails outright and every icon on that sheet
disappears — silently breaking P-9's "no desktop feature unavailable on mobile" requirement, not
degrading gracefully. `pack_sheets` therefore emits as many sheets per usage group as needed to
stay within `MAX_SHEET_DIMENSION` on both axes, while keeping the same determinism guarantees:
one global explicit stable sort by `(height, name)` over the whole usage group, then a single
forward pass that starts a new sheet exactly when the current shelf would push sheet height past
the cap — never reordering, never depending on how many sheets are needed to decide where an
earlier icon lands.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

import PIL

from .decode import DecodedIcon

PADDING = 2  # pixels of edge-extruded border per tile, each side.

MAX_SHEET_DIMENSION = 2048  # WebGL's guaranteed MAX_TEXTURE_SIZE floor -- see module docstring.

# Combined WebP bytes across every sheet, both usage kinds -- excluded from P-10's ≤2 MB base
# dataset budget (atlases load lazily), but not unbounded either.
#
# NOT a budget: it sits above today's measured ~8.65 MB *unfiltered* ceiling (every source
# packed unconditionally, before the P-16 rendering-scope closure removes ACOT/AoT content
# nothing rendered actually needs), so the real, filtered atlas set can essentially never trip
# it. This is a tripwire against a pipeline bug that pulls in far more sprites than intended
# (e.g. a resolution regression that stops deduplicating shared icons, or a source accidentally
# included twice) — not a size target to design toward or feel good about staying under.
# TODO(Stage 2): revisit this figure against the *filtered* atlas size once icon resolution
# actually runs against the P-16 closure (pipeline/icons/resolve.py's other TODO(Stage 2)) --
# that is the first point a meaningful budget, as opposed to a tripwire, can be set.
MAX_TOTAL_ATLAS_BYTES = 12 * 1024 * 1024

WEBP_SAVE_KWARGS = {"lossless": True, "method": 6, "exact": True}
PNG_SAVE_KWARGS = {"optimize": False, "compress_level": 6}


@dataclass(frozen=True)
class PackedTile:
    name: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class AtlasSheet:
    sheet_name: str
    width: int
    height: int
    rgba: bytes
    tiles: list[PackedTile]


def _extrude(rgba: bytes, w: int, h: int) -> tuple[bytes, int, int]:
    """Returns a new RGBA buffer of size (w + 2*PADDING, h + 2*PADDING) with the source image
    centered and its edge pixels clamped outward into the padding band (corners clamped to the
    nearest source corner pixel)."""
    p = PADDING
    ow, oh = w + 2 * p, h + 2 * p
    out = bytearray(ow * oh * 4)

    def src_px(x: int, y: int) -> bytes:
        x = min(max(x, 0), w - 1)
        y = min(max(y, 0), h - 1)
        i = (y * w + x) * 4
        return rgba[i : i + 4]

    for oy in range(oh):
        sy = oy - p
        row_start = oy * ow * 4
        for ox in range(ow):
            sx = ox - p
            out[row_start + ox * 4 : row_start + ox * 4 + 4] = src_px(sx, sy)
    return bytes(out), ow, oh


def pack_sheets(sheet_base_name: str, icons: dict[str, DecodedIcon], target_width: int) -> list[AtlasSheet]:
    """`icons` maps resolved icon name -> its decoded (level-0) RGBA. Sort is explicit and
    deterministic: by (height, name) ascending, both stable and never dependent on dict/set
    iteration order or the filesystem — computed once, globally, over the whole usage group,
    before any sheet boundary is decided.

    A single forward pass places each icon on the current shelf (starting a new shelf when it
    doesn't fit `target_width`), and starts an entirely new *sheet* — not just a new shelf —
    exactly when placing the current shelf would push the sheet past `MAX_SHEET_DIMENSION` in
    height. `target_width` itself must not exceed `MAX_SHEET_DIMENSION` (checked below); nothing
    here ever produces a sheet wider or taller than the cap. Sheets are named
    `f"{sheet_base_name}_{n}"`, 0-indexed in pack order — always suffixed, even when only one
    sheet results, so a sheet's filename never changes just because a later rebuild needed one
    more or one fewer page.
    """
    if target_width > MAX_SHEET_DIMENSION:
        raise ValueError(f"target_width {target_width} exceeds MAX_SHEET_DIMENSION {MAX_SHEET_DIMENSION}")

    ordered_names = sorted(icons.keys(), key=lambda n: (icons[n].height, n))
    extruded: dict[str, tuple[bytes, int, int]] = {}
    for name in ordered_names:
        icon = icons[name]
        extruded[name] = _extrude(icon.rgba, icon.width, icon.height)

    sheets: list[AtlasSheet] = []
    sheet_index = 0
    placements: list[tuple[str, int, int, int, int]] = []  # (name, x, y, ew, eh) in current sheet
    x = y = shelf_height = sheet_width = 0

    def finish_sheet() -> None:
        nonlocal sheet_index, placements, x, y, shelf_height, sheet_width
        if not placements:
            return
        sheet_height = y + shelf_height
        canvas = bytearray(sheet_width * sheet_height * 4)
        tiles: list[PackedTile] = []
        for name, tx, ty, ew, eh in placements:
            data, _, _ = extruded[name]
            for row in range(eh):
                src_off = row * ew * 4
                dst_off = ((ty + row) * sheet_width + tx) * 4
                canvas[dst_off : dst_off + ew * 4] = data[src_off : src_off + ew * 4]
            icon = icons[name]
            tiles.append(PackedTile(name=name, x=tx + PADDING, y=ty + PADDING, width=icon.width, height=icon.height))
        sheets.append(
            AtlasSheet(
                sheet_name=f"{sheet_base_name}_{sheet_index}",
                width=sheet_width,
                height=sheet_height,
                rgba=bytes(canvas),
                tiles=tiles,
            )
        )
        sheet_index += 1
        placements = []
        x = y = shelf_height = sheet_width = 0

    for name in ordered_names:
        _, ew, eh = extruded[name]
        if ew > target_width or eh > MAX_SHEET_DIMENSION:
            raise ValueError(
                f"icon {name!r} ({ew}x{eh} padded) does not fit within a single sheet "
                f"(target_width={target_width}, MAX_SHEET_DIMENSION={MAX_SHEET_DIMENSION})"
            )
        if x + ew > target_width and x > 0:
            x = 0
            y += shelf_height
            shelf_height = 0
        if y + eh > MAX_SHEET_DIMENSION and placements:
            finish_sheet()
        placements.append((name, x, y, ew, eh))
        x += ew
        shelf_height = max(shelf_height, eh)
        sheet_width = max(sheet_width, x)

    finish_sheet()
    return sheets


def encode_webp(sheet: AtlasSheet) -> bytes:
    from PIL import Image

    im = Image.frombytes("RGBA", (sheet.width, sheet.height), sheet.rgba)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", **WEBP_SAVE_KWARGS)
    return buf.getvalue()


def encode_png(sheet: AtlasSheet) -> bytes:
    from PIL import Image

    im = Image.frombytes("RGBA", (sheet.width, sheet.height), sheet.rgba)
    buf = io.BytesIO()
    im.save(buf, format="PNG", **PNG_SAVE_KWARGS)
    return buf.getvalue()


def encoder_metadata() -> dict:
    """Recorded in every atlas's metadata JSON so a future byte diff is attributable to a known
    Pillow/libwebp version change rather than investigated as a mystery regression."""
    try:
        from PIL import features

        webp_version = features.version("webp")
    except Exception:  # noqa: BLE001 - metadata only, never fatal
        webp_version = None
    return {
        "pillow_version": PIL.__version__,
        "webp_library_version": webp_version,
        "webp_save_kwargs": WEBP_SAVE_KWARGS,
        "png_save_kwargs": PNG_SAVE_KWARGS,
        "padding_px": PADDING,
    }


def sheet_content_hash(sheet: AtlasSheet) -> str:
    """Hash of the packed pixel content only (not encoded bytes, not metadata) — used by the
    single-icon-change isolation test to prove a changed source icon only touches the sheet that
    contains it."""
    return hashlib.sha256(sheet.rgba).hexdigest()
