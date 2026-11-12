# Land cover change

**Question:** What land cover changed into what between two years?

## Method

1. The Esri / Impact Observatory annual land cover maps of both years are read at 10 m on the
   same UTM grid (nearest neighbour).
2. Pixels classed as clouds (or without data) in either year are left out.
3. Every from–to pair is counted: the transition matrix (largest 20 changes shown), the area of
   each class in both years with its gain or loss, and per admin unit the changed share and the
   net change of crops, trees and built area.
4. Maps: land cover in each year, and changed pixels coloured by their class in the later year.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Land cover | Esri / Impact Observatory annual LULC v02 (Karra et al. 2021), Microsoft Planetary Computer | 10 m | 2017–2023 | CC BY 4.0 |

## Outputs

| Output | Meaning |
|---|---|
| `changed_share` | Share of the compared area whose class changed |
| `cropland_change`, `tree_change`, `built_change` | Net change of these classes (km²) |
| `transitions` | Largest from → to changes |
| `classes` | Area per class in both years, change in km² and % |
| `per_zone` | Changed share and net changes per admin unit |
| `cover_from`, `cover_to`, `changes` | Maps |

## Limitations

- Each year is classified independently: part of the apparent change is map error (typically
  a few percent of the area, more between similar classes such as crops and rangeland).
  Treat small changes with caution and check large ones on imagery (Satellite imagery by date).
- The product is v02; Esri publishes later years in newer versions that should not be mixed.
