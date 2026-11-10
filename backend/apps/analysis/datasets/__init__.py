"""
Datasets modules can use. Each dataset fetches (and caches) what a run needs for a
bounding box. A file placed in backend/data/datasets/<dataset id>/ overrides the
download, e.g. backend/data/datasets/worldpop_2020/UGA.tif or
backend/data/datasets/osm_schools/UGA.geojson (country) or any *.tif / *.geojson there.
"""
from .base import Dataset, DatasetUnavailable  # noqa: F401
from .registry import DATASETS, get_dataset  # noqa: F401
