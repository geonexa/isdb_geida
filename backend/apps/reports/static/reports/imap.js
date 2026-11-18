/*
 * Interactive maps for the GEIDA web report (Leaflet, embedded in the page). Each figure keeps its static SVG;
 * when a map opens, the SVG is hidden and a live map takes its place: pan and zoom, satellite or light basemap,
 * the result layer with an opacity slider, the area of influence, feature details on click, fullscreen and reset.
 * Raster results reuse the image already in the static map (warped to Web Mercator, so it lines up exactly).
 * If anything fails, the static map stays.
 */
(function () {
  "use strict";
  var spec = document.getElementById("geida-maps");
  if (!spec || !window.L) return;
  var cfg;
  try { cfg = JSON.parse(spec.textContent); } catch (e) { return; }
  var base = cfg.base || {};
  var AREA = "#0B3B47";

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(v) {
    if (typeof v === "number") {
      if (Number.isInteger(v)) return Math.abs(v) >= 10000 ? v.toLocaleString("en") : String(v);
      return Math.abs(v) < 100 ? String(+v.toFixed(2)) : Math.round(v).toLocaleString("en");
    }
    if (typeof v === "boolean") return v ? "Yes" : "No";
    return v;
  }
  function boundsOf(b) { return b ? L.latLngBounds([b[1], b[0]], [b[3], b[2]]) : null; }

  function featureStyle(props, st) {
    var color = st.color || "#1f77b4", width = st.width || 1.6;
    if (st.property && st.classes) {
      var v = props ? props[st.property] : undefined;
      for (var i = 0; i < st.classes.length; i++) {
        var c = st.classes[i];
        if (c.value === v || String(c.value) === String(v)) { color = c.color || color; width = c.width || width; break; }
      }
    }
    return { color: color, width: width };
  }
  function classLabel(props, st) {
    if (!st.property || !st.classes) return "";
    var v = props[st.property];
    for (var i = 0; i < st.classes.length; i++) {
      if (String(st.classes[i].value) === String(v)) return st.classes[i].label || "";
    }
    return "";
  }

  function button(parent, label, title, onClick) {
    var b = L.DomUtil.create("button", "imap-btn", parent);
    b.type = "button"; b.innerHTML = label; b.title = title; b.setAttribute("aria-label", title);
    L.DomEvent.on(b, "click", function (e) { L.DomEvent.stop(e); onClick(b); });
    return b;
  }

  function build(fig) {
    var id = fig.getAttribute("data-imap");
    var m = id === "cover" ? { kind: "area", view: base.area_view } : (cfg.maps || {})[id];
    if (!m) return;
    var holder = fig.querySelector(".imap");
    var stat = fig.querySelector(".smap");
    var ovImg = stat && stat.querySelector("image.ov");
    holder.hidden = false;
    var map = L.map(holder, { zoomSnap: 0.25, zoomDelta: 0.5, scrollWheelZoom: false, attributionControl: true,
                              zoomControl: false, worldCopyJump: true });
    map.attributionControl.setPrefix(false);
    L.control.zoom({ position: "topright" }).addTo(map);
    var globe = fig.querySelector(".imap-globe");
    if (globe) { holder.appendChild(globe); globe.hidden = false; }

    // Basemaps
    var tiles = {}, current = base.basemap || "satellite";
    Object.keys(base.basemaps || {}).forEach(function (k) {
      var b = base.basemaps[k];
      tiles[k] = L.tileLayer(b.url, { maxNativeZoom: b.max_zoom, maxZoom: 19, attribution: esc(b.attribution) });
    });
    if (tiles[current]) tiles[current].addTo(map);

    // Area of influence (outside dimmed on the cover and on vector maps)
    var areaLayer = null;
    if (base.area) {
      var outer = [[[-89, -360], [-89, 360], [89, 360], [89, -360]]];
      var holes = [];
      var polys = base.area.type === "Polygon" ? [base.area.coordinates] : base.area.coordinates;
      polys.forEach(function (p) { holes.push(p[0].map(function (c) { return [c[1], c[0]]; })); });
      var group = [];
      if (m.kind !== "raster") {
        group.push(L.polygon(outer.concat(holes), { stroke: false, fillColor: current === "satellite" ? "#000" : "#fff",
                                                     fillOpacity: current === "satellite" ? 0.35 : 0.45, interactive: false }));
      }
      group.push(L.geoJSON(base.area, { interactive: false, style: { color: "#fff", weight: 4.5, opacity: 0.8, fill: false } }));
      group.push(L.geoJSON(base.area, { interactive: false, style: { color: AREA, weight: 2.2, fill: false } }));
      areaLayer = L.layerGroup(group);
    }

    // The result layer
    var layer = null, vectorStyle = null, opacity = m.kind === "raster" ? 0.92 : (m.style && m.style.opacity != null ? m.style.opacity : 0.35);
    if (m.kind === "raster" && ovImg && m.bounds) {
      layer = L.imageOverlay(ovImg.getAttribute("href"), boundsOf(m.bounds), { opacity: opacity, className: "imap-raster" });
    } else if (m.kind === "vector" && m.data) {
      var st = m.style || {};
      var many = m.data.features.length > 2000;
      var hasPoly = m.data.features.some(function (f) { return /Polygon/.test(f.geometry.type); });
      if (!hasPoly) opacity = 1;      // lines and points: the slider fades the whole feature
      vectorStyle = function (f) {
        var s = featureStyle(f.properties, st);
        if (/Polygon/.test(f.geometry.type)) {
          return { color: st.outline || s.color, weight: Math.min(s.width, 2), fillColor: s.color, fillOpacity: opacity };
        }
        if (/Point/.test(f.geometry.type)) {
          return { radius: many ? 3 : 5, color: "#fff", weight: 1, opacity: opacity, fillColor: s.color, fillOpacity: 0.95 * opacity };
        }
        return { color: s.color, weight: s.width, opacity: opacity, lineCap: "round", lineJoin: "round" };
      };
      var renderer = m.data.features.length > 3000 ? L.canvas({ padding: 0.3 }) : undefined;
      layer = L.geoJSON(m.data, {
        renderer: renderer,
        style: vectorStyle,
        pointToLayer: function (f, ll) { return L.circleMarker(ll, L.extend({ renderer: renderer }, vectorStyle(f))); },
        onEachFeature: function (f, l) {
          var p = f.properties || {}, keys = Object.keys(p);
          var head = classLabel(p, st);
          var rows = keys.filter(function (k) { return p[k] !== null && p[k] !== ""; }).map(function (k) {
            return "<tr><th>" + esc((k.charAt(0).toUpperCase() + k.slice(1)).replace(/_/g, " ")) + "</th><td>" + esc(fmt(p[k])) + "</td></tr>";
          }).join("");
          if (!rows && !head) return;
          l.bindPopup("<div class='imap-pop'><strong>" + esc(head || m.title) + "</strong>" +
                      (rows ? "<table>" + rows + "</table>" : "") + "</div>", { maxWidth: 320 });
          l.on("mouseover", function () { if (l.setStyle) l.setStyle({ weight: (l.options.weight || 1.6) + 1.5 }); });
          l.on("mouseout", function () { if (l.setStyle) layer.resetStyle(l); });
        }
      });
    }
    if (areaLayer && m.kind === "raster") areaLayer.addTo(map);
    if (layer) layer.addTo(map);
    if (areaLayer && m.kind !== "raster") areaLayer.addTo(map);

    var home = boundsOf(m.view) || (layer && layer.getBounds && layer.getBounds()) || boundsOf(m.bounds);
    if (home) map.fitBounds(home, { padding: [4, 4] }); else map.setView([0, 0], 2);
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

    // Tools: fullscreen, reset view, basemap, layers, opacity
    var Tools = L.Control.extend({
      options: { position: "topright" },
      onAdd: function () {
        var box = L.DomUtil.create("div", "imap-tools");
        L.DomEvent.disableClickPropagation(box);
        L.DomEvent.disableScrollPropagation(box);
        button(box, "&#x26F6;", "Full screen", function () {
          if (document.fullscreenElement) document.exitFullscreen();
          else if (fig.requestFullscreen) fig.requestFullscreen();
        });
        button(box, "&#x2302;", "Back to the full view", function () { if (home) map.fitBounds(home, { padding: [4, 4] }); });
        var panel;
        var toggle = button(box, "&#x2630;", "Basemap and layers", function () {
          panel.hidden = !panel.hidden;
          toggle.setAttribute("aria-expanded", String(!panel.hidden));
        });
        panel = L.DomUtil.create("div", "imap-panel", box);
        panel.hidden = holder.clientWidth < 640;          // folded on small screens
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        var html = "<label>Basemap <select data-k='base'>";
        Object.keys(tiles).forEach(function (k) {
          html += "<option value='" + k + "'" + (k === current ? " selected" : "") + ">" + (k === "satellite" ? "Satellite" : "Light") + "</option>";
        });
        html += "</select></label>";
        if (layer) {
          html += "<label class='imap-check'><input type='checkbox' data-k='layer' checked> " + esc(m.title || "Result") + "</label>";
          html += "<label>Opacity <input type='range' min='0' max='1' step='0.05' value='" + opacity + "' data-k='op'></label>";
        }
        if (areaLayer && m.kind !== "area") html += "<label class='imap-check'><input type='checkbox' data-k='area' checked> Area of influence</label>";
        panel.innerHTML = html;
        L.DomEvent.on(panel, "input change", function (e) {
          var t = e.target, k = t.getAttribute("data-k");
          if (k === "base") {
            if (tiles[current]) map.removeLayer(tiles[current]);
            current = t.value; tiles[current].addTo(map); tiles[current].bringToBack();
          } else if (k === "layer") {
            t.checked ? layer.addTo(map) : map.removeLayer(layer);
          } else if (k === "area") {
            t.checked ? areaLayer.addTo(map) : map.removeLayer(areaLayer);
          } else if (k === "op") {
            opacity = +t.value;
            if (layer.setOpacity) layer.setOpacity(opacity); else layer.setStyle(vectorStyle);
          }
        });
        return box;
      }
    });
    map.addControl(new Tools());

    // Scroll zooms only once the map was clicked, so the page still scrolls past it.
    var hint = L.DomUtil.create("div", "imap-hint", holder);
    hint.textContent = "Click the map to zoom with the mouse wheel";
    map.on("click focus", function () { map.scrollWheelZoom.enable(); holder.classList.add("is-active"); });
    holder.addEventListener("mouseleave", function () { map.scrollWheelZoom.disable(); holder.classList.remove("is-active"); });
    document.addEventListener("fullscreenchange", function () {
      setTimeout(function () { map.invalidateSize(); }, 50);
      if (document.fullscreenElement === fig) map.scrollWheelZoom.enable();
    });

    if (stat) stat.hidden = true;
    fig.classList.add("is-live");
  }

  var figs = Array.prototype.slice.call(document.querySelectorAll("[data-imap]"));
  function open(fig) {
    if (fig.__imap) return;
    fig.__imap = true;
    try { build(fig); } catch (e) {
      // Keep the static picture.
      var h = fig.querySelector(".imap"); if (h) h.hidden = true;
      var s = fig.querySelector(".smap"); if (s) s.hidden = false;
      if (window.console) console.warn("Interactive map unavailable", e);
    }
  }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { io.unobserve(en.target); open(en.target); } });
    }, { rootMargin: "300px" });
    figs.forEach(function (f) { io.observe(f); });
  } else {
    figs.forEach(open);
  }
})();
