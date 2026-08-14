"""Decode tests, one fixture per DDS variant confirmed in the Step 1 survey: DXT1 (BC1), DXT3
(BC2), DXT5 (BC3), uncompressed 32-bit BGRA (with alpha), uncompressed 24-bit BGR (no alpha), and
a real mipmapped file (level-0-only decode must discard the extra levels)."""

from pathlib import Path

from tests.conftest import FIXTURES_ROOT

from pipeline.icons.decode import decode_level0

ICON_FIXTURES = FIXTURES_ROOT / "icons"


def test_dxt1_decodes():
    icon = decode_level0(ICON_FIXTURES / "dxt1_sample.dds")
    assert icon.width == 52 and icon.height == 52
    assert len(icon.rgba) == 52 * 52 * 4
    assert icon.used_fallback is False


def test_dxt3_decodes():
    icon = decode_level0(ICON_FIXTURES / "dxt3_sample.dds")
    assert icon.width == 52 and icon.height == 52
    assert len(icon.rgba) == 52 * 52 * 4


def test_dxt5_decodes():
    icon = decode_level0(ICON_FIXTURES / "dxt5_sample.dds")
    assert icon.width == 52 and icon.height == 52
    assert len(icon.rgba) == 52 * 52 * 4


def test_uncompressed_32bit_bgra_decodes_with_alpha():
    icon = decode_level0(ICON_FIXTURES / "uncompressed32_sample.dds")
    assert icon.width == 58 and icon.height == 58
    alphas = icon.rgba[3::4]
    assert min(alphas) < 255  # confirmed real: this icon has genuine partial transparency.


def test_uncompressed_24bit_bgr_decodes_opaque():
    icon = decode_level0(ICON_FIXTURES / "uncompressed24_sample.dds")
    assert icon.width == 52 and icon.height == 52
    alphas = icon.rgba[3::4]
    assert set(alphas) == {255}  # no alpha channel in source -> fully opaque.


def test_mipmapped_file_decodes_only_level_0():
    # tech_acot_army_hive_3.dds carries a real 6-level mip chain (mipmapcount=6,
    # DDSD_MIPMAPCOUNT set). Decoding must only ever produce the base level's dimensions.
    icon = decode_level0(ICON_FIXTURES / "mipmapped_sample.dds")
    assert icon.width == 52 and icon.height == 52
    assert len(icon.rgba) == 52 * 52 * 4


def test_pillow_and_imagemagick_agree_on_every_format():
    """Independent-decode verification, promoted from the Step 1 survey's manual check into a
    standing test: for each format fixture, Pillow's decode (the primary path) must match an
    ImageMagick decode (the fallback path) pixel-for-pixel. If this ever fails, it means Pillow's
    behaviour for that format has changed and the fallback path needs re-evaluating."""
    import subprocess
    import tempfile

    from PIL import Image

    for name in [
        "dxt1_sample.dds",
        "dxt3_sample.dds",
        "dxt5_sample.dds",
        "uncompressed32_sample.dds",
        "uncompressed24_sample.dds",
        "mipmapped_sample.dds",
    ]:
        path = ICON_FIXTURES / name
        pillow_icon = decode_level0(path)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.png"
            subprocess.run(["convert", f"{path}[0]", str(out_path)], check=True, capture_output=True)
            with Image.open(out_path) as im:
                im.load()
                magick_rgba = im.convert("RGBA").tobytes()
        assert pillow_icon.rgba == magick_rgba, f"{name}: Pillow and ImageMagick decodes disagree"
