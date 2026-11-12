"""
Datasets modules can use. Each dataset fetches (and caches) what a run needs for a
bounding box. A file placed in DATA_DIR/datasets/<dataset id>/ overrides the
download, e.g. DATA_DIR/datasets/worldpop/UGA.tif (UGA_2025.tif for one year) or
DATA_DIR/datasets/osm_schools/UGA.geojson (country) or any *.tif / *.geojson there.
"""
from .base import Dataset, DatasetUnavailable  # noqa: F401
from .registry import DATASETS, get_dataset  # noqa: F401
