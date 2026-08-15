// Foundation-only dataset loader -- proves the emitted artefacts are fetchable and typed-array
// side-files decode correctly in a real browser, against REAL pipeline output (not the deploy
// spike's synthetic data). No rendering logic here; Stage 3's real loader design (caching,
// per-profile overlay switching, lazy detail-payload fetch batching) is future work.

import type { BaseDataset, EmpireOverlay, GeometryRef } from "../../schema/generated/dataset-types";

const DATASET_BASE = "./dataset/";

/** `dataset/manifest.json` -- the one unhashed, stable entry point (see
 * `tools/build_dataset.py`'s module docstring). Every other dataset artefact is
 * content-hashed (`<name>.<hash>.<ext>`) for GitHub Pages cache-busting, since Pages' cache
 * headers aren't configurable, and is reached only through this manifest, never a hardcoded
 * filename. */
interface DatasetManifest {
  baseDataset: string;
  searchIndex: string;
  diagnostics: string;
  overlays: Record<string, string>;
  details: Record<string, string>;
}

let manifestPromise: Promise<DatasetManifest> | null = null;

function fetchManifest(): Promise<DatasetManifest> {
  manifestPromise ??= fetch(`${DATASET_BASE}manifest.json`, { cache: "no-store" }).then((res) => {
    if (!res.ok) {
      throw new Error(`manifest.json fetch failed: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<DatasetManifest>;
  });
  return manifestPromise;
}

async function fetchViaManifest<T>(path: string): Promise<T> {
  const res = await fetch(`${DATASET_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} fetch failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function fetchBaseDataset(): Promise<BaseDataset> {
  const manifest = await fetchManifest();
  return fetchViaManifest<BaseDataset>(manifest.baseDataset);
}

export async function fetchEmpireOverlay(profileKey: string): Promise<EmpireOverlay> {
  const manifest = await fetchManifest();
  const path = manifest.overlays[profileKey];
  if (!path) {
    throw new Error(`manifest.json has no overlay entry for profile key "${profileKey}"`);
  }
  return fetchViaManifest<EmpireOverlay>(path);
}

const TYPED_ARRAY_CTORS = {
  float32: Float32Array,
  int32: Int32Array,
  uint32: Uint32Array,
  uint16: Uint16Array,
} as const;

/** Fetches a `GeometryRef`'s side-file and returns the typed-array view it describes, matching
 * `pipeline/geometry.py`'s little-endian `struct.pack("<Nf", ...)` packing -- a plain typed-array
 * view over the fetched ArrayBuffer assumes the platform is little-endian, true for every real
 * browser target (the same assumption deploy-spike/README.md already confirmed round-trips
 * against real GitHub Pages hosting; this repeats that check against the real geometry
 * side-files, not the spike's synthetic arithmetic sequence). `ref.file` is already the final
 * content-hashed path (set by `tools/build_dataset.py` before `base-dataset.json` was written),
 * so no manifest lookup is needed here -- only the base dataset's own path comes from the
 * manifest. */
export async function fetchGeometry(ref: GeometryRef): Promise<InstanceType<(typeof TYPED_ARRAY_CTORS)[keyof typeof TYPED_ARRAY_CTORS]>> {
  const res = await fetch(`${DATASET_BASE}${ref.file}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${ref.file} fetch failed: ${res.status} ${res.statusText}`);
  }
  const buf = await res.arrayBuffer();
  const Ctor = TYPED_ARRAY_CTORS[ref.dtype];
  const view = new Ctor(buf, ref.byteOffset);
  if (view.length !== ref.length) {
    throw new Error(
      `${ref.file}: GeometryRef declares length ${ref.length} but decoded ${view.length} ${ref.dtype} elements`
    );
  }
  return view;
}

/** An `iconAtlases[].webp`/`.png` value is already the final content-hashed path (set by
 * `tools/build_dataset.py` before `base-dataset.json` was written, same pattern as
 * `GeometryRef.file`) -- resolved relative to `dataset/`, same as everything else here. */
export function atlasUrl(relativePath: string): string {
  return `${DATASET_BASE}${relativePath}`;
}
