/*
 * GEIDA processing worker. Runs the GeoLibre / Whitebox WebAssembly tools off the
 * main thread so the map stays responsive. Messages: {id, op, args} -> {id, ok, result|error}.
 */
let lib = null;
let tools = null;
let manifests = null;

async function init(cfg) {
  if (tools) return { manifests, version: cfg.version, mode: cfg.mode };
  lib = await import(cfg.lib);
  await lib.default(cfg.libWasm);
  tools = await import(cfg.tools);
  await tools.initTools(cfg.cliWasm);
  manifests = await tools.listManifests();
  return { manifests, version: cfg.version, mode: cfg.mode };
}

function rasterInfo(bytes) {
  const r = new lib.GeoTiffReader(bytes);
  try {
    const info = JSON.parse(r.info_json());
    let stats = null;
    try { stats = JSON.parse(r.stats_json()); } catch (e) { stats = null; }
    return {
      width: r.width, height: r.height, bands: r.bands, epsg: r.epsg ?? null,
      nodata: r.nodata ?? null, bounds: Array.from(r.bounds_lonlat()),
      sampleFormat: r.sample_format, info, stats,
    };
  } finally { r.free(); }
}

const enc = new TextEncoder();

const ops = {
  init,
  async run({ tool, args, input }) {
    const res = await tools.runTool(tool, { args, input });
    return { exitCode: res.exitCode, stdout: res.stdout.slice(-60), files: res.files };
  },
  async rasterInfo({ bytes }) { return rasterInfo(bytes); },
  async vectorReproject({ bytes, format, dst, src }) {
    return enc.encode(lib.vector_to_geojson_reproject(bytes, format || "geojson", dst, src || 0));
  },
  async vectorInfo({ bytes, format }) { return JSON.parse(lib.vector_info(bytes, format)); },
};

self.onmessage = async (e) => {
  const { id, op, args } = e.data;
  try {
    if (!ops[op]) throw new Error(`Unknown operation: ${op}`);
    if (op !== "init" && !tools) throw new Error("Processing engine isn't loaded yet.");
    const result = await ops[op](args || {});
    const transfer = new Set();
    if (result && result.files) for (const v of Object.values(result.files)) transfer.add(v.buffer);
    else if (result instanceof Uint8Array) transfer.add(result.buffer);
    self.postMessage({ id, ok: true, result }, [...transfer]);
  } catch (err) {
    self.postMessage({ id, ok: false, error: String((err && err.message) || err) });
  }
};
