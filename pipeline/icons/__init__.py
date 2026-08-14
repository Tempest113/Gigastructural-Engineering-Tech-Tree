"""Icon extraction and atlas-packing pipeline (Stage 1, spec/00-overview.md).

Scope: `gfx/interface/icons/technologies` and `gfx/interface/icons/ascension_perks`, across all
four vendored sources (see spec/00-overview.md's required-directories list — the ascension-perk
directory was added after the P-3 survey found gate icons for Cosmogenesis/Galactic
Wonders/Gigastructural Constructs are not filed under `technologies/` in any source).

Stage boundary, deliberately narrow: **this stage resolves candidate icon keys and packs every
icon it can decode. It has no concept of rendering scope and never fails the build on a missing
icon.** Whether a technology with no resolvable icon is a real problem depends on whether that
technology is ever actually rendered for any empire profile — and "is this technology reachable"
is exactly what Stage 2's partial trigger evaluator exists to answer (a `potential = { always =
no }` technology is unreachable, but recognising that pattern by hand here would be trigger
evaluation performed manually in Stage 1, which is the same mistake for icons that it would be
for the DAG). So: `resolve.py` records every unresolved candidate as a diagnostic, uninterpreted;
Stage 2 (not yet built — see the TODO in `resolve.py`'s module docstring) is the one place that
gets to decide which of those diagnostics become build failures, once it knows which
technologies are actually in scope.
"""
