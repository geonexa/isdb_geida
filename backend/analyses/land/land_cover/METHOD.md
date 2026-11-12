# Land cover composition

**Question:** How much of the area is cropland, forest, built-up, water and other classes?

## Method

1. The chosen 10 m land cover map is read for the area of influence and reprojected to the
   area's UTM zone with nearest-neighbour resampling (classes are never averaged).
2. Pixels whose centre lies inside the area are counted per class; area = pixels × pixel area.
3. Shares of cropland, trees and built-up land are reported for the area and per
   administrative unit, with the main class of each unit.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Land cover (default) | ESA WorldCover v100 (2020) / v200 (2021), AWS Open Data | 10 m | 2020, 2021 | CC BY 4.0 |
| Land cover (option) | Esri / Impact Observatory annual LULC v02, Microsoft Planetary Computer | 10 m | 2017–2023 | CC BY 4.0 |

## Outputs

| Output | Meaning |
|---|---|
| `cropland_share`, `tree_share`, `built_share` | Share of the area in each of these classes |
| `classes` | Area and share of every class present |
| `per_zone` | Area, main class and cropland / tree / built-up shares per admin unit |
| `land_cover` | The class map |

## Limitations

- WorldCover 2020 and 2021 were made with different algorithms: differences between them are
  mostly method, not change. Use Land cover change (Esri yearly maps) for change.
- The two products use different classes (WorldCover: 11, Esri: 9, e.g. "Rangeland" groups
  grass and shrubs) and are not directly comparable.
- Reported accuracy is about 75–85% overall; small classes and mixed landscapes (smallholder
  farming, sparse trees) are less accurate.
