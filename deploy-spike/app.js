// Deploy spike -- see README.md. Fetches both dummy artifacts using the SAME relative-path
// pattern the real client will use (no leading "/", resolved against the page's own URL), so
// this exercises real base-path resolution under a GitHub Pages *project* subpath
// (tempest113.github.io/Gigastructural-Engineering-Tech-Tree/), not a domain root -- a plain
// leading-slash path would silently work in local testing at a domain root and silently break
// here, which is exactly the failure mode this spike exists to surface before Stage 3 hits it.

async function reportFetch(url, elementId, isBinary) {
  const el = document.getElementById(elementId);
  const lines = [`URL requested (relative): ${url}`];
  try {
    const res = await fetch(url, { cache: "no-store" });
    const contentType = res.headers.get("content-type");
    lines.push(`Resolved URL: ${res.url}`);
    lines.push(`HTTP status: ${res.status} ${res.statusText}`);
    lines.push(`Content-Type header: ${contentType}`);

    const buf = await res.arrayBuffer();
    lines.push(`Byte length: ${buf.byteLength}`);

    if (isBinary) {
      // Same decode approach Stage 3 will use for typed-array geometry side-files
      // (00-overview.md): a plain Float32Array view over the fetched ArrayBuffer, no manual
      // endianness handling -- this assumes the reader's platform is little-endian, true for
      // every real browser target, and is exactly the assumption Stage 3's renderer will make.
      const floats = new Float32Array(buf);
      const preview = Array.from(floats.slice(0, 8)).map((v) => v.toFixed(4));
      lines.push(`Decoded as Float32Array: ${floats.length} values`);
      lines.push(`First 8 decoded values: ${preview.join(", ")}`);
    } else {
      const text = new TextDecoder("utf-8").decode(buf);
      const json = JSON.parse(text);
      lines.push(`Parsed JSON: ${JSON.stringify(json)}`);
      lines.push(`schemaVersion field: ${json.schemaVersion}`);
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
