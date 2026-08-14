// Deploy spike -- see README.md. Fetches both dummy artifacts using the SAME relative-path
// pattern the real client will use (no leading "/", resolved against the page's own URL), so
// this exercises real base-path resolution under a GitHub Pages *project* subpath
// (tempest113.github.io/Gigastructural-Engineering-Tech-Tree/), not a domain root -- a plain
// leading-slash path would silently work in local testing at a domain root and silently break
// here, which is exactly the failure mode this spike exists to surface before Stage 3 hits it.
//
// Also reports actual transfer-vs-decoded byte sizes via the Resource Timing API, because
// `fetch`'s ArrayBuffer size is always the DECODED size -- gzip is transparent to it. P-10 is
// specified as "compressed, over the wire" (spec/P-10-performance-automation.md); nothing before
// this spike had confirmed GitHub Pages actually serves these artefacts compressed at all, let
// alone at anything close to the ~6x assumed for the base-dataset size estimate.

async function resourceTimingFor(url, attemptsLeft = 8) {
  // Resource Timing entries are recorded asynchronously and can lag slightly behind the fetch
  // promise resolving (the network transfer is done, but the entry hasn't been buffered into
  // performance.getEntriesByName yet). Poll briefly rather than assume it's there on the first
  // check -- and be explicit when it never shows up, so a genuinely-missing measurement isn't
  // silently reported as zero.
  for (let attempt = 0; attempt < attemptsLeft; attempt++) {
    const entries = performance.getEntriesByName(url);
    if (entries.length > 0) return entries[entries.length - 1];
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return null;
}

async function reportFetch(url, elementId, isBinary) {
  const el = document.getElementById(elementId);
  const lines = [`URL requested (relative): ${url}`];
  try {
    const res = await fetch(url, { cache: "no-store" });
    const contentType = res.headers.get("content-type");
    const contentEncoding = res.headers.get("content-encoding");
    lines.push(`Resolved URL: ${res.url}`);
    lines.push(`HTTP status: ${res.status} ${res.statusText}`);
    lines.push(`Content-Type header: ${contentType}`);
    lines.push(`Content-Encoding header: ${contentEncoding === null ? "(absent)" : contentEncoding}`);

    const buf = await res.arrayBuffer();
    lines.push(`Decoded byte length (what fetch() hands you -- gzip is transparent to this): ${buf.byteLength}`);

    if (isBinary) {
      // Same decode approach Stage 3 will use for typed-array geometry side-files
      // (00-overview.md): a plain Float32Array view over the fetched ArrayBuffer, no manual
      // endianness handling -- this assumes the reader's platform is little-endian, true for
      // every real browser target, and is exactly the assumption Stage 3's renderer will make.
      const floats = new Float32Array(buf);
      const preview = Array.from(floats.slice(0, 8)).map((v) => v.toFixed(4));
      lines.push(`Decoded as Float32Array: ${floats.length} values`);
      lines.push(`First 8 decoded values: ${preview.join(", ")}`);
      lines.push(
        "Clean 0.5-increment values above confirm little-endian round-trips end to end " +
          "(a byte-order mismatch would produce garbage, not a clean arithmetic sequence)."
      );
    } else {
      const text = new TextDecoder("utf-8").decode(buf);
      const json = JSON.parse(text);
      lines.push(`schemaVersion field: ${json.schemaVersion}`);
      lines.push(`technologyCount field: ${json.technologyCount}`);
    }

    // Actual wire size vs decoded size -- the thing this extension exists to measure.
    const timing = await resourceTimingFor(res.url);
    if (timing === null) {
      lines.push("Resource Timing entry: UNAVAILABLE (not a measurement of zero -- the browser " +
        "never surfaced one for this request; do not read the absence of this section as " +
        "'no compression').");
    } else {
      const { encodedBodySize, decodedBodySize, transferSize } = timing;
      lines.push(`Resource Timing encodedBodySize (actual bytes over the wire): ${encodedBodySize}`);
      lines.push(`Resource Timing decodedBodySize (after any Content-Encoding is undone): ${decodedBodySize}`);
      lines.push(`Resource Timing transferSize (encoded body + response header overhead): ${transferSize}`);
      if (encodedBodySize > 0) {
        const ratio = decodedBodySize / encodedBodySize;
        lines.push(`Compression ratio (decoded / encoded): ${ratio.toFixed(2)}x`);
      } else {
        lines.push("Compression ratio: N/A (encodedBodySize is 0 -- likely served from a cache " +
          "that doesn't record it; re-run with cache disabled if this shows up).");
      }
    }

    el.textContent = lines.join("\n");
    el.dataset.status = "ok";
  } catch (err) {
    lines.push(`FETCH OR DECODE FAILED: ${err}`);
    el.textContent = lines.join("\n");
    el.dataset.status = "failed";
  }
}

reportFetch("./sample-dataset.json", "json-report", false);
reportFetch("./geometry.f32", "binary-report", true);
