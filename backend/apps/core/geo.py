"""Small geographic helpers shared by apps."""


def utm_epsg(lon, lat):
    """EPSG code of the WGS 84 / UTM zone containing (lon, lat)."""
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + min(max(zone, 1), 60)
