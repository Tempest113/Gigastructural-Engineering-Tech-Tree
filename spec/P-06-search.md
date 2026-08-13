# P-6 — Technology search

**Requirement.** Users MUST be able to search technologies by name or keyword, with matching
results highlighted or isolated within the tree view.

## Acceptance criteria

- Search matches against, at minimum: localised name, internal technology key, and description
  text.
- Results update incrementally as the user types, with no perceptible input lag (see P-10
  budgets).
- Matching nodes are visually emphasised; non-matching nodes are dimmed. The user can toggle
  between *highlight* mode (non-matches dimmed but present) and *isolate* mode (non-matches
  hidden).
- The view can pan/zoom to fit the result set on request, and can step through results
  sequentially.
- Search is diacritic- and case-insensitive and tolerant of partial word matches.
- Search state is encoded in the URL.

## Implied technical decisions

- A **search index MUST be built at build time** and shipped with the dataset. Linear scans over
  full description text at runtime are acceptable only if measured within the P-10 budget on a
  mid-range mobile device; otherwise a prefix/trigram index is required.
- Fuzzy matching (edit distance) is OPTIONAL; if implemented, exact and prefix matches MUST rank
  above fuzzy matches.
