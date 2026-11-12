# Forest cover and loss

**Question:** How much forest is there, and how much was lost each year?

## Method

1. Hansen / UMD Global Forest Change v1.12 tree canopy cover in 2000 and loss year are read at
   30 m on the area's UTM grid (loss year with nearest neighbour).
2. Forest in 2000 = canopy cover at or above the threshold (default 30%, the common choice;
   FAO's definition uses 10%).
3. Loss = forest pixels with a loss year from the chosen first year to 2024; counted per year,
   cumulatively, as a share of the 2000 forest, and per admin unit.
4. Maps: canopy cover in 2000 and loss by five-year period.

## Data

| Input | Dataset | Resolution | Period | Licence |
|---|---|---|---|---|
| Tree cover, loss year | Hansen et al. 2013, Global Forest Change 2000–2024 v1.12 (University of Maryland), Google Cloud Storage | 30 m (1 arc-second) | 2000–2024 | CC BY 4.0 |

## Limitations

- "Loss" is stand-replacing disturbance (clearing, fire, harvest, storms) of forest present in
  2000, not net change: regrowth and plantations established later are not counted, and a
  harvested plantation counts as loss.
- Tree cover includes plantations and orchards; it is not a natural-forest map.
- Methods were updated over the years (2011 onwards uses improved detection), so trends across
  the whole series should be read with care.
