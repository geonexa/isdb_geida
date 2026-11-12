/*
 * GEIDA Geo-Portal engine: OpenLayers map, layer catalogue, basemaps, area tools and
 * saved project areas. Ported from the Django version (static/js/geoportal.js).
 * The React page renders the markup; initGeoportal() wires it up and returns
 * { destroy }. (Processing tools live in the project's Analyses tab: features/toolbox.)
 */
import { renderIcons } from "./icons.js";
import { ol } from "./ol.js";
import { PMTiles } from "pmtiles";

export function initGeoportal(cfg) {
  "use strict";
  var ac = new AbortController(), signal = ac.signal, observers = [];
  var track = function (o) { observers.push(o); return o; };

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var icons = function () { renderIcons(); };
  var store = {
    get: function (k) { try { return localStorage.getItem("geida." + k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem("geida." + k, v); } catch (e) {} }
  };

  var catalog = cfg.catalog;
  var basemaps = cfg.basemaps;
  var defs = {};
  catalog.forEach(function (g) { g.layers.forEach(function (l) { l.type = g.type; defs[l.id] = l; }); });

  var root = $("[data-gp]");
  var mapWrap = $("[data-gp-mapwrap]");
  var MEMBER_EXTENT = ol.proj.transformExtent([-25, -28, 142, 56], "EPSG:4326", "EPSG:3857");

  // Map ------------------------------------------------------------------
  var baseLayer = new ol.layer.Tile({ zIndex: -1, preload: 2 });
  window.geidaMap = null;
  var view = new ol.View({ center: ol.proj.fromLonLat([40, 18]), zoom: 3, minZoom: 2, maxZoom: 19 });
  var map = new ol.Map({
    target: "gp-map",
    layers: [baseLayer],
    view: view,
    // The map div has a tabindex (keyboard access), which by default makes OpenLayers ignore the
    // mouse wheel until the map is clicked. Keep wheel zoom and drag working at all times.
    interactions: ol.interaction.defaults.defaults({ onFocusOnly: false }),
    controls: [
      new ol.control.Attribution({ collapsible: true, collapsed: true }),
      new ol.control.ScaleLine({ target: $("[data-gp-scale]"), units: "metric", minWidth: 70 })
    ]
  });
  window.geidaMap = map; // handy for debugging in the console
  view.fit(MEMBER_EXTENT, { size: map.getSize() || [1200, 800], padding: [40, 40, 40, 40] });

  function setBasemap(id) {
    var b = basemaps.find(function (x) { return x.id === id; }) || basemaps[0];
    baseLayer.setSource(new ol.source.XYZ({ url: b.url, attributions: b.attribution, crossOrigin: "anonymous", maxZoom: b.maxZoom || 19 }));
    $$("[data-gp-basemap]").forEach(function (btn) {
      var on = btn.getAttribute("data-gp-basemap") === b.id;
      btn.classList.toggle("is-on", on);
      btn.setAttribute("aria-checked", String(on));
    });
    $("[data-gp-bm-thumb]").src = b.thumb;
    $("[data-gp-bm-name]").textContent = b.name;
    store.set("basemap", b.id);
  }
  setBasemap(store.get("basemap") || basemaps[0].id);
  $$("[data-gp-basemap]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setBasemap(btn.getAttribute("data-gp-basemap"));
      var wrap = btn.closest("[data-menu]");
      wrap.querySelector("[data-menu-panel]").classList.remove("is-open");
      wrap.querySelector("[data-menu-toggle]").setAttribute("aria-expanded", "false");
    });
  });

  // Layer factory ----------------------------------------------------------
  var vectorStyle = function (color, hover) {
    return new ol.style.Style({
      stroke: new ol.style.Stroke({ color: color, width: hover ? 2.5 : 1.2 }),
      fill: new ol.style.Fill({ color: hover ? "rgba(47,143,78,0.18)" : "rgba(11,59,71,0.04)" })
    });
  };

  function makeLayer(d) {
    var layer;
    if (d.kind === "xyz") {
      layer = new ol.layer.Tile({ source: new ol.source.XYZ({ url: d.url, attributions: d.attribution, crossOrigin: "anonymous", maxZoom: d.maxZoom || 19 }) });
    } else if (d.kind === "wms") {
      layer = new ol.layer.Tile({
        source: new ol.source.TileWMS({ url: d.url, params: { LAYERS: d.wmsLayer, TILED: true, FORMAT: "image/png", TRANSPARENT: true }, attributions: d.attribution, crossOrigin: "anonymous" })
      });
    } else if (d.kind === "cog" || d.kind === "tiles") {
      layer = new ol.layer.Tile({ preload: 1 }); // source arrives from loadTiles()
    } else if (d.kind === "arcgis_image") {
      layer = new ol.layer.Image({
        source: new ol.source.ImageArcGISRest({ url: d.url, params: d.params || {}, attributions: d.attribution, crossOrigin: "anonymous", ratio: 1 })
      });
    } else if (d.kind === "pmtiles") {
      layer = new ol.layer.VectorTile({ declutter: false }); // source set by setPmtilesSource() for the chosen year
    } else if (d.kind === "geojson") {
      var color = (d.legend && d.legend.color) || "#0B3B47";
      layer = new ol.layer.Vector({
        source: new ol.source.Vector({ url: d.url, format: new ol.format.GeoJSON() }),
        style: vectorStyle(color, false)
      });
      layer.set("hoverStyle", vectorStyle(color, true));
      layer.set("queryable", true);
    }
    if (layer) {
      layer.set("gpId", d.id);
      layer.setOpacity(d.opacity != null ? d.opacity : 1);
    }
    return layer;
  }

  // Active layers ----------------------------------------------------------
  var layers = {};   // id -> ol layer
  var order = [];    // top first
  var meta = {};     // id -> { year, status: loading|ready|error, msg }

  function setStatus(id, status, msg) {
    var m = meta[id]; if (!m) return;
    m.status = status; m.msg = msg || "";
    var el = activeList.querySelector('li[data-id="' + id + '"] [data-status]');
    if (el) { el.className = "gp-status-line is-" + status; el.textContent = statusText(m); }
    var item = document.querySelector('.gp-item[data-layer="' + id + '"]');
    if (item) item.classList.toggle("is-loading", status === "loading");
  }
  function statusText(m) {
    if (m.minzoom && view.getZoom() < m.minzoom - 0.5) return "Zoom in to see this layer (zoom " + m.minzoom + " and closer).";
    if (m.status === "loading") return "Loading tiles\u2026";
    if (m.status === "error") return m.msg || "Couldn't load this layer.";
    return "";
  }

  // Cloud-optimised layers: ask GEIDA for the tile URL (TiTiler, or GEIDA's tile route for tiled datasets).
  function loadTiles(id) {
    var d = defs[id], m = meta[id];
    setStatus(id, "loading");
    var url = "/api/geoportal/layers/" + encodeURIComponent(id) + "/tiles/" + (m.year != null ? "?year=" + encodeURIComponent(m.year) : "");
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!layers[id]) return;
        if (!res.ok) throw new Error(res.j.error || "Couldn't load this layer.");
        var pending = 0, src = new ol.source.XYZ({ url: res.j.tiles[0], attributions: d.attribution, crossOrigin: "anonymous", maxZoom: res.j.maxzoom || 20 });
        if (res.j.minzoom) { m.minzoom = res.j.minzoom; layers[id].setMinZoom(res.j.minzoom - 0.5); }
        src.on("tileloadstart", function () { pending++; if (meta[id].status !== "loading") setStatus(id, "loading"); });
        var done = function () { pending = Math.max(0, pending - 1); if (!pending) setStatus(id, "ready"); };
        src.on("tileloadend", done);
        src.on("tileloaderror", done);
        layers[id].setSource(src);
        setStatus(id, "ready");
      })
      .catch(function (err) { setStatus(id, "error", err.message); });
  }

  // PMTiles vector layers (e.g. Fields of The World): tiles read straight from the archive with
  // HTTP range requests, coloured per source layer by a value property (catalogue "pmtiles.layers").
  var stepCache = {};
  function hexRgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
  // Colour of a value on a source layer: linear "ramp", classed "steps", or one "color". Null = not drawn.
  function featureColor(l, v) {
    if (l.ramp) {
      if (l.hide_zero && !(v > 0)) return null;
      var r = l.ramp, i = 1;
      while (i < r.length - 1 && v > r[i][0]) i++;
      var t = Math.max(0, Math.min(1, (v - r[i - 1][0]) / (r[i][0] - r[i - 1][0] || 1)));
      var c0 = hexRgb(r[i - 1][1]), c1 = hexRgb(r[i][1]);
      // Quantised to 2% so styles can be cached.
      t = Math.round(t * 50) / 50;
      return "rgb(" + c0.map(function (c, k) { return Math.round(c + (c1[k] - c) * t); }).join(",") + ")";
    }
    if (l.steps) {
      var c = l.steps[0][1];
      for (var j = 0; j < l.steps.length; j++) if (v >= l.steps[j][0]) c = l.steps[j][1];
      return c;
    }
    return l.color || "#0B3B47";
  }
  function pmtilesStyle(d) {
    var defsByLayer = {};
    d.pmtiles.layers.forEach(function (l) { defsByLayer[l.source_layer] = l; });
    return function (feature, resolution) {
      var l = defsByLayer[feature.get("layer")];
      if (!l) return null;
      // Each source layer only within its zoom range (no density cells over the fields while tiles load).
      var z = Math.log2(156543.03392 / resolution);
      if ((l.minzoom != null && z < l.minzoom - 0.01) || (l.maxzoom != null && z >= l.maxzoom)) return null;
      var color = featureColor(l, Number(feature.get(l.property)) || 0);
      if (!color) return null;
      var key = d.id + "|" + l.source_layer + "|" + color;
      if (!stepCache[key]) {
        var rgb = color.charAt(0) === "#" ? hexRgb(color) : color.slice(4, -1).split(",").map(Number);
        stepCache[key] = new ol.style.Style({
          fill: new ol.style.Fill({ color: "rgba(" + rgb.join(",") + "," + (l.outline ? 0.35 : 0.75) + ")" }),
          stroke: l.outline ? new ol.style.Stroke({ color: typeof l.outline === "string" ? l.outline : "rgba(30,30,30,0.55)", width: 0.8 }) : undefined
        });
      }
      return stepCache[key];
    };
  }
  function setPmtilesSource(id) {
    var d = defs[id], m = meta[id];
    var archive = new PMTiles(d.pmtiles.url.replace(/\{year\}/g, m.year));
    var format = new ol.format.MVT();
    var src = new ol.source.VectorTile({
      format: format,
      url: "pmtiles://{z}/{x}/{y}",
      maxZoom: d.pmtiles.maxzoom || 14,
      attributions: d.attribution,
      tileLoadFunction: function (tile) {
        tile.setLoader(function (extent, resolution, projection) {
          var c = tile.getTileCoord();
          archive.getZxy(c[0], c[1], c[2]).then(function (r) {
            tile.setFeatures(r && r.data ? format.readFeatures(r.data, { extent: extent, featureProjection: projection }) : []);
          }).catch(function () { tile.setFeatures([]); });
        });
      }
    });
    var pending = 0;
    src.on("tileloadstart", function () { pending++; if (meta[id] && meta[id].status !== "loading") setStatus(id, "loading"); });
    var done = function () { pending = Math.max(0, pending - 1); if (!pending) setStatus(id, "ready"); };
    src.on("tileloadend", done);
    src.on("tileloaderror", done);
    layers[id].setStyle(pmtilesStyle(d));
    layers[id].setSource(src);
  }

  function restack() {
    order.forEach(function (id, i) { layers[id].setZIndex(order.length - i); });
  }

  function addLayer(id, ready) {
    if (layers[id]) return;
    var layer = ready || makeLayer(defs[id]);
    if (!layer) return;
    layers[id] = layer;
    meta[id] = { year: defs[id].year || null, status: "ready", msg: "" };
    // New rasters go just below any vector layers at the top, so boundaries stay visible.
    var pos = 0;
    if (defs[id].type === "raster" && !defs[id].result) { while (pos < order.length && defs[order[pos]].type === "vector") pos++; }
    order.splice(pos, 0, id);
    map.addLayer(layer);
    restack();
    renderActive();
    syncItem(id, true);
    if (defs[id].kind === "cog" || defs[id].kind === "tiles") loadTiles(id);
    if (defs[id].kind === "pmtiles") setPmtilesSource(id);
  }
  function syncItem(id, on) {
    var item = document.querySelector('.gp-item[data-layer="' + id + '"]');
    if (item) item.classList.toggle("is-on", on);
    var cb = document.querySelector('[data-gp-toggle="' + id + '"]');
    if (cb) cb.checked = on;
  }

  function removeLayer(id) {
    if (!layers[id]) return;
    map.removeLayer(layers[id]);
    delete layers[id];
    delete meta[id];
    var item = document.querySelector('.gp-item[data-layer="' + id + '"]');
    if (item) item.classList.remove("is-loading");
    order = order.filter(function (x) { return x !== id; });
    syncItem(id, false);
    if (defs[id] && defs[id].result) { if (defs[id].onRemove) defs[id].onRemove(); delete defs[id]; }
    restack();
    renderActive();
  }

  function legendHTML(d) {
    var lg = d.legend;
    if (!lg) return "";
    if (lg.type === "classes") {
      return '<div class="gp-legend">' + lg.items.map(function (it) {
        return '<div class="gp-legend-row"><span class="gp-swatch" style="background:' + it[0] + '"></span>' + it[1] + "</div>";
      }).join("") + "</div>";
    }
    if (lg.type === "ramp") {
      var colors = lg.palette || [lg.from, lg.to];
      return '<div class="gp-legend"><div class="gp-ramp" style="background:linear-gradient(90deg,' + colors.join(",") + ')"></div>' +
        '<div class="gp-ramp-labels"><span>' + lg.min + "</span>" + (lg.unit ? '<span class="gp-unit">' + lg.unit + "</span>" : "") + "<span>" + lg.max + "</span></div></div>";
    }
    if (lg.type === "line") {
      return '<div class="gp-legend"><div class="gp-legend-row"><span class="gp-line-swatch" style="border-color:' + lg.color + '"></span>Boundary</div></div>';
    }
    return "";
  }

  var activeList = $("[data-gp-active]");
  function renderActive() {
    activeList.innerHTML = order.map(function (id, i) {
      var d = defs[id], l = layers[id], pct = Math.round(l.getOpacity() * 100), vis = l.getVisible();
      return '<li data-id="' + id + '" class="' + (vis ? "" : "is-hidden") + '">' +
        '<div class="gp-active-top">' +
          '<button type="button" class="gp-icon-btn" data-act="vis" aria-label="' + (vis ? "Hide " : "Show ") + d.name + '" title="' + (vis ? "Hide" : "Show") + '"><i data-lucide="' + (vis ? "eye" : "eye-off") + '"></i></button>' +
          '<span class="gp-active-name">' + (d.result ? '<span class="gp-result-tag">Result</span>' : "") + d.name + "<small>" + d.source + "</small></span>" +
          '<button type="button" class="gp-icon-btn" data-act="up" aria-label="Move up" title="Move up"' + (i === 0 ? " disabled" : "") + '><i data-lucide="chevron-up"></i></button>' +
          '<button type="button" class="gp-icon-btn" data-act="down" aria-label="Move down" title="Move down"' + (i === order.length - 1 ? " disabled" : "") + '><i data-lucide="chevron-down"></i></button>' +
          '<button type="button" class="gp-icon-btn" data-act="zoom" aria-label="Zoom to layer" title="Zoom to layer"><i data-lucide="scan"></i></button>' +
          (d.download ? '<button type="button" class="gp-icon-btn" data-act="download" aria-label="Download ' + d.name + '" title="Download"><i data-lucide="download"></i></button>' : "") +
          '<button type="button" class="gp-icon-btn" data-act="remove" aria-label="Remove ' + d.name + '" title="Remove"><i data-lucide="x"></i></button>' +
        "</div>" +
        (d.years && d.years.length ? '<label class="gp-year"><span>' + (d.period_label || "Year") + '</span><select data-act="year" aria-label="' + (d.period_label || "Year") + " for " + d.name + '">' +
          d.years.slice().reverse().map(function (y) { return '<option value="' + y + '"' + (y === meta[id].year ? " selected" : "") + ">" + y + "</option>"; }).join("") +
          "</select></label>" : "") +
        '<p class="gp-status-line is-' + meta[id].status + '" data-status>' + statusText(meta[id]) + "</p>" +
        '<label class="gp-opacity"><span>Opacity</span><input type="range" min="0" max="100" value="' + pct + '" data-act="opacity" aria-label="Opacity for ' + d.name + '"><output>' + pct + "%</output></label>" +
        legendHTML(d) +
      "</li>";
    }).join("");
    $("[data-gp-active-empty]").hidden = order.length > 0;
    var count = $("[data-gp-count]");
    count.textContent = order.length;
    count.classList.toggle("has", order.length > 0);
    icons();
  }

  activeList.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-act]");
    // Year select and opacity slider handle their own events; re-rendering here would close the open dropdown.
    if (!btn || btn.tagName === "INPUT" || btn.tagName === "SELECT") return;
    var id = btn.closest("li").getAttribute("data-id"), i = order.indexOf(id), act = btn.getAttribute("data-act");
    if (act === "vis") layers[id].setVisible(!layers[id].getVisible());
    if (act === "remove") return removeLayer(id);
    if (act === "up" && i > 0) { order.splice(i, 1); order.splice(i - 1, 0, id); restack(); }
    if (act === "down" && i < order.length - 1) { order.splice(i, 1); order.splice(i + 1, 0, id); restack(); }
    if (act === "download" && defs[id].download) { var dl = defs[id].download; saveBytes(dl.bytes, dl.name, dl.mime); return; }
    if (act === "zoom") {
      var src = layers[id].getSource(), fit = layers[id].get("fitExtent");
      if (fit) view.fit(fit, { padding: [60, 60, 60, 60], duration: 500, maxZoom: 16 });
      else if (src.getExtent && src.getFeatures && src.getFeatures().length) view.fit(src.getExtent(), { padding: [60, 60, 60, 60], duration: 500 });
      else view.fit(MEMBER_EXTENT, { padding: [40, 40, 40, 40], duration: 500 });
    }
    renderActive();
  });
  activeList.addEventListener("change", function (e) {
    if (e.target.getAttribute("data-act") !== "year") return;
    var id = e.target.closest("li").getAttribute("data-id");
    var v = e.target.value;
    meta[id].year = /^\d+$/.test(v) ? Number(v) : v; // years are numbers; months and dates stay strings
    if (defs[id].kind === "pmtiles") setPmtilesSource(id); else loadTiles(id);
  });
  activeList.addEventListener("input", function (e) {
    if (e.target.getAttribute("data-act") !== "opacity") return;
    var id = e.target.closest("li").getAttribute("data-id");
    layers[id].setOpacity(e.target.value / 100);
    e.target.nextElementSibling.textContent = e.target.value + "%";
  });

  // Catalog ----------------------------------------------------------------
  $$("[data-gp-toggle]").forEach(function (cb) {
    cb.addEventListener("change", function () {
      var id = cb.getAttribute("data-gp-toggle");
      if (cb.checked) addLayer(id); else removeLayer(id);
    });
    if (defs[cb.getAttribute("data-gp-toggle")].default) { cb.checked = true; addLayer(cb.getAttribute("data-gp-toggle")); }
  });

  $$("[data-gp-info]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var box = document.getElementById(btn.getAttribute("aria-controls"));
      var open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!open));
      box.hidden = open;
    });
  });

  var typeFilter = "all";
  function applyFilter() {
    var q = $("[data-gp-search]").value.trim().toLowerCase(), any = false;
    $$(".gp-group").forEach(function (g) {
      var typeOk = typeFilter === "all" || g.getAttribute("data-type") === typeFilter, shown = 0;
      $$(".gp-item", g).forEach(function (it) {
        var ok = typeOk && (!q || it.getAttribute("data-search").indexOf(q) !== -1);
        it.hidden = !ok; if (ok) shown++;
      });
      g.hidden = shown === 0;
      if (q && shown) g.open = true;
      if (shown) any = true;
    });
    $("[data-gp-noresults]").hidden = any;
  }
  $("[data-gp-search]").addEventListener("input", applyFilter);
  $$("[data-gp-filter] button").forEach(function (b) {
    b.addEventListener("click", function () {
      typeFilter = b.getAttribute("data-type");
      $$("[data-gp-filter] button").forEach(function (x) { x.classList.toggle("is-on", x === b); x.setAttribute("aria-pressed", String(x === b)); });
      applyFilter();
    });
  });

  // Floating catalog window -----------------------------------------------
  var win = $("[data-gp-catwin]"), head = $("[data-gp-drag]");
  var openers = $$("[data-gp-open-catalog]");
  var small = function () { return window.innerWidth <= 720; };

  function clampWin() {
    if (win.hidden || small()) return;
    var W = mapWrap.clientWidth, H = mapWrap.clientHeight;
    var left = Math.min(Math.max(0, win.offsetLeft), Math.max(0, W - win.offsetWidth - 62)); // keep clear of the map buttons
    var top = Math.min(Math.max(0, win.offsetTop), Math.max(0, H - 56));
    win.style.left = left + "px"; win.style.top = top + "px";
  }
  function savePos() {
    store.set("catalogPos", JSON.stringify({ left: win.offsetLeft, top: win.offsetTop, w: win.offsetWidth, h: win.offsetHeight }));
  }
  (function restorePos() {
    try {
      var p = JSON.parse(store.get("catalogPos") || "null");
      if (p && !small()) { win.style.left = p.left + "px"; win.style.top = p.top + "px"; if (p.w) win.style.width = p.w + "px"; if (p.h) win.style.height = p.h + "px"; }
    } catch (e) {}
  })();

  function setCatalog(open, focus) {
    win.hidden = !open;
    openers.forEach(function (b) { b.setAttribute("aria-expanded", String(open)); });
    store.set("catalog", open ? "open" : "closed");
    if (open) { clampWin(); if (focus !== false) $("[data-gp-search]").focus(); }
  }
  openers.forEach(function (b) {
    b.addEventListener("click", function () {
      var toggle = b.hasAttribute("data-gp-catalog-toggle");
      setCatalog(toggle ? win.hidden : true);
    });
  });
  $("[data-gp-close-catalog]").addEventListener("click", function () { setCatalog(false); openers[0].focus(); });
  win.addEventListener("keydown", function (e) { if (e.key === "Escape" && !drawInt) { setCatalog(false); openers[0].focus(); } });

  // Drag with mouse, pen or touch
  var drag = null;
  head.setAttribute("tabindex", "0");
  head.setAttribute("aria-label", "Data catalog. Drag, or use arrow keys, to move. Double-click to reset position.");
  head.addEventListener("pointerdown", function (e) {
    if (small() || e.button !== 0 || e.target.closest("button")) return;
    drag = { x: e.clientX, y: e.clientY, left: win.offsetLeft, top: win.offsetTop };
    head.setPointerCapture(e.pointerId);
    win.classList.add("is-dragging");
    e.preventDefault();
  });
  head.addEventListener("pointermove", function (e) {
    if (!drag) return;
    win.style.left = drag.left + e.clientX - drag.x + "px";
    win.style.top = drag.top + e.clientY - drag.y + "px";
    clampWin();
  });
  function endDrag() { if (!drag) return; drag = null; win.classList.remove("is-dragging"); savePos(); }
  head.addEventListener("pointerup", endDrag);
  head.addEventListener("pointercancel", endDrag);
  head.addEventListener("dblclick", function (e) {
    if (e.target.closest("button")) return;
    win.style.left = "14px"; win.style.top = "66px"; win.style.width = ""; win.style.height = ""; clampWin(); savePos();
  });
  // Move with the keyboard
  head.addEventListener("keydown", function (e) {
    var step = e.shiftKey ? 60 : 20, dx = 0, dy = 0;
    if (e.key === "ArrowLeft") dx = -step; else if (e.key === "ArrowRight") dx = step;
    else if (e.key === "ArrowUp") dy = -step; else if (e.key === "ArrowDown") dy = step; else return;
    e.preventDefault();
    win.style.left = win.offsetLeft + dx + "px"; win.style.top = win.offsetTop + dy + "px"; clampWin(); savePos();
  });
  // Remember a resize made with the corner handle
  if (window.ResizeObserver) {
    var rt; track(new ResizeObserver(function () { clearTimeout(rt); rt = setTimeout(function () { if (!win.hidden && !small()) { clampWin(); savePos(); } }, 300); })).observe(win);
  }
  window.addEventListener("resize", clampWin, { signal: signal });

  // The catalog starts closed; it opens from the Catalog button.

  // Panel tabs -------------------------------------------------------------
  var tabs = $$("[data-gp-tabs] [role=tab]");
  function selectTab(t, focus) {
    tabs.forEach(function (x) {
      var on = x === t;
      x.setAttribute("aria-selected", String(on)); x.tabIndex = on ? 0 : -1;
      document.getElementById(x.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) t.focus();
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { selectTab(t); });
    t.addEventListener("keydown", function (e) {
      var n = e.key === "ArrowRight" ? tabs[(i + 1) % tabs.length] : e.key === "ArrowLeft" ? tabs[(i - 1 + tabs.length) % tabs.length] : null;
      if (n) { e.preventDefault(); selectTab(n, true); }
    });
  });

  // Collapse panel ---------------------------------------------------------
  var collapseBtn = $("[data-gp-collapse]"), expandBtn = $("[data-gp-expand]");
  function setCollapsed(c) {
    root.classList.toggle("is-collapsed", c);
    collapseBtn.setAttribute("aria-expanded", String(!c));
    expandBtn.hidden = !c;
    store.set("panel", c ? "closed" : "open");
    var start = performance.now();
    (function tick(now) { map.updateSize(); if (now - start < 320) requestAnimationFrame(tick); else if (typeof clampWin === "function") clampWin(); })(start);
  }
  collapseBtn.addEventListener("click", function () { setCollapsed(true); expandBtn.focus(); });
  expandBtn.addEventListener("click", function () { setCollapsed(false); collapseBtn.focus(); });
  if (store.get("panel") === "closed" || window.innerWidth < 720) setCollapsed(true);

  // Map controls -----------------------------------------------------------
  $$("[data-gp-zoom]").forEach(function (b) {
    b.addEventListener("click", function () { view.animate({ zoom: view.getZoom() + Number(b.getAttribute("data-gp-zoom")), duration: 250 }); });
  });
  $("[data-gp-home]").addEventListener("click", function () { view.fit(MEMBER_EXTENT, { padding: [40, 40, 40, 40], duration: 600 }); });
  $("[data-gp-locate]").addEventListener("click", function () {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(function (p) {
      view.animate({ center: ol.proj.fromLonLat([p.coords.longitude, p.coords.latitude]), zoom: 12, duration: 700 });
    });
  });
  $("[data-gp-fullscreen]").addEventListener("click", function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (mapWrap.requestFullscreen) mapWrap.requestFullscreen();
  });
  document.addEventListener("fullscreenchange", function () {
    mapWrap.classList.toggle("is-fullscreen", !!document.fullscreenElement);
    setTimeout(function () { map.updateSize(); }, 50);
  }, { signal: signal });

  var coordsEl = $("[data-gp-coords]"), zoomEl = $("[data-gp-zoomlevel]");
  map.on("pointermove", function (e) {
    var ll = ol.proj.toLonLat(e.coordinate);
    coordsEl.textContent = Math.abs(ll[1]).toFixed(4) + "\u00b0" + (ll[1] >= 0 ? "N" : "S") + "  " + Math.abs(ll[0]).toFixed(4) + "\u00b0" + (ll[0] >= 0 ? "E" : "W");
  });
  map.on("moveend", function () {
    zoomEl.textContent = Math.round(view.getZoom() * 10) / 10;
    // Layers drawn only from a zoom level say so in the active list.
    Object.keys(meta).forEach(function (id) { if (meta[id].minzoom) setStatus(id, meta[id].status, meta[id].msg); });
  });
  window.addEventListener("resize", function () { map.updateSize(); }, { signal: signal });

  // Hover and popup --------------------------------------------------------
  var hovered = null, drawing = false;
  map.on("pointermove", function (e) {
    if (e.dragging || drawing) return;
    var hit = null;
    map.forEachFeatureAtPixel(e.pixel, function (f, l) { if (l && l.get("queryable")) { hit = [f, l]; return true; } });
    if (hovered && (!hit || hit[0] !== hovered[0])) { hovered[0].setStyle(undefined); hovered = null; }
    if (hit && !hovered) { hit[0].setStyle(hit[1].get("hoverStyle")); hovered = hit; }
    map.getTargetElement().style.cursor = hit ? "pointer" : "";
  });

  var popupEl = $("[data-gp-popup]");
  var popup = new ol.Overlay({ element: popupEl, autoPan: { animation: { duration: 250 } }, stopEvent: true });
  map.addOverlay(popup);
  map.on("singleclick", function (e) {
    if (drawing) return;
    var hit = null;
    map.forEachFeatureAtPixel(e.pixel, function (f, l) { if (l && l.get("queryable")) { hit = [f, l]; return true; } });
    if (!hit) { popup.setPosition(undefined); popupEl.hidden = true; return; }
    var p = hit[0].getProperties(), d = defs[hit[1].get("gpId")];
    $("[data-gp-popup-body]").innerHTML = "<h3>" + (p.name || "Feature") + "</h3><p>" + d.name + (p.iso ? " &middot; " + p.iso : "") + "</p>";
    popupEl.hidden = false;
    popup.setPosition(e.coordinate);
  });
  $("[data-gp-popup-close]").addEventListener("click", function () { popup.setPosition(undefined); popupEl.hidden = true; });

  // Area of interest -------------------------------------------------------
  var aoiSource = new ol.source.Vector();
  var aoiLayer = new ol.layer.Vector({
    source: aoiSource, zIndex: 999,
    // Selected project area: solid yellow with a dark halo so it reads on any basemap.
    style: [
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(20,20,20,0.55)", width: 6 }) }),
      new ol.style.Style({
        stroke: new ol.style.Stroke({ color: "#FFD60A", width: 3 }),
        fill: new ol.style.Fill({ color: "rgba(255,214,10,0.22)" })
      })
    ]
  });
  map.addLayer(aoiLayer);
  var drawInt = null;

  function boxGeometry(coords, geom) {
    var a = coords[0], b = coords[coords.length - 1];
    var ring = [[a[0], a[1]], [b[0], a[1]], [b[0], b[1]], [a[0], b[1]], [a[0], a[1]]];
    if (!geom) geom = new ol.geom.Polygon([ring]); else geom.setCoordinates([ring]);
    return geom;
  }
  function fmtArea(m2) { return m2 >= 1e6 ? (m2 / 1e6).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km\u00b2" : (m2 / 1e4).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " ha"; }
  function fmtLen(m) { return m >= 1000 ? (m / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km" : Math.round(m) + " m"; }

  function showAoi() {
    var feats = aoiSource.getFeatures();
    $("[data-gp-aoi]").hidden = !feats.length;
    // Save and download only make sense once an area is drawn, uploaded or selected.
    $$("[data-gp-save-open], [data-gp-download]").forEach(function (b) { b.disabled = !feats.length; b.hidden = !feats.length; });
    if (!feats.length) return;
    var area = 0, perim = 0;
    feats.forEach(function (f) {
      var g = f.getGeometry();
      area += ol.sphere.getArea(g);
      var polys = g.getType() === "MultiPolygon" ? g.getPolygons() : g.getType() === "Polygon" ? [g] : [];
      polys.forEach(function (p) { perim += ol.sphere.getLength(new ol.geom.LineString(p.getLinearRing(0).getCoordinates())); });
    });
    detectCountry();
    $("[data-gp-area]").textContent = fmtArea(area);
    $("[data-gp-perim]").textContent = fmtLen(perim);
  }

  function stopDraw() {
    if (drawInt) map.removeInteraction(drawInt);
    drawInt = null; drawing = false;
    $$("[data-gp-draw]").forEach(function (b) { b.classList.remove("is-on"); b.setAttribute("aria-pressed", "false"); });
    $("[data-gp-draw-hint]").hidden = true;
  }
  $$("[data-gp-draw]").forEach(function (b) {
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () {
      var mode = b.getAttribute("data-gp-draw"), wasOn = b.classList.contains("is-on");
      stopDraw();
      if (wasOn) return;
      drawInt = new ol.interaction.Draw(mode === "Box" ? { source: aoiSource, type: "Circle", geometryFunction: boxGeometry } : { source: aoiSource, type: "Polygon" });
      drawInt.on("drawstart", function () { aoiSource.clear(); areaChanged(); });
      drawInt.on("drawend", function () { setTimeout(function () { stopDraw(); showAoi(); }, 0); });
      map.addInteraction(drawInt);
      drawing = true;
      b.classList.add("is-on"); b.setAttribute("aria-pressed", "true");
      $("[data-gp-draw-hint]").hidden = false;
      $("[data-gp-draw-hint]").textContent = mode === "Box" ? "Click and drag on the map to draw a rectangle. Press Esc to cancel." : "Click on the map to add points. Double-click to finish. Press Esc to cancel.";
      popup.setPosition(undefined); popupEl.hidden = true;
    });
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && drawInt) stopDraw(); }, { signal: signal });

  $("[data-gp-upload]").addEventListener("change", function (e) {
    var file = e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var feats = new ol.format.GeoJSON().readFeatures(reader.result, { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" })
          .filter(function (f) { var t = f.getGeometry() && f.getGeometry().getType(); return t === "Polygon" || t === "MultiPolygon"; });
        if (!feats.length) throw new Error("no polygons");
        aoiSource.clear(); aoiSource.addFeatures(feats);
        view.fit(aoiSource.getExtent(), { padding: [60, 60, 60, 60], duration: 600, maxZoom: 15 });
        areaChanged();
        showAoi();
        var nameInput = $("[data-gp-area-name]");
        if (nameInput) nameInput.dataset.suggest = file.name.replace(/\.[^.]+$/, "");
      } catch (err) {
        window.dispatchEvent(new CustomEvent("geida:toast", { detail: { kind: "error", text: "This file doesn't contain a polygon GeoJSON in longitude/latitude. Check the file and try again." } }));
      }
      e.target.value = "";
    };
    reader.readAsText(file);
  });
  $("[data-gp-clear]").addEventListener("click", function () { aoiSource.clear(); areaChanged(); showAoi(); });
  $("[data-gp-download]").addEventListener("click", function () {
    var json = new ol.format.GeoJSON().writeFeatures(aoiSource.getFeatures(), { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857", decimals: 6 });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([json], { type: "application/geo+json" }));
    a.download = "geida_project_area.geojson";
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });


  // Country selector -------------------------------------------------------
  var areasCfg = cfg.areas;
  var esc = function (t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var countrySel = $("[data-gp-country]");
  var countryFeats = [];
  var countrySource = new ol.source.Vector();
  map.addLayer(new ol.layer.Vector({
    source: countrySource, zIndex: 998,
    // Selected country: dashed amber outline with a light tint, under the project area.
    style: [
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(20,20,20,0.45)", width: 5 }) }),
      new ol.style.Style({
        stroke: new ol.style.Stroke({ color: "#FFB703", width: 2.5, lineDash: [10, 6] }),
        fill: new ol.style.Fill({ color: "rgba(255,183,3,0.10)" })
      })
    ]
  }));
  fetch(areasCfg.countries).then(function (r) { return r.json(); }).then(function (gj) {
    // The options are rendered by the server; this loads the outlines for zoom and highlight.
    countryFeats = new ol.format.GeoJSON().readFeatures(gj, { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" });
    if (countrySel.value) selectCountry(countrySel.value, true);  // chosen before the outlines arrived
    detectCountry();
  }).catch(function () {});

  function countryByIso(iso) { return countryFeats.find(function (f) { return f.get("iso") === iso; }) || null; }
  function countryAt(coord) { return countryFeats.find(function (f) { return f.getGeometry().intersectsCoordinate(coord); }) || null; }
  function selectCountry(iso, zoom) {
    countrySel.value = iso || "";
    countrySource.clear();
    var f = countryByIso(iso);
    if (!f) { if (zoom) view.fit(MEMBER_EXTENT, { padding: [40, 40, 40, 40], duration: 600 }); return; }
    countrySource.addFeature(f.clone());
    if (zoom) view.fit(f.getGeometry().getExtent(), { padding: [50, 50, 50, 50], duration: 600 });
  }
  countrySel.addEventListener("change", function () { selectCountry(countrySel.value, true); });
  // A new area with no country chosen: pick the country under its centre.
  function detectCountry() {
    if (countrySel.value || !aoiSource.getFeatures().length) return;
    var f = countryAt(ol.extent.getCenter(aoiSource.getExtent()));
    if (f) selectCountry(f.get("iso"), false);
  }

  // Saved project areas (PostGIS) -------------------------------------------
  var savedSel = $("[data-gp-saved]"), moreMenu = $("[data-gp-more]");
  var saveDlg = $("[data-gp-save-dialog]"), delDlg = $("[data-gp-delete-dialog]");
  var saved = [], activeAreaId = null;
  function csrfToken() { var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function api(url, opts) {
    opts = opts || {};
    opts.credentials = "same-origin";
    opts.headers = { Accept: "application/json", "X-CSRFToken": csrfToken() };
    if (opts.body) opts.headers["Content-Type"] = "application/json";
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || "Something went wrong (HTTP " + r.status + "). Try again.");
        return j;
      });
    });
  }
  function aoiGeometry() {
    var feats = aoiSource.getFeatures();
    if (!feats.length) return null;
    var fc = JSON.parse(new ol.format.GeoJSON().writeFeatures(feats, { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857", decimals: 7 }));
    var geoms = fc.features.map(function (f) { return f.geometry; });
    if (geoms.length === 1) return geoms[0];
    var polys = [];
    geoms.forEach(function (g) { if (g.type === "Polygon") polys.push(g.coordinates); if (g.type === "MultiPolygon") polys = polys.concat(g.coordinates); });
    return { type: "MultiPolygon", coordinates: polys };
  }
  function fmtKm(km2) { return km2 >= 1 ? km2.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km²" : (km2 * 100).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " ha"; }
  function saveMsg(text, isError) {
    var el = $("[data-gp-save-msg]"); if (!el) return;
    el.textContent = text || ""; el.hidden = !text; el.classList.toggle("is-error", !!isError);
  }
  function areaChanged() { activeAreaId = null; saveMsg(""); renderSaved(); }

  function renderSaved() {
    if (!savedSel) return;
    savedSel.innerHTML = '<option value="">' + (saved.length ? "Select a saved area (" + saved.length + ")" : "No saved areas yet") + "</option>" +
      saved.map(function (a) {
        return '<option value="' + a.id + '">' + esc(a.name) + "</option>";
      }).join("");
    savedSel.disabled = !saved.length;
    savedSel.value = activeAreaId ? String(activeAreaId) : "";
    if (moreMenu) moreMenu.hidden = !activeAreaId;
    var title = $("[data-gp-aoi-title]"), a = current();
    if (title) title.textContent = a ? a.name : "Project area";
  }
  function current() { return saved.find(function (x) { return x.id === activeAreaId; }) || null; }
  function openArea(a) {
    aoiSource.clear();
    aoiSource.addFeatures(new ol.format.GeoJSON().readFeatures(
      { type: "Feature", geometry: a.geometry, properties: { name: a.name } },
      { dataProjection: "EPSG:4326", featureProjection: "EPSG:3857" }));
    view.fit(aoiSource.getExtent(), { padding: [60, 60, 60, 60], duration: 600, maxZoom: 15 });
    if (a.country_iso && countryByIso(a.country_iso)) selectCountry(a.country_iso, false);
    activeAreaId = a.id;
    showAoi();
    saveMsg("");
    renderSaved();
  }
  function openDialog(dlg) {
    $$("[data-gp-save-err],[data-gp-delete-err]", dlg).forEach(function (e) { e.hidden = true; });
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
  }
  function closeDialog(dlg) { if (dlg.close) dlg.close(); else dlg.removeAttribute("open"); }
  function dlgError(dlg, sel, text) { var e = $(sel, dlg); e.textContent = text; e.hidden = !text; }
  $$("[data-gp-dialog-cancel]").forEach(function (b) { b.addEventListener("click", function () { closeDialog(b.closest("dialog")); }); });

  if (savedSel) {
    api(areasCfg.api).then(function (j) { saved = j.areas || []; renderSaved(); })
      .catch(function (err) { savedSel.innerHTML = '<option value="">' + esc(err.message) + "</option>"; });

    savedSel.addEventListener("change", function () {
      var a = saved.find(function (x) { return String(x.id) === savedSel.value; });
      if (a) openArea(a);
      else { aoiSource.clear(); activeAreaId = null; showAoi(); renderSaved(); saveMsg(""); }  // deselected: remove it from the map
    });

    // Save: button -> dialog asking for the name -> POST
    $("[data-gp-save-open]").addEventListener("click", function () {
      var geom = aoiGeometry();
      if (!geom) return saveMsg("Draw or upload a project area first.", true);
      var opt = countrySel.selectedOptions[0];
      $("[data-gp-save-sub]").textContent = [countrySel.value && opt ? opt.textContent : "", $("[data-gp-area]").textContent].filter(Boolean).join(" · ");
      var input = $("[data-gp-area-name]");
      input.value = current() ? "" : (input.dataset.suggest || "");
      setSaveMode("save");
      openDialog(saveDlg);
      input.focus(); input.select();
    });
    $("[data-gp-area-name]").addEventListener("input", function () { dlgError(saveDlg, "[data-gp-save-err]", ""); });
    $("[data-gp-save]").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = $("[data-gp-area-name]"), name = input.value.trim(), geometry = aoiGeometry();
      if (!name) { dlgError(saveDlg, "[data-gp-save-err]", "Give the area a name."); return input.focus(); }
      if (saveDlg.dataset.mode === "rename") return renameArea(name);
      if (!geometry) { dlgError(saveDlg, "[data-gp-save-err]", "Draw or upload a project area first."); return; }
      var opt = countrySel.selectedOptions[0], btn = $("button[type=submit]", saveDlg);
      btn.disabled = true;
      api(areasCfg.api, {
        method: "POST",
        body: JSON.stringify({ name: name, geometry: geometry, country_iso: countrySel.value, country_name: countrySel.value && opt ? opt.textContent : "" })
      }).then(function (j) {
        saved.unshift(j.area);
        activeAreaId = j.area.id;
        input.dataset.suggest = "";
        renderSaved();
        closeDialog(saveDlg);
        saveMsg("Saved “" + j.area.name + "” to your areas.");
      }).catch(function (err) { dlgError(saveDlg, "[data-gp-save-err]", err.message); })
        .then(function () { btn.disabled = false; });
    });

    // Three-dot menu for the selected saved area: zoom, rename, download, delete
    function setSaveMode(mode) {
      saveDlg.dataset.mode = mode;
      $("#gp-save-title").textContent = mode === "rename" ? "Rename area" : "Save area";
      $("button[type=submit]", saveDlg).lastChild.textContent = mode === "rename" ? "Rename" : "Save";
    }
    function closeMore() {
      $("[data-menu-panel]", moreMenu).classList.remove("is-open");
      $("[data-menu-toggle]", moreMenu).setAttribute("aria-expanded", "false");
    }
    function slug(t) { return String(t).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "area"; }
    function downloadArea(a) {
      var fc = { type: "FeatureCollection", features: [{ type: "Feature", geometry: a.geometry,
        properties: { name: a.name, country: a.country_name || null, country_iso: a.country_iso || null, area_km2: a.area_km2, updated: a.updated } }] };
      saveBytes(new TextEncoder().encode(JSON.stringify(fc)), "geida_" + slug(a.name) + ".geojson", "application/geo+json");
    }
    function renameArea(name) {
      var a = current(), btn = $("button[type=submit]", saveDlg);
      if (!a) return closeDialog(saveDlg);
      btn.disabled = true;
      api(areasCfg.api + a.id + "/", { method: "PATCH", body: JSON.stringify({ name: name }) }).then(function (j) {
        Object.assign(a, j.area);
        renderSaved();
        closeDialog(saveDlg);
        saveMsg("Renamed to “" + a.name + "”.");
      }).catch(function (err) { dlgError(saveDlg, "[data-gp-save-err]", err.message); })
        .then(function () { btn.disabled = false; });
    }
    $("[data-menu-panel]", moreMenu).addEventListener("click", function (e) {
      var item = e.target.closest("[data-area-act]"), a = current();
      if (!item || !a) return;
      closeMore();
      var act = item.getAttribute("data-area-act");
      if (act === "zoom") view.fit(aoiSource.getExtent(), { padding: [60, 60, 60, 60], duration: 600, maxZoom: 15 });
      if (act === "download") downloadArea(a);
      if (act === "rename") {
        setSaveMode("rename");
        $("[data-gp-save-sub]").textContent = [a.country_name, fmtKm(a.area_km2)].filter(Boolean).join(" · ");
        var input = $("[data-gp-area-name]"); input.value = a.name;
        openDialog(saveDlg); input.focus(); input.select();
      }
      if (act === "delete") {
        $("[data-gp-delete-sub]").textContent = "“" + a.name + "” will be removed from your saved areas. This can't be undone.";
        openDialog(delDlg);
      }
    });
    $("[data-gp-delete-form]").addEventListener("submit", function (e) {
      e.preventDefault();
      var a = current(); if (!a) return closeDialog(delDlg);
      var btn = $("button[type=submit]", delDlg); btn.disabled = true;
      api(areasCfg.api + a.id + "/", { method: "DELETE" }).then(function () {
        saved = saved.filter(function (x) { return x.id !== a.id; });
        activeAreaId = null;
        aoiSource.clear(); showAoi();
        renderSaved();
        closeDialog(delDlg);
        saveMsg("");
      }).catch(function (err) { dlgError(delDlg, "[data-gp-delete-err]", err.message); })
        .then(function () { btn.disabled = false; });
    });
  }

  renderActive();

  // Downloads of result layers
  function saveBytes(bytes, name, mime) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([bytes], { type: mime || "application/octet-stream" }));
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  }

  // Dropdown menus inside the portal (basemap picker, saved-area actions).
  var menus = $$("[data-menu]", root);
  function closeMenus(except) {
    menus.forEach(function (m) {
      if (m === except) return;
      var b = m.querySelector("[data-menu-toggle]"), p = m.querySelector("[data-menu-panel]");
      if (b) b.setAttribute("aria-expanded", "false");
      if (p) p.classList.remove("is-open");
    });
  }
  menus.forEach(function (m) {
    var b = m.querySelector("[data-menu-toggle]"), p = m.querySelector("[data-menu-panel]");
    if (!b || !p) return;
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = b.getAttribute("aria-expanded") === "true";
      closeMenus(m);
      b.setAttribute("aria-expanded", String(!open));
      p.classList.toggle("is-open", !open);
    });
  });
  document.addEventListener("click", function (e) { if (!e.target.closest("[data-menu]")) closeMenus(); }, { signal: signal });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenus(); }, { signal: signal });

  icons();
  return {
    destroy: function () {
      ac.abort();
      observers.forEach(function (o) { o.disconnect(); });
      popup.setPosition(undefined);
      map.setTarget(undefined);
      if (window.geidaMap === map) window.geidaMap = null;
    },
  };
}
