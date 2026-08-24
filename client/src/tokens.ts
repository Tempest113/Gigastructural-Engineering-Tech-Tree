// Colour tokens, spec/S-01-colour.md's "single source of truth consumed by both node rendering
// and connector rendering". Edge (connector) styling is defined further down this file, added in
// Stage 3 slice 3.
//
// spec/S-01-colour.md pins exact hex only for the five crisis factions; research-area colours
// are specified by name only ("Physics: blue", "Society: green", "Engineering: orange"). The
// values below are this session's first concrete pick, chosen to clear the spec's own pairwise
// contrast bar (S-1: every pair of background colours >= 15 CIEDE2000 units) against each other
// and against the crisis-faction fills -- not yet run through a mechanical ΔE2000 check (that
// CI-enforced acceptance criterion is still open work, see CLAUDE.md). Pattern fills (S-1's
// second, non-colour channel per classification) are not implemented in this slice -- these are
// flat fills only, matching the LOD table's <7%-zoom degraded state.

export const AREA_COLORS: Record<string, number> = {
  physics: 0x2e6fb0,
  society: 0x2e8b57,
  engineering: 0xc97a2b,
};

// Badges slice (reconciliation session): rare/dangerous outline + badge colours. S-1 pins
// "dangerous red" by name only, and says nothing at all about a rare colour beyond "badge, not a
// warning treatment" -- both values below are this session's own first concrete pick, same
// unresolved-spec-colour status as AREA_COLORS above, not yet checked against the ΔE2000/WCAG
// acceptance criteria. DANGEROUS_COLOR is a clear warning red, distinct from EDGE_COLOR/
// HOVER_COLOR and every AREA_COLORS/CRISIS_FACTION_COLORS value. RARE_COLOR is a gold/amber,
// chosen for the conventional "rare = valuable" association and checked by eye against every
// other token here for basic distinguishability -- not yet run through the mechanical ΔE2000
// check S-1 requires.
export const DANGEROUS_COLOR = 0xd7373f;
export const RARE_COLOR = 0xd4af37;
// Mod-requirement badge (ACOT/AoT chip) -- a neutral, non-classification colour, since the
// requirement itself is informational (P-16), not a rarity/danger signal.
export const MOD_REQUIREMENT_BADGE_COLOR = 0x4a5568;

// CLAUDE.md's "Colour and pattern" section, signed-off palette -- these are the faction's own
// identity colours, used for a faction row's header chip (D-16: the row, not the card, carries
// faction colour now -- see below for the card-neutral change).
export const CRISIS_FACTION_COLORS: Record<string, number> = {
  Aeternum: 0x823269,
  Blokkats: 0x2a6b2a,
  Compound: 0x2f137f,
  Sirenalia: 0xb0338c,
  "Katzenartig Imperium": 0x2e3f98,
};

// D-16's row re-axis: colour/pattern now encode the ROW's backing, not the card fill (see
// CARD_FILL/CARD_STROKE below). A faction row's backing is its own tiled pattern, not the flat
// CRISIS_FACTION_COLORS value the card used to carry -- CLAUDE.md's signed-off palette names a
// distinct backing tone for Blokkats specifically ("#1C451C, the authentic flag colour, reserved
// for tier-band/lane backing, not node fill"); the other four factions have only one signed-off
// hex each, reused here as the backing base. `accent` is the pattern's second colour, used to draw
// the tiled motif over the panel fill -- Blokkats' and Katzenartig's accents are CLAUDE.md's own
// signed-off values ("pattern stroke #63A85C", "with #CC9429"); Aeternum/Compound have no second
// signed-off hex, so their accent is the same hue as `base`. Sirenalia's "high-contrast sweeping
// bands" names a *shape*, not a hex -- its accent (white) is this session's own placeholder
// pending a real signed-off contrast colour, flagged here rather than silently treated as final.
// The real traced Blokkats flag SVG tile (CLAUDE.md's open item) is still not built.
//
// **Real faction pattern artwork (this session, DEFECT 5), replacing the procedural placeholders.**
// All five geometries below are user-supplied -- the user is a Gigastructures contributor -- not
// inferred by Claude, except Katzenartig's, explicitly flagged provisional (see its own entry).
// `accent` becomes `accents: number[]` (was a single colour) so Sirenalia can carry its several
// distinct pink/purple shades; every style function in `main.ts` reads `accents[0]` when it only
// needs one colour. Feature size still scales with row height, not card size (`main.ts`'s
// `drawFactionRowPattern` -- unchanged rationale from the previous rescale), and every accent
// layer is now clipped with a PixiJS mask rather than analytic per-line bounding (`main.ts`'s
// `maskToRowRect`) -- the earlier analytic-clip approach doesn't generalise to hexagons/swirls/
// chevrons the way it did to a single diagonal line family, and a per-row rectangular mask (5 of
// them, one per faction row) costs nothing measurable at this scene size. The mask Graphics MUST
// be added as a scene-graph child alongside its target (see `maskToRowRect`'s own comment) -- an
// unparented mask's transform never updates and clips in the wrong coordinate space entirely,
// a real bug this session's own screenshot review caught (the pattern rendered correctly but was
// invisible, clipped to nothing).
export interface RowPatternSpec {
  base: number;
  accents: number[];
  accentAlpha: number;
  style: "herringbone" | "waves" | "hexagons" | "swirls" | "chevrons";
}

export const CRISIS_FACTION_ROW_PATTERNS: Record<string, RowPatternSpec> = {
  // Aeternum: "the Blokkat flag device is a circle containing a lightning-bolt/arrow chevron" --
  // wait, that's Blokkats (see below); Aeternum's own device (user-supplied) is tiled hexagons,
  // lighter pink outline on a burgundy background. `base` becomes the in-game BURGUNDY flag colour
  // (rgb 89,18,39 = #591227), newly added here -- CLAUDE.md's signed-off #823269 was the in-game
  // PINK flag colour, now used as the hexagon outline accent instead of the row's flat base tint.
  //
  // Lightened, later session: the user found the hexagon stroke too dark against the burgundy
  // backing. The SIGNED-OFF base hexes (#591227 backing, #823269 flag pink -- CRISIS_FACTION_
  // COLORS.Aeternum above, used elsewhere e.g. badges/legend) are unchanged; only THIS pattern's
  // own stroke colour/opacity moved. `accents[0]` (the hexagon outline colour `main.ts`'s
  // `drawFactionRowPattern` actually strokes with) is now #823269 blended 35% toward white
  // (130,50,105 -> ~174,122,158 -> #AE7A9E) instead of the raw signed-off pink -- a rendering-only
  // lightening local to this pattern spec, not an edit to the signed-off constant itself.
  // accentAlpha raised 0.30->0.42 alongside it -- "opacity" was the other half of the ask.
  Aeternum: { base: 0x591227, accents: [0xae7a9e], accentAlpha: 0.42, style: "hexagons" },
  // Blokkats: the flag device is a circle containing a lightning-bolt/arrow chevron -- tiled as a
  // repeating, staggered, INTERLOCKING lattice (adjacent rows offset, herringbone-style), lighter
  // green (#63A85C) OUTLINE only on the darker green flag background (#1C451C) -- never solid
  // shapes, per the user's own instruction.
  Blokkats: { base: 0x1c451c, accents: [0x63a85c], accentAlpha: 0.26, style: "herringbone" },
  // Compound: dark blue/purple swirls matching the faction's dark-matter theming -- large-radius,
  // SLOW-curving swirls, deliberately not tight spirals (the user's own warning: tight spirals
  // read as noise once tiled across a 12,000px+ row). Real population as of this session (15
  // nodes, post D-7 override reclassification) -- no longer the zero-population hypothetical it
  // was when the "dots" placeholder was first written.
  Compound: { base: 0x2f137f, accents: [0x6a3fd1], accentAlpha: 0.22, style: "swirls" },
  // Sirenalia: ported DIRECTLY from v1's own `drawWaves` (js/render.js), at the user's explicit
  // request, after three earlier attempts (a procedural "several shades" placeholder among them)
  // were tried and rejected -- see main.ts's `drawFactionRowPattern` "waves" branch for the full
  // port writeup. v1 uses ONE accent colour across its 4 sine-filled layers, alpha-only
  // progression (0.05->0.09) -- NOT multiple hues, correcting this entry's own earlier "distinct
  // pink/purple shade" description. `accents[0]` is the single wave colour; kept the highest
  // accentAlpha of the five factions, deliberately, per S-1's "high-contrast" text (v1's own
  // absolute per-layer alphas are scaled by this value at the call site).
  Sirenalia: { base: 0xb0338c, accents: [0xb0338c], accentAlpha: 0.30, style: "waves" },
  // Katzenartig Imperium: gold chevrons/pinstripes on deep blue, military-heraldic in feel -- the
  // ONE faction the user had no specific in-game reference for ("no specific reference... flagged
  // as provisional and refinable"). This is Claude's own inference from the two already-signed-off
  // hexes (#2E3F98 blue, #CC9429 gold) alone, not a user-described device the way the other four
  // are -- do not treat this entry as settled art; refine it if a real reference ever surfaces.
  "Katzenartig Imperium": { base: 0x2e3f98, accents: [0xcc9429], accentAlpha: 0.20, style: "chevrons" },
};

// D-16/CLAUDE.md's "Colour and pattern" amendment: cards themselves are neutral dark -- colour is
// no longer a per-card fill channel at all (research area and faction both moved to the row axis).
// Outline colour still carries area (unaffected by D-16 -- see CLAUDE.md), applied at the call site
// via AREA_COLORS directly; this pair is only the neutral fill/stroke every card shares.
export const CARD_FILL = 0x1b1e26;
export const CARD_STROKE_NEUTRAL = 0x333844;

// Row header chip: category rows are coloured by their research area; faction rows by the
// faction's own signed-off colour (CRISIS_FACTION_COLORS, unchanged from the palette above).
export function rowChipColorFor(area: string | null, crisisFaction: string | null): number {
  if (crisisFaction) return CRISIS_FACTION_COLORS[crisisFaction] ?? 0x888888;
  return (area ? AREA_COLORS[area] : undefined) ?? 0x888888;
}

// DEFECT 5 fix, found while wiring Aeternum's new burgundy background (this session): the row
// PANEL's own fill/border colour is DISTINCT from the header chip's colour and must NOT reuse
// `rowChipColorFor` -- a faction's flag-identity colour (the chip) and its row's own BACKING tone
// (the panel) are not always the same value. CLAUDE.md already states this for Blokkats
// specifically ("#1C451C, the authentic flag colour, reserved for tier-band/lane backing, not
// node fill" vs. the brighter #2A6B2A used elsewhere) -- but the row panel introduced in the
// previous session's defect-fix pass called `rowChipColorFor` for BOTH the chip and the panel,
// so that distinction existed only in `CRISIS_FACTION_ROW_PATTERNS`'s own `base` field and was
// never actually applied to what the panel draws. Fixed here, not just for Aeternum: every
// faction row's panel now reads its background from its OWN pattern spec's `base`, falling back
// to `CRISIS_FACTION_COLORS` only if a faction has no pattern spec at all (never true today).
export function rowPanelColorFor(area: string | null, crisisFaction: string | null): number {
  if (crisisFaction) return CRISIS_FACTION_ROW_PATTERNS[crisisFaction]?.base ?? CRISIS_FACTION_COLORS[crisisFaction] ?? 0x888888;
  return (area ? AREA_COLORS[area] : undefined) ?? 0x888888;
}

// Row PANEL (defect fix, later session): every one of the 18 rows -- category and faction alike
// -- gets the same tinted-panel/border/rounded-corner treatment, differing only in colour (via
// `rowChipColorFor` above, reused directly so panel and chip never disagree) and, for faction
// rows, an additional pattern accent. Values named once here so no call site hardcodes them.
export const ROW_PANEL_RADIUS = 10;
export const ROW_PANEL_FILL_ALPHA = 0.10;
export const ROW_PANEL_BORDER_ALPHA = 0.40;
export const ROW_PANEL_BORDER_WIDTH = 1.5;

// Per-(row, band)-cell tier label (defect fix: replaces the removed sticky/pinned header
// mechanism -- v1 repeats a small, subdued tier label above each row's own band cell instead of
// one floating global header; see main.ts and spec/S-03-tier-differentiation.md's amended
// acceptance criterion). Deliberately muted -- this is wayfinding chrome, not content.
export const CELL_TIER_LABEL_COLOR = 0x8b95a5;

// DEFECT 2 (this session): tier-band alternating background tint. Tier bands were previously
// distinguished only by their (per-cell) labels -- no visual separation existed between one
// band's card column and the next, so the canvas read as one undifferentiated field. Drawn
// FIRST (beneath the row panels, `main.ts`'s draw order), so row/faction colour still dominates
// on top of it -- these are two neutral, non-hued overlays (white lightens, black darkens the
// dark #111318 canvas background) alternating by band index, deliberately carrying no hue of
// their own so they never compete with an area colour or a faction pattern, only read as faint
// vertical banding. Tinted rect spans exactly each band's own card-slot width (excluding
// INTER_BAND_GUTTER), so the untinted gutter itself doubles as the boundary line between bands.
export const TIER_BAND_TINT_COLOR_EVEN = 0xffffff;
export const TIER_BAND_TINT_ALPHA_EVEN = 0.035;
export const TIER_BAND_TINT_COLOR_ODD = 0x000000;
export const TIER_BAND_TINT_ALPHA_ODD = 0.05;

// Edge (connector) styling -- Stage 3 slice 3. spec/P-08-connectors.md specifies connector
// COLOUR follows the tail (depended-upon) technology's area/faction classification, the same
// palette as the node it originates from. This slice deliberately does NOT do that: at 989 edges
// crossing area boundaries constantly, a per-edge tail colour would be ambiguous for cross-area
// edges and would compete visually with the cards it runs beneath -- a scoped simplification for
// this slice, not an oversight, and flagged as a spec deviation (see CLAUDE.md/HANDOFF.md's write-up
// of this slice). One neutral, low-contrast stroke colour for every edge, distinguished only by
// P-08's OTHER composed dimension: line style + opacity by EdgeKind.
//
// DEFECT 3 (an earlier session): brightened toward a light blue-cyan PCB-trace colour (was
// 0x5b6472 slate) on the belief that was v1's own colour. **Corrected this session, checked
// against v1's actual source (github.com/Tempest113/Gigas-Tech-Tree)**: v1's real edge colour is
// its `--line` CSS custom property, `#38363c` (css/*.css:11, consumed as `ctx.strokeStyle = C.line`
// at js/render.js:618) -- a dark, low-contrast GREY, not blue-cyan. The earlier brightening was
// simply wrong about what it was porting. EDGE_COLOR is now v1's real grey; the light blue-cyan is
// kept as HOVER_COLOR below, reserved for a hover/selection state that does not exist yet in this
// client (no hover, no click, no selection -- see CLAUDE.md's "Not in scope" list) -- it must NOT
// be spent on the default edge state, which is why it is a separate, currently-unused export
// rather than deleted. The single-neutral-colour-for-every-kind rule (above) is unchanged.
export const EDGE_COLOR = 0x38363c; // v1's own `--line` grey (css/*.css:11) -- readable but low-contrast against #111318 bg, matching v1's own restrained default-state look
export const EDGE_STROKE_WIDTH = 1.4; // thinner, cleaner trace stroke -- was 2
// Reserved for a future hover/selection state (not implemented -- P-08/S-3 scope, still open).
// This was EDGE_COLOR's value in an earlier session, on the mistaken belief it was v1's default
// edge colour; it is v1's OWN highlighted-lineage stroke colour instead (`C.accent`,
// js/render.js:626, used only while a technology's dependency chain is being traced), which is
// exactly a hover/selection-shaped use, not a default-state one. Do not wire this into the
// default edge draw call -- see the EDGE_COLOR comment above for why.
export const HOVER_COLOR = 0x5cc9e6;

// Hover/selection slice (reconciliation session 3): HOVER_COLOR above is now actually consumed
// (a hovered card's outline and its directly-incident edges). Selection needs two FURTHER
// colours, distinct from HOVER_COLOR and from each other, so a selected node's ANCESTRY
// (technologies required to reach it) reads as visually different from its DEPENDENTS
// (technologies that require it) -- "distinguishably from each other" per this session's own
// instruction. Both are first concrete picks (same unresolved-spec-colour status as every other
// token in this file), chosen to sit clearly apart from HOVER_COLOR/RARE_COLOR/DANGEROUS_COLOR/
// every AREA_COLORS value by eye: ANCESTRY_COLOR a cool violet (things BEHIND/BELOW the
// selection, prerequisite direction), DEPENDENT_COLOR a warm amber-orange (things AHEAD/beyond
// the selection, dependent direction) -- an intentional warm/cool split so the two directions
// read apart even for a colour-blind user relying on hue temperature rather than exact hue.
export const ANCESTRY_COLOR = 0x8a6fd6;
export const DEPENDENT_COLOR = 0xe0932e;
export const SELECTED_COLOR = 0xf2f2f2; // the selected node's OWN outline -- neutral bright white, distinct from both directions

// Empire-profile switching slice (reconciliation session 4): per-profile availability treatment.
// CLAUDE.md: availability is three-state (available/locked/uncertain) NEVER boolean, plus D-10's
// CONFIG_GATED fourth state. "Do not use colour alone if that would collide with the row/faction
// colour system" -- the dim overlay below is a NEUTRAL DARKENING (alpha over the card's own
// fill/outline), not a new hue, so it never competes with the row-axis colour channel; the actual
// state identity is carried by a distinct glyph badge (a non-colour channel), matching this
// project's own established "colour is never the sole carrier" discipline (S-1) applied to a
// fourth classification the original S-1 write-up never anticipated. `available` gets NEITHER
// treatment -- the common case stays exactly as today's neutral render.
export const AVAILABILITY_DIM_COLOR = 0x000000; // pure darken, no hue
export const LOCKED_DIM_ALPHA = 0.55;
export const UNCERTAIN_DIM_ALPHA = 0.3;
export const CONFIG_GATED_DIM_ALPHA = 0.45;
export const LOCKED_BADGE_COLOR = 0xb0433d; // muted red -- "cannot reach this"
export const UNCERTAIN_BADGE_COLOR = 0x9a8b5a; // muted amber -- "might reach this"
export const CONFIG_GATED_BADGE_COLOR = 0x4a7a9e; // muted blue -- "a game OPTION, not your empire, is the obstacle"
// WEIGHT_GATED fifth state (D-10's Extension, a later session): distinct hue from every other
// badge colour (a muted violet, between CONFIG_GATED's blue and ANCESTRY_COLOR's violet but not
// equal to either) -- "not currently drawn, but eventually reachable," the lightest dim of the
// four non-available states since this is the LEAST restrictive one (unlike locked/config-gated,
// the research-path builder treats it as a viable step, P-12.9's Extension).
export const WEIGHT_GATED_DIM_ALPHA = 0.25;
export const WEIGHT_GATED_BADGE_COLOR = 0x7a5a9e; // muted violet -- "not offered right now, but not impossible"

// Search slice (reconciliation session 4): matches highlight IN PLACE on the canvas -- never a
// filter, per this session's own instruction ("hiding nodes breaks the reading of prerequisite
// chains"). A colour distinct from every other outline/highlight colour in this file.
export const SEARCH_MATCH_COLOR = 0x4ade80;

// DEFECT 3 (this session): P-08's "rounded corners" acceptance criterion was skipped as a scoped
// simplification in the original edge slice (sharp H-V-H joins) -- closed now. Corner radius is
// applied at RENDER time only (`main.ts`'s `roundPolylineCorners`), never by re-routing -- the
// underlying 4-point H-V-H polylines from `edge-polylines.f32` (server-computed) are unchanged;
// only how they're TRACED changes, per spec/P-08-connectors.md's own "quadratic/arc segments at
// each vertex rather than stroke-linejoin, so the radius is zoom-stable" guidance.
export const EDGE_CORNER_RADIUS = 12;

// P-08's acceptance criteria: "potential-gate edges are dashed, at reduced opacity" and
// "alternative edges are dotted, at further reduced opacity" -- prerequisite is solid at full
// opacity, the most prominent since it carries the graph's main structure. `dash` is
// [dashLengthPx, gapLengthPx] in WORLD units (drawn inside the world container, so it scales with
// zoom like everything else); `null` means an unbroken stroke.
export const EDGE_STYLE: Record<"prerequisite" | "potential-gate" | "alternative", { alpha: number; dash: [number, number] | null }> = {
  prerequisite: { alpha: 0.9, dash: null },
  "potential-gate": { alpha: 0.55, dash: [12, 7] },
  alternative: { alpha: 0.4, dash: [2, 5] },
};

export const EDGE_ARROW_LENGTH = 14;
export const EDGE_ARROW_HALF_WIDTH = 5;
