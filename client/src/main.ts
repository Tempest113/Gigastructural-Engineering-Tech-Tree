// Stage 3 foundation entry point. Proves the toolchain end to end (TypeScript, PixiJS, the
// generated dataset-types.ts, and the real emitted dataset) -- deliberately NOT rendering the
// tech tree itself. That is real Stage 3 scope, not foundation scope.

import { Assets, Application, Graphics, Rectangle, Sprite, Texture } from "pixi.js";
import type { BaseDataset } from "../../schema/generated/dataset-types";
import { atlasUrl, fetchBaseDataset, fetchEmpireOverlay, fetchGeometry } from "./dataset";

let pixiApp: Application | null = null;

async function initPixi(): Promise<Application> {
  const app = new Application();
  await app.init({ resizeTo: window, background: "#111111", antialias: true });
  document.getElementById("pixi-root")!.appendChild(app.canvas);

  // A single static shape -- proof PixiJS is actually rendering via WebGL in this toolchain,
  // not a placeholder for any real node/card rendering (see spec/00-overview.md: PixiJS/WebGL
  // canvas + DOM overlay, D-11).
  const dot = new Graphics().circle(0, 0, 24).fill(0x4a90d9);
  dot.position.set(app.screen.width / 2, app.screen.height / 2);
  app.stage.addChild(dot);

  pixiApp = app;
  return app;
}

/** Loads the first technology's icon tile from the real atlas and draws it as a Sprite -- proof
 * the content-hashed WebP atlas files `tools/build_dataset.py` now writes are actually fetchable
 * and decodable as a real PixiJS Texture, not just present on disk. Still no real node-card
 * rendering (foundation only). */
async function renderSampleIcon(app: Application, base: BaseDataset): Promise<string> {
  const sample = base.technologies[0];
  if (!sample) throw new Error("base dataset has no technologies");
  const sheet = base.iconAtlases.find((s) => s.name === sample.icon.sheet);
  if (!sheet) throw new Error(`no iconAtlases entry named "${sample.icon.sheet}"`);

  const texture = (await Assets.load(atlasUrl(sheet.webp))) as Texture;
  const frame = new Rectangle(sample.icon.x, sample.icon.y, sample.icon.width, sample.icon.height);
  const tileTexture = new Texture({ source: texture.source, frame });

  const sprite = new Sprite(tileTexture);
  sprite.anchor.set(0.5);
  sprite.position.set(app.screen.width / 2 + 60, app.screen.height / 2);
  app.stage.addChild(sprite);

  return `${sample.id} from ${sheet.webp} (frame ${sample.icon.x},${sample.icon.y} ${sample.icon.width}x${sample.icon.height})`;
}

async function reportDatasetLoad(): Promise<void> {
  const report = document.getElementById("report")!;
  const lines: string[] = [];

  try {
    const t0 = performance.now();
    const base = await fetchBaseDataset();
    const t1 = performance.now();
    lines.push(`base-dataset.json fetched + parsed in ${(t1 - t0).toFixed(1)}ms`);
    lines.push(`schemaVersion: ${base.schemaVersion}`);
    lines.push(`technologies: ${base.technologies.length}`);
    lines.push(`edges: ${base.edges.length}`);
    lines.push(`tierBands: ${base.tierBands.length}`);
    lines.push(`lanes: ${base.lanes.map((l) => l.id).join(", ")}`);

    const nodePositions = await fetchGeometry(base.geometry.nodePositions);
    lines.push(
      `node-positions side-file: ${nodePositions.length} float32 values ` +
        `(${base.technologies.length} nodes x 2 = ${base.technologies.length * 2} expected)`
    );
    lines.push(`  first node position: (${nodePositions[0]?.toFixed(2)}, ${nodePositions[1]?.toFixed(2)})`);

    const edgePolylines = await fetchGeometry(base.geometry.edgePolylines);
    lines.push(`edge-polylines side-file: ${edgePolylines.length} float32 values`);

    lines.push("");
    lines.push("Little-endian float32 round-trip against real hosting: OK (finite, non-NaN values above).");
    if (!Number.isFinite(nodePositions[0] ?? NaN)) {
      throw new Error("node-positions.f32 decoded to a non-finite value -- byte-order or packing mismatch");
    }

    const overlay = await fetchEmpireOverlay("regular-mechanical-no");
    lines.push("");
    lines.push(`Sample empire overlay (regular/mechanical/non-nomadic) loaded via manifest.json: ${Object.keys(overlay.availability).length} availability entries`);

    lines.push("");
    lines.push(`iconAtlases: ${base.iconAtlases.map((s) => `${s.name} (${s.width}x${s.height})`).join(", ")}`);
    if (!pixiApp) throw new Error("PixiJS app not initialised yet");
    const iconDescription = await renderSampleIcon(pixiApp, base);
    lines.push(`Sample icon rendered as a real PixiJS Sprite: ${iconDescription}`);

    report.dataset.status = "ok";
    report.textContent = lines.join("\n");
  } catch (err) {
    report.dataset.status = "failed";
    lines.push(`FAILED: ${err instanceof Error ? err.message : String(err)}`);
    report.textContent = lines.join("\n");
    throw err;
  }
}

void initPixi().then(() => reportDatasetLoad());
