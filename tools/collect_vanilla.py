#!/usr/bin/env python3
"""
Copy the Stellaris base-game and Workshop mod files this project needs into
vendor/, which is gitignored. Nothing here is ever committed or redistributed.

Usage
-----
    python tools/collect_vanilla.py
    python tools/collect_vanilla.py --game-dir "D:/Steam/steamapps/common/Stellaris"
    python tools/collect_vanilla.py --list-mods

Run it again after any game or mod update. It overwrites vendor/ in place and
rewrites the manifest, so a re-run is always safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

STELLARIS_APP_ID = "281990"

# Base-game directories we need. Each entry is (relative path, required).
# Optional entries are copied when present and reported when absent, because
# Paradox moves things between versions and a hard failure on an optional
# folder would be a false alarm.
VANILLA_PATHS: list[tuple[str, bool]] = [
    ("common/technology", True),
    ("common/scripted_variables", True),
    ("common/scripted_triggers", True),
    ("common/ascension_perks", True),
    ("common/inline_scripts", False),
    ("common/strategic_resources", False),
    ("localisation/english", True),
    ("gfx/interface/icons/technologies", True),
    ("gfx/interface/icons/ascension_perks", False),
]

# Workshop mods we need, matched on the name in each mod's descriptor.mod
# rather than on a hardcoded Workshop ID, so a re-upload or a local copy
# still resolves. Matching is case-insensitive substring.
WANTED_MODS: dict[str, str] = {
    "gigastructural engineering": "gigastructures",
    "ancient cache of technologies": "acot",
    "acquisition of technology": "aot",
}

# Only these extensions are copied out of a mod or the game. Keeps vendor/
# to a sane size and avoids dragging in models, music and video.
KEEP_SUFFIXES = {".txt", ".yml", ".yaml", ".dds", ".png", ".mod", ".csv"}


def default_steam_roots() -> list[Path]:
    """Best-guess Steam library locations for the current OS."""
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        return [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Steam"),
            home / "Steam",
        ]
    if system == "Darwin":
        return [home / "Library/Application Support/Steam"]
    return [
        home / ".steam/steam",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/data/Steam",
    ]


def find_extra_libraries(steam_root: Path) -> list[Path]:
    """Read libraryfolders.vdf so secondary drives are searched too."""
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return []
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [Path(p.replace("\\\\", "/")) for p in re.findall(r'"path"\s+"([^"]+)"', text)]


def locate_game_dir(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not (path / "common" / "technology").is_dir():
            sys.exit(f"No common/technology under {path} — is that the Stellaris install root?")
        return path

    roots = default_steam_roots()
    for root in list(roots):
        roots.extend(find_extra_libraries(root))

    for root in roots:
        candidate = root / "steamapps" / "common" / "Stellaris"
        if (candidate / "common" / "technology").is_dir():
            return candidate

    sys.exit(
        "Could not find a Stellaris install automatically.\n"
        "Pass it explicitly, for example:\n"
        '  python tools/collect_vanilla.py --game-dir "C:/Program Files (x86)/Steam/steamapps/common/Stellaris"'
    )


def locate_workshop_dir(game_dir: Path) -> Path | None:
    """Workshop content sits as a sibling of common/ inside steamapps/."""
    for parent in game_dir.parents:
        candidate = parent / "workshop" / "content" / STELLARIS_APP_ID
        if candidate.is_dir():
            return candidate
    return None


def read_mod_name(mod_dir: Path) -> str | None:
    descriptor = mod_dir / "descriptor.mod"
    if not descriptor.is_file():
        return None
    try:
        text = descriptor.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def read_game_version(game_dir: Path) -> str:
    """Pull the version string out of launcher-settings.json where available."""
    settings = game_dir / "launcher-settings.json"
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8", errors="replace"))
            version = data.get("rawVersion") or data.get("version")
            if version:
                return str(version)
        except (OSError, json.JSONDecodeError):
            pass
    return "unknown"


def copy_tree(source: Path, dest: Path) -> tuple[int, int]:
    """Copy source into dest, keeping only KEEP_SUFFIXES. Returns (files, bytes)."""
    files = 0
    total = 0
    for item in source.rglob("*"):
        if not item.is_file() or item.suffix.lower() not in KEEP_SUFFIXES:
            continue
        target = dest / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        files += 1
        total += item.stat().st_size
    return files, total


def hash_tree(root: Path) -> str:
    """Stable digest over a copied tree, for change detection between runs."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def collect_mods(workshop_dir: Path, vendor_dir: Path, manifest: dict) -> None:
    found: dict[str, Path] = {}
    for mod_dir in sorted(p for p in workshop_dir.iterdir() if p.is_dir()):
        name = read_mod_name(mod_dir)
        if not name:
            continue
        lowered = name.lower()
        for needle, slug in WANTED_MODS.items():
            if needle in lowered and slug not in found:
                found[slug] = mod_dir
                manifest["mods"][slug] = {"name": name, "workshop_id": mod_dir.name}

    for slug, mod_dir in found.items():
        dest = vendor_dir / "mods" / slug
        if dest.exists():
            shutil.rmtree(dest)
        files, total = copy_tree(mod_dir, dest)
        manifest["mods"][slug].update(
            {"files": files, "bytes": total, "hash": hash_tree(dest)}
        )
        print(f"  {slug:<16} {files:>6} files  {total / 1_048_576:>7.1f} MB")

    for slug in WANTED_MODS.values():
        if slug not in found:
            manifest["missing_mods"].append(slug)
            print(f"  {slug:<16} NOT FOUND — subscribe in Steam, or copy it into vendor/mods/{slug}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", help="Stellaris install root")
    parser.add_argument("--vendor-dir", default="vendor", help="output directory (default: vendor)")
    parser.add_argument("--list-mods", action="store_true", help="list installed Workshop mods and exit")
    args = parser.parse_args()

    game_dir = locate_game_dir(args.game_dir)
    workshop_dir = locate_workshop_dir(game_dir)
    print(f"Game:     {game_dir}")
    print(f"Workshop: {workshop_dir or 'not found'}")

    if args.list_mods:
        if not workshop_dir:
            sys.exit("No Workshop directory found.")
        for mod_dir in sorted(p for p in workshop_dir.iterdir() if p.is_dir()):
            print(f"  {mod_dir.name:<14} {read_mod_name(mod_dir) or '(no descriptor)'}")
        return 0

    version = read_game_version(game_dir)
    vendor_dir = Path(args.vendor_dir).expanduser().resolve()
    manifest: dict = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "game_version": version,
        "vanilla": {},
        "mods": {},
        "missing_mods": [],
        "missing_vanilla": [],
    }

    print(f"\nVanilla (version {version}) -> {vendor_dir / 'stellaris'}")
    for rel, required in VANILLA_PATHS:
        source = game_dir / rel
        if not source.is_dir():
            manifest["missing_vanilla"].append(rel)
            marker = "MISSING (required)" if required else "absent (optional)"
            print(f"  {rel:<40} {marker}")
            continue
        dest = vendor_dir / "stellaris" / rel
        if dest.exists():
            shutil.rmtree(dest)
        files, total = copy_tree(source, dest)
        manifest["vanilla"][rel] = {"files": files, "bytes": total}
        print(f"  {rel:<40} {files:>6} files  {total / 1_048_576:>7.1f} MB")

    if workshop_dir:
        print(f"\nMods -> {vendor_dir / 'mods'}")
        collect_mods(workshop_dir, vendor_dir, manifest)

    vendor_dir.mkdir(parents=True, exist_ok=True)
    (vendor_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nWrote {vendor_dir / 'manifest.json'}")

    required_missing = [
        rel for rel, required in VANILLA_PATHS
        if required and rel in manifest["missing_vanilla"]
    ]
    if required_missing:
        print("\nRequired vanilla paths are missing — the pipeline cannot build without them:")
        for rel in required_missing:
            print(f"  {rel}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
