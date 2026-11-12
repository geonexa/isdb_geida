# Vegetation indices (NDVI, EVI, SAVI, NDMI)

**Question:** How green and healthy is the vegetation in a chosen period?

## Method

1. Sentinel-2 L2A scenes (collection 1) over the area in the chosen year and season are found
   in the Earth Search STAC catalogue; scenes cloudier than the limit are skipped and the least
   cloudy ones are kept per 100 km tile (default 8).
2. Each band needed is warped by GDAL from the cloud-optimised GeoTIFF straight onto the area's
   UTM grid: 10 m for areas up to about 1,500 km², coarser (20, 30 m, …) above, so the grid stays
   under 16 million pixels. Digital numbers become reflectance with the scale and offset in the
   catalogue (0.0001, −0.1).
3. Pixels flagged in the scene classification layer as no data, saturated, cloud shadow,
   medium or high probability cloud, thin cirrus or snow are dropped.
4. The index is computed per scene, then the composite is the **median** of the clear
   observations per pixel. The number of clear observations is mapped as a quality check.
5. Index values are classed, averaged per admin unit and per ESA WorldCover 2021 class.

| Index | Formula | Use |
|---|---|---|
| NDVI | (NIR − Red) / (NIR + Red) | Greenness, general vegetation condition |
| EVI | 2.5 (NIR − Red) / (NIR + 6 Red − 7.5 Blue + 1) | Greenness in dense canopy (less saturated) |
| SAVI | 1.5 (NIR − Red) / (NIR + Red + 0.5) | Sparse vegetation on bright soils |
| NDMI | (NIR narrow − SWIR 1.6 µm) / (NIR narrow + SWIR) | Canopy water content, drought stress |

NDVI classes: under 0.1 water, built-up or bare; 0.1–0.2 sparse; 0.2–0.4 low; 0.4–0.6 moderate;
0.6 and above dense (EVI and SAVI: 0.1, 0.2, 0.3, 0.45). NDMI: under −0.2 very dry to 0.4 and
above very moist.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Imagery | Copernicus Sentinel-2 L2A collection 1, Earth Search (Element 84) on AWS Open Data | 10 m (NDMI from 20 m bands) | 2017 onwards | Copernicus open data |
| Land cover | ESA WorldCover 2021 v200 | 10 m | 2021 | CC BY 4.0 |

## Limitations

- A median over a long period (a whole year) mixes seasons; choose the growing season for crop
  condition. Values from different seasons or sensors aren't comparable.
- In persistently cloudy areas few clear observations remain (see the observations map);
  pixels with none are left empty.
- The scene classification misses some thin cloud and haze; the median limits their effect.
- Index values describe greenness or moisture, not yield.
