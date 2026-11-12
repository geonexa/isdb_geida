"""Map previews for analysis outputs: colour classes, downsample, write PNG overlays with their bounds."""
import math
import warnings
from pathlib import Path

import numpy as np
import rasterio


def write_png(path, rgba, transform):
    """Write an RGBA preview PNG; returns the [w, s, e, n] bounds for a map image overlay."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    h, w = rgba.shape[:2]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", rasterio.errors.NotGeoreferencedWarning)
        with rasterio.open(path, "w", driver="PNG", height=h, width=w, count=4, dtype="uint8") as dst:
            for i in range(4):
                dst.write(rgba[:, :, i], i + 1)
    west, north = transform.c, transform.f
    east, south = west + w * transform.a, north + h * transform.e
    return [west, south, east, north]


def colorize(classes, palette, inside=None):
    """classes: int array; palette: {class: (r,g,b)}; pixels outside `inside` are transparent."""
    rgba = np.zeros(classes.shape + (4,), dtype=np.uint8)
    for k, (r, g, b) in palette.items():
        m = classes == k
        rgba[m] = (r, g, b, 200)
    if inside is not None:
        rgba[~inside] = 0
    return rgba


def downsample_for_preview(arr, max_side=1600):
    step = max(1, int(math.ceil(max(arr.shape[:2]) / max_side)))
    return arr[::step, ::step], step


def hex_color(rgb):
    return "#%02x%02x%02x" % tuple(rgb)
