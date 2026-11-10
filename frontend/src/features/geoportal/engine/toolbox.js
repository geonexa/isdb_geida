/*
 * GEIDA Processing Toolbox.
 * GeoLibre / Whitebox WebAssembly tools run in a Web Worker. Inputs come from the
 * project area, catalog layers clipped to the area (TiTiler), earlier results or uploads.
 * Tools run in the local UTM zone (metres); results are added to the map.
 */
import proj4 from "proj4";

import { ol } from "./ol.js";

export function initToolbox(G, cfg) {
  "use strict";
  var ac = new AbortController(), signal = ac.signal, observers = [];

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };

  var curated = cfg.toolbox;
  var clippable = cfg.clippable;
  var engineCfg = cfg.engine;
  var curatedById = {};
  curated.forEach(function (g) { g.tools.forEach(function (t) { t.group = g.group; curatedById[t.id] = t; }); });
  var clipById = {};
  clippable.forEach(function (c) { clipById[c.id] = c; });

  // ---------------------------------------------------------------------------
  // Worker and engine
  // ---------------------------------------------------------------------------
  var worker = null, seq = 0, pending = {}, engine = null, manifests = [], manifestById = {};
  function call(op, args) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { resolve: resolve, reject: reject };
      worker.postMessage({ id: id, op: op, args: args || {} });
    });
  }
  function startEngine() {
    if (engine) return engine;
    setEngine("loading", "Loading the processing engine (about 9 MB, first time only)…");
    worker = new Worker(cfg.workerUrl, { type: "module" });
    worker.onmessage = function (e) {
      var p = pending[e.data.id]; if (!p) return;
      delete pending[e.data.id];
      if (e.data.ok) p.resolve(e.data.result); else p.reject(new Error(e.data.error));
    };
    worker.onerror = function (e) { setEngine("error", "The processing engine failed to start: " + (e.message || "unknown error")); };
    engine = call("init", engineCfg).then(function (res) {
      manifests = res.manifests;
      manifests.forEach(function (m) { manifestById[m.id] = m; });
      $("[data-tb-all-count]").textContent = manifests.length.toLocaleString();
      $("[data-tb-subtitle]").textContent = manifests.length.toLocaleString() + " tools · engine " + res.version + (res.mode === "local" ? " (local)" : " (CDN)");
      setEngine("ready");
      renderList();
      return res;
    }).catch(function (err) {
      setEngine("error", "Couldn't load the processing engine. " + err.message);
      engine = null;
      if (worker) { worker.terminate(); worker = null; }
      throw err;
    });
    return engine;
  }
  function setEngine(state, text) {
    var el = $("[data-tb-engine]");
    el.className = "tb-engine is-" + state;
    el.hidden = state === "ready";
    if (text) $("[data-tb-engine-text]").textContent = text;
  }

  // ---------------------------------------------------------------------------
  // Projections (UTM zones are generated, so any member country works)
  // ---------------------------------------------------------------------------
  function utmFor(lon, lat) { var z = Math.min(60, Math.max(1, Math.floor((lon + 180) / 6) + 1)); return (lat >= 0 ? 32600 : 32700) + z; }
  function ensureProj(epsg) {
    if (!epsg) return false;
    var code = "EPSG:" + epsg;
    if (ol.proj.get(code)) return true;
    var def = null;
    if (epsg >= 32601 && epsg <= 32660) def = "+proj=utm +zone=" + (epsg - 32600) + " +datum=WGS84 +units=m +no_defs";
    if (epsg >= 32701 && epsg <= 32760) def = "+proj=utm +zone=" + (epsg - 32700) + " +south +datum=WGS84 +units=m +no_defs";
    if (!def) return false;
    proj4.defs(code, def);
    ol.proj.proj4.register(proj4);
    return !!ol.proj.get(code);
  }
  function aoiCenter(aoi) {
    var ext = new ol.format.GeoJSON().readFeatures(aoi).reduce(function (e, f) { return ol.extent.extend(e, f.getGeometry().getExtent()); }, ol.extent.createEmpty());
    return ol.extent.getCenter(ext);
  }
  function workingEpsg() {
    var aoi = G.aoi();
    var c = aoi ? aoiCenter(aoi) : ol.proj.toLonLat(G.view.getCenter());
    return utmFor(c[0], c[1]);
  }

  // ---------------------------------------------------------------------------
  // Datasets: results and uploads available as tool inputs
  // ---------------------------------------------------------------------------
  var datasets = [];          // {id, name, kind, bytes+epsg (raster) | geojson (vector, EPSG:4326)}
  var clipCache = {};
  var dsSeq = 0;
  var enc = new TextEncoder();
  function addDataset(d) { d.id = "ds" + (++dsSeq); datasets.unshift(d); return d; }
  function aoiGeometry(aoi) {
    var geoms = aoi.features.map(function (f) { return f.geometry; });
    if (geoms.length === 1) return geoms[0];
    var polys = [];
    geoms.forEach(function (g) { if (g.type === "Polygon") polys.push(g.coordinates); if (g.type === "MultiPolygon") polys = polys.concat(g.coordinates); });
    return { type: "MultiPolygon", coordinates: polys };
  }
  function csrf() { var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function requireAoi() {
    var aoi = G.aoi();
    if (!aoi) throw new Error("Draw or upload a project area first. Open the Area tab, draw a polygon or rectangle, then run the tool again.");
    return aoi;
  }
  function clipLayer(layerId, year) {
    var geom = aoiGeometry(requireAoi());
    var key = layerId + "|" + (year || "") + "|" + JSON.stringify(geom);
    if (clipCache[key]) return Promise.resolve(clipCache[key]);
    return fetch("/api/geoportal/layers/" + encodeURIComponent(layerId) + "/clip/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ geometry: geom, year: year || null }),
    }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (j) { throw new Error(j.error || "Couldn't prepare the data (HTTP " + r.status + ")."); });
      var epsg = Number(r.headers.get("X-GEIDA-EPSG"));
      var scale = Number(r.headers.get("X-GEIDA-Scale"));
      return r.arrayBuffer().then(function (buf) {
        var out = { bytes: new Uint8Array(buf), epsg: epsg, scale: scale };
        clipCache[key] = out;
        return out;
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Floating window (drag, keyboard, remember position)
  // ---------------------------------------------------------------------------
  var win = $("[data-tb-win]"), head = $("[data-tb-drag]"), toggles = $$("[data-tb-toggle]");
  var mapWrap = $("[data-gp-mapwrap]");
  var small = function () { return window.innerWidth <= 720; };
  var running = false;
  function clamp() {
    if (win.hidden || small()) return;
    var W = mapWrap.clientWidth, H = mapWrap.clientHeight;
    win.style.left = Math.min(Math.max(0, win.offsetLeft), Math.max(0, W - win.offsetWidth - 62)) + "px";
    win.style.top = Math.min(Math.max(0, win.offsetTop), Math.max(0, H - 56)) + "px";
  }
  function savePos() { G.store.set("toolboxPos", JSON.stringify({ left: win.offsetLeft, top: win.offsetTop, w: win.offsetWidth, h: win.offsetHeight })); }
  function defaultPos() { win.style.left = Math.max(14, mapWrap.clientWidth - 420 - 76) + "px"; win.style.top = "66px"; }
  (function restore() {
    try {
      var p = JSON.parse(G.store.get("toolboxPos") || "null");
      if (p && !small()) { win.style.left = p.left + "px"; win.style.top = p.top + "px"; if (p.w) win.style.width = p.w + "px"; if (p.h) win.style.height = p.h + "px"; }
      else defaultPos();
    } catch (e) { defaultPos(); }
  })();
  function setOpen(open) {
    win.hidden = !open;
    toggles.forEach(function (b) { b.setAttribute("aria-expanded", String(open)); });
    G.store.set("toolbox", open ? "open" : "closed");
    if (open) { clamp(); startEngine().catch(function () {}); }
  }
  toggles.forEach(function (b) { b.addEventListener("click", function () { setOpen(win.hidden); }); });
  $("[data-tb-close]").addEventListener("click", function () { setOpen(false); toggles[0].focus(); });
  win.addEventListener("keydown", function (e) { if (e.key === "Escape" && !running) { setOpen(false); toggles[0].focus(); } });
  var drag = null;
  head.setAttribute("tabindex", "0");
  head.setAttribute("aria-label", "Processing toolbox. Drag, or use arrow keys, to move. Double-click to reset position.");
  head.addEventListener("pointerdown", function (e) {
    if (small() || e.button !== 0 || e.target.closest("button")) return;
    drag = { x: e.clientX, y: e.clientY, left: win.offsetLeft, top: win.offsetTop };
    head.setPointerCapture(e.pointerId); win.classList.add("is-dragging"); e.preventDefault();
  });
  head.addEventListener("pointermove", function (e) {
    if (!drag) return;
    win.style.left = drag.left + e.clientX - drag.x + "px"; win.style.top = drag.top + e.clientY - drag.y + "px"; clamp();
  });
  function endDrag() { if (!drag) return; drag = null; win.classList.remove("is-dragging"); savePos(); }
  head.addEventListener("pointerup", endDrag);
  head.addEventListener("pointercancel", endDrag);
  head.addEventListener("dblclick", function (e) { if (e.target.closest("button")) return; win.style.width = ""; win.style.height = ""; defaultPos(); clamp(); savePos(); });
  head.addEventListener("keydown", function (e) {
    var step = e.shiftKey ? 60 : 20, dx = 0, dy = 0;
    if (e.key === "ArrowLeft") dx = -step; else if (e.key === "ArrowRight") dx = step; else if (e.key === "ArrowUp") dy = -step; else if (e.key === "ArrowDown") dy = step; else return;
    e.preventDefault(); win.style.left = win.offsetLeft + dx + "px"; win.style.top = win.offsetTop + dy + "px"; clamp(); savePos();
  });
  if (window.ResizeObserver) { var rt; observers.push(new ResizeObserver(function () { clearTimeout(rt); rt = setTimeout(function () { if (!win.hidden && !small()) { clamp(); savePos(); } }, 300); })); observers[observers.length - 1].observe(win); }
  window.addEventListener("resize", clamp, { signal: signal });

  // ---------------------------------------------------------------------------
  // Tool list
  // ---------------------------------------------------------------------------
  var listEl = $("[data-tb-tools]"), searchEl = $("[data-tb-search]"), allEl = $("[data-tb-all]");
  function toolName(id) { var m = manifestById[id]; return m ? m.display_name : id.replace(/_/g, " ").replace(/^\w/, function (c) { return c.toUpperCase(); }); }
  function row(id, hint) {
    return '<li><button type="button" class="tb-tool" data-tb-tool="' + esc(id) + '"><span class="tb-tool-name">' + esc(toolName(id)) +
      '</span><span class="tb-tool-hint">' + esc(hint || "") + '</span><i data-lucide="chevron-right" aria-hidden="true"></i></button></li>';
  }
  function renderList() {
    var q = searchEl.value.trim().toLowerCase();
    var match = function (id, text) { return !q || (id + " " + toolName(id) + " " + (text || "")).toLowerCase().indexOf(q) !== -1; };
    var html = "";
    curated.forEach(function (g) {
      var items = g.tools.filter(function (t) { return match(t.id, t.hint); });
      if (!items.length) return;
      html += '<div class="tb-group"><h4><i data-lucide="' + esc(g.icon) + '" aria-hidden="true"></i>' + esc(g.group) + "</h4><ul>" +
        items.map(function (t) { return row(t.id, t.hint); }).join("") + "</ul></div>";
    });
    if (allEl.checked && manifests.length) {
      var groups = {}, shown = 0, total = 0, LIMIT = 150;
      manifests.forEach(function (m) {
        if (curatedById[m.id] || !match(m.id, m.summary)) return;
        total++;
        if (shown >= LIMIT) return;
        shown++;
        (groups[m.category || "Other"] = groups[m.category || "Other"] || []).push(m);
      });
      Object.keys(groups).sort().forEach(function (cat) {
        html += '<div class="tb-group is-all"><h4>' + esc(cat) + " <small>all tools</small></h4><ul>" +
          groups[cat].map(function (m) { return row(m.id, (m.summary || "").slice(0, 110)); }).join("") + "</ul></div>";
      });
      if (total > shown) html += '<p class="gp-empty">Showing ' + shown + " of " + total.toLocaleString() + " tools. Search to narrow the list.</p>";
    } else if (allEl.checked) {
      html += '<p class="gp-empty">The full tool list appears once the engine has loaded.</p>';
    }
    listEl.innerHTML = html || '<p class="gp-empty">No tools match your search.</p>';
    G.icons();
  }
  searchEl.addEventListener("input", renderList);
  allEl.addEventListener("change", renderList);
  listEl.addEventListener("click", function (e) {
    var b = e.target.closest("[data-tb-tool]"); if (!b) return;
    openTool(b.getAttribute("data-tb-tool"));
  });
  renderList();

  // ---------------------------------------------------------------------------
  // Tool form, built from the tool's manifest
  // ---------------------------------------------------------------------------
  var formView = $("[data-tb-form-view]"), listView = $("[data-tb-list]"), formEl = $("[data-tb-form]");
  var current = null;

  function inputKind(p) { return p.schema && p.schema.kind === "input" ? ((p.schema.dataset && p.schema.dataset.kind) || "file") : null; }
  function isOutput(p) { return p.schema && p.schema.kind === "output"; }
  function defaultFor(m, cur, p) {
    if (cur.defaults && p.name in cur.defaults) return cur.defaults[p.name];
    var v = m.defaults ? m.defaults[p.name] : undefined;
    if (v == null) return "";
    return typeof v === "object" ? JSON.stringify(v) : v;
  }
  function inputOptions(kind, geometry) {
    var html = "";
    if (kind === "raster") {
      html += '<optgroup label="Catalog layer, clipped to project area">' + clippable.map(function (c) {
        return '<option value="clip:' + esc(c.id) + '">' + esc(c.name) + " (" + esc(c.source) + ")</option>";
      }).join("") + "</optgroup>";
    }
    if (kind === "vector") {
      html += '<option value="aoi">Project area (drawn on map)</option>';
      if (geometry === "point" || geometry === "any") html += '<option value="pick">Place a point on the map…</option>';
    }
    var own = datasets.filter(function (d) { return d.kind === kind; });
    if (own.length) html += '<optgroup label="Results and uploads">' + own.map(function (d) { return '<option value="ds:' + d.id + '">' + esc(d.name) + "</option>"; }).join("") + "</optgroup>";
    html += '<option value="upload">Upload ' + (kind === "raster" ? "a GeoTIFF" : "a file (GeoJSON, KML, GeoPackage, …)") + "…</option>";
    return html;
  }
  function preferredInput(kind) {
    var own = datasets.filter(function (d) { return d.kind === kind; });
    if (own.length) return "ds:" + own[0].id;
    if (kind === "vector") return "aoi";
    return clipById.elevation ? "clip:elevation" : (clippable[0] ? "clip:" + clippable[0].id : "upload");
  }
  function fieldHtml(m, cur, p) {
    var id = "tb-f-" + p.name, kind = p.schema && p.schema.kind, label = p.name.replace(/_/g, " ");
    label = label.charAt(0).toUpperCase() + label.slice(1);
    var req = p.required ? ' <span class="tb-req" aria-label="required">*</span>' : "";
    var help = p.description ? '<p class="field-help">' + esc(p.description) + "</p>" : "";
    var ik = inputKind(p);
    if (ik) {
      if (ik !== "raster" && ik !== "vector") return '<div class="field"><label>' + esc(label) + req + '</label><p class="field-help">This input type (' + esc(ik) + ") isn't supported in the Toolbox yet.</p></div>";
      var geom = p.schema.dataset && p.schema.dataset.geometry;
      return '<div class="field" data-param="' + esc(p.name) + '" data-input="' + ik + '">' +
        '<div class="field-top"><label for="' + id + '">' + esc(label) + req + '</label><span class="tb-kind">' + ik + "</span></div>" +
        '<select class="input" id="' + id + '" data-geom="' + esc(geom || "") + '">' + inputOptions(ik, geom) + "</select>" +
        '<div class="tb-year" data-year-for="' + esc(p.name) + '" hidden><label>Year <select class="input"></select></label></div>' + help + "</div>";
    }
    var val = defaultFor(m, cur, p);
    if (kind === "enum") {
      return '<div class="field" data-param="' + esc(p.name) + '"><label for="' + id + '">' + esc(label) + req + '</label><select class="input" id="' + id + '">' +
        (p.required ? "" : '<option value="">Default</option>') +
        p.schema.options.map(function (o) { return '<option value="' + esc(o.value) + '"' + (String(o.value) === String(val) ? " selected" : "") + ">" + esc(o.label || o.value) + "</option>"; }).join("") +
        "</select>" + help + "</div>";
    }
    if (kind === "bool") {
      var on = val === true || val === "true";
      return '<div class="field" data-param="' + esc(p.name) + '" data-bool><label class="check"><input type="checkbox" class="checkbox" id="' + id + '"' + (on ? " checked" : "") + "><span>" + esc(label) + "</span></label>" + help + "</div>";
    }
    if (kind === "scalar") {
      var stepAttr = p.schema.scalar === "integer" ? "1" : "any";
      return '<div class="field" data-param="' + esc(p.name) + '"><label for="' + id + '">' + esc(label) + req + '</label><input class="input" type="number" step="' + stepAttr + '" id="' + id + '" value="' + esc(val) + '" placeholder="Default">' + help + "</div>";
    }
    return '<div class="field" data-param="' + esc(p.name) + '"><label for="' + id + '">' + esc(label) + req + '</label><input class="input" type="text" id="' + id + '" value="' + esc(val) + '" placeholder="' + (p.required ? "" : "Default") + '">' + help + "</div>";
  }

  function openTool(id) {
    startEngine().then(function () {
      var m = manifestById[id];
      if (!m) return;
      var cur = curatedById[id] || {};
      current = { id: id, manifest: m, cur: cur };
      $("[data-tb-tool-name]").textContent = m.display_name;
      $("[data-tb-tool-summary]").textContent = cur.hint || m.summary || "";
      var params = m.params.filter(function (p) { return !isOutput(p); });
      var req = params.filter(function (p) { return p.required || inputKind(p); });
      var opt = params.filter(function (p) { return !(p.required || inputKind(p)); });
      formEl.innerHTML = req.map(function (p) { return fieldHtml(m, cur, p); }).join("") +
        (opt.length ? '<details class="tb-more"><summary>More options (' + opt.length + ")</summary>" + opt.map(function (p) { return fieldHtml(m, cur, p); }).join("") + "</details>" : "") +
        '<p class="tb-note"><i data-lucide="info" aria-hidden="true"></i>Runs in your browser in the local UTM zone, so distances and areas are in metres.</p>';
      $$("[data-input]", formEl).forEach(function (f) {
        var sel = $("select", f);
        sel.value = preferredInput(f.getAttribute("data-input"));
        if (!sel.value) sel.selectedIndex = 0;
        sel.dataset.prev = sel.value;
        sel.addEventListener("change", function () { onInputChange(f, sel); });
        syncYear(f, sel);
      });
      $("[data-tb-run]").hidden = true;
      listView.hidden = true; formView.hidden = false;
      $("[data-tb-submit]").disabled = false;
      G.icons();
      var first = $("select, input", formEl); if (first) first.focus();
    }).catch(function () {});
  }
  $("[data-tb-back]").addEventListener("click", function () { if (running) return; formView.hidden = true; listView.hidden = false; current = null; searchEl.focus(); });

  function syncYear(field, sel) {
    var box = $("[data-year-for]", field), v = sel.value;
    var c = v.indexOf("clip:") === 0 ? clipById[v.slice(5)] : null;
    if (!c || !c.years.length) { box.hidden = true; return; }
    var y = G.layerYear(c.id) || c.year;
    $("select", box).innerHTML = c.years.slice().reverse().map(function (yr) { return "<option" + (yr === y ? " selected" : "") + ">" + yr + "</option>"; }).join("");
    box.hidden = false;
  }
  function refreshInputs(keep) {
    $$("[data-input]", formEl).forEach(function (f) {
      var sel = $("select", f), v = keep && keep.field === f ? keep.value : sel.value;
      sel.innerHTML = inputOptions(f.getAttribute("data-input"), sel.getAttribute("data-geom"));
      sel.value = v; if (!sel.value) sel.selectedIndex = 0; sel.dataset.prev = sel.value;
      syncYear(f, sel);
    });
  }
  var uploadInput = document.createElement("input");
  uploadInput.type = "file"; uploadInput.hidden = true; document.body.appendChild(uploadInput);
  function onInputChange(field, sel) {
    var kind = field.getAttribute("data-input"), prev = sel.dataset.prev;
    if (sel.value === "upload") {
      sel.value = prev;
      uploadInput.accept = kind === "raster" ? ".tif,.tiff" : ".geojson,.json,.kml,.kmz,.gpkg,.fgb,.parquet,.gpx,.gml,.topojson";
      uploadInput.onchange = function () {
        var file = uploadInput.files[0]; uploadInput.value = "";
        if (!file) return;
        loadUpload(file, kind).then(function (d) { refreshInputs({ field: field, value: "ds:" + d.id }); })
          .catch(function (err) { stepsEl.innerHTML = ""; showError(err.message); });
      };
      uploadInput.click();
      return;
    }
    if (sel.value === "pick") {
      sel.value = prev;
      G.pickPoint("Click on the map to place the point. Press Esc to cancel.").then(function (ll) {
        var gj = { type: "FeatureCollection", features: [{ type: "Feature", properties: { name: "Point" }, geometry: { type: "Point", coordinates: ll } }] };
        var d = addDataset({ kind: "vector", name: "Point " + ll[1].toFixed(4) + ", " + ll[0].toFixed(4), geojson: gj });
        addVectorLayer(d, "Placed point");
        refreshInputs({ field: field, value: "ds:" + d.id });
      }).catch(function () {});
      return;
    }
    sel.dataset.prev = sel.value;
    syncYear(field, sel);
  }

  var VECTOR_FORMATS = { geojson: "geojson", json: "geojson", kml: "kml", kmz: "kmz", gpkg: "geopackage", fgb: "flatgeobuf", parquet: "geoparquet", gpx: "gpx", gml: "gml", topojson: "topojson" };
  function loadUpload(file, kind) {
    return startEngine().then(function () { return file.arrayBuffer(); }).then(function (buf) {
      var bytes = new Uint8Array(buf), name = file.name.replace(/\.[^.]+$/, "");
      if (kind === "raster") {
        return call("rasterInfo", { bytes: bytes.slice() }).then(function (info) {
          var d = addDataset({ kind: "raster", name: name + " (upload)", bytes: bytes, epsg: info.epsg });
          addRasterLayer(d, info, "Uploaded file", null);
          return d;
        });
      }
      var ext = file.name.split(".").pop().toLowerCase(), fmt = VECTOR_FORMATS[ext];
      if (!fmt) throw new Error("This file type isn't supported. Use GeoJSON, KML, GeoPackage, FlatGeobuf, GeoParquet or GPX.");
      return call("vectorReproject", { bytes: bytes, format: fmt, dst: 4326, src: 0 }).then(function (out) {
        var d = addDataset({ kind: "vector", name: name + " (upload)", geojson: JSON.parse(new TextDecoder().decode(out)) });
        addVectorLayer(d, "Uploaded file");
        return d;
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Running a tool
  // ---------------------------------------------------------------------------
  var stepsEl = $("[data-tb-steps]"), logEl = $("[data-tb-log]");
  function step(text, state) {
    var li = document.createElement("li");
    li.className = "is-" + (state || "doing"); li.textContent = text;
    stepsEl.appendChild(li);
    return { done: function (t) { li.className = "is-done"; if (t) li.textContent = t; }, fail: function (t) { li.className = "is-error"; if (t) li.textContent = t; } };
  }
  function showError(msg, log) {
    $("[data-tb-run]").hidden = false;
    step(msg, "error");
    if (log && log.length) { logEl.textContent = log.join("\n"); logEl.hidden = false; }
  }

  function prepareInput(field, epsgHolder) {
    var kind = field.getAttribute("data-input"), v = $("select", field).value;
    if (kind === "raster") {
      if (v.indexOf("clip:") === 0) {
        var c = clipById[v.slice(5)], yearBox = $("[data-year-for]", field);
        var year = yearBox.hidden ? null : Number($("select", yearBox).value);
        var s = step("Preparing " + c.name + (year ? " " + year : "") + " for the project area…");
        return clipLayer(c.id, year).then(function (r) {
          s.done(c.name + (year ? " " + year : "") + " ready (" + Math.round(r.scale) + " m pixels, EPSG:" + r.epsg + ")");
          epsgHolder.raster = epsgHolder.raster || r.epsg;
          return { bytes: r.bytes, ext: "tif" };
        }).catch(function (err) { s.fail(err.message); err.shown = true; throw err; });
      }
      var d = datasets.find(function (x) { return "ds:" + x.id === v; });
      if (!d) return Promise.reject(new Error("Choose an input raster."));
      epsgHolder.raster = epsgHolder.raster || d.epsg;
      return Promise.resolve({ bytes: d.bytes, ext: "tif" });
    }
    var gj;
    if (v === "aoi") { try { gj = requireAoi(); } catch (e) { return Promise.reject(e); } }
    else { var dv = datasets.find(function (x) { return "ds:" + x.id === v; }); if (!dv) return Promise.reject(new Error("Choose an input layer.")); gj = dv.geojson; }
    return Promise.resolve({ geojson: gj, vector: true });
  }

  $("[data-tb-submit]").addEventListener("click", runTool);
  formEl.addEventListener("submit", function (e) { e.preventDefault(); runTool(); });

  function runTool() {
    if (!current || running) return;
    var m = current.manifest, toolId = current.id;
    stepsEl.innerHTML = ""; logEl.hidden = true; logEl.textContent = "";
    $("[data-tb-run]").hidden = false;
    var missing = $$("[data-param]", formEl).filter(function (f) {
      var p = m.params.find(function (x) { return x.name === f.getAttribute("data-param"); });
      if (!p || !p.required || f.hasAttribute("data-input") || f.hasAttribute("data-bool")) return false;
      return !$("input, select", f).value.trim();
    });
    if (missing.length) { showError("Fill in: " + missing.map(function (f) { return f.getAttribute("data-param").replace(/_/g, " "); }).join(", ") + "."); return; }

    running = true;
    var btn = $("[data-tb-submit]"); btn.disabled = true;
    var t0 = performance.now(), epsgHolder = {}, input = {}, args = [];
    var fields = $$("[data-param]", formEl);
    var inputFields = fields.filter(function (f) { return f.hasAttribute("data-input"); });
    var outputs = m.params.filter(isOutput);
    var record = { tool: m.display_name, status: "running", ms: 0 };

    // Rasters first: they fix the working CRS; vectors are then projected to match.
    var ordered = inputFields.slice().sort(function (a, b) { return (a.getAttribute("data-input") === "raster" ? 0 : 1) - (b.getAttribute("data-input") === "raster" ? 0 : 1); });
    var chain = Promise.resolve();
    ordered.forEach(function (f) {
      chain = chain.then(function () {
        return prepareInput(f, epsgHolder).then(function (r) {
          var name = f.getAttribute("data-param");
          if (r.vector) {
            var epsg = epsgHolder.raster || workingEpsg();
            epsgHolder.vector = epsg;
            return call("vectorReproject", { bytes: enc.encode(JSON.stringify(r.geojson)), format: "geojson", dst: epsg, src: 4326 }).then(function (b) {
              input[name + ".geojson"] = b; args.push("--" + name + "=/work/" + name + ".geojson");
            });
          }
          input[name + "." + r.ext] = r.bytes.slice(); args.push("--" + name + "=/work/" + name + "." + r.ext);
        });
      });
    });
    chain.then(function () {
      fields.forEach(function (f) {
        if (f.hasAttribute("data-input")) return;
        var name = f.getAttribute("data-param"), el = $("input, select", f);
        if (f.hasAttribute("data-bool")) { args.push("--" + name + "=" + (el.checked ? "true" : "false")); return; }
        var v = el.value.trim(); if (v !== "") args.push("--" + name + "=" + v);
      });
      outputs.forEach(function (o) {
        var k = o.schema.dataset && o.schema.dataset.kind, ext = k === "vector" ? "geojson" : "tif";
        args.push("--" + o.name + "=/work/" + toolId + "_" + o.name + "." + ext);
      });
      var s = step("Running " + m.display_name + "…");
      return call("run", { tool: toolId, args: args, input: input }).then(function (res) {
        var names = Object.keys(res.files);
        if (res.exitCode !== 0 || !names.length) {
          s.fail(m.display_name + " didn't finish." + (res.exitCode !== 0 ? " (exit code " + res.exitCode + ")" : " It produced no output."));
          if (res.stdout.length) { logEl.textContent = res.stdout.join("\n"); logEl.hidden = false; }
          var e = new Error("tool failed"); e.shown = true; throw e;
        }
        s.done(m.display_name + " finished in " + ((performance.now() - t0) / 1000).toFixed(1) + " s");
        var epsg = epsgHolder.raster || epsgHolder.vector || workingEpsg();
        var adds = names.map(function (file) {
          var bytes = res.files[file], label = m.display_name + (names.length > 1 ? " · " + file : "");
          if (/\.tiff?$/i.test(file)) {
            return call("rasterInfo", { bytes: bytes.slice() }).then(function (info) {
              var d = addDataset({ kind: "raster", name: label, bytes: bytes, epsg: info.epsg || epsg });
              addRasterLayer(d, info, "Toolbox · " + m.display_name, toolId);
            });
          }
          if (/\.(geo)?json$/i.test(file)) {
            return call("vectorReproject", { bytes: bytes, format: "geojson", dst: 4326, src: epsg }).then(function (b) {
              var d = addDataset({ kind: "vector", name: label, geojson: JSON.parse(new TextDecoder().decode(b)) });
              addVectorLayer(d, "Toolbox · " + m.display_name);
            });
          }
          G.saveBytes(bytes, file);
          return null;
        });
        return Promise.all(adds).then(function () {
          step("Added to the map. Find it under Layers, with a download button.", "done");
          refreshInputs();
          record.status = "done";
        });
      });
    }).catch(function (err) {
      record.status = "error";
      if (!err.shown) showError(err.message);
    }).then(function () {
      running = false; btn.disabled = false;
      record.ms = performance.now() - t0;
      addHistory(record);
    });
  }

  // ---------------------------------------------------------------------------
  // Results on the map
  // ---------------------------------------------------------------------------
  var PALETTES = {
    slope: ["#FFFFE0", "#FED976", "#FD8D3C", "#E31A1C", "#800026"],
    aspect: ["#E41A1C", "#FF7F00", "#FFFF33", "#4DAF4A", "#377EB8", "#984EA3", "#E41A1C"],
    hillshade: ["#000000", "#FFFFFF"],
    d8_flow_accum: ["#F7FBFF", "#9ECAE1", "#4292C6", "#08519C", "#08306B"],
    extract_streams: ["#2171B5", "#08306B"],
    fill_depressions: ["#0B6E4F", "#5FA35F", "#C9CB86", "#DDB06B", "#B1773F", "#F2F2F2"],
    watershed: ["#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854"],
  };
  var DEFAULT_RAMP = ["#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"];
  var VECTOR_COLORS = ["#C2410C", "#7C3AED", "#0E7490", "#BE185D", "#4D7C0F"];
  var resSeq = 0;
  function hexRgb(h) { var n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255, 1]; }
  function fmt(v) { return Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (Math.round(v * 100) / 100).toString(); }

  function addRasterLayer(d, info, source, toolId) {
    var epsg = info.epsg || d.epsg;
    var known = epsg === 4326 || epsg === 3857 || ensureProj(epsg);
    var def = { id: "result-" + (++resSeq), name: d.name, source: source, type: "raster",
      download: { bytes: d.bytes, name: d.name.replace(/[^\w.-]+/g, "_") + ".tif", mime: "image/tiff" } };
    if (!known) {
      showError("The result uses EPSG:" + epsg + ", which the map can't display yet. It's listed under Layers so you can download it.");
      G.addResult(def, new ol.layer.Vector({ source: new ol.source.Vector() }));
      return;
    }
    var st = info.stats || {}, min = Number(st.min), max = Number(st.max);
    if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
    if (max === min) max = min + 1;
    var pal = (toolId && PALETTES[toolId]) || DEFAULT_RAMP;
    var stops = [];
    pal.forEach(function (c, i) { stops.push(min + (max - min) * i / (pal.length - 1), hexRgb(c)); });
    var ramp = ["interpolate", ["linear"], ["band", 1]].concat(stops);
    var hasNodata = info.nodata != null && isFinite(info.nodata);
    var srcCfg = { blob: new Blob([d.bytes], { type: "image/tiff" }), bands: [1] };
    if (hasNodata) srcCfg.nodata = info.nodata;
    // With nodata set, OpenLayers appends an alpha band after the one band we read (band 2).
    var color = hasNodata ? ["case", ["==", ["band", 2], 0], [0, 0, 0, 0], ramp] : ramp;
    var source = new ol.source.GeoTIFF({ sources: [srcCfg], normalize: false, interpolate: false, projection: "EPSG:" + epsg, wrapX: false });
    var layer = new ol.layer.WebGLTile({ source: source, style: { color: color } });
    // Fit to the extent the GeoTIFF itself reports, once OpenLayers has read it.
    function fitToSource() {
      var tg = source.getTileGrid();
      if (!tg) return;
      var ext = ol.proj.transformExtent(tg.getExtent(), "EPSG:" + epsg, G.view.getProjection());
      if (!ext.every(isFinite)) return;
      layer.set("fitExtent", ext);
      G.view.fit(ext, { padding: [80, 80, 80, 80], duration: 600, maxZoom: 15 });
    }
    if (source.getState() === "ready") fitToSource();
    else source.on("change", function onReady() {
      if (source.getState() !== "loading") { source.un("change", onReady); if (source.getState() === "ready") fitToSource(); }
    });
    def.legend = { type: "ramp", palette: pal, min: fmt(min), max: fmt(max), unit: "" };
    G.addResult(def, layer);
  }

  function addVectorLayer(d, source) {
    var color = VECTOR_COLORS[resSeq % VECTOR_COLORS.length];
    var feats = new ol.format.GeoJSON().readFeatures(d.geojson, { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" });
    var style = new ol.style.Style({
      stroke: new ol.style.Stroke({ color: color, width: 2 }),
      fill: new ol.style.Fill({ color: color + "33" }),
      image: new ol.style.Circle({ radius: 6, fill: new ol.style.Fill({ color: color }), stroke: new ol.style.Stroke({ color: "#fff", width: 2 }) }),
    });
    var src = new ol.source.Vector({ features: feats });
    var layer = new ol.layer.Vector({ source: src, style: style, zIndex: 900 });
    if (feats.length) layer.set("fitExtent", src.getExtent());
    var bytes = enc.encode(JSON.stringify(d.geojson));
    G.addResult({ id: "result-" + (++resSeq), name: d.name, source: source + " · " + feats.length + " feature" + (feats.length === 1 ? "" : "s"), type: "vector",
      legend: { type: "classes", items: [[color, "Features"]] },
      download: { bytes: bytes, name: d.name.replace(/[^\w.-]+/g, "_") + ".geojson", mime: "application/geo+json" } }, layer);
  }

  // ---------------------------------------------------------------------------
  // History
  // ---------------------------------------------------------------------------
  var history = [];
  function addHistory(r) {
    history.unshift(r);
    $("[data-tb-history]").hidden = false;
    $("[data-tb-history-count]").textContent = history.length;
    $("[data-tb-history-list]").innerHTML = history.slice(0, 20).map(function (h) {
      return '<li class="is-' + h.status + '"><span>' + esc(h.tool) + "</span><span>" + (h.status === "done" ? (h.ms / 1000).toFixed(1) + " s" : h.status === "error" ? "Failed" : "…") + "</span></li>";
    }).join("");
  }

  if (G.store.get("toolbox") === "open" && !small()) setOpen(true);

  return function destroy() {
    ac.abort();
    observers.forEach(function (o) { o.disconnect(); });
    if (worker) { worker.terminate(); worker = null; }
    uploadInput.remove();
  };
}
