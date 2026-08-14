"""DDS decoding — level 0 only.

Mipmap chains are discarded at decode, deliberately: the renderer generates its own mip levels
from the packed atlas (standard for a WebGL/PixiJS texture), so a source DDS's own mip chain
(present in only 105/2,251 files in the survey corpus — 57 Gigastructures, 48 ACOT, none in
Stellaris or AoT) would be dead weight in the atlas and, worse, a determinism surface with
nothing checking it: an encoder decision about how many levels to keep, or whether to trust an
upstream mip level's exact bytes, is one more thing that could silently vary between runs for no
reason the output format needs. Pillow's DDS plugin already only decodes the base level by
default; this module makes that explicit rather than incidental.

Primary decoder is Pillow (verified byte-for-byte identical to an independent ImageMagick decode
across one sample of every format actually present in the corpus — DXT1, DXT3, DXT5,
uncompressed 32-bit BGRA, uncompressed 24-bit BGR, and a mipmapped file — during the Step 1
survey). No BC5/BC7/DX10-extended file exists anywhere in the current corpus, so the ImageMagick
fallback is never exercised today — kept anyway as defensive coding for a future source or
upstream format change, and made loud when it *does* trigger: a silent fallback would hide
exactly the kind of format drift this module exists to catch, so every fallback use is logged at
warning level with the file path and the Pillow error that triggered it, and recorded on the
returned `DecodedIcon` so a caller building a diagnostics report can surface it instead of losing
it in a log stream.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class IconDecodeError(Exception):
    pass


@dataclass
class DecodedIcon:
    path: Path
    width: int
    height: int
    rgba: bytes  # width * height * 4 bytes, row-major, top-to-bottom
    used_fallback: bool
    fallback_reason: str | None = None


def decode_level0(path: Path) -> DecodedIcon:
    try:
        return _decode_with_pillow(path)
    except Exception as exc:  # noqa: BLE001 - genuinely any Pillow failure should fall back
        logger.warning("Pillow failed to decode %s (%s: %s) — falling back to ImageMagick", path, type(exc).__name__, exc)
        return _decode_with_imagemagick(path, fallback_reason=f"{type(exc).__name__}: {exc}")


def _decode_with_pillow(path: Path) -> DecodedIcon:
    with Image.open(path) as im:
        im.load()  # force decode now, not lazily at first pixel access
        rgba = im.convert("RGBA")
        width, height = rgba.size
        data = rgba.tobytes()
    return DecodedIcon(path=path, width=width, height=height, rgba=data, used_fallback=False)


def _decode_with_imagemagick(path: Path, fallback_reason: str) -> DecodedIcon:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "decoded.png"
        try:
            subprocess.run(
                ["convert", f"{path}[0]", str(out_path)],  # [0] pins to the first (base) frame/level
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise IconDecodeError(f"both Pillow and ImageMagick failed to decode {path}: {exc}") from exc
        with Image.open(out_path) as im:
            im.load()
            rgba = im.convert("RGBA")
            width, height = rgba.size
            data = rgba.tobytes()
    logger.warning("ImageMagick fallback used for %s (Pillow failure: %s)", path, fallback_reason)
    return DecodedIcon(path=path, width=width, height=height, rgba=data, used_fallback=True, fallback_reason=fallback_reason)
