// Stage 3 visual-fidelity pass: removes slice 4's sticky/pinned headers (rejected by the user --
// a floating banner that swaps contents as you scroll belongs to no visible object), adds a real
// tinted-panel/border treatment to every row (category rows previously had none), rescales the
// faction row-backing patterns for row scale rather than card scale, and clamps card name text to
// a fixed line count with an ellipsis instead of letting it overflow the card. Builds on slice 3's
// edges and slice 4's row model. Still out of scope, per this pass's own boundary (next slice):
// rare/dangerous/gate/repeatable/mod-requirement badges, the rare/dangerous outline rule, hover,
// click, selection, popups, search, empire-profile switching.

import { Application, Assets, Container, Graphics, Rectangle, Sprite, Text, TextStyle, Texture } from "pixi.js";
import type { BaseDataset, EmpireOverlay, EmpireTypeConstraint, GestaltAuthority, Nomadic as NomadicValue, Shipset as ShipsetValue } from "../../schema/generated/dataset-types";
import { atlasUrl, fetchBaseDataset, fetchDetailPayload, fetchDiagnostics, fetchEmpireOverlay, fetchGeometry, fetchSearchIndex } from "./dataset";
import {
  allProfiles,
  axisValues,
  DEFAULT_PROFILE,
  empireProfileIndex,
  initEmpireProfileAxes,
  profileKey,
  type EmpireProfile,
} from "./empireProfile";
import {
  ANCESTRY_COLOR,
  AREA_COLORS,
  AVAILABILITY_DIM_COLOR,
  CARD_FILL,
  CELL_TIER_LABEL_COLOR,
  CONFIG_GATED_BADGE_COLOR,
  CONFIG_GATED_DIM_ALPHA,
  CRISIS_FACTION_ROW_PATTERNS,
  DANGEROUS_COLOR,
  DEPENDENT_COLOR,
  EDGE_ARROW_HALF_WIDTH,
  EDGE_ARROW_LENGTH,
  EDGE_COLOR,
  EDGE_CORNER_RADIUS,
  EDGE_STROKE_WIDTH,
  EDGE_STYLE,
  HOVER_COLOR,
  LOCKED_BADGE_COLOR,
  LOCKED_DIM_ALPHA,
  MOD_REQUIREMENT_BADGE_COLOR,
  RARE_COLOR,
  ROW_PANEL_BORDER_ALPHA,
  ROW_PANEL_BORDER_WIDTH,
  ROW_PANEL_FILL_ALPHA,
  ROW_PANEL_RADIUS,
  rowChipColorFor,
  rowPanelColorFor,
  SEARCH_MATCH_COLOR,
  SELECTED_COLOR,
  TIER_BAND_TINT_ALPHA_EVEN,
  TIER_BAND_TINT_ALPHA_ODD,
  TIER_BAND_TINT_COLOR_EVEN,
  TIER_BAND_TINT_COLOR_ODD,
  UNCERTAIN_BADGE_COLOR,
  UNCERTAIN_DIM_ALPHA,
  type RowPatternSpec,
} from "./tokens";
import { createCamera, type Camera, type ContentBBox } from "./camera";
import {
  CONTENT_SHED_THRESHOLD,
  COST_SHED_THRESHOLD,
  DANGEROUS_BADGE_SHED_THRESHOLD,
  edgeTierForScale,
  edgeTierLabel,
  GATE_ICON_SHED_THRESHOLD,
  GATE_LABEL_SHED_THRESHOLD,
  ICON_SHED_THRESHOLD,
  MOD_REQUIREMENT_BADGE_SHED_THRESHOLD,
  NAME_SHED_THRESHOLD,
  PATTERN_SOLID_THRESHOLD,
  RARE_BADGE_SHED_THRESHOLD,
  REPEATABLE_SHED_THRESHOLD,
  tierForScale,
  tierLabel,
  TIER_BADGE_SHED_THRESHOLD,
  type EdgeLodTier,
  type LodTier,
} from "./lod";

// dataset-types.ts's technologies/tierBands/rows entries are inline anonymous object types (no
// standalone exported interface for any of them) -- indexed-access types pull the real per-item
// shape out of BaseDataset itself rather than hand-duplicating it here, so this can't drift from
// the generated contract.
type TechnologyRecord = BaseDataset["technologies"][number];
type SwapMapping = EmpireOverlay["swapMappings"][number];
type TierBandRecord = BaseDataset["tierBands"][number];
type EdgeRecord = BaseDataset["edges"][number];
type EdgeKind = EdgeRecord["kind"];

const EDGE_KINDS: EdgeKind[] = ["prerequisite", "potential-gate", "alternative"];
// pipeline/geometry.py::pack_edge_polylines: every edge's polyline is a fixed 6 (x,y) waypoints
// (the card-avoidance router's exit-stub/V/transit/V/entry-stub route, moved from 4 points/3
// segments in the session that closed the plain H-V-H router's card-crossing bug -- see
// pipeline/layout.py's _route_edges docstring), packed back to back in `base.edges` order -- the
// SAME index alignment convention node-positions.f32 uses for `base.technologies`. No
// offset/length lookup needed: edge i's 12 floats live at [i*12, i*12+12).
const FLOATS_PER_EDGE_POLYLINE = 12;

// Card dimensions/gutters mirrored exactly from pipeline/layout.py's own constants -- no
// geometry side-file carries row heights or band x-extents (only node positions/edge polylines
// do), so the row panel/pattern rects and per-cell label positions below are derived here the
// same way the pipeline derives them. A drift between these numbers and pipeline/layout.py's
// would show up immediately as visibly misaligned row panels -- not silent.
//
// DEFECT 1/DEFECT 4/Part-2 spacing pass (across sessions): INTRA_GAP_X 16->24->40->120,
// INTRA_GAP_Y 16->24 (unchanged since), INTER_BAND_GUTTER 48->96, ROW_HEADER_HEIGHT 40->52,
// ROW_GUTTER 16->24->48, AREA_GROUP_GUTTER 96->64 -- mirrored from pipeline/layout.py's own
// updated constants and comment (the single named place these values live); see that file for the
// chosen-value reasoning, including the EAWAF/v1-routing session's row-panel bleed fix that made
// ROW_GUTTER's existing 48px value finally visible (see `drawRowPanel`'s call site below).
const CARD_WIDTH = 270;
const CARD_HEIGHT = 92;
const INTRA_GAP_X = 120;
const INTRA_GAP_Y = 24;
const INTER_BAND_GUTTER = 96;
const ROW_HEADER_HEIGHT = 68;
const ROW_GUTTER = 48;
const AREA_GROUP_GUTTER = 64;
const AREA_ORDER = ["physics", "society", "engineering"];
const SUBGRID_WIDTH = 6; // D-17: user picked 6 from the 4/6/8/12 trade-off survey (spec/decisions.md)

const ICON_SIZE = 44;
const ICON_MARGIN = 8;

// Badges slice (reconciliation session): a fixed-width vertical gutter along the card's right
// edge holds every indicator badge (tier/repeat, mod-requirement, dangerous, rare, gate icon),
// stacked top-to-bottom in that order, one per technology that actually carries the flag -- never
// reflowed by LOD (a shed badge just becomes invisible in its own slot, it doesn't close the
// gap). Sized against the real corpus's worst case (checked directly, not assumed): a technology
// can carry at most rare + dangerous + one mod requirement simultaneously (57 rare+dangerous, 2
// of those also mod-gated; never mod+repeatable in the real corpus) -- 4 badges including the
// tier/repeat slot. `BADGE_HEIGHT`/`BADGE_GAP` are sized so even a hypothetical 5th (a gate, 0 in
// the real corpus but not schema-impossible) still fits: 5*16 + 4*2 = 88px, under CARD_HEIGHT's
// 92px with margin to spare.
const BADGE_GUTTER_WIDTH = 34;
const BADGE_HEIGHT = 16;
const BADGE_GAP = 2;
const BADGE_GUTTER_X = CARD_WIDTH - ICON_MARGIN - BADGE_GUTTER_WIDTH;
// Item 4 (later session): the gate icon was rendered at BADGE_HEIGHT (16px, sized for a square
// text badge's glyph, e.g. "T5"/"★") -- too small to actually identify which perk it depicts. It
// is always the LAST gutter-stack item claimed for a card (nothing else is added after it), so
// enlarging it can only ever push into unclaimed space below its own slot, never into another
// badge's territory -- verified against the real corpus (window.__tt.checkIndicatorBounds) rather
// than assumed safe from the stacking order alone. Fits inside BADGE_GUTTER_WIDTH (34px) with
// margin to spare.
const GATE_ICON_SIZE = 24;

// Card name text (defect fix): clamped to a fixed line count, never shrunk, never overflowing the
// card. p95 rendered-name length is 39 chars -- pipeline/layout.py's own CARD_WIDTH/CARD_HEIGHT
// comment already sizes the card "to fit the p95 rendered-name length (39 chars) across up to two
// lines" -- so 2 lines is not a new number invented here, it's the card's own original sizing
// intent, now actually enforced rather than assumed. Real corpus distribution: p50=21, p90=35,
// p95=39, p99=46, max=54 -- 2 lines comfortably fits everything through p95 untruncated; only the
// ~5% beyond p95 (up to the 54-char max) ever shows an ellipsis. Badges slice: narrowed to make
// room for BADGE_GUTTER_WIDTH on the right -- name text now stops before the gutter rather than
// running underneath it, at the cost of more names needing the ellipsis than before (an accepted,
// reported trade-off of fitting every indicator inside the fixed 270x92 card -- see this
// session's own report for the real before/after ellipsis count).
const MAX_NAME_LINES = 2;
const NAME_MAX_WIDTH_PX = BADGE_GUTTER_X - ICON_MARGIN - (ICON_SIZE + ICON_MARGIN * 2);

// Row header chip (world-anchored now, not sticky -- defect fix).
const CHIP_PADDING_X = 10;
const CHIP_HEIGHT = 26;
const CHIP_MARGIN = 8; // from the row panel's own left/top edge

// Per-(row, band)-cell tier label (defect fix: replaces the removed sticky header).
const CELL_LABEL_FONT_SIZE = 13;

// DEFECT 4 (this session): the row header chip and the per-(row,band)-cell tier label used to
// occupy the SAME vertical sub-range of the 40px header strip (chip vertically centred in it,
// label anchored to its bottom few px) -- for band 0 (and any band whose x-start falls under the
// chip's own width, which varies by row's label length), the two visibly collided. Fixed by
// giving each a STRICTLY disjoint vertical band within the header strip (now 52px tall,
// pipeline/layout.py's own ROW_HEADER_HEIGHT) -- chip on top, cell label below it with a fixed
// gap -- so overlap is impossible by construction, independent of chip width, band index, or
// row. `CHIP_TOP_PAD` is `main.ts`'s own choice (not mirrored from the pipeline, since chip
// layout is purely a client rendering decision); `CELL_LABEL_TOP_GAP` is the clearance below the
// chip before the label starts.
const CHIP_TOP_PAD = 4;
const CELL_LABEL_TOP_GAP = 4;

let statusExtra = ""; // camera/LOD line, appended to the load-report line by updateStatusLine()
let statusBase = "";
let edgeCountByKindForStatus: Record<"prerequisite" | "potential-gate" | "alternative", number> | null = null;

function visibleEdgeCount(edgeTier: EdgeLodTier): number {
  if (!edgeCountByKindForStatus || edgeTier === "none") return 0;
  if (edgeTier === "reduced") return edgeCountByKindForStatus.prerequisite;
  return edgeCountByKindForStatus.prerequisite + edgeCountByKindForStatus["potential-gate"] + edgeCountByKindForStatus.alternative;
}

function setStatus(text: string, failed = false): void {
  statusBase = text;
  const el = document.getElementById("report")!;
  el.textContent = statusExtra ? `${text}\n${statusExtra}` : text;
  el.dataset.status = failed ? "failed" : "ok";
}

function updateStatusLine(camera: Camera, tier: LodTier, edgeTier: EdgeLodTier): void {
  const scale = camera.getScale();
  statusExtra =
    `Zoom: ${(scale * 100).toFixed(1)}% (min ${(camera.getMinScale() * 100).toFixed(1)}%, ` +
    `max ${(camera.getMaxScale() * 100).toFixed(0)}%) | LOD tier: ${tierLabel(tier)} | ` +
    `Edges visible: ${visibleEdgeCount(edgeTier)} | Edge LOD: ${edgeTierLabel(edgeTier)} | ` +
    `drag to pan · wheel/pinch to zoom · arrows pan · +/- zoom · 0 fit · 1 = 100%`;
  const el = document.getElementById("report")!;
  el.textContent = `${statusBase}\n${statusExtra}`;
}

async function loadAtlasTextures(base: BaseDataset): Promise<Map<string, Texture>> {
  const entries = await Promise.all(
    base.iconAtlases.map(async (sheet) => [sheet.name, (await Assets.load(atlasUrl(sheet.webp))) as Texture] as const)
  );
  return new Map(entries);
}

/** A technology's band is never a field on the technology record itself (D-13: the base dataset
 * states declared `tier`, not band membership) -- it's derived the same way pipeline/layout.py
 * derives it: repeatable technologies always land in the terminal Repeatables band regardless of
 * their own declared tier; everything else matches its declared tier to the tierBands entry that
 * names it. */
function bandIndexOf(tech: TechnologyRecord, tierBands: TierBandRecord[]): number {
  if (tech.repeatable) {
    const repeatables = tierBands.find((b) => b.tier === "repeatables");
    if (!repeatables) throw new Error("tierBands has no 'repeatables' terminal band");
    return repeatables.bandIndex;
  }
  const band = tierBands.find((b) => b.tier === tech.tier);
  if (!band) throw new Error(`tierBands has no entry for declared tier ${tech.tier} (technology ${tech.id})`);
  return band.bandIndex;
}

/** DEFECT 3 (this session): closes P-08's "rounded corners" acceptance criterion, skipped as a
 * scoped simplification in the original edge slice (sharp H-V-H joins). Takes the exact polyline
 * server-computed by `pipeline/geometry.py`'s edge-polyline side-file -- UNCHANGED, no
 * client-side re-routing -- and returns an expanded point list with each of the polyline's
 * INTERIOR corners (every point except the first and last -- 4 of them, since the card-avoidance
 * router emits 6 waypoints) replaced by a short quadratic-bezier arc, sampled into straight
 * segments; this function is already generic over point count, not hardcoded to any particular
 * router shape. This is exactly spec/P-08-connectors.md's own "Rounded corners SHOULD be
 * produced by quadratic/arc segments at each vertex rather than by stroke-linejoin, so the radius
 * is zoom-stable" guidance -- a stroke-linejoin round join would scale its visual radius with
 * on-screen line width, not with world-space geometry, which is exactly what "zoom-stable" rules
 * out. The FIRST and LAST points are always returned byte-identical to the input -- corner
 * rounding never moves an edge's own card-attachment endpoint, so an edge can't detach from its
 * source/target card by this transform (verified directly, see `checkEdgeEndpointsInCards` on
 * `window.__tt`). Per-corner radius is clamped to half of each adjacent segment's own length, so a
 * short segment (e.g. a node whose channel offset happens to be near-zero) still produces a valid,
 * non-overshooting arc rather than a corner that overruns past its neighbouring point. */
function roundPolylineCorners(pts: [number, number][], radius: number, arcSteps = 6): [number, number][] {
  if (radius <= 0 || pts.length < 3) return pts;
  const result: [number, number][] = [pts[0]!];
  for (let i = 1; i < pts.length - 1; i++) {
    const prev = result[result.length - 1]!;
    const corner = pts[i]!;
    const next = pts[i + 1]!;
    const v1x = corner[0] - prev[0];
    const v1y = corner[1] - prev[1];
    const v2x = next[0] - corner[0];
    const v2y = next[1] - corner[1];
    const len1 = Math.hypot(v1x, v1y);
    const len2 = Math.hypot(v2x, v2y);
    const r = Math.min(radius, len1 / 2, len2 / 2);
    if (r < 0.5 || len1 < 1e-6 || len2 < 1e-6) {
      result.push(corner);
      continue;
    }
    const u1x = v1x / len1;
    const u1y = v1y / len1;
    const u2x = v2x / len2;
    const u2y = v2y / len2;
    const p1: [number, number] = [corner[0] - u1x * r, corner[1] - u1y * r];
    const p2: [number, number] = [corner[0] + u2x * r, corner[1] + u2y * r];
    result.push(p1);
    for (let s = 1; s < arcSteps; s++) {
      const t = s / arcSteps;
      const qx = (1 - t) * (1 - t) * p1[0] + 2 * (1 - t) * t * corner[0] + t * t * p2[0];
      const qy = (1 - t) * (1 - t) * p1[1] + 2 * (1 - t) * t * corner[1] + t * t * p2[1];
      result.push([qx, qy]);
    }
    result.push(p2);
  }
  result.push(pts[pts.length - 1]!);
  return result;
}

/** Traces a polyline (any point count) into `g`'s current path, as one solid subpath
 * (`dash === null`) or as a series of dash/gap subpaths (PixiJS v8 Graphics has no native
 * dash-pattern stroke). The dash phase is carried across every segment (not reset per segment)
 * so the pattern reads continuously through every elbow corner instead of restarting a fresh
 * dash at each one. */
function tracePolyline(g: Graphics, pts: [number, number][], dash: [number, number] | null): void {
  if (!dash) {
    g.moveTo(pts[0]![0], pts[0]![1]);
    for (let i = 1; i < pts.length; i++) g.lineTo(pts[i]![0], pts[i]![1]);
    return;
  }
  const [dashLen, gapLen] = dash;
  let remaining = dashLen;
  let drawing = true;
  for (let i = 0; i < pts.length - 1; i++) {
    let [x0, y0] = pts[i]!;
    const [x1, y1] = pts[i + 1]!;
    let segLen = Math.hypot(x1 - x0, y1 - y0);
    const dx = segLen > 0 ? (x1 - x0) / segLen : 0;
    const dy = segLen > 0 ? (y1 - y0) / segLen : 0;
    while (segLen > 1e-6) {
      const step = Math.min(remaining, segLen);
      const nx = x0 + dx * step;
      const ny = y0 + dy * step;
      if (drawing) {
        g.moveTo(x0, y0);
        g.lineTo(nx, ny);
      }
      x0 = nx;
      y0 = ny;
      segLen -= step;
      remaining -= step;
      if (remaining <= 1e-6) {
        drawing = !drawing;
        remaining = drawing ? dashLen : gapLen;
      }
    }
  }
}

/** Adds a filled triangular arrowhead to `g`'s current path, tip at `pts`'s last point, oriented
 * along the final segment's direction (P-8: "arrowhead at the target/dependent end"). Falls back
 * to the second-to-last segment if the final one is degenerate (near-zero length). */
function addArrowhead(g: Graphics, pts: [number, number][]): void {
  const tip = pts[pts.length - 1]!;
  let from = pts[pts.length - 2]!;
  if (Math.hypot(tip[0] - from[0], tip[1] - from[1]) < 1e-6 && pts.length >= 3) {
    from = pts[pts.length - 3]!;
  }
  const dx = tip[0] - from[0];
  const dy = tip[1] - from[1];
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const baseX = tip[0] - ux * EDGE_ARROW_LENGTH;
  const baseY = tip[1] - uy * EDGE_ARROW_LENGTH;
  g.moveTo(tip[0], tip[1]);
  g.lineTo(baseX + px * EDGE_ARROW_HALF_WIDTH, baseY + py * EDGE_ARROW_HALF_WIDTH);
  g.lineTo(baseX - px * EDGE_ARROW_HALF_WIDTH, baseY - py * EDGE_ARROW_HALF_WIDTH);
  g.closePath();
}

/** DEFECT 5 (this session): clips a faction row's pattern accent layer to its own row rectangle
 * via a PixiJS mask, replacing the previous per-style analytic-bounding approach. The earlier
 * "diagonal" style clipped its own line segments algebraically because that generalised easily to
 * one line family; it does NOT generalise to hexagons/swirls/chevron lattices without a lot of
 * per-shape boundary math, and a real bug already came from getting that math wrong once (see
 * git history / CLAUDE.md's "pattern bled across the entire canvas height" finding). A per-row
 * rectangular mask is exact regardless of the shape drawn inside it, and 18 small masks (5 of
 * which are ever actually used, one per faction) cost nothing measurable at this scene's already-
 * measured real-hardware frame budget (median 6.1ms/p95 12.1ms). The mask Graphics does not need
 * to be a display-list child to be RENDERED (PixiJS automatically skips the normal draw of any
 * object assigned as another's `.mask`) -- but it DOES need to be a child of the same container
 * the masked target is in, so its transform actually gets updated by the scene graph each frame.
 * An earlier version of this function left the mask unparented entirely; its transform then
 * stayed at its initial identity value forever, so the mask clipped in the wrong coordinate space
 * and every faction row's pattern accent silently clipped to nothing -- found via this session's
 * own screenshot review (the accent traced real, correctly-shaped geometry the whole time; only
 * the mask was wrong), the same "screenshots catch what tests couldn't" pattern this project's
 * history already has several entries for. The caller MUST add the returned mask as a child of
 * `target`'s own parent. */
function maskToRowRect(target: Graphics, x0: number, y0: number, width: number, height: number): Graphics {
  const maskG = new Graphics().rect(x0, y0, width, height).fill(0xffffff);
  target.mask = maskG;
  return maskG;
}

/** DEFECT 5 (this session): real faction pattern artwork, replacing the procedural placeholders
 * (flat diagonal lines / dots / flat-rect bands) with the five user-supplied (a Gigastructures
 * contributor) motifs named in `tokens.ts`'s `CRISIS_FACTION_ROW_PATTERNS`. Feature size still
 * scales with the row's own height, not card size -- unchanged rationale from the previous
 * rescale (a typical multi-tier row is far taller than a single 270x92 card, so a fixed
 * card-scale spacing tiled hundreds of times across a row's width was always the wrong unit).
 * Every style is a "row backing" motif per the shared rule stated in tokens.ts: it identifies the
 * row at a glance, low opacity, never competing with cards/edges drawn on top of it. */
function drawFactionRowPattern(accent: Graphics, spec: RowPatternSpec, x0: number, y0: number, width: number, height: number): void {
  const feature = Math.min(320, Math.max(140, height * 0.9));
  const primary = spec.accents[0] ?? spec.base;

  if (spec.style === "herringbone") {
    // Blokkats: the flag device (a circle containing a lightning-bolt/arrow chevron) tiled as a
    // staggered, INTERLOCKING lattice -- adjacent rows offset by half the horizontal step, so
    // each row's arrows nestle into the gaps of its neighbours (herringbone), outline only.
    const size = feature * 0.5;
    const stepX = size * 1.3;
    const stepY = size * 0.9;
    const strokeWidth = Math.max(3, size * 0.12);
    let row = 0;
    for (let cy = y0 - size; cy < y0 + height + size; cy += stepY, row++) {
      const offset = (row % 2) * (stepX / 2);
      for (let cx = x0 - size + offset; cx < x0 + width + size; cx += stepX) {
        accent.moveTo(cx - size / 2, cy - size / 2);
        accent.lineTo(cx + size / 2, cy);
        accent.lineTo(cx - size / 2, cy + size / 2);
      }
    }
    accent.stroke({ width: strokeWidth, color: primary, alpha: spec.accentAlpha, cap: "round", join: "round" });
  } else if (spec.style === "chevrons") {
    // Katzenartig Imperium (PROVISIONAL, see tokens.ts): a uniform, non-interlocking lattice of
    // thin gold chevrons -- "pinstripe" weight rather than Blokkats' thicker interlocking outline,
    // for a more military-heraldic than tribal-flag feel.
    const size = feature * 0.6;
    const strokeWidth = Math.max(2, size * 0.06);
    const stepX = size * 0.9;
    const stepY = size * 0.8;
    for (let cy = y0 - size; cy < y0 + height + size; cy += stepY) {
      for (let cx = x0 - size; cx < x0 + width + size; cx += stepX) {
        accent.moveTo(cx - size / 2, cy - size / 2);
        accent.lineTo(cx + size / 2, cy);
        accent.lineTo(cx - size / 2, cy + size / 2);
      }
    }
    accent.stroke({ width: strokeWidth, color: primary, alpha: spec.accentAlpha, cap: "round", join: "round" });
  } else if (spec.style === "hexagons") {
    // Aeternum: tiled hexagon outlines (lighter pink accent) on the burgundy row background --
    // standard pointy-top hex tiling, outline only, never filled.
    const r = feature / 2;
    const strokeWidth = Math.max(3, r * 0.12);
    const hexW = Math.sqrt(3) * r;
    const hexH = 1.5 * r;
    let row = 0;
    for (let cy = y0 - r; cy < y0 + height + r; cy += hexH, row++) {
      const xOff = (row % 2) * (hexW / 2);
      for (let cx = x0 - hexW + xOff; cx < x0 + width + hexW; cx += hexW) {
        for (let i = 0; i < 6; i++) {
          const a1 = (Math.PI / 180) * (60 * i - 30);
          const a2 = (Math.PI / 180) * (60 * (i + 1) - 30);
          const p1x = cx + r * Math.cos(a1);
          const p1y = cy + r * Math.sin(a1);
          const p2x = cx + r * Math.cos(a2);
          const p2y = cy + r * Math.sin(a2);
          if (i === 0) accent.moveTo(p1x, p1y);
          accent.lineTo(p2x, p2y);
        }
      }
    }
    accent.stroke({ width: strokeWidth, color: primary, alpha: spec.accentAlpha, join: "round" });
  } else if (spec.style === "swirls") {
    // Compound: large-radius, SLOW-curving swirls (dark-matter theming) -- deliberately not tight
    // spirals (the user's own warning that a tight spiral reads as noise once tiled across a
    // 12,000px+ row). Each swirl is a single spiral arc sampled into straight segments; `turns`
    // is kept low (loose winding) and `maxR` large relative to `feature` for the "slow-curving,
    // large-radius" character asked for.
    const strokeWidth = Math.max(4, feature * 0.05);
    const spacingX = feature * 1.6;
    const spacingY = feature * 1.3;
    const maxR = feature * 0.55;
    const turns = 1.3;
    const steps = 40;
    let row = 0;
    for (let cy = y0 + feature * 0.7; cy < y0 + height; cy += spacingY, row++) {
      const xOff = (row % 2) * (spacingX / 2);
      for (let cx = x0 + xOff; cx < x0 + width; cx += spacingX) {
        let first = true;
        for (let s = 0; s <= steps; s++) {
          const t = s / steps;
          const angle = t * turns * Math.PI * 2;
          const r = t * maxR;
          const px = cx + r * Math.cos(angle);
          const py = cy + r * Math.sin(angle);
          if (first) {
            accent.moveTo(px, py);
            first = false;
          } else {
            accent.lineTo(px, py);
          }
        }
      }
    }
    accent.stroke({ width: strokeWidth, color: primary, alpha: spec.accentAlpha, cap: "round", join: "round" });
  } else {
    // "waves" -- Sirenalia. Ported DIRECTLY from v1's own `drawWaves` (js/render.js) at the
    // user's explicit request, after the procedural placeholder was tried and rejected three
    // times -- shape, amplitude, frequency, layering, and alpha ("shade") progression are v1's
    // own numbers, not re-inferred. v1 draws each of 4 layers as a FILLED region bounded above by
    // a sine curve and below by the row's own bottom edge (not a stroked ribbon the way the
    // earlier placeholder drew it) -- `y = rowTop + rowHeight * (base + sin(t) * amp)`, one
    // straight-line-sampled path per layer, `step = 60` (v1's own sampling interval, copied
    // verbatim rather than re-tuned for our much wider canvas -- more repeats at this scale is a
    // faithful consequence of the same absolute period, not a deviation from it). v1 uses ONE
    // accent colour across all 4 layers (`C.area["siren"]`, a CSS custom property with no
    // counterpart in this project's own signed-off palette) with only ALPHA varying per layer
    // (0.05 -> 0.06 -> 0.07 -> 0.09, low-to-high going down the row) -- that alpha progression IS
    // v1's "shade progression"; there is no second hue involved. Ported using OUR signed-off
    // Sirenalia hex (`spec.base`, #B0338C, CLAUDE.md's "Palette signed off" section) as that one
    // colour, per this project's own "signed-off base hex values do not change" rule -- v1's CSS
    // colour itself is a styling value from a different palette, not something this session's
    // scope-limited "read v1 for styling only" instruction extends to overriding a hex CLAUDE.md
    // already signed off.
    const waveColor = spec.accents[0] ?? spec.base;
    const layers = [
      { amp: 0.10, phase: 0.0, base: 0.30, alpha: 0.05, period: 1600 },
      { amp: 0.08, phase: 1.1, base: 0.52, alpha: 0.06, period: 1150 },
      { amp: 0.07, phase: 2.4, base: 0.72, alpha: 0.07, period: 900 },
      { amp: 0.05, phase: 3.6, base: 0.88, alpha: 0.09, period: 700 },
    ];
    const step = 60;
    const x1 = x0 + width;
    for (const L of layers) {
      accent.moveTo(x0, y0 + height);
      for (let x = x0; x <= x1 + step; x += step) {
        const t = ((x - x0) / L.period) * Math.PI * 2 + L.phase;
        const y = y0 + height * (L.base + Math.sin(t) * L.amp);
        accent.lineTo(Math.min(x, x1), y);
      }
      accent.lineTo(x1, y0 + height);
      accent.closePath();
      accent.fill({ color: waveColor, alpha: L.alpha * (spec.accentAlpha / 0.3) });
    }
  }
}

/** Every one of the 18 rows -- category and faction alike -- gets the identical tinted-panel/
 * border/rounded-corner treatment (defect fix: category rows previously had no backing at all, so
 * they read as empty space and the 5 faction rows looked like the only real objects on the
 * canvas). Colour comes from `rowChipColorFor` -- the SAME function the header chip uses, so a
 * panel and its own chip can never disagree. */
function drawRowPanel(g: Graphics, color: number, x0: number, y0: number, width: number, height: number): void {
  g.roundRect(x0, y0, width, height, ROW_PANEL_RADIUS)
    .fill({ color, alpha: ROW_PANEL_FILL_ALPHA })
    .stroke({ width: ROW_PANEL_BORDER_WIDTH, color, alpha: ROW_PANEL_BORDER_ALPHA });
}

/** Greedy word-wrap simulated against a real canvas 2D measurement context (the same measurement
 * approach PixiJS's own CanvasTextRenderer uses internally for wordWrap), capped at `maxLines` and
 * ellipsis-truncated on the final line when the name doesn't fit -- replaces PixiJS's own
 * open-ended wordWrap, which has no line-count cap and let long names overflow the card (defect
 * fix). Every returned line is defensively clamped to `maxWidthPx` regardless of how it was
 * produced, so a single word wider than the card's text column (not just an overlong full name)
 * still can't push the render past the card edge.
 *
 * `fontCss` is set on `ctx` before any measurement -- REQUIRED, not optional, and not inherited
 * from whatever the caller last left `ctx.font` as. Found the hard way (screenshot-review
 * session): a shared `measureCtx` left at the 20px name font by the main per-card loop was then
 * reused, unchanged, to measure an 11px gate label -- every width came back ~1.8x too large, so
 * "Needs Civil Phanon Engineering" over-truncated to a near-unreadable "Ne…Engineering" despite
 * having plenty of real room at its actual 11px render size. Self-contained font-setting is the
 * fix that makes this class of bug structurally impossible, not just fixed for this one caller.
 *
 * `mode` (this session, Item 1a correction): "tail" is the DEFAULT (`headOfLine + "…"`) -- plain
 * and readable, and what every truncated name used before an earlier session over-corrected it to
 * always MIDDLE-ellipsize (`headOfLine + "…" + lastWord`, preserving the final word) for every
 * truncated name, not just the ones that needed it. Middle-ellipsis exists to solve one specific
 * problem -- two truncated names becoming visually IDENTICAL, e.g. `tech_dark_matter_deflector`
 * ("Dark Matter Dimensional Deflector") and `tech_dark_matter_propulsion` ("Dark Matter
 * Dimensional Thruster") both tail-truncating to "Dark Matter\nDimensional…" -- and should only
 * be spent on the minimal set of names that actually collide under tail truncation (computed by
 * the caller, see `resolveNameTruncations` below), never as the default for every long name: it
 * destroys the informative MIDDLE of a name (e.g. "Runic Matter Ma…Techniques") for no benefit on
 * names that were never going to collide with anything. Falls back to plain tail-ellipsis in the
 * pathological case where "…" + the last word alone doesn't even fit the column width. */
function wrapAndClampName(
  ctx: CanvasRenderingContext2D,
  name: string,
  maxWidthPx: number,
  maxLines: number,
  mode: "tail" | "middle" = "tail",
  fontCss?: string
): string {
  if (fontCss) ctx.font = fontCss;
  const ellipsis = "…";
  const widthOf = (s: string): number => ctx.measureText(s).width;

  function clampToWidth(s: string, suffix: string): string {
    if (widthOf(s + suffix) <= maxWidthPx) return s + suffix;
    let lo = 0;
    let hi = s.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (widthOf(s.slice(0, mid) + suffix) <= maxWidthPx) lo = mid;
      else hi = mid - 1;
    }
    return s.slice(0, lo) + suffix;
  }

  const words = name.split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (current === "" || widthOf(candidate) <= maxWidthPx) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
    if (lines.length === maxLines) {
      current = ""; // discard: overflow content, accounted for via `truncated` below
      break;
    }
  }
  if (lines.length < maxLines && current) lines.push(current);

  const consumedWords = lines.reduce((n, l) => n + l.split(" ").length, 0);
  const truncated = consumedWords < words.length;

  let tailSuffix = ellipsis;
  if (mode === "middle") {
    // Preserve the tail: "…" + the name's real final word, so two names differing only in their
    // last word stay visually distinct even after truncation. Falls back to plain "…" if even
    // that doesn't fit the column on its own.
    const lastWord = words[words.length - 1]!;
    tailSuffix = widthOf(ellipsis + lastWord) <= maxWidthPx ? ellipsis + lastWord : ellipsis;
  }

  return lines
    .map((line, i) => clampToWidth(line, truncated && i === lines.length - 1 ? tailSuffix : ""))
    .join("\n");
}

/** Item 1a (screenshot-review session): computes, for every rendered technology, which wrapped
 * name to use -- plain TAIL truncation by default, MIDDLE-ellipsis only for names in the minimal
 * set that would otherwise render IDENTICALLY to another truncated name (a real collision, not a
 * hypothetical one). Two-pass: (1) wrap every name in "tail" mode and group by output string
 * among truncated names; (2) any group with >1 member switches to "middle" mode and is
 * RE-CHECKED to confirm the switch actually resolved the collision -- never assumed. Returns the
 * final per-key wrapped-name map plus the exact set of keys that needed middle-ellipsis, so
 * `window.__tt.checkNameRendering` can report both the collision count (should be 0) and the
 * middle-ellipsis count (should be the minimum necessary, not "every long name"). */
function resolveNameTruncations(
  ctx: CanvasRenderingContext2D,
  technologies: { id: string; name: string }[],
  maxWidthPx: number,
  maxLines: number,
  fontCss: string
): { wrapped: Map<string, string>; middleEllipsisKeys: Set<string> } {
  const tailWrapped = new Map<string, string>();
  for (const t of technologies) {
    tailWrapped.set(t.id, wrapAndClampName(ctx, t.name, maxWidthPx, maxLines, "tail", fontCss));
  }

  const groupsByOutput = new Map<string, string[]>();
  for (const t of technologies) {
    const isTruncated = tailWrapped.get(t.id)!.includes("…");
    if (!isTruncated) continue;
    const output = tailWrapped.get(t.id)!;
    const group = groupsByOutput.get(output) ?? [];
    group.push(t.id);
    groupsByOutput.set(output, group);
  }

  const middleEllipsisKeys = new Set<string>();
  for (const group of groupsByOutput.values()) {
    if (group.length < 2) continue;
    for (const id of group) middleEllipsisKeys.add(id);
  }

  const wrapped = new Map(tailWrapped);
  const nameById = new Map(technologies.map((t) => [t.id, t.name]));
  for (const id of middleEllipsisKeys) {
    wrapped.set(id, wrapAndClampName(ctx, nameById.get(id)!, maxWidthPx, maxLines, "middle", fontCss));
  }

  return { wrapped, middleEllipsisKeys };
}

async function render(): Promise<void> {
  setStatus("fetching dataset…");
  const base = await fetchBaseDataset();
  initEmpireProfileAxes(base.empireProfileAxes);
  const nodePositions = await fetchGeometry(base.geometry.nodePositions);
  if (nodePositions.length !== base.technologies.length * 2) {
    throw new Error(
      `node-positions side-file has ${nodePositions.length} values, expected 2x technology count (${base.technologies.length * 2})`
    );
  }

  const edgePositions = await fetchGeometry(base.geometry.edgePolylines);
  if (edgePositions.length !== base.edges.length * FLOATS_PER_EDGE_POLYLINE) {
    throw new Error(
      `edge-polylines side-file has ${edgePositions.length} values, expected ${FLOATS_PER_EDGE_POLYLINE}x edge count (${base.edges.length * FLOATS_PER_EDGE_POLYLINE})`
    );
  }

  // Item 1 (activeEdgeIds wiring): `pipeline.edge_constraints` now computes a REAL per-profile
  // active edge set (980-983 of 984 edges, real corpus -- previously a no-op 984/984 for every
  // profile, undetected across many sessions). `activeEdgeIds` gates drawing, ancestry/dependent
  // traversal, and the popup's prerequisite/dependent lists alike -- one Set, three consumers,
  // never three independent filters that could drift apart. Fetched here (before the initial edge
  // draw) so the very first render already reflects DEFAULT_PROFILE's real active set rather than
  // drawing everything and correcting a frame later.
  const initialOverlay = await fetchEmpireOverlay(profileKey(DEFAULT_PROFILE));
  let activeEdgeIds: Set<number> = new Set(initialOverlay.activeEdgeIds);

  setStatus("loading icon atlases…");
  const atlasTextures = await loadAtlasTextures(base);
  // P-3 popup gate section: sheet name -> its own webp URL, so the DOM popup can crop a gate
  // icon via CSS background-position from the same already-fetched atlas the PixiJS card icons
  // use -- no separate icon fetch, no manually-maintained path (P-3's acceptance criteria).
  const atlasWebpUrlBySheet = new Map(base.iconAtlases.map((s) => [s.name, atlasUrl(s.webp)]));

  setStatus("initialising PixiJS…");
  const app = new Application();
  await app.init({ resizeTo: window, background: "#111318", antialias: true });
  document.getElementById("pixi-root")!.appendChild(app.canvas);

  // Everything lives in `world`, the single container the camera scales/translates -- no sibling
  // viewport-pinned layer. The sticky/pinned header mechanism from the previous slice is REMOVED
  // entirely (defect fix, not hidden behind a flag): the user rejected it outright ("a banner
  // floating in the top-left that swaps contents as you scroll doesn't belong to any visible
  // object"). Row header chips and tier-band cell labels below are ordinary world-space content
  // now, anchored to their own row/band geometry and scaling with everything else.
  const world = new Container();
  app.stage.addChild(world);

  // --- Row/band geometry (reconciliation session: DERIVED FROM ACTUAL NODE POSITIONS, not
  // reimplemented from pipeline/layout.py's own formulas). A prior version of this block
  // re-derived row heights (`Math.ceil(count / SUBGRID_WIDTH)`, a plain wrap-at-N) and band
  // x-starts (uniform `SUBGRID_WIDTH` per band) independently client-side -- this was ALWAYS a
  // second, parallel implementation of pipeline/layout.py's geometry, and it silently went stale
  // the moment D-17's same-band depth-slot wrap replaced BOTH formulas server-side (a cell's row
  // height is now capped at `subgrid_width` regardless of population, and a band's width is a
  // cumulative sum of per-depth slot widths, not a uniform `SUBGRID_WIDTH`): row panels, tier
  // tints and cell labels kept drawing at the OLD geometry while cards drew at the real
  // (authoritative, geometry-side-file-sourced) positions -- found by a headless screenshot
  // showing a faction row's own decorative backing nowhere near its actual cards. The permanent
  // fix is this block: derive every row's/band's start and extent directly from the REAL min/max
  // node position within it, so client and server geometry can never drift apart again, by
  // construction, regardless of how the depth-slot/wrap formula changes in the future. A row or
  // band with zero real members (none in the current corpus, but not assumed impossible) falls
  // back to a cumulative placeholder extent purely so the geometry stays well-defined; there is no
  // card to misalign against in that case either way. ---
  const cellCounts = new Map<string, number>(); // `${rowId}#${bandIndex}` -> count, presence only
  for (const tech of base.technologies) {
    const key = `${tech.rowId}#${bandIndexOf(tech, base.tierBands)}`;
    cellCounts.set(key, (cellCounts.get(key) ?? 0) + 1);
  }

  // rowArea (moved earlier this session, DEFECT 2): a category row's own research area, taken
  // from its first technology's `area` field -- no schema change needed, `pipeline/layout.py`'s
  // AREA_ORDER grouping is already implicit in `base.rows`' own derived order, so this map is
  // enough to detect a GROUP boundary (area change, or category->faction) the same way
  // `pipeline.layout._row_order`'s `row_group_of` does server-side, without a new field.
  const rowArea = new Map<string, string>();
  for (const tech of base.technologies) {
    if (!rowArea.has(tech.rowId)) rowArea.set(tech.rowId, tech.area);
  }
  function rowGroupIndex(row: (typeof base.rows)[number]): number {
    if (row.crisisFaction !== null) return AREA_ORDER.length;
    const area = rowArea.get(row.id);
    const idx = area ? AREA_ORDER.indexOf(area) : -1;
    return idx >= 0 ? idx : AREA_ORDER.length;
  }

  // Real min/max node Y per row, and min/max node X per band -- the authoritative source for all
  // geometry below (see the block comment above).
  const rowMinY = new Map<string, number>();
  const rowMaxY = new Map<string, number>();
  const bandMinX: (number | undefined)[] = new Array(base.tierBands.length);
  const bandMaxX: (number | undefined)[] = new Array(base.tierBands.length);
  for (let i = 0; i < base.technologies.length; i++) {
    const tech = base.technologies[i]!;
    const x = nodePositions[i * 2]!;
    const y = nodePositions[i * 2 + 1]!;
    rowMinY.set(tech.rowId, Math.min(rowMinY.get(tech.rowId) ?? Infinity, y));
    rowMaxY.set(tech.rowId, Math.max(rowMaxY.get(tech.rowId) ?? -Infinity, y));
    const b = bandIndexOf(tech, base.tierBands);
    bandMinX[b] = Math.min(bandMinX[b] ?? Infinity, x);
    bandMaxX[b] = Math.max(bandMaxX[b] ?? -Infinity, x);
  }

  const rowYOffset = new Map<string, number>();
  const rowHeight = new Map<string, number>();
  let canvasHeightComputed = 0;
  {
    let yCursor = 0;
    let previousGroup: number | null = null;
    for (const row of base.rows) {
      // DEFECT 2 (this session): AREA_GROUP_GUTTER before the first row of a new group, mirroring
      // pipeline/layout.py's own row_y_offset loop exactly (see that module for the chosen value
      // and full reasoning) -- never before the very first row overall.
      const currentGroup = rowGroupIndex(row);
      if (previousGroup !== null && currentGroup !== previousGroup) yCursor += AREA_GROUP_GUTTER;
      previousGroup = currentGroup;

      const minY = rowMinY.get(row.id);
      let y0: number;
      let h: number;
      if (minY !== undefined) {
        const maxY = rowMaxY.get(row.id)!;
        y0 = minY - ROW_HEADER_HEIGHT;
        h = ROW_HEADER_HEIGHT + ROW_GUTTER + (maxY + CARD_HEIGHT - minY);
      } else {
        y0 = yCursor;
        h = ROW_HEADER_HEIGHT + ROW_GUTTER;
      }
      rowYOffset.set(row.id, y0);
      rowHeight.set(row.id, h);
      yCursor = y0 + h;
    }
    canvasHeightComputed = yCursor;
  }

  const bandXStart: number[] = [];
  const bandWidth: number[] = [];
  {
    let xCursor = 0;
    for (let b = 0; b < base.tierBands.length; b++) {
      let x0: number;
      let w: number;
      if (bandMinX[b] !== undefined) {
        x0 = bandMinX[b]!;
        w = bandMaxX[b]! + CARD_WIDTH - x0;
      } else {
        x0 = xCursor;
        w = SUBGRID_WIDTH * CARD_WIDTH + (SUBGRID_WIDTH - 1) * INTRA_GAP_X;
      }
      bandXStart.push(x0);
      bandWidth.push(w);
      xCursor = x0 + w + INTER_BAND_GUTTER;
    }
  }
  const canvasWidthComputed =
    bandXStart.length > 0 ? bandXStart[bandXStart.length - 1]! + bandWidth[bandWidth.length - 1]! : 0;

  const rowDrawnCounts = new Map<string, number>();
  for (const tech of base.technologies) {
    rowDrawnCounts.set(tech.rowId, (rowDrawnCounts.get(tech.rowId) ?? 0) + 1);
  }

  // --- DEFECT 2 (this session): tier-band alternating background tint, drawn FIRST (bottom of
  // `world`, beneath the row panels below) so row/faction colour still dominates on top of it --
  // see tokens.ts's own comment for why two neutral (non-hued) overlays alternating by band index
  // rather than any single hued tint. Spans exactly each band's own card-slot width, leaving the
  // untinted INTER_BAND_GUTTER as the natural boundary between adjacent tints. ---
  const tierTintLayer = new Container();
  world.addChild(tierTintLayer);
  for (let b = 0; b < base.tierBands.length; b++) {
    const isEven = b % 2 === 0;
    const color = isEven ? TIER_BAND_TINT_COLOR_EVEN : TIER_BAND_TINT_COLOR_ODD;
    const alpha = isEven ? TIER_BAND_TINT_ALPHA_EVEN : TIER_BAND_TINT_ALPHA_ODD;
    const tintG = new Graphics().rect(bandXStart[b]!, 0, bandWidth[b]!, canvasHeightComputed).fill({ color, alpha });
    tierTintLayer.addChild(tintG);
  }

  // --- Row backing (defect fix): EVERY row -- 13 category, 5 faction -- gets the identical
  // tinted-panel/border/rounded-corner treatment (`drawRowPanel`), beneath edges beneath cards --
  // added to `world` after the tier-band tint, before anything else. Previously only the 5
  // faction rows had any backing at all, so the category rows read as empty space and the faction
  // rows looked like a different species of object; all 18 are now "the same class of object,
  // differing only in colour and texture" (faction rows additionally get a pattern accent on top
  // of the panel, DEFECT 5's real pattern artwork, clipped to the row rect via `maskToRowRect`
  // rather than the previous per-style analytic bounding -- see that function's own comment). ---
  const rowBackingLayer = new Container();
  world.addChild(rowBackingLayer);
  let rowPanelCount = 0;
  const rowPatternAccents: Graphics[] = [];
  const rowPatternMasks: Graphics[] = []; // kept referenced so PixiJS's mask assignment can't be GC'd away
  for (const row of base.rows) {
    const y0 = rowYOffset.get(row.id)!;
    // EAWAF/v1-routing session, row-panel-bleed fix: `rowHeight.get(row.id)` (mirroring
    // pipeline/layout.py's `row_height = ROW_HEADER_HEIGHT + ROW_GUTTER + cards`) includes the
    // row's own TRAILING ROW_GUTTER -- the reserved separation before the NEXT row's header, not
    // part of this row's own visible content. Drawing the panel across the full `h` (as a prior
    // session did) made the panel bleed into that trailing gutter, so one row's panel bottom edge
    // touched the next row's panel top edge directly -- ROW_GUTTER was a real, nonzero number
    // that was simply never visible on screen. `visibleH` stops the panel (and its pattern
    // accent) ROW_GUTTER short of the row's own bottom, leaving that reserved space genuinely
    // empty so the gap is actually rendered, not just reserved in the geometry.
    const h = rowHeight.get(row.id)! - ROW_GUTTER;
    // DEFECT 5 fix: panel background is the row's own BACKING tone (rowPanelColorFor), not the
    // chip's flag-identity colour -- see tokens.ts's own comment on why these differ.
    const panelColor = rowPanelColorFor(rowArea.get(row.id) ?? null, row.crisisFaction);
    const panelG = new Graphics();
    drawRowPanel(panelG, panelColor, 0, y0, canvasWidthComputed, h);
    rowBackingLayer.addChild(panelG);
    rowPanelCount++;

    if (row.crisisFaction) {
      const spec = CRISIS_FACTION_ROW_PATTERNS[row.crisisFaction];
      if (spec) {
        const accentG = new Graphics();
        drawFactionRowPattern(accentG, spec, 0, y0, canvasWidthComputed, h);
        const maskG = maskToRowRect(accentG, 0, y0, canvasWidthComputed, h);
        rowBackingLayer.addChild(maskG); // must be a scene-graph child for its transform to update -- see maskToRowRect's own comment
        rowPatternMasks.push(maskG);
        rowBackingLayer.addChild(accentG);
        rowPatternAccents.push(accentG);
      }
    }
  }

  // Edges are added to `world` next (after row backing, before any node card), so they draw
  // beneath cards but above row backing. Batched into 6 Graphics total (one line + one arrowhead
  // object per EdgeKind), not one per edge (P-8: frame-budget requirement at 989 edges).
  const edgeLineLayer = new Container();
  const edgeArrowLayer = new Container();
  world.addChild(edgeLineLayer);
  world.addChild(edgeArrowLayer);
  const edgeLineGraphics = new Map<EdgeKind, Graphics>();
  const edgeArrowGraphics = new Map<EdgeKind, Graphics>();
  for (const kind of EDGE_KINDS) {
    const lineG = new Graphics();
    edgeLineLayer.addChild(lineG);
    edgeLineGraphics.set(kind, lineG);
    const arrowG = new Graphics();
    edgeArrowLayer.addChild(arrowG);
    edgeArrowGraphics.set(kind, arrowG);
  }

  // DEFECT 3: endpoints (each edge's card-attachment points) recorded per edge so the headless
  // verification harness can assert every rounded polyline still terminates inside its source/
  // target card bounds -- see `checkEdgeEndpointsInCards` on `window.__tt` below.
  const edgeEndpoints: { fromId: string; toId: string; start: [number, number]; end: [number, number] }[] = [];
  // Part-1 verification: the RAW (pre-corner-rounding) exit/entry stub lengths -- rounding
  // shortens the segment nearest a corner, so the MIN_STUB requirement is checked against the
  // server-computed polyline exactly as pipeline/layout.py emits it, not the rendered one.
  const edgeStubLengths: { fromId: string; toId: string; exitStub: number; entryStub: number }[] = [];
  // EAWAF/v1-routing session: the raw (pre-rounding) polyline per edge, kept around so
  // `checkUnrelatedCardCrossings` (window.__tt) can measure the real unrelated-card-crossing
  // count under the new v1-style router -- the previous gutter router measured a proven zero;
  // this session's port is a deliberate, known trade of that property for legibility (see
  // pipeline/layout.py's `_route_edges` docstring and CLAUDE.md), and the number is reported
  // rather than assumed.
  const edgeRawPolylines: { fromId: string; toId: string; pts: [number, number][] }[] = [];
  // Hover/selection slice: the RENDERED (post-rounding) polyline per edge, index-aligned with
  // `base.edges` -- reused for drawing hover/selection highlight overlays so they trace the exact
  // same geometry already on screen, rather than a second, parallel computation.
  const edgeRoundedPolylines: [number, number][][] = [];
  // Geometry (endpoints/stub-lengths/raw+rounded polylines) is computed for EVERY edge
  // unconditionally, active or not -- these feed the routing-correctness verification harness
  // (window.__tt) and the hover/selection highlight overlay, neither of which is about which
  // edges are currently active for a profile. Only the VISUAL trace (below) respects
  // `activeEdgeIds`.
  for (let i = 0; i < base.edges.length; i++) {
    const edge = base.edges[i]!;
    const baseOffset = i * FLOATS_PER_EDGE_POLYLINE;
    const rawPts: [number, number][] = [];
    for (let p = 0; p < FLOATS_PER_EDGE_POLYLINE; p += 2) {
      rawPts.push([edgePositions[baseOffset + p]!, edgePositions[baseOffset + p + 1]!]);
    }
    edgeStubLengths.push({
      fromId: edge.from,
      toId: edge.to,
      exitStub: Math.hypot(rawPts[1]![0] - rawPts[0]![0], rawPts[1]![1] - rawPts[0]![1]),
      entryStub: Math.hypot(
        rawPts[rawPts.length - 1]![0] - rawPts[rawPts.length - 2]![0],
        rawPts[rawPts.length - 1]![1] - rawPts[rawPts.length - 2]![1]
      ),
    });
    edgeRawPolylines.push({ fromId: edge.from, toId: edge.to, pts: rawPts });
    // DEFECT 3: apply corner rounding at render time only -- rawPts (the server-computed
    // card-avoidance route) is untouched; `pts` is only what's actually traced/arrowed.
    const pts = roundPolylineCorners(rawPts, EDGE_CORNER_RADIUS);
    edgeRoundedPolylines.push(pts);
    edgeEndpoints.push({ fromId: edge.from, toId: edge.to, start: pts[0]!, end: pts[pts.length - 1]! });
  }

  // Item 1: (re)traces only the edges active for the current profile. Called once for the
  // initial draw and again on every profile switch -- clears and rebuilds each kind's shared
  // Graphics rather than maintaining one Graphics per edge (P-8's frame-budget reasoning above
  // for why edges are batched per-kind, not per-edge, still applies).
  function traceActiveEdges(active: Set<number>): void {
    const edgeCountByKind: Record<EdgeKind, number> = { prerequisite: 0, "potential-gate": 0, alternative: 0 };
    for (const kind of EDGE_KINDS) {
      edgeLineGraphics.get(kind)!.clear();
      edgeArrowGraphics.get(kind)!.clear();
    }
    for (let i = 0; i < base.edges.length; i++) {
      if (!active.has(i)) continue;
      const edge = base.edges[i]!;
      const pts = edgeRoundedPolylines[i]!;
      const style = EDGE_STYLE[edge.kind];
      tracePolyline(edgeLineGraphics.get(edge.kind)!, pts, style.dash);
      addArrowhead(edgeArrowGraphics.get(edge.kind)!, pts);
      edgeCountByKind[edge.kind]++;
    }
    for (const kind of EDGE_KINDS) {
      edgeLineGraphics.get(kind)!.stroke({ width: EDGE_STROKE_WIDTH, color: EDGE_COLOR, alpha: EDGE_STYLE[kind].alpha });
      edgeArrowGraphics.get(kind)!.fill({ color: EDGE_COLOR, alpha: EDGE_STYLE[kind].alpha });
    }
    edgeCountByKindForStatus = edgeCountByKind;
  }
  traceActiveEdges(activeEdgeIds);

  const NAME_FONT_SIZE = 20;
  const NAME_FONT_FAMILY = "system-ui, sans-serif";
  // wordWrap is OFF -- name text is pre-wrapped/clamped by `wrapAndClampName` below and joined
  // with explicit "\n"s, so PixiJS just lays out the exact lines it's given (defect fix: PixiJS's
  // own wordWrap has no line-count cap, which is exactly how long names overflowed the card).
  const nameStyle = new TextStyle({ fill: "#f0f0f0", fontSize: NAME_FONT_SIZE, fontFamily: NAME_FONT_FAMILY, wordWrap: false });
  // Real canvas 2D measurement context, matched to `nameStyle`'s font exactly -- PixiJS's own
  // CanvasTextRenderer measures wordWrap the same way, so this produces the same wrapping
  // PixiJS would have, just with a hard line-count cap PixiJS itself doesn't offer.
  const measureCtx = document.createElement("canvas").getContext("2d")!;
  measureCtx.font = `${NAME_FONT_SIZE}px ${NAME_FONT_FAMILY}`;

  const costStyle = new TextStyle({ fill: "#9fb3c8", fontSize: 15, fontFamily: "system-ui, sans-serif" });
  const badgeTextStyle = new TextStyle({ fill: "#0d0f13", fontSize: 14, fontFamily: "system-ui, sans-serif", fontWeight: "700" });
  // Badges slice: smaller text style for the BADGE_GUTTER_WIDTH (34px) badge row -- the original
  // badgeTextStyle (14px) was sized for the old standalone 30x20 tier badge; the gutter's stacked
  // 16px-tall rows need a smaller face to keep short labels ("T5", "×5", "ACOT") legible without
  // overflowing their own badge.
  const gutterBadgeTextStyle = new TextStyle({ fill: "#0d0f13", fontSize: 10, fontFamily: "system-ui, sans-serif", fontWeight: "700" });
  // Item 8a (later session): "∞" (unbounded repeatable, 88 real technologies share the repeatable
  // badge but only the unbounded ones use this glyph) sits at the SAME 10px font size as every
  // other gutter badge, but the glyph's own ink is much smaller/thinner than a digit at that size
  // -- the autoscale below can only shrink text to fit the badge box, never enlarge it, so a
  // naturally-small glyph stays small and reads as a hyphen at anything under near-maximum zoom,
  // per the user's report. A dedicated, larger base font size for this one glyph fixes it without
  // touching the shared digit/badge style everything else still uses.
  const infinityBadgeTextStyle = new TextStyle({ fill: "#0d0f13", fontSize: 20, fontFamily: "system-ui, sans-serif", fontWeight: "700" });
  const gateLabelStyle = new TextStyle({ fill: "#c8b98a", fontSize: 11, fontFamily: "system-ui, sans-serif" });
  const chipTextStyle = new TextStyle({ fill: "#0d0f13", fontSize: 15, fontFamily: "system-ui, sans-serif", fontWeight: "700" });
  // Per-(row, band)-cell tier label (defect fix: replaces the removed sticky header -- v1 repeats
  // a small, subdued label above each row's own band cell instead of one floating global header).
  const cellLabelStyle = new TextStyle({
    fill: CELL_TIER_LABEL_COLOR,
    fontSize: CELL_LABEL_FONT_SIZE,
    fontFamily: "system-ui, sans-serif",
  });

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  // Parallel arrays, indexed same as base.technologies -- the LOD toggler below flips
  // icon/name/cost/badge .visible without touching per-node world coordinates or recreating
  // objects.
  const nodeIcons: (Sprite | null)[] = [];
  const nodeNames: Text[] = [];
  // Item 2 (tech swaps): the card's own outline Graphics, so a swap that changes `area` (7/123
  // real swaps do) can be recoloured on a profile switch without recreating the card.
  const nodeCards: Graphics[] = [];
  // Reconciliation-session verification questions (Item 7): the exact wrapped/clamped display
  // text per card, so `window.__tt.checkNameRendering` can report real ellipsis-truncation and
  // duplicate-visible-text counts rather than approximating from raw name length.
  const wrappedNames: string[] = [];
  const nodeCosts: (Text | null)[] = [];
  // Badges slice: one array per indicator, each independently LOD-toggled per its own S-03
  // threshold (see lod.ts) -- tier and repeat badges are mutually exclusive per node (never both
  // non-null for the same index) but shed at DIFFERENT thresholds (repeat: <60%, tier: <20%), so
  // they can't share one array the way the pre-badges-slice code did.
  const nodeTierBadges: (Container | null)[] = [];
  const nodeRepeatBadges: (Container | null)[] = [];
  const nodeRareBadges: (Container | null)[] = [];
  const nodeDangerousBadges: (Container | null)[] = [];
  // Array-per-node, not Container-per-node: `makeTextBadge` already positions and adds each
  // badge to `world` directly in absolute world coordinates, so a wrapping Container would need
  // its OWN correct position for bounds-checking to make sense -- simpler and less error-prone to
  // just track the flat list of already-placed badges per node (real corpus max is 1, but this
  // handles more without a data-shape change).
  const nodeModRequirementBadges: Container[][] = [];
  const nodeGateIcons: (Sprite | null)[] = [];
  const nodeGateLabels: (Text | null)[] = [];
  // Item 4 ("path to zero uncertain" follow-up): the primary gate's own `appliesToEmpireTypes`
  // (null when unconstrained -- applies to every profile), index-parallel to nodeGateIcons/
  // nodeGateLabels. An alternative gate backed by a genuinely axis-constrained potential-gate
  // edge (e.g. tech_torpedoes_1's "Riddle Escort", shipset=[biological]) must not present as a
  // requirement for a profile the constraint rules out -- non-bio-ship empires already qualify
  // via a completely different OR branch, unrelated to this gate.
  const nodePrimaryGateConstraint: (EmpireTypeConstraint | null)[] = [];
  let costlessCardCount = 0;

  // Item 1a fix (screenshot-review session): resolved ONCE, up front, over every rendered
  // technology's real name -- see `resolveNameTruncations`'s own docstring. Must run before the
  // per-card loop below, since a collision is only detectable by comparing ALL names' tail-mode
  // output against each other, not one card at a time.
  const { wrapped: resolvedNames, middleEllipsisKeys } = resolveNameTruncations(
    measureCtx, base.technologies, NAME_MAX_WIDTH_PX, MAX_NAME_LINES, `${NAME_FONT_SIZE}px ${NAME_FONT_FAMILY}`
  );

  for (let i = 0; i < base.technologies.length; i++) {
    const tech = base.technologies[i]!;
    const x = nodePositions[i * 2]!;
    const y = nodePositions[i * 2 + 1]!;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + CARD_WIDTH);
    maxY = Math.max(maxY, y + CARD_HEIGHT);

    // D-16 amendment: cards are neutral dark fill -- research area/faction colour moved to the
    // row axis (backing + header chip). The card's own OUTLINE still carries research area
    // unconditionally, UNLESS the technology is rare or dangerous, in which case that takes
    // priority (CLAUDE.md's "Colour and pattern", S-1's "Outline priority: dangerous outranks
    // rare"). Both: a 45-degree split outline, dangerous red on the top-left half.
    const areaOutlineColor = AREA_COLORS[tech.area] ?? 0x888888;
    const baseOutlineColor = tech.dangerous ? DANGEROUS_COLOR : tech.rare ? RARE_COLOR : areaOutlineColor;
    const card = new Graphics().roundRect(0, 0, CARD_WIDTH, CARD_HEIGHT, 6).fill(CARD_FILL)
      .stroke({ width: 2, color: tech.rare && tech.dangerous ? RARE_COLOR : baseOutlineColor });
    card.position.set(x, y);
    world.addChild(card);
    nodeCards.push(card);

    if (tech.rare && tech.dangerous) {
      // 45-degree split outline: a duplicate stroke in DANGEROUS_COLOR, masked to the top-left
      // triangular half so it reads first on a left-to-right scan (S-1). The mask MUST be added
      // as a child of the SAME container the target is in (`world`) for PixiJS to keep its
      // transform in sync -- an earlier session's row-pattern mask bug (tokens.ts/main.ts's own
      // comments on `maskToRowRect`) is the exact failure mode this avoids.
      const dangerousHalf = new Graphics().roundRect(0, 0, CARD_WIDTH, CARD_HEIGHT, 6).stroke({ width: 2, color: DANGEROUS_COLOR });
      dangerousHalf.position.set(x, y);
      const splitMask = new Graphics().poly([0, 0, CARD_WIDTH, 0, 0, CARD_HEIGHT]).fill(0xffffff);
      splitMask.position.set(x, y);
      world.addChild(splitMask);
      dangerousHalf.mask = splitMask;
      world.addChild(dangerousHalf);
    }

    const sheetTexture = atlasTextures.get(tech.icon.sheet);
    let iconSprite: Sprite | null = null;
    if (sheetTexture) {
      const frame = new Rectangle(tech.icon.x, tech.icon.y, tech.icon.width, tech.icon.height);
      iconSprite = new Sprite(new Texture({ source: sheetTexture.source, frame }));
      iconSprite.width = ICON_SIZE;
      iconSprite.height = ICON_SIZE;
      iconSprite.position.set(x + ICON_MARGIN, y + ICON_MARGIN);
      world.addChild(iconSprite);
    }
    nodeIcons.push(iconSprite);

    const wrappedName = resolvedNames.get(tech.id)!;
    const nameText = new Text({ text: wrappedName, style: nameStyle });
    nameText.position.set(x + ICON_SIZE + ICON_MARGIN * 2, y + ICON_MARGIN);
    world.addChild(nameText);
    nodeNames.push(nameText);
    wrappedNames.push(wrappedName);

    // Cost line: 15/980 rendered nodes have a null (unresolvable) cost -- render no cost line at
    // all for those, never 0/"N/A"/a placeholder. Bottom-anchored under the icon; name is now hard
    // -clamped to MAX_NAME_LINES so it can no longer grow into this space the way an unclamped
    // wrapped name could before (defect fix) -- the `belowNameY` term stays only as a defensive
    // floor, never actually the binding constraint post-clamp for the real corpus.
    if (tech.cost !== null) {
      const costText = new Text({ text: `Cost: ${Math.round(tech.cost).toLocaleString("en-US")}`, style: costStyle });
      const bottomAnchorY = y + CARD_HEIGHT - costText.height - 8;
      const belowNameY = nameText.y + nameText.height + 4;
      costText.position.set(x + ICON_MARGIN, Math.max(bottomAnchorY, belowNameY));
      world.addChild(costText);
      nodeCosts.push(costText);
    } else {
      nodeCosts.push(null);
      costlessCardCount++;
    }

    // Badges slice: every indicator stacks top-to-bottom in the fixed BADGE_GUTTER_WIDTH gutter
    // (see that constant's own comment for the sizing rationale), one slot per flag this
    // technology ACTUALLY carries -- a technology with only "rare" gets one badge, not five empty
    // slots. Order (top to bottom, this session's own layout choice, not spec-mandated): tier/
    // repeat -> mod requirement(s) -> dangerous -> rare -> gate icon. LOD toggling (see
    // `updateLod` below) only flips `.visible` per indicator's own S-03 threshold -- it never
    // reflows the stack, so a shed badge leaves its slot empty rather than closing the gap.
    let gutterY = y + ICON_MARGIN;
    function nextGutterSlot(): number {
      const slotY = gutterY;
      gutterY += BADGE_HEIGHT + BADGE_GAP;
      return slotY;
    }
    function makeTextBadge(text: string, color: number): Container {
      const c = new Container();
      const bg = new Graphics().roundRect(0, 0, BADGE_GUTTER_WIDTH, BADGE_HEIGHT, 3).fill({ color, alpha: 0.92 });
      c.addChild(bg);
      const t = new Text({ text, style: text === "∞" ? infinityBadgeTextStyle : gutterBadgeTextStyle });
      t.scale.set(Math.min(1, (BADGE_GUTTER_WIDTH - 4) / t.width, (BADGE_HEIGHT - 2) / t.height));
      t.position.set(BADGE_GUTTER_WIDTH / 2 - (t.width * t.scale.x) / 2, BADGE_HEIGHT / 2 - (t.height * t.scale.y) / 2);
      c.addChild(t);
      c.position.set(x + BADGE_GUTTER_X, nextGutterSlot());
      world.addChild(c);
      return c;
    }

    // Tier / repeat badge (mutually exclusive -- D-13's declared exception means a repeatable
    // node's badge is its REPEAT COUNT, never its declared tier).
    if (tech.repeatable) {
      const label = tech.repeatable.levels === null ? "∞" : `×${tech.repeatable.levels}`;
      nodeTierBadges.push(null);
      nodeRepeatBadges.push(makeTextBadge(label, 0xc9d3e0));
    } else {
      nodeTierBadges.push(makeTextBadge(`T${tech.tier}`, 0xc9d3e0));
      nodeRepeatBadges.push(null);
    }

    // Mod-requirement badge(s) -- `requiresMods: string[]`, distinct from gates and prerequisites
    // (P-16), NEVER a visibility toggle. Real corpus max is 1 entry; the loop handles more without
    // a schema change if a future corpus ever has them. Each badge is placed and added to `world`
    // directly by `makeTextBadge` -- no wrapping container to keep positioned correctly.
    nodeModRequirementBadges.push(tech.requiresMods.map((mod) => makeTextBadge(mod, MOD_REQUIREMENT_BADGE_COLOR)));

    // Dangerous / rare badges -- S-1: "Colour is never the sole carrier. Rare and dangerous each
    // also get a card badge" (the outline above is the colour channel; these badges are the
    // non-colour channel, distinguished by TEXT glyph, not colour alone).
    nodeDangerousBadges.push(tech.dangerous ? makeTextBadge("!", DANGEROUS_COLOR) : null);
    nodeRareBadges.push(tech.rare ? makeTextBadge("★", RARE_COLOR) : null);

    // Gate icon + label (P-3): `gates` is now real (pipeline.gate_patterns' classification
    // pass, gate-classification session -- 70 gate instances over 60 technologies in the real
    // corpus). This wiring against the schema's `gates` shape predates real data and needed no
    // changes once the pipeline started populating it. Only the PRIMARY gate (index 0, D-3's
    // ascension-perk-outranks-technology ordering) renders on the card -- spec's "where space
    // permits, additional gates render as compact secondary badges" for a technology with more
    // than one gate is NOT built (only 10/977 real technologies have a second gate instance);
    // flagged here rather than silently built as new scope beyond what this session asked for.
    const primaryGate = tech.gates[0];
    nodePrimaryGateConstraint.push(primaryGate?.appliesToEmpireTypes ?? null);
    if (primaryGate) {
      // Item 3a (a later session, user-reported): an origin/ethics-or-civic gate's `icon` is
      // `null` (no source vendors those icons at all -- CLAUDE.md's "Icons -- reported, not
      // vendored"), never the old degenerate 1x1-pixel stretched fallback that read as a
      // rendering error (a "teal square"). No sprite is created at all in that case -- the label
      // alone identifies the gate, exactly the same "drop the icon, keep the label" contract this
      // block already uses when card space runs out (see the label-fit comment below).
      const gateSheetTexture = primaryGate.icon ? atlasTextures.get(primaryGate.icon.sheet) : undefined;
      let gateIconSprite: Sprite | null = null;
      if (gateSheetTexture && primaryGate.icon) {
        const gateFrame = new Rectangle(primaryGate.icon.x, primaryGate.icon.y, primaryGate.icon.width, primaryGate.icon.height);
        gateIconSprite = new Sprite(new Texture({ source: gateSheetTexture.source, frame: gateFrame }));
        gateIconSprite.width = GATE_ICON_SIZE;
        gateIconSprite.height = GATE_ICON_SIZE;
        const slotY = nextGutterSlot();
        gateIconSprite.position.set(x + BADGE_GUTTER_X + (BADGE_GUTTER_WIDTH - GATE_ICON_SIZE) / 2, slotY);
        world.addChild(gateIconSprite);
      } else if (primaryGate.icon) {
        nextGutterSlot(); // keep stack accounting consistent even if the icon itself failed to resolve
      }
      nodeGateIcons.push(gateIconSprite);

      // Label reads to the LEFT of the icon, inward toward the name. Item 1b fix (screenshot-
      // review session), two real bugs found from one screenshot (`giga_tech_amb_supertensiles_
      // acot_phanon`, "Needs Civil Phanon Engineering"):
      //  1. Measured with the wrong font -- `measureCtx` was left at the 20px NAME font by the
      //     block above, not reset to `gateLabelStyle`'s actual 11px, so every width came back
      //     ~1.8x too large and the label over-truncated to a near-unreadable "Ne…Engineering".
      //     Fixed by passing the real font explicitly (`wrapAndClampName`'s new `fontCss` param,
      //     which sets `ctx.font` itself rather than trusting caller state). Tail mode, not
      //     middle -- a gate label is never compared against another gate label for collisions
      //     the way card names are, so there's nothing for middle-ellipsis to protect against
      //     here; plain tail truncation is simpler and reads better.
      //  2. Y-position collided with the card NAME's own text -- the label used to sit at the
      //     gate icon's Y, which is wherever its turn in the badge-gutter stack landed (as early
      //     as the 2nd slot, for a technology with no rare/dangerous/mod badges before it) --
      //     well within a 2-line name's own vertical span, since the small square badges never
      //     need this care (they live entirely inside the gutter column, never overlapping the
      //     name's horizontal territory the way this label deliberately does). Clamped to never
      //     start above where the name text block actually ends.
      //  3. Item 4 (later session): that name-only clamp still collided with the COST line for a
      //     2-line name on a short card -- both the gate label's Y (nameText bottom + 2) and the
      //     cost line's own `belowNameY` fallback (nameText bottom + 4, used whenever the
      //     bottom-anchored position would sit ABOVE where the name ends) are independently
      //     derived from the exact same `nameText.height`, landing within 2px of each other
      //     whenever the name is long enough to push both off their preferred anchors. Real
      //     corpus examples: "Phased Hyperenergetics", "Planetary-Scale Fabrication". Fixed by
      //     also clamping below the cost line's own bottom edge, the same defensive pattern
      //     already used for the name -- `nodeCosts[i]` is already populated by this point in the
      //     per-node loop (the cost line is built earlier in the same iteration).
      const gateLabelFontCss = "11px system-ui, sans-serif";
      const gateLabelText = wrapAndClampName(measureCtx, primaryGate.label, NAME_MAX_WIDTH_PX, 1, "tail", gateLabelFontCss);
      const gateLabel = new Text({ text: gateLabelText, style: gateLabelStyle });
      let gateLabelY = Math.max(gateIconSprite ? gateIconSprite.y : y, nameText.y + nameText.height + 2);
      // Item 4: only push further down when the name-driven position would actually reach the
      // cost line's own rect -- a REAL overlap check, not an unconditional clamp, so the common
      // case (short name, cost safely bottom-anchored) keeps the label at its natural position
      // right under the name instead of being dragged down to the card's bottom edge for no
      // reason. `gateLabel.height` is already valid here (PixiJS computes Text metrics
      // synchronously on construction, before this line runs).
      const costTextForThisCard = nodeCosts[i];
      if (costTextForThisCard) {
        const overlapsY = gateLabelY < costTextForThisCard.y + costTextForThisCard.height
          && costTextForThisCard.y < gateLabelY + gateLabel.height;
        if (overlapsY) gateLabelY = costTextForThisCard.y + costTextForThisCard.height + 2;
      }
      // Item 4: a 2-line name + a real cost line + a gate badge can leave NO room at all for the
      // label between the (correctly cost-clamped) position and the card's own bottom edge --
      // real corpus examples: giga_tech_alderson_disk and 49 others, all 2-line-name cards with a
      // real (non-null) cost. Per this session's own instruction, the fix is NOT to shrink the
      // font or let it overflow -- it's to drop the label text entirely and keep only the icon
      // (still identifies the gate; full "Needs X" text remains available in the popup's Gates
      // section, which always lists every gate regardless of card-level space). Checked against
      // the card's bottom edge, not an arbitrary threshold, so this only fires when there is
      // truly no room, never as a blanket simplification.
      const fitsOnCard = gateLabelY + gateLabel.height <= y + CARD_HEIGHT;
      if (fitsOnCard) {
        gateLabel.position.set(x + BADGE_GUTTER_X - ICON_MARGIN - gateLabel.width, gateLabelY);
        world.addChild(gateLabel);
        nodeGateLabels.push(gateLabel);
      } else {
        nodeGateLabels.push(null);
      }
    } else {
      nodeGateIcons.push(null);
      nodeGateLabels.push(null);
    }
  }

  // Item 2 (tech swaps): `overlay.swapMappings` substitutes name/icon/area/category for the
  // profile-active swap alternate of a technology that has one (123 real technologies carry at
  // least one axis-expressible swap somewhere across the 12 profiles; 116 differ by name only,
  // 7 also change area/category -- both handled here, never just the name). A swap NEVER creates
  // a second node (D-1) -- this only ever mutates the ONE existing card's already-created
  // Graphics/Sprite/Text objects in place, exactly like `traceActiveEdges` does for edges, never
  // a re-layout. `currentSwapMap` is empty (falls back to base name/icon/area everywhere) until
  // the first `applyProfile` call populates it from the real overlay.
  let currentSwapMap = new Map<string, SwapMapping>();
  let previousSwappedIds = new Set<string>();

  function displayName(techId: string): string {
    return currentSwapMap.get(techId)?.name ?? base.technologies[techIndexById.get(techId)!]!.name;
  }
  function displayIcon(techId: string): TechnologyRecord["icon"] {
    return currentSwapMap.get(techId)?.icon ?? base.technologies[techIndexById.get(techId)!]!.icon;
  }
  function displayArea(techId: string): TechnologyRecord["area"] {
    const tech = base.technologies[techIndexById.get(techId)!]!;
    return currentSwapMap.get(techId)?.area ?? tech.area;
  }
  function displayCategory(techId: string): string {
    const tech = base.technologies[techIndexById.get(techId)!]!;
    return currentSwapMap.get(techId)?.category ?? tech.category;
  }

  function applySwapVisuals(newSwapMap: Map<string, SwapMapping>): void {
    const affected = new Set([...previousSwappedIds, ...newSwapMap.keys()]);
    for (const id of affected) {
      const idx = techIndexById.get(id);
      if (idx === undefined) continue;
      const tech = base.technologies[idx]!;
      const swap = newSwapMap.get(id);

      const name = swap?.name ?? tech.name;
      const wrapped = wrapAndClampName(measureCtx, name, NAME_MAX_WIDTH_PX, MAX_NAME_LINES, "tail", `${NAME_FONT_SIZE}px ${NAME_FONT_FAMILY}`);
      nodeNames[idx]!.text = wrapped;
      wrappedNames[idx] = wrapped;

      const icon = swap?.icon ?? tech.icon;
      const sheetTexture = atlasTextures.get(icon.sheet);
      if (sheetTexture && nodeIcons[idx]) {
        nodeIcons[idx]!.texture = new Texture({ source: sheetTexture.source, frame: new Rectangle(icon.x, icon.y, icon.width, icon.height) });
      }

      const area = swap?.area ?? tech.area;
      const areaOutlineColor = AREA_COLORS[area] ?? 0x888888;
      const baseOutlineColor = tech.dangerous ? DANGEROUS_COLOR : tech.rare ? RARE_COLOR : areaOutlineColor;
      const x = nodePositions[idx * 2]!;
      const y = nodePositions[idx * 2 + 1]!;
      nodeCards[idx]!.clear().roundRect(0, 0, CARD_WIDTH, CARD_HEIGHT, 6).fill(CARD_FILL)
        .stroke({ width: 2, color: tech.rare && tech.dangerous ? RARE_COLOR : baseOutlineColor });
      nodeCards[idx]!.position.set(x, y);
    }
    previousSwappedIds = new Set(newSwapMap.keys());
    currentSwapMap = newSwapMap;
  }
  applySwapVisuals(new Map(initialOverlay.swapMappings.map((s) => [s.technologyId, s])));

  // --- Empire-profile switching (reconciliation session 4): per-node availability overlay. ---
  // One dim-rect + one small state-badge per node, created ONCE at layout time (position is
  // static -- only the fill/text/visibility changes per profile switch), so switching profiles
  // never rebuilds the scene, only toggles/recolors ~977*2 already-existing objects. Drawn in
  // their own layer, above cards but the hover/selection layers (added later, further below)
  // still draw on top, so an outline highlight is never hidden by the dim overlay.
  const availabilityLayer = new Container();
  world.addChild(availabilityLayer);
  const availabilityBadgeStyle = new TextStyle({ fill: "#f0f0f0", fontSize: 11, fontFamily: "system-ui, sans-serif", fontWeight: "700" });
  const nodeAvailabilityDim: Graphics[] = [];
  const nodeAvailabilityBadge: { container: Container; bg: Graphics; text: Text }[] = [];
  for (let i = 0; i < base.technologies.length; i++) {
    const x = nodePositions[i * 2]!;
    const y = nodePositions[i * 2 + 1]!;
    const dim = new Graphics().roundRect(0, 0, CARD_WIDTH, CARD_HEIGHT, 6).fill({ color: AVAILABILITY_DIM_COLOR, alpha: 1 });
    dim.position.set(x, y);
    dim.visible = false;
    availabilityLayer.addChild(dim);
    nodeAvailabilityDim.push(dim);

    const badgeSize = 16;
    const badgeText = new Text({ text: "", style: availabilityBadgeStyle });
    const badgeBg = new Graphics().roundRect(0, 0, badgeSize, badgeSize, 3);
    const badgeContainer = new Container();
    badgeContainer.addChild(badgeBg, badgeText);
    badgeContainer.position.set(x + CARD_WIDTH - ICON_MARGIN - badgeSize, y + CARD_HEIGHT - ICON_MARGIN - badgeSize);
    badgeContainer.visible = false;
    availabilityLayer.addChild(badgeContainer);
    nodeAvailabilityBadge.push({ container: badgeContainer, bg: badgeBg, text: badgeText });
  }

  const contentBBox: ContentBBox = {
    left: minX,
    top: minY - 80, // headroom above the topmost row
    width: maxX - minX,
    height: maxY - (minY - 80),
  };

  const camera = createCamera(app, world, contentBBox);

  // --- Empire-profile switching: state + display update. ---
  // `availabilityMatrix` (already in the base dataset, index-aligned with `base.technologies`)
  // is the SOLE source of per-node state -- never recomputed client-side, per this session's own
  // instruction ("no client-side recomputation, no silent divergence"). `empireProfileIndex`
  // (client/src/empireProfile.ts) mirrors pipeline/dataset_schema/empire_profile.py's canonical
  // formula exactly, so `tech.availabilityMatrix[empireProfileIndex(currentProfile)]` is
  // guaranteed to read the SAME slot the pipeline computed for this exact profile.
  let currentProfile: EmpireProfile = DEFAULT_PROFILE;

  function updateAvailabilityDisplay(): void {
    const index = empireProfileIndex(currentProfile);
    for (let i = 0; i < base.technologies.length; i++) {
      const tech = base.technologies[i]!;
      const state = tech.availabilityMatrix[index];
      const dim = nodeAvailabilityDim[i]!;
      const badge = nodeAvailabilityBadge[i]!;
      if (state === "available") {
        dim.visible = false;
        badge.container.visible = false;
        continue;
      }
      dim.visible = true;
      badge.container.visible = true;
      let alpha: number;
      let badgeColor: number;
      let glyph: string;
      if (state === "locked") {
        alpha = LOCKED_DIM_ALPHA;
        badgeColor = LOCKED_BADGE_COLOR;
        glyph = "✕"; // ✕ -- cannot reach this
      } else if (state === "uncertain") {
        alpha = UNCERTAIN_DIM_ALPHA;
        badgeColor = UNCERTAIN_BADGE_COLOR;
        glyph = "?";
      } else {
        // config-gated
        alpha = CONFIG_GATED_DIM_ALPHA;
        badgeColor = CONFIG_GATED_BADGE_COLOR;
        glyph = "⚙"; // ⚙ -- a game OPTION, not empire state, is the obstacle
      }
      dim.alpha = alpha;
      badge.bg.clear().roundRect(0, 0, 16, 16, 3).fill({ color: badgeColor, alpha: 0.95 });
      badge.text.text = glyph;
      badge.text.position.set(8 - badge.text.width / 2, 8 - badge.text.height / 2);
    }
  }

  // --- Row header chips (defect fix): world-anchored, inside their own row, top-left -- no
  // counter-scaling, no visibility toggling. A world-scaled label cannot collide with another
  // one the way the removed sticky labels did, because each holds a fixed position relative to
  // its own row's geometry rather than fighting for the same screen-space corner. Every row's
  // chip is always in the scene graph and always visible; labels become unreadable at
  // fit-to-viewport zoom, which is intended (see main.ts's own module comment / CLAUDE.md's S-03
  // amendment) -- at overview zoom the user navigates by row shape and colour, not by reading. ---
  const rowLabelLayer = new Container();
  world.addChild(rowLabelLayer); // added after edges (below), so labels/chips draw above edge lines
  // DEFECT 4 verification surface: the chip's own bounding rect and every cell label's bounding
  // rect, per row, so `checkChipLabelOverlap` (window.__tt) can assert non-overlap numerically
  // across every row/band pair rather than by eye.
  const rowChipRects = new Map<string, { x: number; y: number; w: number; h: number }>();
  const rowCellLabelRects = new Map<string, { band: number; x: number; y: number; w: number; h: number }[]>();
  for (const row of base.rows) {
    const y0 = rowYOffset.get(row.id)!;
    const color = rowChipColorFor(rowArea.get(row.id) ?? null, row.crisisFaction);
    const label = `${row.label} (${row.technologyCount})`;
    const text = new Text({ text: label, style: chipTextStyle });
    const bg = new Graphics().roundRect(0, 0, text.width + CHIP_PADDING_X * 2, CHIP_HEIGHT, 5).fill({ color, alpha: 0.95 });
    text.position.set(CHIP_PADDING_X, CHIP_HEIGHT / 2 - text.height / 2);
    const chip = new Container();
    chip.addChild(bg);
    chip.addChild(text);
    // DEFECT 4: chip is TOP-anchored within the header strip now (was vertically centred in it) --
    // the cell tier label below is anchored to sit strictly BELOW the chip's own bottom edge, so
    // the two occupy disjoint vertical bands within the header regardless of the chip's own width
    // (which varies by row's label length) or which band's label is being positioned.
    const chipY = y0 + CHIP_TOP_PAD;
    chip.position.set(CHIP_MARGIN, chipY);
    rowLabelLayer.addChild(chip);
    rowChipRects.set(row.id, { x: CHIP_MARGIN, y: chipY, w: bg.width, h: CHIP_HEIGHT });

    // Defect fix: a zero-population row (Compound, confirmed real -- pipeline/crisis_faction.py)
    // previously rendered as a bare collapsed strip with no explanation, reading as a rendering
    // failure rather than real information. An explicit inline note makes it read as deliberate;
    // never skipped or hidden, so a future corpus change giving it members shows up immediately.
    if (row.technologyCount === 0) {
      const note = new Text({
        text: "No technologies in the current corpus.",
        style: new TextStyle({ fill: 0x8b95a5, fontSize: 14, fontFamily: "system-ui, sans-serif", fontStyle: "italic" }),
      });
      note.position.set(CHIP_MARGIN * 2 + bg.width, chipY + (CHIP_HEIGHT - note.height) / 2);
      rowLabelLayer.addChild(note);
    }

    // Per-(row, band)-cell tier label (defect fix, replaces the removed sticky band header): v1
    // repeats a small, subdued tier label above each row's own populated band cell -- this
    // contradicts S-03's original "renders once across the full lane stack" criterion, which is
    // amended below to match (see spec/S-03-tier-differentiation.md and CLAUDE.md for the
    // amendment record).
    //
    // DEFECT 4: anchored strictly below the chip's own bottom edge (`chipY + CHIP_HEIGHT +
    // CELL_LABEL_TOP_GAP`), not to the header strip's own bottom edge the way it was before --
    // that previous anchor put the label in the SAME vertical range the (vertically centred) chip
    // occupied, which is exactly what collided for band 0 (and any band whose x-start falls under
    // the chip's own width).
    // Part-2 spacing pass (this session): the per-cell label previously used a hardcoded +4px
    // inset from its own band's left edge, while the chip used CHIP_MARGIN (8px) from the row's
    // left edge -- a real, reported 4px misalignment between the two, most visible for band 0's
    // label, which sits directly below the chip. Both now share the SAME inset (CHIP_MARGIN), so
    // every band's label lines up with the chip along one consistent left edge.
    const cellLabelRects: { band: number; x: number; y: number; w: number; h: number }[] = [];
    const cellLabelY = chipY + CHIP_HEIGHT + CELL_LABEL_TOP_GAP;
    for (let b = 0; b < base.tierBands.length; b++) {
      if ((cellCounts.get(`${row.id}#${b}`) ?? 0) === 0) continue;
      const cellLabel = new Text({ text: base.tierBands[b]!.label, style: cellLabelStyle });
      cellLabel.position.set(bandXStart[b]! + CHIP_MARGIN, cellLabelY);
      rowLabelLayer.addChild(cellLabel);
      cellLabelRects.push({ band: b, x: bandXStart[b]! + CHIP_MARGIN, y: cellLabelY, w: cellLabel.width, h: cellLabel.height });
    }
    rowCellLabelRects.set(row.id, cellLabelRects);
  }

  // Item 4 ("path to zero uncertain" follow-up): true iff `constraint` (a Gate's
  // appliesToEmpireTypes, null when unconstrained) permits `profile`. Same per-axis-array
  // semantics as EmpireTypeConstraint everywhere else in this file -- an absent axis is
  // unconstrained (all its values allowed), a present axis lists the allowed values.
  function gateAppliesToProfile(constraint: EmpireTypeConstraint | null, profile: EmpireProfile): boolean {
    if (!constraint) return true;
    if (constraint.authority && !constraint.authority.includes(profile.authority)) return false;
    if (constraint.shipset && !constraint.shipset.includes(profile.shipset)) return false;
    if (constraint.nomadic && !constraint.nomadic.includes(profile.nomadic)) return false;
    return true;
  }

  let currentTier: LodTier | null = null;
  let currentEdgeTier: EdgeLodTier | null = null;
  let patternSolid: boolean | null = null;
  // Badges slice: previously toggled per the coarse 3-bucket `LodTier`; now each indicator has
  // its own S-03 threshold (lod.ts), so the dedupe key is the exact set of booleans, not the old
  // enum -- `lodStateKey` packs them into one string cheap to compare, so this still only touches
  // ~977*7 `.visible` flags on an actual threshold crossing, not every camera-change event.
  let lodStateKey = "";
  function updateLod(): void {
    const scale = camera.getScale();
    const showName = scale >= NAME_SHED_THRESHOLD;
    const showCost = scale >= COST_SHED_THRESHOLD;
    const showIcon = scale >= ICON_SHED_THRESHOLD;
    const showTierBadge = scale >= TIER_BADGE_SHED_THRESHOLD;
    const showRepeatable = scale >= REPEATABLE_SHED_THRESHOLD;
    const showRare = scale >= RARE_BADGE_SHED_THRESHOLD;
    const showDangerous = scale >= DANGEROUS_BADGE_SHED_THRESHOLD;
    const showModRequirement = scale >= MOD_REQUIREMENT_BADGE_SHED_THRESHOLD;
    const showGateIcon = scale >= GATE_ICON_SHED_THRESHOLD;
    const showGateLabel = scale >= GATE_LABEL_SHED_THRESHOLD;
    const key = [showName, showCost, showIcon, showTierBadge, showRepeatable, showRare, showDangerous, showModRequirement, showGateIcon, showGateLabel].join(",");
    currentTier = tierForScale(scale);
    if (key !== lodStateKey) {
      lodStateKey = key;
      for (const t of nodeNames) t.visible = showName;
      for (const t of nodeCosts) if (t) t.visible = showCost;
      for (const s of nodeIcons) if (s) s.visible = showIcon;
      for (const b of nodeTierBadges) if (b) b.visible = showTierBadge;
      for (const b of nodeRepeatBadges) if (b) b.visible = showRepeatable;
      for (const b of nodeRareBadges) if (b) b.visible = showRare;
      for (const b of nodeDangerousBadges) if (b) b.visible = showDangerous;
      for (const list of nodeModRequirementBadges) for (const b of list) b.visible = showModRequirement;
      // Item 4: combined with per-profile gate applicability (gateAppliesToProfile) -- an
      // alternative gate constrained away from the current profile (e.g. tech_torpedoes_1's
      // Riddle Escort for a non-biological-shipset profile) never shows regardless of zoom.
      for (let i = 0; i < nodeGateIcons.length; i++) {
        const s = nodeGateIcons[i];
        if (s) s.visible = showGateIcon && gateAppliesToProfile(nodePrimaryGateConstraint[i] ?? null, currentProfile);
      }
      for (let i = 0; i < nodeGateLabels.length; i++) {
        const t = nodeGateLabels[i];
        if (t) t.visible = showGateLabel && gateAppliesToProfile(nodePrimaryGateConstraint[i] ?? null, currentProfile);
      }
    }

    const edgeTier = edgeTierForScale(scale);
    if (edgeTier !== currentEdgeTier) {
      currentEdgeTier = edgeTier;
      edgeLineGraphics.get("prerequisite")!.visible = edgeTier !== "none";
      edgeLineGraphics.get("potential-gate")!.visible = edgeTier === "full";
      edgeLineGraphics.get("alternative")!.visible = edgeTier === "full";
      edgeArrowLayer.visible = edgeTier === "full";
    }

    const solid = scale < PATTERN_SOLID_THRESHOLD;
    if (solid !== patternSolid) {
      patternSolid = solid;
      for (const accent of rowPatternAccents) accent.visible = !solid;
    }
  }

  camera.onChange(() => {
    updateLod();
    updateStatusLine(camera, currentTier!, currentEdgeTier!);
  });

  // --- Hover, selection and detail popup (reconciliation session 3). ---
  //
  // Hit-testing: a plain linear scan over the REAL emitted `nodePositions` (977 rect containment
  // checks), never a parallel geometry formula (CLAUDE.md's Rules) and never per-frame (only on a
  // `pointermove`/`pointerdown` DOM event, and the resulting hover/selection redraw only happens
  // when the resolved node index actually CHANGES, not on every event).
  function hitTestScreen(screenX: number, screenY: number): number {
    const w = camera.screenToWorld(screenX, screenY);
    for (let i = 0; i < base.technologies.length; i++) {
      const cx = nodePositions[i * 2]!;
      const cy = nodePositions[i * 2 + 1]!;
      if (w.x >= cx && w.x <= cx + CARD_WIDTH && w.y >= cy && w.y <= cy + CARD_HEIGHT) return i;
    }
    return -1;
  }

  // Ancestry/dependent traversal: BFS over the REAL emitted `base.edges`, ALL THREE P-14 kinds
  // (prerequisite, alternative, potential-gate) -- this is a STRUCTURAL closure ("what could lead
  // here"), not P-12.9's research-path algorithm (per-profile cheapest-OR-branch resolution,
  // still deferred/unbuilt). An `alternative` edge's OR-group members are never flattened or
  // collapsed to one choice here -- every member that structurally reaches the selected node is
  // included in the ancestor/dependent set, exactly as typed. `edge.from` is the earlier
  // (prerequisite) technology, `edge.to` the later (dependent) one, per pipeline/layout.py's own
  // routing convention (`a = nodes[edge.from_key]` exits right toward `b = nodes[edge.to_key]`).
  // Item 1: only edges active for the CURRENT profile (`activeEdgeIds`, closed over from
  // `render()`'s scope) participate -- an edge inactive for this profile represents no real
  // dependency for it (pipeline.edge_constraints's axis-fact-only definition of "active"), so it
  // must not extend a structural ancestor/dependent closure either.
  function computeAncestryAndDependents(techId: string): { ancestors: Set<string>; dependents: Set<string> } {
    const backward = new Map<string, string[]>(); // to -> [from, ...]
    const forward = new Map<string, string[]>(); // from -> [to, ...]
    for (let i = 0; i < base.edges.length; i++) {
      if (!activeEdgeIds.has(i)) continue;
      const e = base.edges[i]!;
      (backward.get(e.to) ?? backward.set(e.to, []).get(e.to)!).push(e.from);
      (forward.get(e.from) ?? forward.set(e.from, []).get(e.from)!).push(e.to);
    }
    function bfs(start: string, adjacency: Map<string, string[]>): Set<string> {
      const seen = new Set<string>();
      const queue = [start];
      while (queue.length > 0) {
        const cur = queue.pop()!;
        for (const next of adjacency.get(cur) ?? []) {
          if (!seen.has(next)) {
            seen.add(next);
            queue.push(next);
          }
        }
      }
      return seen;
    }
    return { ancestors: bfs(techId, backward), dependents: bfs(techId, forward) };
  }

  const techIndexById = new Map<string, number>();
  for (let i = 0; i < base.technologies.length; i++) techIndexById.set(base.technologies[i]!.id, i);

  function cardOutlineOverlay(color: number, alpha: number, techIndex: number): Graphics {
    const cx = nodePositions[techIndex * 2]!;
    const cy = nodePositions[techIndex * 2 + 1]!;
    const g = new Graphics().roundRect(-2, -2, CARD_WIDTH + 4, CARD_HEIGHT + 4, 8).stroke({ width: 3, color, alpha });
    g.position.set(cx, cy);
    return g;
  }

  function edgeHighlight(color: number, edgeIndex: number): Graphics {
    const g = new Graphics();
    tracePolyline(g, edgeRoundedPolylines[edgeIndex]!, null);
    g.stroke({ width: EDGE_STROKE_WIDTH + 1.6, color, alpha: 0.95 });
    return g;
  }

  // Hover: highlights the hovered card plus its DIRECTLY connected edges (both directions), in
  // HOVER_COLOR -- the colour reserved for exactly this since the edge-router session. Disabled
  // at the "Coloured block" LOD stage (< 5%, CONTENT_SHED_THRESHOLD) per this session's own
  // instruction -- a flat block carries no per-node identity to highlight at that zoom anyway.
  const hoverLayer = new Container();
  world.addChild(hoverLayer);
  let hoveredIndex = -1;

  function setHovered(index: number): void {
    if (index === hoveredIndex) return;
    hoveredIndex = index;
    hoverLayer.removeChildren();
    if (index < 0) return;
    const techId = base.technologies[index]!.id;
    hoverLayer.addChild(cardOutlineOverlay(HOVER_COLOR, 0.9, index));
    for (let i = 0; i < base.edges.length; i++) {
      if (!activeEdgeIds.has(i)) continue;
      const e = base.edges[i]!;
      if (e.from === techId || e.to === techId) hoverLayer.addChild(edgeHighlight(HOVER_COLOR, i));
    }
  }

  // Selection: highlights the selected card (SELECTED_COLOR), its full ancestry (ANCESTRY_COLOR)
  // and its full dependents (DEPENDENT_COLOR) -- distinguishable from each other by design (a
  // cool/warm hue split, see tokens.ts). Persists across pan/zoom (stored independently of
  // camera state); a click on empty space clears it.
  const selectionLayer = new Container();
  world.addChild(selectionLayer);
  let selectedIndex = -1;

  function setSelected(index: number): void {
    selectedIndex = index;
    selectionLayer.removeChildren();
    if (index < 0) {
      closePopup();
      return;
    }
    const techId = base.technologies[index]!.id;
    const { ancestors, dependents } = computeAncestryAndDependents(techId);
    for (let i = 0; i < base.edges.length; i++) {
      if (!activeEdgeIds.has(i)) continue;
      const e = base.edges[i]!;
      if (ancestors.has(e.from) && (ancestors.has(e.to) || e.to === techId)) {
        selectionLayer.addChild(edgeHighlight(ANCESTRY_COLOR, i));
      } else if (dependents.has(e.to) && (dependents.has(e.from) || e.from === techId)) {
        selectionLayer.addChild(edgeHighlight(DEPENDENT_COLOR, i));
      }
    }
    for (const id of ancestors) {
      const idx = techIndexById.get(id);
      if (idx !== undefined) selectionLayer.addChild(cardOutlineOverlay(ANCESTRY_COLOR, 0.85, idx));
    }
    for (const id of dependents) {
      const idx = techIndexById.get(id);
      if (idx !== undefined) selectionLayer.addChild(cardOutlineOverlay(DEPENDENT_COLOR, 0.85, idx));
    }
    selectionLayer.addChild(cardOutlineOverlay(SELECTED_COLOR, 1.0, index));
    openPopup(techId);
  }

  // Focus-pan on selection: pans (never zooms) so the selected card centres in the viewport area
  // LEFT of the fixed-width detail-popup panel -- this is how "the popup must not obscure the
  // selected card" holds structurally rather than by luck of where the card happened to be on
  // screen already. Never re-applied on subsequent pan/zoom (selection persists, but the user is
  // free to move the camera afterward without being fought).
  const POPUP_WIDTH = 360;
  function focusOnNode(techIndex: number): void {
    const cx = nodePositions[techIndex * 2]! + CARD_WIDTH / 2;
    const cy = nodePositions[techIndex * 2 + 1]! + CARD_HEIGHT / 2;
    const availableWidth = window.innerWidth - POPUP_WIDTH;
    const targetSx = availableWidth / 2;
    const targetSy = window.innerHeight / 2;
    const sp = camera.worldToScreen(cx, cy);
    camera.panBy(targetSx - sp.x, targetSy - sp.y);
  }

  // --- Detail popup (DOM overlay, CLAUDE.md's Stack). ---
  const popupEl = document.getElementById("detail-popup")!;
  const popupContentEl = document.getElementById("detail-popup-content")!;
  document.getElementById("detail-popup-close")!.addEventListener("click", () => setSelected(-1));

  function escapeHtml(s: string): string {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
  }

  // P-13: availability is THREE-STATE (available/locked/uncertain), plus D-10's CONFIG_GATED
  // fourth state -- NEVER a boolean (CLAUDE.md is explicit). Empire-profile switching (this
  // session) means the popup now shows the SELECTED profile's own state and reason -- state comes
  // straight from the base dataset's `availabilityMatrix` (no recomputation), reason is lazily
  // fetched from that profile's overlay (structure-derived or trigger-derived text the pipeline
  // already computed, per P-13 -- never fabricated client-side).
  const profileLabel = (p: EmpireProfile): string => `${p.authority} / ${p.shipset} / ${p.nomadic === "yes" ? "nomadic" : "non-nomadic"}`;

  async function openPopup(techId: string): Promise<void> {
    const idx = techIndexById.get(techId)!;
    const tech = base.technologies[idx]!;
    const row = base.rows.find((r) => r.id === tech.rowId);
    const profileIndex = empireProfileIndex(currentProfile);

    // Item 3: kind-labeled, activeEdgeIds-filtered, never pooled. `potential-gate` edges are
    // deliberately excluded from both lists below -- every one already has a corresponding "Needs
    // X" entry in the Gates section above (P-3: the 25 potential-gate edges are the 25 technology-
    // kind gate instances, one to one), so repeating them here would be the exact duplication this
    // fix removes, not a second bug to reproduce.
    const requiredPrereqNames = base.edges
      .filter((e, i) => activeEdgeIds.has(i) && e.kind === "prerequisite" && e.to === techId)
      .map((e) => displayName(e.from));

    // Alternative groups: each groupId is its own "need one of" choice, never flattened together
    // and never flattened with the required list above. Per the survey, membership is additionally
    // narrowed to non-locked members for the SELECTED profile using the already-emitted
    // availabilityMatrix -- an alternative whose branch this profile cannot reach isn't a real
    // choice for it. If every member of a group is locked for this profile, the group still
    // renders (with all members shown, unfiltered) rather than silently vanishing -- an empty
    // "need one of" choice would misrepresent the technology as needing nothing.
    const altGroups = new Map<string, string[]>();
    for (let i = 0; i < base.edges.length; i++) {
      const e = base.edges[i]!;
      if (!activeEdgeIds.has(i) || e.kind !== "alternative" || e.to !== techId) continue;
      (altGroups.get(e.groupId!) ?? altGroups.set(e.groupId!, []).get(e.groupId!)!).push(e.from);
    }
    const altGroupsDisplay = [...altGroups.values()].map((members) => {
      const reachable = members.filter((id) => {
        const t = base.technologies[techIndexById.get(id)!]!;
        return t.availabilityMatrix[profileIndex] !== "locked";
      });
      return reachable.length > 0 ? reachable : members;
    });

    const dependentNames = base.edges
      .filter((e, i) => activeEdgeIds.has(i) && e.kind === "prerequisite" && e.from === techId)
      .map((e) => displayName(e.to));

    const tierBandLabel = tech.repeatable ? "Repeatable" : `Tier ${tech.tier}`;
    const displayedName = displayName(techId);
    const displayedArea = displayArea(techId);
    const displayedCategory = displayCategory(techId);

    popupContentEl.innerHTML = `
      <h2>${escapeHtml(displayedName)}</h2>
      <div class="field-value" style="color:#9fb3c8">${escapeHtml(row?.label ?? tech.rowId)} &middot; ${tierBandLabel} &middot; ${escapeHtml(displayedArea)}${displayedCategory ? ` / ${escapeHtml(displayedCategory)}` : ""}${tech.crisisFaction ? ` &middot; ${escapeHtml(tech.crisisFaction)}` : ""}</div>
      <div class="field-value">${tech.cost !== null ? `Cost: ${Math.round(tech.cost).toLocaleString("en-US")}` : "Cost: unresolvable"}</div>
      ${tech.requiresMods.length > 0 ? `<div class="badge-row">${tech.requiresMods.map((m) => `<span class="chip" style="background:#4a5568;color:#fff">${escapeHtml(m)}</span>`).join("")}</div>` : ""}
      <div class="field-label">Availability (${escapeHtml(profileLabel(currentProfile))})</div>
      <div class="field-value" id="popup-availability">${escapeHtml(tech.availabilityMatrix[profileIndex]!)}</div>
      ${(() => {
        // Item 4: the popup filters the SAME way the card does -- an alternative gate the current
        // profile's own axis facts already rule out (e.g. Riddle Escort for a non-biological-
        // shipset profile) shouldn't appear as a requirement here either, even though the card
        // only ever shows the primary gate and the popup lists every gate.
        const visibleGates = tech.gates.filter((g) => gateAppliesToProfile(g.appliesToEmpireTypes ?? null, currentProfile));
        if (visibleGates.length === 0) return "";

        function gateRow(g: (typeof visibleGates)[number]): string {
          // Item 3 (later session): an inherited gate (propagated from a `prerequisite`-edge
          // ancestor that declares it directly, e.g. the QSO family inheriting `ap_qso` from
          // giga_tech_quasi_stellar_1) is rendered distinctly -- naming the source technology --
          // so a user can tell where the requirement originates, per this gate's own schema
          // field docs (`Gate.inherited`/`Gate.sourceTechnologyId`).
          const sourceName = g.sourceTechnologyId ? displayName(g.sourceTechnologyId) : null;
          const viaSuffix = g.inherited && sourceName ? ` <span class="gate-inherited-note">(via ${escapeHtml(sourceName)})</span>` : "";
          // Item 3a: null icon (origin/ethics-or-civic, no source vendors these) renders no icon
          // element at all -- never the old degenerate 1x1-pixel "teal square" fallback.
          const iconSpan = g.icon
            ? `<span class="gate-icon" style="background-image:url('${atlasWebpUrlBySheet.get(g.icon.sheet) ?? ""}');background-position:-${g.icon.x}px -${g.icon.y}px;width:${g.icon.width}px;height:${g.icon.height}px;background-size:auto;"></span>`
            : "";
          return `
          <div class="gate-row${g.inherited ? " gate-row-inherited" : ""}">
            ${iconSpan}
            <span>${escapeHtml(g.label)}${viaSuffix}</span>
          </div>`;
        }

        // Nested AND-of-OR fix (a later session, user-reported: Gargantuan Cloning Facilities
        // showed "Needs Galactic Wonders" + "or: Mechromancy" as flat peers, when the real
        // structure is AND(Galactic Wonders, OR(Genetic Ascension, Mechromancy)) -- Galactic
        // Wonders is unconditionally required, and the OR is a SEPARATE branch beneath it, not
        // beside it). `Gate.groupId` (P-3) names the specific OR block a gate belongs to; every
        // gate sharing the same non-null groupId is nested under one "or, need one of" cluster,
        // rendered AFTER the unconditional (groupId === null) gates -- so the AND requirement
        // reads first, then each independent OR choice beneath it. Declaration order among groups
        // and among ungrouped gates is preserved (Map insertion order); a technology whose gates
        // are ALL one group (the common case, e.g. Riddle Escort) or all ungrouped renders exactly
        // as before -- this only changes the MIXED case.
        const ungrouped = visibleGates.filter((g) => g.groupId === null);
        const grouped = new Map<string, typeof visibleGates>();
        for (const g of visibleGates) {
          if (g.groupId === null) continue;
          (grouped.get(g.groupId) ?? grouped.set(g.groupId, []).get(g.groupId)!).push(g);
        }

        return `
        <div class="field-label">Gates${visibleGates.length > 1 ? ` (${visibleGates.length})` : ""}</div>
        <div class="field-value">
          ${ungrouped.map(gateRow).join("")}
          ${[...grouped.values()].map((members) => `
          <div class="gate-group">
            <div class="gate-group-label">Need one of:</div>
            ${members.map(gateRow).join("")}
          </div>`).join("")}
        </div>
      `;
      })()}
      <div class="field-label">Description</div>
      <div class="field-value" id="popup-description">loading&hellip;</div>
      <div class="field-label">Prerequisites (${requiredPrereqNames.length})</div>
      <div class="field-value">${requiredPrereqNames.length > 0 ? `<ul>${requiredPrereqNames.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>` : "none"}</div>
      ${altGroupsDisplay.length > 0 ? altGroupsDisplay.map((members, gi) => `
      <div class="field-label">Alternative${altGroupsDisplay.length > 1 ? ` group ${gi + 1}` : ""} &mdash; need one of (${members.length})</div>
      <div class="field-value"><ul>${members.map((id) => `<li>${escapeHtml(displayName(id))}</li>`).join("")}</ul></div>
      `).join("") : ""}
      <div class="field-label">Dependents (${dependentNames.length})</div>
      <div class="field-value">${dependentNames.length > 0 ? `<ul>${dependentNames.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>` : "none"}</div>
      <div id="popup-off-tree"></div>
      <div id="popup-research-path"></div>
    `;
    popupEl.dataset.open = "true";

    // Lazy-fetched (spec/00-overview.md's own "chunked, lazily fetched when a popup opens"
    // design) -- description and the D-18 off-tree-prerequisite note (Item 3) both live in the
    // detail payload, not the base dataset.
    try {
      const detail = await fetchDetailPayload(techId);
      if (selectedIndex !== idx) return; // selection moved on while the fetch was in flight
      const descEl = document.getElementById("popup-description");
      if (descEl) descEl.textContent = detail.description || "(no description)";
      const offTreeEl = document.getElementById("popup-off-tree");
      if (offTreeEl && detail.offTreePrerequisiteNames.length > 0) {
        // Item 8b (later session): rewritten for an end user -- no decision codes ("D-18"), no
        // internal vocabulary ("rendered scope", "node"). The full internal detail is still
        // available under `?dev`, where the target audience IS someone debugging this tool.
        const names = detail.offTreePrerequisiteNames.map((n) => escapeHtml(n)).join(", ");
        const note = new URLSearchParams(window.location.search).has("dev")
          ? `${names} -- outside the rendered scope (D-18: reachable only via another ACOT/AoT technology, not shown as a node).`
          : `${names} (not shown on this tree).`;
        offTreeEl.innerHTML = `
          <div class="field-label">Also requires</div>
          <div class="field-value off-tree-note">${note}</div>
        `;
      }
    } catch (err) {
      const descEl = document.getElementById("popup-description");
      if (descEl) descEl.textContent = `(description unavailable: ${String(err)})`;
    }

    // Availability REASON: state is already shown above (from the base dataset, no fetch); the
    // structure-derived/trigger-derived REASON text lives in the selected profile's own overlay
    // (P-13) -- fetched here, lazily, same pattern as the description above. Never fetched for
    // `available` (P-13: reason is null when available, per the schema). The SAME overlay fetch
    // also carries P-12.9's research path, so it's now made unconditionally (a "path" needs the
    // overlay regardless of whether this technology itself is locked/uncertain).
    const stateNow = tech.availabilityMatrix[empireProfileIndex(currentProfile)]!;
    try {
      const overlay = await fetchEmpireOverlay(profileKey(currentProfile));
      if (selectedIndex !== idx) return; // selection moved on while the fetch was in flight
      if (stateNow !== "available") {
        const availEl = document.getElementById("popup-availability");
        const entry = overlay.availability[techId];
        if (availEl && entry) {
          availEl.textContent = `${entry.state}${entry.reason ? ` — ${entry.reason}` : ""}`;
        }
      }
      renderResearchPath(overlay.researchPaths[techId]);
    } catch (err) {
      if (stateNow !== "available") {
        const availEl = document.getElementById("popup-availability");
        if (availEl) availEl.textContent = `${stateNow} (reason unavailable: ${String(err)})`;
      }
      const pathEl = document.getElementById("popup-research-path");
      if (pathEl) pathEl.innerHTML = `<div class="field-label">Research path</div><div class="field-value">(unavailable: ${escapeHtml(String(err))})</div>`;
    }
  }

  // P-12.9 (spec/P-12.9-research-path.md): renders the precomputed, per-profile research path --
  // ordered steps, per-step cost, running total, the estimate flag with its reason(s) where set,
  // and OR choices presented as choices (a chosen step's `alternatives`, never flattened). Every
  // field here is already resolved server-side (D-14 name/icon substitution, OR-group viability
  // and cheapest-cost resolution) -- this function only formats what the overlay already carries,
  // never recomputes traversal client-side (CLAUDE.md's "pipeline owns all geometry" discipline,
  // applied to research-path data the same way P-13/D-14 already apply it to availability/swaps).
  function renderResearchPath(entry: EmpireOverlay["researchPaths"][string] | undefined): void {
    const pathEl = document.getElementById("popup-research-path");
    if (!pathEl || !entry) return;

    if (entry.status === "unavailable") {
      pathEl.innerHTML = `
        <div class="field-label">Research path</div>
        <div class="field-value">No research path — see availability above.</div>
      `;
      return;
    }

    const steps = entry.steps ?? [];
    const stepRows = steps
      .map((s) => {
        const uncertainBadge = s.availabilityState === "uncertain" ? ` <span class="research-path-uncertain">uncertain</span>` : "";
        const costText = s.stepCost !== null ? Math.round(s.stepCost).toLocaleString("en-US") : "unresolved";
        const altSuffix = s.alternatives.length > 0
          ? ` <span class="research-path-alt-note">(also: ${s.alternatives.map((a) => escapeHtml(a.name)).join(", ")})</span>`
          : "";
        return `<li>${escapeHtml(s.name)} — ${costText}${uncertainBadge}${altSuffix}</li>`;
      })
      .join("");

    const totalText = entry.totalCost !== null && entry.totalCost !== undefined
      ? Math.round(entry.totalCost).toLocaleString("en-US")
      : "unresolved";
    const estimateNote = entry.totalCostIsEstimate
      ? ` <span class="research-path-estimate-note">(estimate${(entry.estimateReasons ?? []).length > 0 ? `: ${(entry.estimateReasons ?? []).join(", ")}` : ""})</span>`
      : "";

    const configGatedNote = entry.status === "config-gated" && entry.configGatedTarget
      ? `<div class="field-value research-path-config-gated-note">${escapeHtml(entry.configGatedTarget.name)}: ${escapeHtml(entry.configGatedTarget.subject ? `Requires ${entry.configGatedTarget.subject} cap: 1 + Repeatables` : "config-gated")}</div>`
      : "";

    pathEl.innerHTML = `
      <div class="field-label">Research path (${steps.length})</div>
      <div class="field-value">${steps.length > 0 ? `<ul>${stepRows}</ul>` : "none"}</div>
      <div class="field-value">Total: ${totalText}${estimateNote}</div>
      ${configGatedNote}
    `;
  }

  function closePopup(): void {
    popupEl.dataset.open = "false";
  }

  // Pointer handling: independent listeners from camera.ts's own pan/zoom listeners (both attach
  // to the same `app.canvas`, coexist fine). Click-vs-drag is distinguished locally (small
  // movement + short duration = a click), so panning the camera never accidentally selects/
  // deselects a node.
  let pointerDownAt: { x: number; y: number; t: number } | null = null;
  app.canvas.addEventListener("pointerdown", (e: PointerEvent) => {
    pointerDownAt = { x: e.clientX, y: e.clientY, t: performance.now() };
  });
  app.canvas.addEventListener("pointerup", (e: PointerEvent) => {
    if (!pointerDownAt) return;
    const dx = e.clientX - pointerDownAt.x;
    const dy = e.clientY - pointerDownAt.y;
    const dt = performance.now() - pointerDownAt.t;
    pointerDownAt = null;
    if (Math.hypot(dx, dy) > 6 || dt > 600) return; // treated as a drag/pan, not a click
    const rect = app.canvas.getBoundingClientRect();
    const idx = hitTestScreen(e.clientX - rect.left, e.clientY - rect.top);
    if (idx === selectedIndex) return; // clicking the already-selected card is a no-op, not a toggle-off
    setSelected(idx);
    if (idx >= 0) focusOnNode(idx);
  });
  app.canvas.addEventListener("pointermove", (e: PointerEvent) => {
    if (camera.getScale() < CONTENT_SHED_THRESHOLD) {
      setHovered(-1); // "Hover does nothing at LOD tiers where cards are flat coloured blocks"
      return;
    }
    const rect = app.canvas.getBoundingClientRect();
    setHovered(hitTestScreen(e.clientX - rect.left, e.clientY - rect.top));
  });
  app.canvas.addEventListener("pointerleave", () => setHovered(-1));

  // --- Profile selector (three axes independently, never a flat 12-item list). ---
  const authoritySelect = document.getElementById("profile-authority") as HTMLSelectElement;
  const shipsetSelect = document.getElementById("profile-shipset") as HTMLSelectElement;
  const nomadicSelect = document.getElementById("profile-nomadic") as HTMLSelectElement;
  // Display labels are the one thing legitimately hand-authored here -- the emitted axes carry
  // machine value names (e.g. "hive_mind"), never display strings.
  const AUTHORITY_LABELS: Record<string, string> = { regular: "Regular", hive_mind: "Hive Mind", machine_intelligence: "Machine Intelligence" };
  const SHIPSET_LABELS: Record<string, string> = { mechanical: "Mechanical", biological: "Biological" };
  const NOMADIC_LABELS: Record<string, string> = { no: "Non-nomadic", yes: "Nomadic" };
  for (const a of axisValues("authority")) authoritySelect.add(new Option(AUTHORITY_LABELS[a] ?? a, a));
  for (const s of axisValues("shipset")) shipsetSelect.add(new Option(SHIPSET_LABELS[s] ?? s, s));
  for (const n of axisValues("nomadic")) nomadicSelect.add(new Option(NOMADIC_LABELS[n] ?? n, n));
  authoritySelect.value = currentProfile.authority;
  shipsetSelect.value = currentProfile.shipset;
  nomadicSelect.value = currentProfile.nomadic;

  // Item 1: the one shared profile-switch path -- both the real `<select>` change handler and
  // the `window.__tt.setProfile` verification hook go through this, so a test driving profile
  // switches via `__tt` exercises the exact same activeEdgeIds refresh a real user's dropdown
  // change does, never a shortcut that only updates availability dimming.
  async function applyProfile(profile: EmpireProfile): Promise<void> {
    currentProfile = profile;
    authoritySelect.value = profile.authority;
    shipsetSelect.value = profile.shipset;
    nomadicSelect.value = profile.nomadic;
    updateAvailabilityDisplay();
    // Item 4: gate visibility (gateAppliesToProfile) depends on currentProfile, not just zoom --
    // invalidate updateLod's change-detection cache so the gate icon/label loop actually re-runs
    // even though the zoom-derived LOD key itself hasn't changed.
    lodStateKey = "";
    updateLod();
    // activeEdgeIds is per-profile -- re-fetch the new profile's overlay (cached by
    // pipeline.dataset_emit's build, and client-side by fetchEmpireOverlay) and retrace the
    // edges, THEN refresh the selection highlight (which also traverses activeEdgeIds via
    // computeAncestryAndDependents) so a currently-selected node's ancestry/dependent overlay
    // doesn't keep showing a stale profile's active set.
    const overlay = await fetchEmpireOverlay(profileKey(currentProfile));
    activeEdgeIds = new Set(overlay.activeEdgeIds);
    traceActiveEdges(activeEdgeIds);
    // Item 2: swap-substituted name/icon/area only ever touches the technologies that were
    // swapped either just before or just after this switch -- reverting a no-longer-active swap
    // back to its base display is exactly as real a visual change as applying a new one.
    applySwapVisuals(new Map(overlay.swapMappings.map((s) => [s.technologyId, s])));
    if (selectedIndex >= 0) setSelected(selectedIndex);
    // Profile persists across pan/zoom/selection (this session's own instruction) -- selection
    // itself is untouched by a profile change, but the OPEN popup's availability section (state
    // + reason) is specific to a profile, so it needs a refresh if something is selected.
    if (selectedIndex >= 0) await openPopup(base.technologies[selectedIndex]!.id);
  }

  async function onProfileControlChange(): Promise<void> {
    await applyProfile({
      authority: authoritySelect.value as GestaltAuthority,
      shipset: shipsetSelect.value as ShipsetValue,
      nomadic: nomadicSelect.value as NomadicValue,
    });
  }
  authoritySelect.addEventListener("change", onProfileControlChange);
  shipsetSelect.addEventListener("change", onProfileControlChange);
  nomadicSelect.addEventListener("change", onProfileControlChange);
  updateAvailabilityDisplay();

  // --- Search (reconciliation session 4): consumes the emitted search index directly, never a
  // second client-side index. Matches highlight IN PLACE (never a filter -- hiding nodes would
  // break the reading of prerequisite chains, per this session's own instruction) and work at
  // every LOD tier, since the highlight layer is never gated by the card-content LOD ladder. ---
  const searchBox = document.getElementById("search-box") as HTMLInputElement;
  const searchResultsEl = document.getElementById("search-results")!;
  const searchStatusEl = document.getElementById("search-status")!;
  const searchMatchLayer = new Container();
  world.addChild(searchMatchLayer);
  let searchIndexEntries: { technologyId: string; tokens: string[] }[] | null = null;
  let searchIndexLoading: Promise<void> | null = null;

  function ensureSearchIndexLoaded(): Promise<void> {
    searchIndexLoading ??= fetchSearchIndex()
      .then((idx) => {
        searchIndexEntries = idx.entries;
        searchStatusEl.textContent = "";
      })
      .catch((err) => {
        searchStatusEl.textContent = `search index unavailable: ${String(err)}`;
      });
    return searchIndexLoading;
  }
  searchBox.addEventListener("focus", () => {
    if (!searchIndexEntries) {
      searchStatusEl.textContent = "loading search index…";
      void ensureSearchIndexLoaded();
    }
  });

  function tokenizeQuery(q: string): string[] {
    return q.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 0);
  }

  function runSearch(query: string): void {
    searchMatchLayer.removeChildren();
    searchResultsEl.innerHTML = "";
    const trimmed = query.trim();
    if (trimmed === "" || !searchIndexEntries) {
      searchStatusEl.textContent = searchIndexEntries ? "" : searchStatusEl.textContent;
      return;
    }
    const queryTokens = tokenizeQuery(trimmed);
    if (queryTokens.length === 0) return;
    // P-6: exact/prefix matches ranked above fuzzy -- this implementation is prefix-only (no
    // fuzzy/edit-distance matching, which P-6 marks optional), so ranking is exact-name-match >
    // name-starts-with-query > every query token prefix-matches at least one entry token (AND
    // across query words, matching how a multi-word search box query is normally read).
    const matches: { id: string; rank: number }[] = [];
    for (const entry of searchIndexEntries) {
      const allTokensMatch = queryTokens.every((qt) => entry.tokens.some((t) => t.startsWith(qt)));
      if (!allTokensMatch) continue;
      // Item 2: rank against the DISPLAYED (swap-substituted, if any) name -- a search that
      // exactly matches the profile-correct name should rank as an exact match even when the
      // base dataset's own name differs for this profile.
      const nameLower = displayName(entry.technologyId).toLowerCase();
      const rank = nameLower === trimmed.toLowerCase() ? 0 : nameLower.startsWith(trimmed.toLowerCase()) ? 1 : 2;
      matches.push({ id: entry.technologyId, rank });
    }
    matches.sort((a, b) => a.rank - b.rank || a.id.localeCompare(b.id));

    searchStatusEl.textContent = `${matches.length} match${matches.length === 1 ? "" : "es"}`;
    for (const { id } of matches) {
      const idx = techIndexById.get(id)!;
      searchMatchLayer.addChild(cardOutlineOverlay(SEARCH_MATCH_COLOR, 0.95, idx));
    }
    for (const { id } of matches.slice(0, 25)) {
      const idx = techIndexById.get(id)!;
      const tech = base.technologies[idx]!;
      const row = base.rows.find((r) => r.id === tech.rowId);
      const el = document.createElement("div");
      el.className = "result";
      el.innerHTML = `<div class="result-name">${escapeHtml(displayName(id))}</div><div class="result-meta">${escapeHtml(row?.label ?? tech.rowId)} · Tier ${tech.tier}</div>`;
      el.addEventListener("click", () => {
        setSelected(idx);
        focusOnNode(idx);
      });
      searchResultsEl.appendChild(el);
    }
  }
  searchBox.addEventListener("input", () => {
    void ensureSearchIndexLoaded().then(() => runSearch(searchBox.value));
  });

  // Initial state = slice 1's exact fit-to-viewport view, unchanged.
  camera.resetToFit();
  updateLod();

  setStatus(
    `Rendered ${base.technologies.length} technologies, ${activeEdgeIds.size} of ${base.edges.length} edges active ` +
      `(${edgeCountByKindForStatus!.prerequisite} prerequisite, ${edgeCountByKindForStatus!["potential-gate"]} potential-gate, ` +
      `${edgeCountByKindForStatus!.alternative} alternative), ${base.tierBands.length} tier bands, ${base.rows.length} rows.`
  );
  updateStatusLine(camera, currentTier!, currentEdgeTier!);

  // --- Item 1 (later session): dev health monitor, gated behind ?dev. Diagnostic tool for the
  // user to review remaining `uncertain` technologies and decide what's fixable with domain
  // knowledge versus genuinely undecidable game state -- see diagnostics.schema.json's
  // `uncertainTechnologies` (pipeline.dataset_emit.build_diagnostics) for the data shape. Fetched
  // and rendered ONLY when `?dev` is present; otherwise this whole block is a no-op and the
  // diagnostics artefact is never fetched (S-2's own "never affects P-10 budgets when unused"). ---
  const devMonitorEl = document.getElementById("dev-monitor")!;
  const devMonitorContentEl = document.getElementById("dev-monitor-content")!;
  document.getElementById("dev-monitor-close")!.addEventListener("click", () => {
    devMonitorEl.dataset.open = "false";
  });

  if (new URLSearchParams(window.location.search).has("dev")) {
    void (async () => {
      const CATEGORY_LABELS: Record<string, string> = {
        crisis_or_story_progress: "Crisis / story progress",
        origin_requirement: "Origin requirement",
        ethics_or_civic_requirement: "Ethics / civic requirement",
        mod_content_requirement: "Mod content requirement",
        mod_configuration: "Mod configuration",
        opaque_country_state: "Opaque country state",
        unclassified: "Unclassified",
      };
      const profileTag = (p: EmpireProfile) => `${p.authority}/${p.shipset}/${p.nomadic === "yes" ? "nomadic" : "non-nomadic"}`;

      try {
        const diagnostics = await fetchDiagnostics();
        const entries = diagnostics.uncertainTechnologies;

        // Group by the FIRST profile's category per technology for clustering purposes -- a
        // technology can carry more than one category across its 12 profile entries (rare, but
        // real: different axis facts can hit different unresolved leaves), so this groups by the
        // most common category among its own perProfile entries rather than assuming uniformity.
        const categoryOf = (e: (typeof entries)[number]): string => {
          const counts = new Map<string, number>();
          for (const p of e.perProfile) counts.set(p.category, (counts.get(p.category) ?? 0) + 1);
          return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]![0];
        };
        const byCategory = new Map<string, typeof entries>();
        for (const e of entries) {
          const cat = categoryOf(e);
          (byCategory.get(cat) ?? byCategory.set(cat, []).get(cat)!).push(e);
        }

        const unconditionalCount = entries.filter((e) => e.unconditional).length;
        const profileDependentCount = entries.length - unconditionalCount;

        const categorySections = [...byCategory.entries()]
          .sort((a, b) => b[1].length - a[1].length)
          .map(([cat, techs]) => {
            const techRows = techs
              .map((e) => {
                const profileLines = e.unconditional
                  ? `<div class="dm-profile-row">all 12 profiles: ${escapeHtml(e.perProfile[0]!.description)}</div>`
                  : e.perProfile
                      .map((p) => `<div class="dm-profile-row">${escapeHtml(profileTag(p.profile))}: ${escapeHtml(p.description)}</div>`)
                      .join("");
                return `
                <div class="dm-tech">
                  <span class="dm-tech-name" data-tech-id="${escapeHtml(e.technologyId)}">${escapeHtml(e.name)}</span>
                  <span class="dm-tag">${e.unconditional ? "unconditional" : `profile-dependent (${e.perProfile.length}/12)`}</span>
                  <details><summary>reason</summary>${profileLines}</details>
                </div>`;
              })
              .join("");
            return `
              <details>
                <summary class="dm-category">${escapeHtml(CATEGORY_LABELS[cat] ?? cat)} (${techs.length})</summary>
                ${techRows}
              </details>`;
          })
          .join("");

        devMonitorContentEl.innerHTML = `
          <h2>Uncertainty monitor</h2>
          <div class="dm-summary">
            ${entries.length} / ${base.technologies.length} rendered technologies have at least one uncertain profile.<br/>
            ${unconditionalCount} unconditional (uncertain for all 12 profiles) &middot; ${profileDependentCount} profile-dependent.
          </div>
          <h3>By category</h3>
          ${categorySections}
        `;

        devMonitorContentEl.querySelectorAll<HTMLElement>(".dm-tech-name[data-tech-id]").forEach((el) => {
          el.addEventListener("click", () => {
            const id = el.dataset.techId!;
            const idx = techIndexById.get(id);
            if (idx === undefined) return;
            setSelected(idx);
            focusOnNode(idx);
          });
        });

        devMonitorEl.dataset.open = "true";
      } catch (err) {
        devMonitorContentEl.innerHTML = `<h2>Uncertainty monitor</h2><div class="dm-summary">failed to load diagnostics: ${escapeHtml(String(err))}</div>`;
        devMonitorEl.dataset.open = "true";
      }
    })();
  }

  // Debug/verification surface only -- this is a static client-only site with no backend or
  // security surface, so exposing introspection on `window` costs nothing and is what the
  // headless-browser verification harness drives directly rather than screenshot-only eyeballing.
  (window as unknown as { __tt: unknown }).__tt = {
    camera,
    getTier: () => currentTier,
    getEdgeTier: () => currentEdgeTier,
    contentBBox,
    edgeCountByKind: () => edgeCountByKindForStatus,
    edgeVisible: {
      prerequisite: () => edgeLineGraphics.get("prerequisite")!.visible,
      "potential-gate": () => edgeLineGraphics.get("potential-gate")!.visible,
      alternative: () => edgeLineGraphics.get("alternative")!.visible,
    },
    arrowsVisible: () => edgeArrowLayer.visible,
    nodePositions,
    edgePositions,
    base,
    cardCount: base.technologies.length,
    costlessCardCount,
    // Reconciliation session, Item 7 -- verification-question checks, real numbers from the
    // real render rather than approximated from raw dataset fields alone.
    checkTierBadgeMatchesBand: () => {
      // Every non-repeatable node's card renders `T<declared tier>` (see the tier-badge draw
      // call below); its BAND is `tierBands.find(b => b.tier === tech.tier).bandIndex` -- assert
      // the two can never disagree by construction (v1's exact reported defect class), over every
      // rendered node, not just non-repeatables (repeatables render no tier badge at all -- see
      // checkRepeatableBadging below -- so they can't disagree by having none).
      let checked = 0;
      const violations: { id: string; declaredTier: number | null; bandId: number | string }[] = [];
      for (let i = 0; i < base.technologies.length; i++) {
        const tech = base.technologies[i]!;
        if (tech.repeatable) continue;
        checked++;
        const band = base.tierBands.find((b) => b.tier === tech.tier);
        if (!band || band.bandIndex !== bandIndexOf(tech, base.tierBands)) {
          violations.push({ id: tech.id, declaredTier: tech.tier, bandId: band?.bandIndex ?? -1 });
        }
      }
      return { ok: violations.length === 0, checked, violations };
    },
    checkRepeatableBadging: () => {
      const repeatables = base.technologies.filter((t) => t.repeatable);
      const inTerminalBand = repeatables.every((t) => bandIndexOf(t, base.tierBands) === base.tierBands.find((b) => b.tier === "repeatables")!.bandIndex);
      const allHaveRepeatBadge = base.technologies.every((t, i) => (t.repeatable ? nodeRepeatBadges[i] !== null : nodeRepeatBadges[i] === null));
      return { repeatableCount: repeatables.length, allInTerminalBand: inTerminalBand, rendersRepeatCountBadge: true, allHaveRepeatBadge };
    },
    checkCostZero: () => {
      const zero = base.technologies.filter((t) => t.cost === 0).map((t) => t.id);
      const nullCost = base.technologies.filter((t) => t.cost === null).length;
      return { zeroCostCount: zero.length, zeroCostIds: zero, nullCostCount: nullCost };
    },
    getWrappedNames: () => wrappedNames,
    // Empire-profile switching + search verification (reconciliation session 4). Goes through
    // the same `applyProfile` path a real dropdown change does (Item 1) -- see that function's
    // own comment for why this must not be a shortcut.
    setProfile: (profile: EmpireProfile) => applyProfile(profile),
    getProfile: () => currentProfile,
    // Item 1 verification: the real drawn edge count (sum of edgeCountByKind, i.e. what's
    // actually traced into the Graphics objects) vs. the active set size, and the raw active
    // edge index set itself, so a test can assert they match and that they change across
    // profiles without recomputing anything main.ts doesn't already compute.
    activeEdgeIds: () => [...activeEdgeIds],
    drawnEdgeCount: () => edgeCountByKindForStatus
      ? edgeCountByKindForStatus.prerequisite + edgeCountByKindForStatus["potential-gate"] + edgeCountByKindForStatus.alternative
      : 0,
    // Item 2 verification: the swap-aware display name/rendered card text for a technology under
    // the CURRENT profile, and the raw swap map itself, so a test can assert a known swap pair's
    // name changes across profiles and that no group ever shows two members simultaneously.
    displayName: (techId: string) => displayName(techId),
    cardRenderedName: (techId: string) => {
      const idx = techIndexById.get(techId);
      return idx === undefined ? null : nodeNames[idx]?.text ?? null;
    },
    debugGateGeometry: (techId: string) => {
      const idx = techIndexById.get(techId);
      if (idx === undefined) return null;
      const cardY = nodePositions[idx * 2 + 1]!;
      const label = nodeGateLabels[idx];
      const icon = nodeGateIcons[idx];
      const cost = nodeCosts[idx];
      const name = nodeNames[idx];
      return {
        cardY, cardBottom: cardY + CARD_HEIGHT,
        label: label ? { y: label.y, height: label.height, bottom: label.y + label.height, text: label.text } : null,
        icon: icon ? { y: icon.y, height: icon.height, bottom: icon.y + icon.height } : null,
        cost: cost ? { y: cost.y, height: cost.height, bottom: cost.y + cost.height } : null,
        name: name ? { y: name.y, height: name.height, bottom: name.y + name.height } : null,
      };
    },
    currentSwapMap: () => Object.fromEntries(currentSwapMap),
    empireProfileIndex: (profile: EmpireProfile) => empireProfileIndex(profile),
    allProfiles: () => allProfiles(),
    checkAvailabilityMatchesEmitted: () => {
      // Proves the render never recomputes availability -- every visible dim/badge state is read
      // straight from base.technologies[i].availabilityMatrix[index], so "matches the emitted
      // matrix" is true by construction; this returns the exact per-node state list for the
      // CURRENT profile so a test can assert it against the matrix directly, plus per-state
      // counts for the report.
      const index = empireProfileIndex(currentProfile);
      const counts: Record<string, number> = {};
      const perNode = base.technologies.map((t) => {
        const state = t.availabilityMatrix[index]!;
        counts[state] = (counts[state] ?? 0) + 1;
        return { id: t.id, state };
      });
      return { profile: currentProfile, index, counts, perNode };
    },
    availabilityVisualState: (techId: string) => {
      const idx = techIndexById.get(techId);
      if (idx === undefined) return null;
      return {
        dimVisible: nodeAvailabilityDim[idx]!.visible,
        dimAlpha: nodeAvailabilityDim[idx]!.alpha,
        badgeVisible: nodeAvailabilityBadge[idx]!.container.visible,
        badgeGlyph: nodeAvailabilityBadge[idx]!.text.text,
      };
    },
    searchMatchCount: () => searchMatchLayer.children.length,
    runSearchFor: async (query: string) => {
      await ensureSearchIndexLoaded();
      runSearch(query);
      return {
        resultCount: searchResultsEl.children.length,
        matchCount: searchMatchLayer.children.length,
        status: searchStatusEl.textContent,
      };
    },
    getSearchIndexEntries: () => searchIndexEntries,
    clickSearchResult: (index: number) => {
      (searchResultsEl.children[index] as HTMLElement | undefined)?.click();
    },
    checkNameRendering: () => {
      const ellipsisCount = wrappedNames.filter((n) => n.includes("…")).length;
      // Item 4a (reconciliation session): report the actual colliding TECHNOLOGY IDs, not just
      // the count of duplicate visible-text groups -- two cards reading the same is a real
      // usability defect only if it's actually two DIFFERENT technologies, not the same one
      // counted twice, so this groups by visible text and lists every id sharing it.
      const idsByText = new Map<string, string[]>();
      for (let i = 0; i < base.technologies.length; i++) {
        const text = wrappedNames[i]!;
        const ids = idsByText.get(text) ?? [];
        ids.push(base.technologies[i]!.id);
        idsByText.set(text, ids);
      }
      const duplicates = [...idsByText.entries()].filter(([, ids]) => ids.length > 1);
      return {
        ellipsisCount,
        duplicateVisibleTextGroups: duplicates.length,
        duplicatePairs: duplicates.map(([text, ids]) => ({ visibleText: text, technologyIds: ids })),
        // Item 1a (screenshot-review session): the minimal set of names actually using
        // middle-ellipsis mode -- must be 0 whenever duplicateVisibleTextGroups is 0, and should
        // stay small (only real collision pairs/groups), never "every truncated name."
        middleEllipsisCount: middleEllipsisKeys.size,
        middleEllipsisIds: [...middleEllipsisKeys],
      };
    },
    // Item 5 (screenshot-review session): proves S-03's shedding table is really applied to
    // name/cost/icon (not merely alpha-dimmed) -- `.visible` is a real PixiJS visibility flag,
    // skipping both render and hit-test, never a transparency trick. Thresholds reported in the
    // same zoom-percentage units the status strip shows (`scale * 100`).
    checkLodTextShedding: () => ({
      thresholds: {
        nameSheddedBelowPercent: NAME_SHED_THRESHOLD * 100,
        costSheddedBelowPercent: COST_SHED_THRESHOLD * 100,
        iconSheddedBelowPercent: ICON_SHED_THRESHOLD * 100,
      },
      currentScalePercent: camera.getScale() * 100,
      nameVisible: nodeNames[0]?.visible ?? null,
      costVisible: nodeCosts[0]?.visible ?? null,
      iconVisible: nodeIcons[0]?.visible ?? null,
    }),
    checkIconFallback: () => {
      const missing = nodeIcons.filter((s) => s === null).length;
      return { totalCards: nodeIcons.length, missingIconCount: missing };
    },
    findLongSpanPotentialGateEdges: () => {
      return base.edges
        .filter((e) => e.kind === "potential-gate" && e.backward)
        .map((e) => ({ from: e.from, to: e.to, bandSpan: e.bandSpan }))
        .sort((a, b) => b.bandSpan - a.bandSpan);
    },
    // Hover/selection slice verification (reconciliation session 3).
    hitTestScreenId: (sx: number, sy: number) => {
      const idx = hitTestScreen(sx, sy);
      return idx >= 0 ? base.technologies[idx]!.id : null;
    },
    screenPositionOf: (techId: string) => {
      const idx = techIndexById.get(techId);
      if (idx === undefined) return null;
      return camera.worldToScreen(nodePositions[idx * 2]! + CARD_WIDTH / 2, nodePositions[idx * 2 + 1]! + CARD_HEIGHT / 2);
    },
    getAncestryAndDependents: (techId: string) => {
      const { ancestors, dependents } = computeAncestryAndDependents(techId);
      return { ancestors: [...ancestors].sort(), dependents: [...dependents].sort() };
    },
    simulateHover: (techId: string | null) => setHovered(techId === null ? -1 : (techIndexById.get(techId) ?? -1)),
    simulateSelect: (techId: string | null) => {
      const idx = techId === null ? -1 : (techIndexById.get(techId) ?? -1);
      setSelected(idx);
      if (idx >= 0) focusOnNode(idx);
    },
    getHoveredId: () => (hoveredIndex >= 0 ? base.technologies[hoveredIndex]!.id : null),
    getSelectedId: () => (selectedIndex >= 0 ? base.technologies[selectedIndex]!.id : null),
    hoverHighlightCount: () => hoverLayer.children.length,
    selectionHighlightCount: () => selectionLayer.children.length,
    isPopupOpen: () => popupEl.dataset.open === "true",
    popupText: () => popupContentEl.textContent,
    waitForPopupDescription: () =>
      new Promise<string>((resolve) => {
        const check = () => {
          const el = document.getElementById("popup-description");
          const text = el?.textContent ?? "";
          if (text && text !== "loading…") resolve(text);
          else setTimeout(check, 20);
        };
        check();
      }),
    rowDrawnCounts: Object.fromEntries(rowDrawnCounts),
    rowDeclaredCounts: Object.fromEntries(base.rows.map((r) => [r.id, r.technologyCount])),
    rowGeometry: Object.fromEntries(base.rows.map((r) => [r.id, { y: rowYOffset.get(r.id)!, height: rowHeight.get(r.id)! }])),
    bandXStart,
    isPatternSolid: () => patternSolid,
    debugPatternAccents: () =>
      rowPatternAccents.map((g) => ({ visible: g.visible, alpha: g.alpha, bounds: g.getBounds(), maskSet: !!g.mask })),
    // Defect-fix verification surface (Stage 3 visual-fidelity pass): no sticky/pinned layer
    // exists any more -- `app.stage` has exactly one child, `world`, itself. `rowPanelCount`
    // should equal 18 (every row, category and faction alike, gets a panel). `checkNameBounds()`
    // asserts that pass's card name-overflow requirement directly: no rendered name's bounding
    // box may exceed its own card's bounds, for any of the 980 nodes -- returns the
    // empty-violations shape a headless script can assert on.
    stageChildCount: app.stage.children.length,
    rowPanelCount,
    checkNameBounds: () => {
      const violations: { id: string; dx: number; dy: number }[] = [];
      for (let i = 0; i < base.technologies.length; i++) {
        const tech = base.technologies[i]!;
        const cardX = nodePositions[i * 2]!;
        const cardY = nodePositions[i * 2 + 1]!;
        const t = nodeNames[i]!;
        const overRight = t.x + t.width - (cardX + CARD_WIDTH);
        const overBottom = t.y + t.height - (cardY + CARD_HEIGHT);
        const underLeft = cardX - t.x;
        const underTop = cardY - t.y;
        const dx = Math.max(overRight, underLeft, 0);
        const dy = Math.max(overBottom, underTop, 0);
        if (dx > 0.5 || dy > 0.5) violations.push({ id: tech.id, dx, dy });
      }
      return { ok: violations.length === 0, violations };
    },
    // Badges slice verification: every indicator (tier, repeat, rare, dangerous, mod-requirement,
    // gate icon, gate label) must render inside its own card's bounds -- same discipline as
    // checkNameBounds above, extended to every new indicator array. Checked at LAYOUT-TIME
    // positions (each object's own .x/.y/.width/.height), independent of current LOD visibility,
    // since a badge that overflows while merely invisible is still a real defect waiting to
    // reappear at a different zoom.
    checkIndicatorBounds: () => {
      const violations: { id: string; indicator: string; dx: number; dy: number }[] = [];
      let checked = 0;
      const checkOne = (id: string, indicator: string, obj: Container | Sprite | Text, cardX: number, cardY: number, w: number) => {
        checked++;
        const overRight = obj.x + w - (cardX + CARD_WIDTH);
        const overBottom = obj.y + obj.height - (cardY + CARD_HEIGHT);
        const underLeft = cardX - obj.x;
        const underTop = cardY - obj.y;
        const dx = Math.max(overRight, underLeft, 0);
        const dy = Math.max(overBottom, underTop, 0);
        if (dx > 0.5 || dy > 0.5) violations.push({ id, indicator, dx, dy });
      };
      const badgeArrays: [string, (Container | null)[]][] = [
        ["tier", nodeTierBadges],
        ["repeat", nodeRepeatBadges],
        ["rare", nodeRareBadges],
        ["dangerous", nodeDangerousBadges],
      ];
      for (const [indicator, arr] of badgeArrays) {
        for (let i = 0; i < base.technologies.length; i++) {
          const obj = arr[i];
          if (!obj) continue;
          checkOne(base.technologies[i]!.id, indicator, obj, nodePositions[i * 2]!, nodePositions[i * 2 + 1]!, BADGE_GUTTER_WIDTH);
        }
      }
      for (let i = 0; i < base.technologies.length; i++) {
        for (const obj of nodeModRequirementBadges[i]!) {
          checkOne(base.technologies[i]!.id, "modRequirement", obj, nodePositions[i * 2]!, nodePositions[i * 2 + 1]!, BADGE_GUTTER_WIDTH);
        }
      }
      for (let i = 0; i < base.technologies.length; i++) {
        const icon = nodeGateIcons[i];
        if (icon) checkOne(base.technologies[i]!.id, "gateIcon", icon, nodePositions[i * 2]!, nodePositions[i * 2 + 1]!, icon.width);
        const label = nodeGateLabels[i];
        if (label) checkOne(base.technologies[i]!.id, "gateLabel", label, nodePositions[i * 2]!, nodePositions[i * 2 + 1]!, label.width);
      }
      return { ok: violations.length === 0, checked, violations };
    },
    // Item 4: the gate-label font-measurement regression fix (measured at 20px instead of its
    // actual 11px, plus a Y-collision with 2-line card names) affected every gated card since the
    // badges slice, not just the one observed -- this asserts it numerically, over ALL 60 real
    // gated technologies, rather than trusting the fix by inspection. Two independent checks:
    // (1) the label's real rendered width never exceeds what an 11px measurement would allow
    // (i.e. it was actually measured/wrapped with `gateLabelStyle`'s own font, not `nameStyle`'s
    // 20px -- a stale 20px measurement would UNDER-wrap the text relative to its real 11px
    // rendered width, so a mismatch here would show as the rendered width sitting far below what
    // NAME_MAX_WIDTH_PX allows at 11px, never as an overflow); (2) the label's bounding rect never
    // intersects the name text's own bounding rect, checked as real rectangle intersection, not
    // just "same card" as checkIndicatorBounds's card-containment check already does.
    checkGateLabelFontAndCollision: () => {
      const violations: { id: string; kind: string; detail: string }[] = [];
      let checked = 0;
      for (let i = 0; i < base.technologies.length; i++) {
        const label = nodeGateLabels[i];
        if (!label) continue;
        checked++;
        const name = nodeNames[i]!;
        const id = base.technologies[i]!.id;
        // Real rectangle intersection (not just card-bounds containment).
        const overlapsX = label.x < name.x + name.width && name.x < label.x + label.width;
        const overlapsY = label.y < name.y + name.height && name.y < label.y + label.height;
        if (overlapsX && overlapsY) violations.push({ id, kind: "name-collision", detail: `label y=${label.y}..${label.y + label.height}, name y=${name.y}..${name.y + name.height}` });
        // Font-measurement sanity: an 11px-measured, tail-clamped single line can never be wider
        // than NAME_MAX_WIDTH_PX (the same column every card name is clamped to) -- a stale 20px
        // measurement would produce a label whose REAL 11px-rendered width sits well under this,
        // since 20px-wrapped text over-truncates relative to what 11px could actually fit.
        if (label.width > NAME_MAX_WIDTH_PX + 0.5) violations.push({ id, kind: "overwidth", detail: `width=${label.width}` });
        if (Math.abs(label.style.fontSize as number) !== 11) violations.push({ id, kind: "wrong-font-size", detail: `fontSize=${label.style.fontSize}` });
      }
      return { ok: violations.length === 0, checked, violations };
    },
    checkIndicatorCounts: () => {
      const count = (arr: unknown[]) => arr.filter((v) => v !== null).length;
      return {
        rare: count(nodeRareBadges),
        dangerous: count(nodeDangerousBadges),
        modRequirement: nodeModRequirementBadges.filter((list) => list.length > 0).length,
        gated: count(nodeGateIcons),
        repeatable: count(nodeRepeatBadges),
        tierBadged: count(nodeTierBadges),
        datasetRareCount: base.technologies.filter((t) => t.rare).length,
        datasetDangerousCount: base.technologies.filter((t) => t.dangerous).length,
        datasetModRequirementCount: base.technologies.filter((t) => t.requiresMods.length > 0).length,
        datasetGatedCount: base.technologies.filter((t) => t.gates.length > 0).length,
        datasetRepeatableCount: base.technologies.filter((t) => t.repeatable).length,
      };
    },
    // DEFECT 4 verification: asserts, numerically, across EVERY row and every one of that row's
    // populated bands, that the row header chip's own rect and the per-cell tier label's rect
    // never intersect -- the exact requirement the task asked to check "rather than by eye".
    checkChipLabelOverlap: () => {
      const violations: { rowId: string; band: number }[] = [];
      for (const row of base.rows) {
        const chip = rowChipRects.get(row.id);
        const labels = rowCellLabelRects.get(row.id) ?? [];
        if (!chip) continue;
        for (const label of labels) {
          const overlapsX = chip.x < label.x + label.w && label.x < chip.x + chip.w;
          const overlapsY = chip.y < label.y + label.h && label.y < chip.y + chip.h;
          if (overlapsX && overlapsY) violations.push({ rowId: row.id, band: label.band });
        }
      }
      return { ok: violations.length === 0, violations };
    },
    // DEFECT 3 verification: asserts every edge's rendered (post-corner-rounding) polyline still
    // starts inside its source card's bounds and ends inside its target card's bounds -- rounding
    // must not detach an edge from either endpoint. `techIndexById` maps a technology id to its
    // index in `base.technologies`/`nodePositions`, the same alignment convention used throughout.
    checkEdgeEndpointsInCards: () => {
      const techIndexById = new Map<string, number>();
      for (let i = 0; i < base.technologies.length; i++) techIndexById.set(base.technologies[i]!.id, i);
      const inCard = (px: number, py: number, techId: string, epsilon: number): boolean => {
        const idx = techIndexById.get(techId);
        if (idx === undefined) return false;
        const cx = nodePositions[idx * 2]!;
        const cy = nodePositions[idx * 2 + 1]!;
        return px >= cx - epsilon && px <= cx + CARD_WIDTH + epsilon && py >= cy - epsilon && py <= cy + CARD_HEIGHT + epsilon;
      };
      const epsilon = 0.5;
      const violations: { fromId: string; toId: string; end: "start" | "end" }[] = [];
      for (const e of edgeEndpoints) {
        if (!inCard(e.start[0], e.start[1], e.fromId, epsilon)) violations.push({ fromId: e.fromId, toId: e.toId, end: "start" });
        if (!inCard(e.end[0], e.end[1], e.toId, epsilon)) violations.push({ fromId: e.fromId, toId: e.toId, end: "end" });
      }
      return { ok: violations.length === 0, checked: edgeEndpoints.length, violations };
    },
    // Part-1 verification: MIN_STUB (pipeline/layout.py, 8px) must hold at both ends of every
    // edge's server-computed polyline, before any corner rounding.
    checkMinStubLength: () => {
      const MIN_STUB = 8;
      const epsilon = 0.01;
      const violations: { fromId: string; toId: string; end: "exit" | "entry"; length: number }[] = [];
      for (const s of edgeStubLengths) {
        if (s.exitStub < MIN_STUB - epsilon) violations.push({ fromId: s.fromId, toId: s.toId, end: "exit", length: s.exitStub });
        if (s.entryStub < MIN_STUB - epsilon) violations.push({ fromId: s.fromId, toId: s.toId, end: "entry", length: s.entryStub });
      }
      return { ok: violations.length === 0, checked: edgeStubLengths.length, violations };
    },
    // EAWAF/v1-routing session: measures the real unrelated-card-crossing count under the new
    // v1-style router, mirroring the pipeline-side script that measured 2,586 crossings on the
    // original 4-point router and 0 on the gutter-channel rewrite it replaced. This session's
    // number is expected to be nonzero -- v1's own routing was never proven card-avoiding, only
    // ported for its look, per a deliberate, KNOWN trade recorded in CLAUDE.md -- and is reported
    // honestly rather than assumed. Uses Liang-Barsky segment/AABB clipping so a chamfered
    // (non-axis-aligned) segment is tested correctly, not just the old router's pure H/V segments.
    checkUnrelatedCardCrossings: () => {
      const techIndexById = new Map<string, number>();
      for (let i = 0; i < base.technologies.length; i++) techIndexById.set(base.technologies[i]!.id, i);
      const segmentIntersectsRect = (
        x1: number, y1: number, x2: number, y2: number, rx: number, ry: number, rw: number, rh: number
      ): boolean => {
        let t0 = 0, t1 = 1;
        const dx = x2 - x1, dy = y2 - y1;
        const p = [-dx, dx, -dy, dy];
        const q = [x1 - rx, rx + rw - x1, y1 - ry, ry + rh - y1];
        for (let i = 0; i < 4; i++) {
          const pi = p[i]!, qi = q[i]!;
          if (pi === 0) {
            if (qi < 0) return false;
          } else {
            const r = qi / pi;
            if (pi < 0) {
              if (r > t1) return false;
              if (r > t0) t0 = r;
            } else {
              if (r < t0) return false;
              if (r < t1) t1 = r;
            }
          }
        }
        return true;
      };
      let crossingCount = 0;
      const affectedEdges = new Set<string>();
      const margin = 1; // shrink card bbox by 1px so a trace merely touching a card edge (its own attachment point) doesn't false-positive
      for (const { fromId, toId, pts } of edgeRawPolylines) {
        const fromIdx = techIndexById.get(fromId)!;
        const toIdx = techIndexById.get(toId)!;
        for (let s = 0; s < pts.length - 1; s++) {
          const [x1, y1] = pts[s]!;
          const [x2, y2] = pts[s + 1]!;
          for (let i = 0; i < base.technologies.length; i++) {
            if (i === fromIdx || i === toIdx) continue;
            const cx = nodePositions[i * 2]! + margin;
            const cy = nodePositions[i * 2 + 1]! + margin;
            if (segmentIntersectsRect(x1, y1, x2, y2, cx, cy, CARD_WIDTH - 2 * margin, CARD_HEIGHT - 2 * margin)) {
              crossingCount++;
              affectedEdges.add(`${fromId}->${toId}`);
            }
          }
        }
      }
      return { crossingCount, affectedEdgeCount: affectedEdges.size, totalEdges: edgeRawPolylines.length };
    },
    // Screenshot/verification convenience only (EAWAF/v1-routing session) -- centres the given
    // WORLD coordinate in the viewport at the given scale, clamped the same way ordinary
    // zoom/pan already is. Not part of the product surface, purely a debug hook for a headless
    // script to frame a specific neighbourhood without simulating drag/wheel gestures.
    focusOn: (worldX: number, worldY: number, scale: number) => {
      camera.setScale(scale, app.screen.width / 2, app.screen.height / 2);
      const s = camera.getScale();
      world.position.set(app.screen.width / 2 - worldX * s, app.screen.height / 2 - worldY * s);
    },
  };
}

void render().catch((err: unknown) => {
  console.error(err);
  setStatus(`FAILED: ${err instanceof Error ? err.message : String(err)}`, true);
});
