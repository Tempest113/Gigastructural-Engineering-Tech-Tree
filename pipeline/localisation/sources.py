"""Per-source localisation file discovery, driven by configuration — never by sniffing a
directory shape.

The Step 1 survey found three different conventions for how a mod lays out its "replace"
overrides alone: Gigastructures nests language *under* `replace/`
(`localisation/replace/english/*.yml`), ACOT nests `replace/` *under* language
(`localisation/english/replace/*.yml`), and AoT has no per-language subdirectory at all —
language is identified purely by filename suffix (`localisation/replace/*_l_english.yml`).
Sniffing "does this directory look like a language folder" would be fragile against exactly this
kind of variance, and spec/00-overview.md requires that adding a source be a configuration
change, not new code. So: every real file in the survey corpus (353/353) carries its language as
a filename suffix (`*_l_<language>.yml`), regardless of directory shape — which means a single
recursive glob for that suffix, rooted wherever a source's config says its localisation content
lives, finds every real layout variant above without needing to know which one it is. Each
source still declares its own roots independently (not shared/inferred), so a future source
whose localisation content doesn't fit under one `localisation/` root is a config change here,
not a new sniffing heuristic.

This module only resolves paths. It knows nothing about parsing — `pipeline.localisation.parser`
receives already-resolved `Path` objects and never touches a directory itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalisationSourceConfig:
    name: str
    vendor_root: Path
    localisation_roots: tuple[str, ...] = ("localisation",)
    filename_pattern: str = "*_l_{language}.yml"

    def resolve(self, language: str) -> list[Path]:
        pattern = self.filename_pattern.format(language=language)
        files: set[Path] = set()
        for root_rel in self.localisation_roots:
            root = self.vendor_root / root_rel
            if root.is_dir():
                files.update(root.rglob(pattern))
        return sorted(files)


def default_source_configs(vendor_dir: Path) -> list[LocalisationSourceConfig]:
    """Load order: vanilla, Gigastructures, ACOT, AoT — matching CLAUDE.md's 'Source data' table
    and every other load-order-sensitive pass in this pipeline (pipeline.variables,
    pipeline.inline_scripts). The vendor directory layout itself (`vendor/stellaris`,
    `vendor/mods/<name>`) is the one already established by tools/collect_vanilla.py and
    tests/fixtures/manifest.json — reused here, not reinvented."""
    return [
        LocalisationSourceConfig("stellaris", vendor_dir / "stellaris"),
        LocalisationSourceConfig("gigastructures", vendor_dir / "mods" / "gigastructures"),
        LocalisationSourceConfig("acot", vendor_dir / "mods" / "acot"),
        LocalisationSourceConfig("aot", vendor_dir / "mods" / "aot"),
    ]
