// The OpenLayers pieces the Geo-Portal engine uses, gathered under one `ol`
// namespace so the engine code reads like the original full-build version.
import Map from "ol/Map.js";
import Overlay from "ol/Overlay.js";
import View from "ol/View.js";
import Attribution from "ol/control/Attribution.js";
import ScaleLine from "ol/control/ScaleLine.js";
import { createEmpty, extend, getCenter } from "ol/extent.js";
import GeoJSON from "ol/format/GeoJSON.js";
import MVT from "ol/format/MVT.js";
import LineString from "ol/geom/LineString.js";
import Polygon from "ol/geom/Polygon.js";
import Draw from "ol/interaction/Draw.js";
import { defaults as interactionDefaults } from "ol/interaction/defaults.js";
import ImageLayer from "ol/layer/Image.js";
import TileLayer from "ol/layer/Tile.js";
import VectorLayer from "ol/layer/Vector.js";
import VectorTileLayer from "ol/layer/VectorTile.js";
import WebGLTileLayer from "ol/layer/WebGLTile.js";
import { fromLonLat, get as getProjection, toLonLat, transformExtent } from "ol/proj.js";
import { register as registerProj4 } from "ol/proj/proj4";
import GeoTIFF from "ol/source/GeoTIFF.js";
import ImageArcGISRest from "ol/source/ImageArcGISRest.js";
import TileWMS from "ol/source/TileWMS.js";
import VectorSource from "ol/source/Vector.js";
import VectorTileSource from "ol/source/VectorTile.js";
import XYZ from "ol/source/XYZ.js";
import { getArea, getLength } from "ol/sphere.js";
import CircleStyle from "ol/style/Circle.js";
import Fill from "ol/style/Fill.js";
import Stroke from "ol/style/Stroke.js";
import Style from "ol/style/Style.js";

export const ol = {
  Map, View, Overlay,
  control: { Attribution, ScaleLine },
  extent: { createEmpty, extend, getCenter },
  format: { GeoJSON, MVT },
  geom: { LineString, Polygon },
  interaction: { Draw, defaults: { defaults: interactionDefaults } },
  layer: { Image: ImageLayer, Tile: TileLayer, Vector: VectorLayer, VectorTile: VectorTileLayer, WebGLTile: WebGLTileLayer },
  proj: { fromLonLat, toLonLat, transformExtent, get: getProjection, proj4: { register: registerProj4 } },
  source: { GeoTIFF, ImageArcGISRest, TileWMS, Vector: VectorSource, VectorTile: VectorTileSource, XYZ },
  sphere: { getArea, getLength },
  style: { Circle: CircleStyle, Fill, Stroke, Style },
};
