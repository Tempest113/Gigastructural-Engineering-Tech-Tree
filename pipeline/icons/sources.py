"""Per-source icon file discovery, mirroring `pipeline.localisation.sources`'s posture:
configuration-driven, never sniffed. Unlike localisation's directory-shape variance, the icon
survey found all four sources use the same `gfx/interface/icons/<kind>/*.dds` layout with no
`replace/`-style override subdirectory of their own — cross-source overrides here are separate
files in separate source trees under the same relative path, resolved by `resolve.py`, not by
directory nesting within one source.

`categories/`, `old_tech_icons/` and `tech_templates/` (Stellaris-only subdirectories under
`technologies/`) are deliberately excluded: `categories/` holds research-area icons, not
per-technology icons, and P-4 requires only a category *list*, no category icons to pack against;
`old_tech_icons/` and `tech_templates/` hold legacy/placeholder assets with no current
per-technology referent. Excluding them means only `*.dds` files directly under each `<kind>/`
directory are discovered — `glob`, not `rglob`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ICON_KINDS = ("technologies", "ascension_perks")


@dataclass(frozen=True)
class IconSourceConfig:
    name: str
    vendor_root: Path

    def icon_dir(self, kind: str) -> Path:
        if kind not in ICON_KINDS:
            raise ValueError(f"unknown icon kind {kind!r}, expected one of {ICON_KINDS}")
        return self.vendor_root / "gfx" / "interface" / "icons" / kind

    def resolve(self, kind: str) -> list[Path]:
        d = self.icon_dir(kind)
        if not d.is_dir():
            return []
        return sorted(d.glob("*.dds"))


def default_source_configs(vendor_dir: Path) -> list[IconSourceConfig]:
    """Load order: vanilla, Gigastructures, ACOT, AoT — same as everywhere else in this
    pipeline. Reuses the vendor layout already established by tools/collect_vanilla.py and
    tests/fixtures/manifest.json."""
    return [
        IconSourceConfig("stellaris", vendor_dir / "stellaris"),
        IconSourceConfig("gigastructures", vendor_dir / "mods" / "gigastructures"),
        IconSourceConfig("acot", vendor_dir / "mods" / "acot"),
        IconSourceConfig("aot", vendor_dir / "mods" / "aot"),
    ]
