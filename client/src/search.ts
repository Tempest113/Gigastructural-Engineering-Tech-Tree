// Pure search-matching helpers, extracted out of `main.ts`'s `runSearch` closure (client
// test-infrastructure session) so query tokenisation and ranking can be unit tested without a
// Pixi/DOM render pass or a fetched search index.

export interface SearchIndexEntryLike {
  technologyId: string;
  tokens: string[];
}

export interface SearchMatch {
  id: string;
  rank: number;
}

/** Lower-cases and splits on any run of non-alphanumeric characters -- the same tokenisation the
 * build-time search index (`pipeline.dataset_emit.build_search_index`) uses on the indexed text,
 * so a query token and an index token compare on equal footing. */
export function tokenizeQuery(query: string): string[] {
  return query
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 0);
}

/** P-6: exact/prefix matches ranked above fuzzy -- this implementation is prefix-only (no
 * fuzzy/edit-distance matching, which P-6 marks optional). Rank 0 = exact name match, 1 = name
 * starts with the trimmed query, 2 = every query token prefix-matches at least one entry token
 * (AND across query words, matching how a multi-word search box query is normally read).
 * `nameOf` resolves a technology's CURRENT, profile/swap-correct displayed name (Item 2: a search
 * that exactly matches the profile-correct name should rank as an exact match even when the base
 * dataset's own name differs for this profile) -- callers pass their own display-name lookup
 * rather than this module reaching into dataset state. Returns matches sorted by rank, then id. */
export function rankSearchMatches(
  trimmedQuery: string,
  entries: readonly SearchIndexEntryLike[],
  nameOf: (technologyId: string) => string
): SearchMatch[] {
  const queryTokens = tokenizeQuery(trimmedQuery);
  if (queryTokens.length === 0) return [];
  const queryLower = trimmedQuery.toLowerCase();

  const matches: SearchMatch[] = [];
  for (const entry of entries) {
    const allTokensMatch = queryTokens.every((qt) => entry.tokens.some((t) => t.startsWith(qt)));
    if (!allTokensMatch) continue;
    const nameLower = nameOf(entry.technologyId).toLowerCase();
    const rank = nameLower === queryLower ? 0 : nameLower.startsWith(queryLower) ? 1 : 2;
    matches.push({ id: entry.technologyId, rank });
  }
  matches.sort((a, b) => a.rank - b.rank || a.id.localeCompare(b.id));
  return matches;
}
